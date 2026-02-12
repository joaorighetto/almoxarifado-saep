"""Roteamento raiz do projeto Django."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.requests.urls")),
    path("api/", include("apps.requests.api_urls")),
]
