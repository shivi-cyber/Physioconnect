"""Booking logic lives here (not in views) so it is easy to test and reuse."""
import datetime
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from core.exceptions import business_rule, invalid_slot, slot_taken
from core.models import ClinicSettings
from doctors.models import Doctor, DoctorService, DoctorTimeOff

from .models import Appointment

LIVE_STATUSES = ['requested', 'payment_pending', 'confirmed', 'checked_in', 'in_progress']
CHANGEABLE_STATUSES = ['requested', 'payment_pending', 'confirmed']


def clinic_tz():
    return ZoneInfo(settings.CLINIC_TIME_ZONE)


def clinic_settings():
    return ClinicSettings.objects.first() or ClinicSettings()


def _overlaps(a_start, a_end, b_start, b_end):
    return a_start < b_end and b_start < a_end


def compute_slots(doctor, service, day, exclude_appointment_id=None):
    """All bookable (start, end) pairs for one doctor/service on one clinic-local day.

    A slot is bookable when it sits inside the doctor's weekly hours, is in the
    future, and does not overlap leave or any live appointment - overlap is
    checked properly, so a 45-minute visit blocks the 30-minute slots it touches.
    """
    tz = clinic_tz()
    day_start = datetime.datetime.combine(day, datetime.time.min, tzinfo=tz)
    day_end = day_start + datetime.timedelta(days=1)
    now = timezone.now()
    duration = datetime.timedelta(minutes=service.duration_minutes)

    rules = doctor.availability.filter(is_active=True, day_of_week=day.weekday()).order_by('start_time')
    if not rules:
        return []

    busy = list(
        DoctorTimeOff.objects.filter(doctor=doctor, start_datetime__lt=day_end, end_datetime__gt=day_start)
        .values_list('start_datetime', 'end_datetime')
    )
    appointments = Appointment.objects.filter(
        doctor=doctor, status__in=LIVE_STATUSES,
        scheduled_start__lt=day_end, scheduled_end__gt=day_start,
    )
    if exclude_appointment_id:
        appointments = appointments.exclude(pk=exclude_appointment_id)
    busy += list(appointments.values_list('scheduled_start', 'scheduled_end'))

    slots, seen = [], set()
    for rule in rules:
        cursor = datetime.datetime.combine(day, rule.start_time, tzinfo=tz)
        window_end = datetime.datetime.combine(day, rule.end_time, tzinfo=tz)
        step = datetime.timedelta(minutes=rule.slot_duration_minutes)
        while cursor + duration <= window_end:
            start, end = cursor, cursor + duration
            if start > now and start not in seen and not any(_overlaps(start, end, bs, be) for bs, be in busy):
                seen.add(start)
                slots.append((start, end))
            cursor += step
    return sorted(slots)


def _check_bookable(doctor, service, start, exclude_appointment_id=None):
    """Raise the right error if `start` cannot be booked. Call inside the lock."""
    if doctor.employment_status != 'active':
        raise business_rule('DOCTOR_UNAVAILABLE', 'This doctor is not taking appointments right now.')
    if not DoctorService.objects.filter(doctor=doctor, service=service).exists():
        raise business_rule('SERVICE_NOT_OFFERED', 'This doctor does not offer that service.')
    if start <= timezone.now():
        raise invalid_slot('Please choose a time in the future.')

    local_day = start.astimezone(clinic_tz()).date()
    if any(s == start for s, _ in compute_slots(doctor, service, local_day, exclude_appointment_id)):
        return

    # Not offered. Is it because someone else holds it, or just outside working hours?
    end = start + datetime.timedelta(minutes=service.duration_minutes)
    clash = Appointment.objects.filter(
        doctor=doctor, status__in=LIVE_STATUSES, scheduled_start__lt=end, scheduled_end__gt=start,
    )
    if exclude_appointment_id:
        clash = clash.exclude(pk=exclude_appointment_id)
    if clash.exists():
        raise slot_taken()
    raise invalid_slot()


def _money(value):
    return Decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _next_invoice_number():
    from billing.models import Invoice
    year = timezone.now().year
    prefix = f'INV-{year}-'
    last = Invoice.objects.filter(invoice_number__startswith=prefix).order_by('-invoice_number').first()
    number = int(last.invoice_number.rsplit('-', 1)[1]) + 1 if last else 1
    return f'{prefix}{number:06d}'


