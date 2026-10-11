from django.conf import settings
from django.db import models


class ServiceCategory(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)

    def __str__(self):
        return self.name


class Service(models.Model):
    """
    Shared treatment catalog (e.g. 'Sports Injury Rehab Session'). Lives in
    `core` rather than `doctors` or `appointments` because both of those
    apps need to reference it, and putting it in either would create a
    circular import.
    """
    name = models.CharField(max_length=150)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    duration_minutes = models.PositiveIntegerField(default=30)
    default_price = models.DecimalField(max_digits=8, decimal_places=2)
    category = models.ForeignKey(ServiceCategory, on_delete=models.SET_NULL, null=True, related_name='services')
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class ClinicSettings(models.Model):
    """
    Singleton-style table (enforced in admin/business logic, not at the DB
    level) holding clinic-wide configuration described in Phase 8 Admin
    Settings: hours, cancellation policy, GST.
    """
    clinic_name = models.CharField(max_length=150, default="PhysioConnect Clinic")
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=15, blank=True)
    email = models.EmailField(blank=True)

    cancellation_window_hours = models.PositiveIntegerField(
        default=24, help_text="Patients cannot cancel/reschedule within this many hours of the appointment."
    )
    booking_grace_period_minutes = models.PositiveIntegerField(
        default=15, help_text="How long a 'payment pending' slot is held before release back to availability."
    )

    # India-specific: GST
    gstin = models.CharField(max_length=15, blank=True, help_text="Clinic's GST Identification Number")
    default_gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=18.00)

    class Meta:
        verbose_name = "Clinic Settings"
        verbose_name_plural = "Clinic Settings"

    def __str__(self):
        return self.clinic_name


class AuditLog(models.Model):
    """
    Append-only. No update/delete should ever be exposed for this model in
    any view or admin config — see Security Phase 9.6.
    """
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='audit_actions')
    action = models.CharField(max_length=150, help_text="e.g. 'patient.medical_profile.viewed', 'payment.refunded'")
    entity_type = models.CharField(max_length=100)
    entity_id = models.CharField(max_length=64)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['entity_type', 'entity_id']),
            models.Index(fields=['actor', 'created_at']),
        ]

    def __str__(self):
        return f"{self.actor} — {self.action} @ {self.created_at}"
