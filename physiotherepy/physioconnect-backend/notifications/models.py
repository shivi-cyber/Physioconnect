from django.conf import settings
from django.db import models


class NotificationTemplate(models.Model):
    CATEGORY_CHOICES = [
        ('booking_confirmation', 'Booking Confirmation'),
        ('reminder', 'Reminder'),
        ('cancellation', 'Cancellation'),
        ('payment_receipt', 'Payment Receipt'),
        ('reschedule', 'Reschedule'),
        ('marketing', 'Marketing'),
    ]
    CHANNEL_CHOICES = [('email', 'Email'), ('sms', 'SMS'), ('in_app', 'In-App')]

    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    channel = models.CharField(max_length=10, choices=CHANNEL_CHOICES)
    subject_template = models.CharField(max_length=255, blank=True, help_text="Email only")
    body_template = models.TextField(help_text="Supports {{ patient_name }}, {{ doctor_name }}, {{ appointment_time }} etc.")
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('category', 'channel')

    def __str__(self):
        return f"{self.category} ({self.channel})"


class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    channel = models.CharField(max_length=10, choices=NotificationTemplate.CHANNEL_CHOICES)
    category = models.CharField(max_length=30, choices=NotificationTemplate.CATEGORY_CHOICES)
    subject = models.CharField(max_length=255, blank=True)
    body = models.TextField()

    STATUS_CHOICES = [
        ('queued', 'Queued'), ('sent', 'Sent'), ('failed', 'Failed'), ('read', 'Read'),
    ]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='queued')

    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['user', 'status'])]

    def __str__(self):
        return f"{self.category} to {self.user} ({self.status})"


class NotificationPreference(models.Model):
    """One row per user per category — lets a patient opt out of
    'marketing' emails while keeping 'reminder' SMS on, for example."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notification_preferences')
    category = models.CharField(max_length=30, choices=NotificationTemplate.CATEGORY_CHOICES)
    email_enabled = models.BooleanField(default=True)
    sms_enabled = models.BooleanField(default=True)

    class Meta:
        unique_together = ('user', 'category')