def create_invoice_for(appointment, price):
    """Invoice with GST split into CGST + SGST using the clinic's configured rate."""
    from billing.models import Invoice, InvoiceLineItem

    subtotal = _money(price)
    rate = Decimal(str(clinic_settings().default_gst_rate))
    half = _money(subtotal * rate / Decimal('200'))
    invoice = Invoice.objects.create(
        patient=appointment.patient, appointment=appointment,
        invoice_number=_next_invoice_number(),
        subtotal=subtotal, cgst=half, sgst=half, total=subtotal + half + half,
        due_date=appointment.scheduled_start.date(),
    )
    InvoiceLineItem.objects.create(
        invoice=invoice, description=appointment.service.name,
        quantity=1, unit_price=subtotal, line_total=subtotal,
    )
    return invoice


def create_booking(*, patient, doctor, service, start, created_by, channel='online'):
    """Create an appointment safely.

    The doctor's row is locked for the duration of the transaction, so two people
    booking the same doctor at the same moment are handled one after the other.
    The database constraint is a second safety net behind this lock.
    """
    with transaction.atomic():
        doctor = Doctor.objects.select_for_update().get(pk=doctor.pk)
        _check_bookable(doctor, service, start)
        price = DoctorService.objects.get(doctor=doctor, service=service).effective_price
        try:
            with transaction.atomic():
                appointment = Appointment.objects.create(
                    patient=patient, doctor=doctor, service=service,
                    scheduled_start=start,
                    scheduled_end=start + datetime.timedelta(minutes=service.duration_minutes),
                    status='confirmed', booking_channel=channel, created_by=created_by,
                )
        except IntegrityError:
            raise slot_taken()
        create_invoice_for(appointment, price)
    return appointment


def check_patient_window(appointment, user_is_patient):
    """Patients cannot cancel/reschedule too close to the visit; staff can."""
    if not user_is_patient:
        return
    hours = clinic_settings().cancellation_window_hours
    if appointment.scheduled_start - timezone.now() < datetime.timedelta(hours=hours):
        raise business_rule(
            'CANCELLATION_WINDOW_PASSED',
            f'Appointments cannot be changed within {hours} hours of the visit. Please call the clinic.',
        )


def reschedule_booking(appointment, new_start, user_is_patient):
    if appointment.status not in CHANGEABLE_STATUSES:
        raise business_rule('INVALID_STATE', 'Only upcoming, unstarted appointments can be rescheduled.')
    check_patient_window(appointment, user_is_patient)
    with transaction.atomic():
        Doctor.objects.select_for_update().get(pk=appointment.doctor_id)
        _check_bookable(appointment.doctor, appointment.service, new_start, exclude_appointment_id=appointment.pk)
        appointment.scheduled_start = new_start
        appointment.scheduled_end = new_start + datetime.timedelta(minutes=appointment.service.duration_minutes)
        try:
            with transaction.atomic():
                appointment.save(update_fields=['scheduled_start', 'scheduled_end', 'updated_at'])
        except IntegrityError:
            raise slot_taken()
    return appointment


def cancel_booking(appointment, user, reason, user_is_patient):
    if appointment.status not in CHANGEABLE_STATUSES:
        raise business_rule('INVALID_STATE', 'Only upcoming, unstarted appointments can be cancelled.')
    check_patient_window(appointment, user_is_patient)
    appointment.status = 'cancelled'
    appointment.cancellation_reason = reason[:255]
    appointment.cancelled_by = user
    appointment.save(update_fields=['status', 'cancellation_reason', 'cancelled_by', 'updated_at'])
    return appointment


# status flow for the visit itself: action -> (allowed current statuses, new status)
TRANSITIONS = {
    'check-in': (['requested', 'confirmed'], 'checked_in'),
    'start': (['checked_in', 'confirmed'], 'in_progress'),
    'complete': (['in_progress', 'checked_in'], 'completed'),
    'no-show': (['requested', 'confirmed', 'checked_in'], 'no_show'),
}
