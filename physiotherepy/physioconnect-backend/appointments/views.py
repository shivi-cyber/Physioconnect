import datetime

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from consultations.models import ConsultationNote
from core.audit import audit
from core.exceptions import ApiError, business_rule
from core.models import Service
from core.permissions import ADMIN, DOCTOR, PATIENT, RECEPTIONIST, IsDoctorOrAdmin, get_role, roles_required
from doctors.models import Doctor
from patients.models import Patient

from . import services
from .models import Appointment
from .serializers import (
    AppointmentSerializer, BookingInputSerializer, CancelInputSerializer,
    ConsultationNoteSerializer, RescheduleInputSerializer,
)


def visible_appointments(user):
    """Each role only ever sees the appointments it is entitled to."""
    qs = Appointment.objects.select_related('patient__user', 'doctor', 'service').prefetch_related(
        'invoices__payments'
    )
    role = get_role(user)
    if role in (ADMIN, RECEPTIONIST):
        return qs
    if role == DOCTOR:
        return qs.filter(doctor__user=user)
    if role == PATIENT:
        return qs.filter(patient__user=user)
    return qs.none()


class AppointmentListCreateView(ListAPIView):
    """
    GET  /api/v1/appointments/?date=2026-10-14&status=confirmed&doctor=<id>&scope=upcoming|past
    POST /api/v1/appointments/   {"doctor": "<uuid>", "service": 1, "scheduled_start": "2026-10-14T09:00:00+05:30"}
    """
    serializer_class = AppointmentSerializer

    def get_queryset(self):
        params = self.request.query_params
        qs = visible_appointments(self.request.user)
        if params.get('status'):
            qs = qs.filter(status=params['status'])
        if params.get('doctor'):
            qs = qs.filter(doctor_id=params['doctor'])
        if params.get('patient'):
            qs = qs.filter(patient_id=params['patient'])
        if params.get('date'):
            try:
                day = datetime.date.fromisoformat(params['date'])
            except ValueError:
                raise ApiError('VALIDATION_ERROR', 'Give a date like 2026-10-14.', 400)
            tz = services.clinic_tz()
            start = datetime.datetime.combine(day, datetime.time.min, tzinfo=tz)
            qs = qs.filter(scheduled_start__gte=start, scheduled_start__lt=start + datetime.timedelta(days=1))
        scope = params.get('scope')
        from django.utils import timezone
        if scope == 'upcoming':
            qs = qs.filter(scheduled_end__gte=timezone.now()).exclude(status__in=['cancelled', 'no_show', 'completed'])
        elif scope == 'past':
            qs = qs.filter(scheduled_end__lt=timezone.now())
        newest_first = get_role(self.request.user) == PATIENT or scope == 'past'
        return qs.order_by('-scheduled_start' if newest_first else 'scheduled_start')

    def post(self, request):
        role = get_role(request.user)
        if role not in (PATIENT, RECEPTIONIST, ADMIN):
            raise ApiError('PERMISSION_DENIED', 'Your account cannot book appointments.', 403)

        inputs = BookingInputSerializer(data=request.data)
        inputs.is_valid(raise_exception=True)
        data = inputs.validated_data

        if role == PATIENT:
            patient = get_object_or_404(Patient, user=request.user)
            channel = 'online'
        else:
            if 'patient' not in data:
                raise ApiError('VALIDATION_ERROR', 'Choose which patient this booking is for.', 400,
                               {'patient': ['This field is required.']})
            patient = get_object_or_404(Patient, pk=data['patient'])
            channel = data.get('booking_channel', 'phone')

        doctor = get_object_or_404(Doctor, pk=data['doctor'])
        service = get_object_or_404(Service, pk=data['service'], is_active=True)

        appointment = services.create_booking(
            patient=patient, doctor=doctor, service=service,
            start=data['scheduled_start'], created_by=request.user, channel=channel,
        )
        audit(request, 'appointment.created', 'appointment', appointment.id)
        appointment = visible_appointments(request.user).get(pk=appointment.pk)
        return Response(AppointmentSerializer(appointment).data, status=status.HTTP_201_CREATED)


class AppointmentBase(APIView):
    def get_appointment(self, request, pk):
        return get_object_or_404(visible_appointments(request.user), pk=pk)

    def respond(self, request, appointment):
        fresh = visible_appointments(request.user).get(pk=appointment.pk)
        return Response(AppointmentSerializer(fresh).data)


class AppointmentDetailView(AppointmentBase):
    def get(self, request, pk):
        return self.respond(request, self.get_appointment(request, pk))


class AppointmentCancelView(AppointmentBase):
    """POST /api/v1/appointments/<id>/cancel/   {"reason": "..."}"""

    def post(self, request, pk):
        appointment = self.get_appointment(request, pk)
        body = CancelInputSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        services.cancel_booking(appointment, request.user, body.validated_data['reason'],
                                user_is_patient=get_role(request.user) == PATIENT)
        audit(request, 'appointment.cancelled', 'appointment', appointment.id)
        return self.respond(request, appointment)


class AppointmentRescheduleView(AppointmentBase):
    """POST /api/v1/appointments/<id>/reschedule/   {"scheduled_start": "..."}"""

    def post(self, request, pk):
        appointment = self.get_appointment(request, pk)
        body = RescheduleInputSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        services.reschedule_booking(appointment, body.validated_data['scheduled_start'],
                                    user_is_patient=get_role(request.user) == PATIENT)
        audit(request, 'appointment.rescheduled', 'appointment', appointment.id)
        return self.respond(request, appointment)


class AppointmentTransitionView(AppointmentBase):
    """POST /api/v1/appointments/<id>/check-in|start|complete|no-show/"""
    action = None
    permission_classes = []

    def post(self, request, pk):
        allowed_from, new_status = services.TRANSITIONS[self.action]
        appointment = self.get_appointment(request, pk)
        if appointment.status not in allowed_from:
            raise business_rule(
                'INVALID_STATE',
                f'This appointment is "{appointment.get_status_display()}", so it cannot be moved to '
                f'"{new_status.replace("_", " ")}".',
            )
        appointment.status = new_status
        appointment.save(update_fields=['status', 'updated_at'])
        audit(request, f'appointment.{new_status}', 'appointment', appointment.id)
        return self.respond(request, appointment)


def transition_view(action, *roles):
    return type(
        f'Transition_{action}', (AppointmentTransitionView,),
        {'action': action, 'permission_classes': [roles_required(*roles)]},
    )


class ConsultationNoteView(AppointmentBase):
    """GET/PUT /api/v1/appointments/<id>/notes/  - SOAP notes (doctor/admin only)."""
    permission_classes = [IsDoctorOrAdmin]

    def get(self, request, pk):
        appointment = self.get_appointment(request, pk)
        note = ConsultationNote.objects.filter(appointment=appointment).first()
        audit(request, 'consultation_note.viewed', 'appointment', appointment.id)
        return Response(ConsultationNoteSerializer(note).data if note else
                        {'subjective': '', 'objective': '', 'assessment': '', 'plan': ''})

    def put(self, request, pk):
        appointment = self.get_appointment(request, pk)
        if appointment.status not in ('checked_in', 'in_progress', 'completed'):
            raise business_rule('INVALID_STATE', 'Notes can be written once the patient has checked in.')
        note = ConsultationNote.objects.filter(appointment=appointment).first()
        serializer = ConsultationNoteSerializer(note, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(appointment=appointment, doctor=appointment.doctor)
        audit(request, 'consultation_note.saved', 'appointment', appointment.id)
        return Response(serializer.data)
