from django.contrib import admin, messages

from core.archive import restore
from customers.models import Customer, HouseholdMember


class ArchivableAdmin(admin.ModelAdmin):
    """Admin sees archived rows too, and can restore them. Nothing can be removed."""

    actions = ["restore_selected"]

    def get_queryset(self, request):
        return self.model.all_objects.all()

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="Restore selected archived records")
    def restore_selected(self, request, queryset):
        for obj in queryset.filter(archived_at__isnull=False):
            restore(obj, request.user)
        messages.success(request, "Restored.")


class HouseholdMemberInline(admin.TabularInline):
    model = HouseholdMember
    fk_name = "customer"
    extra = 0
    can_delete = False


@admin.register(Customer)
class CustomerAdmin(ArchivableAdmin):
    list_display = ["last_name", "first_name", "date_of_birth", "phone_primary", "sms_opt_out", "archived_at"]
    search_fields = ["last_name", "first_name", "phone_primary", "phone_secondary"]
    list_filter = ["preferred_language", "sms_opt_out"]
    inlines = [HouseholdMemberInline]


@admin.register(HouseholdMember)
class HouseholdMemberAdmin(ArchivableAdmin):
    list_display = ["last_name", "first_name", "relationship", "customer", "archived_at"]
