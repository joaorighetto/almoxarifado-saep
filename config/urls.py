"""Roteamento raiz do projeto Django."""

from django.contrib import admin
from django.urls import include, path

from apps.accounts.views import RoleBasedLoginView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/login/", RoleBasedLoginView.as_view(), name="login"),
    path("accounts/", include("django.contrib.auth.urls")),
    path("", include("apps.requests.urls")),
    path("api/", include("apps.requests.api_urls")),
]
