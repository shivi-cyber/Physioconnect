import datetime
from collections import Counter
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from appointments.models import Appointment
from appointments.serializers import AppointmentSerializer
from appointments.services import LIVE_STATUSES, clinic_tz
from appointments.views import visible_appointments
from billing.models import Invoice, Payment
from doctors.models import Doctor

from .models import ClinicSettings, Service
from core.permissions import ADMIN, DOCTOR, PATIENT, RECEPTIONIST, get_role
from .serializers import ServiceSerializer


class ServiceListView(ListAPIView):
    """GET /api/v1/services/  (public)"""
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = ServiceSerializer
    pagination_class = None
    queryset = Service.objects.filter(is_active=True).select_related('category').order_by('name')


class ClinicInfoView(APIView):
    """GET /api/v1/clinic/  (public) - name, address, phone for the website footer/contact page."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        c = ClinicSettings.objects.first() or ClinicSettings()
        return Response({'name': c.clinic_name, 'address': c.address, 'phone': c.phone, 'email': c.email,
                         'cancellation_window_hours': c.cancellation_window_hours})


class DashboardView(APIView):
    """GET /api/v1/dashboard/  - small summary shaped for the logged-in role."""

    def get(self, request):
        role = get_role(request.user)
        tz = clinic_tz()
        now = timezone.now()
        today = now.astimezone(tz).date()
        day_start = datetime.datetime.combine(today, datetime.time.min, tzinfo=tz)
        day_end = day_start + datetime.timedelta(days=1)

        mine = visible_appointments(request.user)
        today_qs = mine.filter(scheduled_start__gte=day_start, scheduled_start__lt=day_end)
        upcoming = mine.filter(scheduled_end__gte=now, status__in=LIVE_STATUSES).order_by('scheduled_start')
        next_appt = upcoming.first()

        data = {
            'role': role,
            'today': today.isoformat(),
            'next_appointment': AppointmentSerializer(next_appt).data if next_appt else None,
        }

        if role == PATIENT:
            data['upcoming_count'] = upcoming.count()
            data['unpaid_invoices'] = Invoice.objects.filter(
                patient__user=request.user, status__in=['pending', 'partially_paid']).count()
        else:
            data['today_total'] = today_qs.count()
            data['today_by_status'] = dict(Counter(today_qs.values_list('status', flat=True)))
            if role == DOCTOR:
                data['patients_seen_total'] = mine.filter(status='completed').values('patient').distinct().count()
            if role in (ADMIN, RECEPTIONIST):
                collected = Payment.objects.filter(
                    status='success', paid_at__gte=day_start, paid_at__lt=day_end
                ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
                data['collected_today'] = str(collected)
                data['outstanding_invoices'] = Invoice.objects.filter(
                    status__in=['pending', 'partially_paid']).count()
                data['active_doctors'] = Doctor.objects.filter(employment_status='active').count()
        return Response(data)
