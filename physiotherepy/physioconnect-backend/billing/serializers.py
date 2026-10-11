from decimal import Decimal

from rest_framework import serializers

from .models import Invoice, InvoiceLineItem, Payment

# What the front desk can record. UPI at the counter is stored as an offline-collected UPI payment.
MANUAL_METHODS = {'cash': 'cash', 'pos_card': 'pos_card', 'upi': 'online_upi', 'other': 'other'}


class LineItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceLineItem
        fields = ('description', 'quantity', 'unit_price', 'line_total')


class PaymentSerializer(serializers.ModelSerializer):
    method_label = serializers.CharField(source='get_method_display', read_only=True)
    collected_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = ('id', 'amount', 'method', 'method_label', 'status', 'paid_at', 'collected_by_name')

    def get_collected_by_name(self, p):
        return p.collected_by.get_full_name() if p.collected_by else None


def amount_paid(invoice):
    return sum((p.amount for p in invoice.payments.all() if p.status == 'success'), Decimal('0'))


class InvoiceSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()
    line_items = LineItemSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)
    amount_paid = serializers.SerializerMethodField()
    amount_due = serializers.SerializerMethodField()
    appointment_start = serializers.DateTimeField(source='appointment.scheduled_start', read_only=True, default=None)

    class Meta:
        model = Invoice
        fields = ('id', 'invoice_number', 'patient', 'patient_name', 'appointment', 'appointment_start',
                  'subtotal', 'cgst', 'sgst', 'igst', 'discount', 'total', 'status',
                  'amount_paid', 'amount_due', 'due_date', 'created_at', 'line_items', 'payments')

    def get_patient_name(self, inv):
        return f'{inv.patient.first_name} {inv.patient.last_name}'

    def get_amount_paid(self, inv):
        return str(amount_paid(inv))

    def get_amount_due(self, inv):
        return str(max(inv.total - amount_paid(inv), Decimal('0')))


class ManualPaymentSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0.01'))
    method = serializers.ChoiceField(choices=list(MANUAL_METHODS))
