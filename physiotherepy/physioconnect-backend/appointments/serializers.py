from decimal import Decimal

from rest_framework import serializers

from consultations.models import ConsultationNote

from .models import Appointment


def invoice_summary(appointment):
    invoice = next(iter(sorted(appointment.invoices.all(), key=lambda i: i.created_at, reverse=True)), None)
    if not invoice:
        return None
    paid = sum((p.amount for p in invoice.payments.all() if p.status == 'success'), Decimal('0'))
    return {
        'id': str(invoice.id),
        'invoice_number': invoice.invoice_number,
        'total': str(invoice.total),
        'amount_paid': str(paid),
        'amount_due': str(max(invoice.total - paid, Decimal('0'))),
        'status': invoice.status,
    }


class AppointmentSerializer(serializers.ModelSerializer):
    patient = serializers.SerializerMethodField()
    doctor = serializers.SerializerMethodField()
    service = serializers.SerializerMethodField()
    invoice = serializers.SerializerMethodField()

    class Meta:
        model = Appointment
        fields = (
            'id', 'patient', 'doctor', 'service', 'scheduled_start', 'scheduled_end',
            'status', 'booking_channel', 'cancellation_reason', 'invoice', 'created_at',
        )

    def get_patient(self, a):
        return {'id': str(a.patient_id), 'name': f'{a.patient.first_name} {a.patient.last_name}',
                'phone': a.patient.user.phone}

    def get_doctor(self, a):
        return {'id': str(a.doctor_id), 'slug': a.doctor.slug,
                'name': f'Dr. {a.doctor.first_name} {a.doctor.last_name}'}

    def get_service(self, a):
        return {'id': a.service_id, 'name': a.service.name, 'duration_minutes': a.service.duration_minutes}

    def get_invoice(self, a):
        return invoice_summary(a)


class BookingInputSerializer(serializers.Serializer):
    doctor = serializers.UUIDField()
    service = serializers.IntegerField()
    scheduled_start = serializers.DateTimeField()
    patient = serializers.UUIDField(required=False)  # staff booking on behalf of a patient
    booking_channel = serializers.ChoiceField(choices=['online', 'phone', 'walk_in'], required=False)


class RescheduleInputSerializer(serializers.Serializer):
    scheduled_start = serializers.DateTimeField()


class CancelInputSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')


class ConsultationNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConsultationNote
        fields = ('subjective', 'objective', 'assessment', 'plan', 'created_at', 'updated_at')
        read_only_fields = ('created_at', 'updated_at')
