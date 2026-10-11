import uuid
from django.conf import settings
from django.db import models


class Invoice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey('patients.Patient', on_delete=models.PROTECT, related_name='invoices')
    appointment = models.ForeignKey(
        'appointments.Appointment', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='invoices',
        help_text="Nullable — supports invoices not tied to a single appointment, e.g. a package purchase."
    )
    invoice_number = models.CharField(max_length=30, unique=True, help_text="e.g. INV-2026-000123")

    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    # India-specific: GST split instead of a single generic 'tax' field,
    # since Indian invoices typically need CGST/SGST (intra-state) or IGST
    # (inter-state) broken out for compliance.
    cgst = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    sgst = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    igst = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2)

    STATUS_CHOICES = [
        ('pending', 'Pending'), ('paid', 'Paid'),
        ('partially_paid', 'Partially Paid'), ('refunded', 'Refunded'), ('void', 'Void'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    due_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=['patient', 'status'])]

    def __str__(self):
        return self.invoice_number


class InvoiceLineItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='line_items')
    description = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    line_total = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.description} x{self.quantity}"


class Payment(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    METHOD_CHOICES = [
        ('online_card', 'Online Card'), ('online_upi', 'Online UPI'),
        ('online_netbanking', 'Online Netbanking'), ('cash', 'Cash'),
        ('pos_card', 'POS Card'), ('other', 'Other'),
    ]
    method = models.CharField(max_length=20, choices=METHOD_CHOICES)

    # Razorpay-specific identifiers (India-first gateway per Phase 10)
    gateway_name = models.CharField(max_length=50, blank=True, default='razorpay')
    gateway_order_id = models.CharField(max_length=100, blank=True)
    gateway_payment_id = models.CharField(max_length=100, blank=True)
    gateway_signature = models.CharField(max_length=255, blank=True)

    STATUS_CHOICES = [
        ('initiated', 'Initiated'), ('success', 'Success'),
        ('failed', 'Failed'), ('refunded', 'Refunded'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='initiated')

    collected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='payments_collected',
        help_text="Set for front-desk cash/card collection; null for online payments."
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.amount} — {self.invoice.invoice_number} ({self.status})"
