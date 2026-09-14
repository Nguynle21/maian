from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from core.models import AuditEvent, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ["email"]
    list_display = ["email", "first_name", "last_name", "is_active", "is_staff"]
    search_fields = ["email", "first_name", "last_name"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Name", {"fields": ("first_name", "last_name")}),
        ("Access", {"fields": ("is_active", "is_staff", "groups")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "password1", "password2", "groups", "is_staff")}),)

    def has_delete_permission(self, request, obj=None):
        return False  # deactivate, never remove (ADR-0012)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        AuditEvent.objects.create(
            actor=request.user,
            action=AuditEvent.Action.USER_CHANGED if change else AuditEvent.Action.USER_CREATED,
            target_type="user",
            target_id=str(obj.pk),
            detail=", ".join(form.changed_data)[:255],
        )


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ["created_at", "actor", "action", "target_type", "target_id", "detail"]
    list_filter = ["action", "target_type"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
