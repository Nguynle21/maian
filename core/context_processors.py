from django.conf import settings

from core.roles import is_admin


def roles(request):
    return {"is_admin": is_admin(request.user), "admin_path": settings.ADMIN_PATH}
