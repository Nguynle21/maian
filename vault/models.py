import uuid
from pathlib import Path

from django.conf import settings
from django.core.files.storage import storages
from django.db import models

from core.models import ArchivableModel


def vault_storage():
    return storages["vault"]


def vault_key(instance, filename):
    """Random stored name. The uploaded filename is never used in the path (ADR-0015)."""
    return f"customers/{instance.customer_id}/{uuid.uuid4().hex}{Path(filename).suffix.lower()}"


class VaultDocument(ArchivableModel):
    customer = models.ForeignKey("customers.Customer", on_delete=models.PROTECT, related_name="documents")
    file = models.FileField(upload_to=vault_key, storage=vault_storage, max_length=255)
    original_filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    size_bytes = models.PositiveIntegerField()
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta(ArchivableModel.Meta):
        ordering = ["-uploaded_at"]

    def __str__(self):
        return self.original_filename
