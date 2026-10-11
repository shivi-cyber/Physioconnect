from .models import AuditLog


def audit(request, action, entity_type, entity_id, **metadata):
    """Append a row to the audit log. Never raises - logging must not break a request."""
    try:
        ip = request.META.get('REMOTE_ADDR') if request is not None else None
        user = getattr(request, 'user', None)
        AuditLog.objects.create(
            actor=user if user is not None and user.is_authenticated else None,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            metadata=metadata,
            ip_address=ip,
        )
    except Exception:  # pragma: no cover
        pass
