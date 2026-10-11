from rest_framework.permissions import BasePermission

PATIENT, DOCTOR, RECEPTIONIST, ADMIN = 'patient', 'doctor', 'receptionist', 'admin'
ROLE_NAMES = (PATIENT, DOCTOR, RECEPTIONIST, ADMIN)


def get_role(user):
    """The user's role name. Django superusers always count as admin."""
    if not user or not user.is_authenticated:
        return None
    if user.is_superuser:
        return ADMIN
    return user.role.name if user.role_id else None


def roles_required(*allowed):
    """Build a permission class: roles_required('doctor', 'admin')."""

    class _HasRole(BasePermission):
        message = 'Your account is not allowed to do this.'

        def has_permission(self, request, view):
            return get_role(request.user) in allowed

    _HasRole.__name__ = 'Has_' + '_'.join(allowed)
    return _HasRole


IsStaffRole = roles_required(DOCTOR, RECEPTIONIST, ADMIN)
IsFrontDesk = roles_required(RECEPTIONIST, ADMIN)
IsDoctorOrAdmin = roles_required(DOCTOR, ADMIN)
