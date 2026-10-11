import datetime
import uuid

from django.shortcuts import get_object_or_404
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from appointments.services import compute_slots
from core.exceptions import ApiError
from core.models import Service

from .models import Doctor, DoctorService
from .serializers import DoctorDetailSerializer, DoctorSerializer


def public_doctors():
    return (
        Doctor.objects.filter(employment_status='active')
        .prefetch_related('specializations', 'doctor_services__service', 'availability')
        .order_by('first_name', 'last_name')
    )


def find_doctor(ident):
    """Look a doctor up by UUID or by slug (e.g. dr-arjun-mehta)."""
    qs = public_doctors()
    try:
        return get_object_or_404(qs, pk=uuid.UUID(str(ident)))
    except ValueError:
        return get_object_or_404(qs, slug=ident)


class DoctorListView(ListAPIView):
    """GET /api/v1/doctors/?specialization=<slug>&service=<id>"""
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = DoctorSerializer
    pagination_class = None

    def get_queryset(self):
        qs = public_doctors()
        spec = self.request.query_params.get('specialization')
        service = self.request.query_params.get('service')
        if spec:
            qs = qs.filter(specializations__slug=spec)
        if service and service.isdigit():
            qs = qs.filter(doctor_services__service_id=int(service))
        return qs.distinct()


class DoctorDetailView(RetrieveAPIView):
    """GET /api/v1/doctors/<slug-or-id>/"""
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = DoctorDetailSerializer

    def get_object(self):
        return find_doctor(self.kwargs['ident'])


class AvailableSlotsView(APIView):
    """GET /api/v1/doctors/<id>/available-slots/?date=2026-10-14&service_id=1"""
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, ident):
        doctor = find_doctor(ident)

        raw_date = request.query_params.get('date', '')
        raw_service = request.query_params.get('service_id', '')
        try:
            day = datetime.date.fromisoformat(raw_date)
        except ValueError:
            raise ApiError('VALIDATION_ERROR', 'Give a date like 2026-10-14.', 400, {'date': ['Use YYYY-MM-DD.']})
        if not raw_service.isdigit():
            raise ApiError('VALIDATION_ERROR', 'service_id is required.', 400, {'service_id': ['This field is required.']})

        service = get_object_or_404(Service, pk=int(raw_service), is_active=True)
        if not DoctorService.objects.filter(doctor=doctor, service=service).exists():
            raise ApiError('SERVICE_NOT_OFFERED', 'This doctor does not offer that service.', 422)

        slots = compute_slots(doctor, service, day)
        return Response({
            'doctor_id': str(doctor.id),
            'service_id': service.id,
            'date': day.isoformat(),
            'slots': [{'start': s.isoformat(), 'end': e.isoformat()} for s, e in slots],
        })
