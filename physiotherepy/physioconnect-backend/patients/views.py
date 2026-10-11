from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from appointments.serializers import AppointmentSerializer, ConsultationNoteSerializer
from appointments.views import visible_appointments
from consultations.models import ConsultationNote
from core.audit import audit
from core.exceptions import ApiError
from core.permissions import ADMIN, DOCTOR, PATIENT, RECEPTIONIST, IsFrontDesk, IsStaffRole, get_role

from .models import Patient, PatientMedicalProfile
from .serializers import (
    MedicalProfileSerializer, PatientSerializer, PatientUpdateSerializer, WalkInPatientSerializer,
)


def visible_patients(user):
    qs = Patient.objects.select_related('user')
    role = get_role(user)
    if role in (ADMIN, RECEPTIONIST):
        return qs
    if role == DOCTOR:
        return qs.filter(appointments__doctor__user=user).distinct()
    if role == PATIENT:
        return qs.filter(user=user)
    return qs.none()


class PatientListCreateView(ListAPIView):
    """
    GET  /api/v1/patients/?q=name-or-phone   (doctor / receptionist / admin)
    POST /api/v1/patients/                   (receptionist / admin: register a walk-in patient)
    """
    serializer_class = PatientSerializer
    permission_classes = [IsStaffRole]

    def get_queryset(self):
        qs = visible_patients(self.request.user).order_by('first_name', 'last_name')
        q = self.request.query_params.get('q', '').strip()
        if q:
            qs = qs.filter(Q(first_name__icontains=q) | Q(last_name__icontains=q)
                           | Q(user__phone__icontains=q) | Q(user__email__icontains=q))
        return qs

    def post(self, request):
        if get_role(request.user) not in (RECEPTIONIST, ADMIN):
            raise ApiError('PERMISSION_DENIED', 'Only the front desk can register patients.', 403)
        serializer = WalkInPatientSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        patient = serializer.save()
        audit(request, 'patient.registered', 'patient', patient.id)
        return Response(PatientSerializer(patient).data, status=status.HTTP_201_CREATED)


class PatientBase(APIView):
    def get_patient(self, request, pk):
        return get_object_or_404(visible_patients(request.user), pk=pk)


class PatientDetailView(PatientBase):
    """GET/PATCH /api/v1/patients/<id>/"""

    def get(self, request, pk):
        return Response(PatientSerializer(self.get_patient(request, pk)).data)

    def patch(self, request, pk):
        if get_role(request.user) == DOCTOR:
            raise ApiError('PERMISSION_DENIED', 'Doctors cannot edit contact details.', 403)
        patient = self.get_patient(request, pk)
        serializer = PatientUpdateSerializer(patient, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        audit(request, 'patient.updated', 'patient', patient.id)
        return Response(PatientSerializer(patient).data)


class PatientHistoryView(PatientBase):
    """GET /api/v1/patients/<id>/history/  - past visits. Doctors/admins also get SOAP notes."""

    def get(self, request, pk):
        patient = self.get_patient(request, pk)
        role = get_role(request.user)
        appointments = visible_appointments(request.user).filter(patient=patient).order_by('-scheduled_start')
        rows = AppointmentSerializer(appointments, many=True).data
        if role in (DOCTOR, ADMIN):
            notes = {n.appointment_id: n for n in ConsultationNote.objects.filter(appointment__in=appointments)}
            for row, appt in zip(rows, appointments):
                note = notes.get(appt.id)
                row['notes'] = ConsultationNoteSerializer(note).data if note else None
            audit(request, 'patient.history.viewed', 'patient', patient.id)
        return Response({'patient': PatientSerializer(patient).data, 'visits': rows})


class MedicalProfileView(PatientBase):
    """GET/PATCH /api/v1/patients/<id>/medical-profile/"""

    def _allowed(self, request, write):
        role = get_role(request.user)
        if role not in (DOCTOR, ADMIN) and not (role == PATIENT and not write):
            raise ApiError('PERMISSION_DENIED', 'You cannot access medical details.', 403)

    def get(self, request, pk):
        self._allowed(request, write=False)
        patient = self.get_patient(request, pk)
        profile, _ = PatientMedicalProfile.objects.get_or_create(patient=patient)
        audit(request, 'patient.medical_profile.viewed', 'patient', patient.id)
        return Response(MedicalProfileSerializer(profile).data)

    def patch(self, request, pk):
        self._allowed(request, write=True)
        patient = self.get_patient(request, pk)
        profile, _ = PatientMedicalProfile.objects.get_or_create(patient=patient)
        serializer = MedicalProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        audit(request, 'patient.medical_profile.updated', 'patient', patient.id)
        return Response(serializer.data)
