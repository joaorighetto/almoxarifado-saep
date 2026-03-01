"""Rotas web da aplicação de saídas de materiais."""

from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = "requests"

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="requests:issue_create", permanent=False)),
    path("saidas/nova/", views.issue_create, name="issue_create"),
    path("saidas/<int:pk>/", views.issue_detail, name="issue_detail"),
    path("saidas/<int:pk>/csv/", views.issue_export_csv, name="issue_export_csv"),
]
