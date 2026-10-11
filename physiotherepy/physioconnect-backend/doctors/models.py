import uuid
from django.conf import settings
from django.db import models


class Specialization(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Doctor(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='doctor_profile')

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, help_text="Used in the public profile URL, e.g. /doctors/dr-arjun-mehta")

    specializations = models.ManyToManyField(Specialization, through='DoctorSpecialization', related_name='doctors')
    qualifications = models.TextField(blank=True)
    bio = models.TextField(blank=True)
    years_experience = models.PositiveIntegerField(default=0)
    profile_photo = models.ImageField(upload_to='doctor_photos/', null=True, blank=True)
    consultation_fee_default = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    EMPLOYMENT_STATUS_CHOICES = [
        ('active', 'Active'), ('on_leave', 'On Leave'), ('inactive', 'Inactive'),
    ]
    employment_status = models.CharField(max_length=20, choices=EMPLOYMENT_STATUS_CHOICES, default='active')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Dr. {self.first_name} {self.last_name}"


class DoctorSpecialization(models.Model):
    """Explicit through-table (rather than a plain M2M) so we can add
    fields like 'is_primary' later without a schema-breaking migration."""
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE)
    specialization = models.ForeignKey(Specialization, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('doctor', 'specialization')


class DoctorAvailability(models.Model):
    """Recurring weekly template — e.g. 'every Monday 9am-5pm, 30-min slots'."""
    DAY_CHOICES = [
        (0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'), (3, 'Thursday'),
        (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday'),
    ]
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='availability')
    day_of_week = models.PositiveSmallIntegerField(choices=DAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()
    slot_duration_minutes = models.PositiveIntegerField(default=30)
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [models.Index(fields=['doctor', 'day_of_week'])]

    def __str__(self):
        return f"{self.doctor} — {self.get_day_of_week_display()} {self.start_time}-{self.end_time}"


class DoctorTimeOff(models.Model):
    """One-off exceptions: leave, holidays, blocked time."""
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='time_off')
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    reason = models.CharField(max_length=255, blank=True)

    class Meta:
        indexes = [models.Index(fields=['doctor', 'start_datetime', 'end_datetime'])]

    def __str__(self):
        return f"{self.doctor} off {self.start_datetime} - {self.end_datetime}"


class DoctorService(models.Model):
    """Which services a doctor offers, with an optional per-doctor price
    override (e.g. a senior doctor charges more for the same service)."""
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='doctor_services')
    service = models.ForeignKey('core.Service', on_delete=models.CASCADE, related_name='doctor_services')
    price_override = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)

    class Meta:
        unique_together = ('doctor', 'service')

    def __str__(self):
        return f"{self.doctor} — {self.service}"

    @property
    def effective_price(self):
        return self.price_override if self.price_override is not None else self.service.default_price
