from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        user = self.model(email=self.normalize_email(email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields["is_staff"] = True
        extra_fields["is_superuser"] = True
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Staff login. Email instead of username. Deactivate, never archive or remove (ADR-0012)."""

    username = None
    email = models.EmailField(unique=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.get_full_name() or self.email


class ActiveManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(archived_at__isnull=True)


class ArchivableModel(models.Model):
    """Soft delete (ADR-0011). `objects` hides archived rows everywhere by default;
    `all_objects` is for Django admin and restore only."""

    archived_at = models.DateTimeField(null=True, blank=True)
    archived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )

    objects = ActiveManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True
        base_manager_name = "all_objects"


class AuditEventQuerySet(models.QuerySet):
    """Blocks bulk mutation so the append-only guard can't be bypassed via .update()/.delete()."""

    def update(self, *args, **kwargs):
        raise ValueError("AuditEvent rows are append-only")

    def delete(self, *args, **kwargs):
        raise ValueError("AuditEvent rows are append-only")


class AuditEvent(models.Model):
    """Append-only record of meaningful actions (ADR-0010). Never updated or removed."""

    class Action(models.TextChoices):
        ARCHIVE = "archive"
        RESTORE = "restore"
        USER_CREATED = "user_created"
        USER_CHANGED = "user_changed"

    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name="+")
    action = models.CharField(max_length=40, choices=Action.choices)
    target_type = models.CharField(max_length=50)
    target_id = models.CharField(max_length=50)
    detail = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = AuditEventQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValueError("AuditEvent rows are append-only")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("AuditEvent rows are append-only")
