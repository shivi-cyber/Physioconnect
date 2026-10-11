import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models


class Permission(models.Model):
    """
    A single grantable capability, e.g. 'appointments.cancel.any',
    'patients.medical_profile.view'. Kept as data (not hardcoded Python
    constants) so an Admin can inspect/assign these from the Django admin
    without a code deploy.
    """
    key = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.key


class Role(models.Model):
    """
    patient / doctor / receptionist / admin / super_admin — but stored as
    data rather than a fixed Python enum, so a clinic can later add a
    custom role (e.g. 'billing_clerk') without a migration.
    """
    name = models.CharField(max_length=50, unique=True)
    description = models.CharField(max_length=255, blank=True)
    permissions = models.ManyToManyField(Permission, blank=True, related_name='roles')

    def __str__(self):
        return self.name


class User(AbstractUser):
    """
    Custom user model. We keep Django's built-in username/password/email
    fields (via AbstractUser) but add a UUID primary key, phone number,
    and a role FK, matching the Phase 5 `users` table design.

    NOTE: AbstractUser already gives us: username, first_name, last_name,
    email, password, is_active, date_joined, last_login — we don't need to
    redefine those.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone = models.CharField(max_length=15, unique=True, null=True, blank=True)
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name='users', null=True)

    email_verified_at = models.DateTimeField(null=True, blank=True)
    phone_verified_at = models.DateTimeField(null=True, blank=True)

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('suspended', 'Suspended'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')

    def has_permission(self, permission_key: str) -> bool:
        """Central place to check RBAC — every view should call this
        rather than checking role names directly, so permission logic
        stays in one place."""
        if not self.role:
            return False
        return self.role.permissions.filter(key=permission_key).exists()

    def __str__(self):
        return self.email or self.phone or str(self.id)
