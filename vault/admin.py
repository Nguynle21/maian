from django.contrib import admin

from customers.admin import ArchivableAdmin
from vault.models import VaultDocument


@admin.register(VaultDocument)
class VaultDocumentAdmin(ArchivableAdmin):
    list_display = ["original_filename", "customer", "uploaded_by", "uploaded_at", "archived_at"]
    readonly_fields = ["file", "content_type", "size_bytes", "uploaded_by", "uploaded_at"]
