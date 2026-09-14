from django.conf import settings
from django.contrib import admin
from django.contrib.auth.views import LogoutView
from django.urls import include, path
from two_factor.urls import urlpatterns as two_factor_urls

urlpatterns = [
    path("", include(two_factor_urls)),
    path("account/logout/", LogoutView.as_view(), name="logout"),
    path(settings.ADMIN_PATH, admin.site.urls),
    path("vault/", include("vault.urls")),
    path("", include("customers.urls")),
]
