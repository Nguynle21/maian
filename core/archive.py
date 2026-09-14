from django.core.exceptions import PermissionDenied
from django.utils import timezone

from core.models import AuditEvent
from core.roles import is_admin


def archive(obj, user):
    """Hide a record everywhere. Admin only; checked here so no view can forget."""
    if not is_admin(user):
        raise PermissionDenied("Only Admin can archive records.")
    obj.archived_at = timezone.now()
    obj.archived_by = user
    obj.save(update_fields=["archived_at", "archived_by"])
    _log(user, AuditEvent.Action.ARCHIVE, obj)


def restore(obj, user):
    if not is_admin(user):
        raise PermissionDenied("Only Admin can restore records.")
    obj.archived_at = None
    obj.archived_by = None
    obj.save(update_fields=["archived_at", "archived_by"])
    _log(user, AuditEvent.Action.RESTORE, obj)


def _log(user, action, obj):
    AuditEvent.objects.create(
        actor=user, action=action, target_type=obj._meta.model_name, target_id=str(obj.pk)
    )
