"""The two roles (ADR-0012). Both see and edit every Customer; only Admin archives,
exports, and manages users. Roles are plain Django groups."""

ADMIN_GROUP = "Admin"
STAFF_GROUP = "Staff"


def is_admin(user):
    if not user.is_authenticated:
        return False
    return user.is_superuser or user.groups.filter(name=ADMIN_GROUP).exists()
