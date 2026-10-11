import uuid
from django.conf import settings
from django.db import models


class Appointment(models.Model):
    """
    The central transactional hub of the whole system — almost every other
    app (billing, consultations, notifications) hangs off this model.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    patient = models.ForeignKey('patients.Patient', on_delete=models.PROTECT, related_name='appointments')
    doctor = models.ForeignKey('doctors.Doctor', on_delete=models.PROTECT, related_name='appointments')
    service = models.ForeignKey('core.Service', on_delete=models.PROTECT, related_name='appointments')

    scheduled_start = models.DateTimeField()
    scheduled_end = models.DateTimeField()

    STATUS_CHOICES = [
        ('requested', 'Requested'),
        ('payment_pending', 'Payment Pending'),
        ('confirmed', 'Confirmed'),
        ('checked_in', 'Checked In'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('no_show', 'No Show'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='requested')

    BOOKING_CHANNEL_CHOICES = [
        ('online', 'Online'), ('phone', 'Phone'), ('walk_in', 'Walk-in'),
    ]
    booking_channel = models.CharField(max_length=10, choices=BOOKING_CHANNEL_CHOICES, default='online')

    cancellation_reason = models.CharField(max_length=255, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='appointments_cancelled'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='appointments_created'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            # Powers the availability/slot-lookup query — the single most
            # frequently hit index in the whole system.
            models.Index(fields=['doctor', 'scheduled_start']),
            # Powers "my appointment history" queries for patients.
            models.Index(fields=['patient', 'scheduled_start']),
            models.Index(fields=['status']),
        ]
        constraints = [
            # Belt-and-braces DB-level guard against double-booking the
            # exact same doctor+start-time slot twice while both are in a
            # "live" state. This does NOT replace the SELECT...FOR UPDATE
            # locking discussed in Phase 6 — it's a second line of defense.
            models.UniqueConstraint(
                fields=['doctor', 'scheduled_start'],
                condition=models.Q(status__in=['requested', 'payment_pending', 'confirmed', 'checked_in', 'in_progress']),
                name='unique_active_doctor_slot',
            )
        ]

    def __str__(self):
        return f"{self.patient} with {self.doctor} @ {self.scheduled_start}"
