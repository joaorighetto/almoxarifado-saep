"""Rotas web da aplicação de saídas de materiais."""

from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = "requests"

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="login", permanent=False)),
    path("saidas/", views.issue_list, name="issue_list"),
    path("saidas/nova/", views.issue_create, name="issue_create"),
    path("saidas/<int:pk>/", views.issue_detail, name="issue_detail"),
    path("saidas/<int:pk>/csv/", views.issue_export_csv, name="issue_export_csv"),
    path("solicitacoes/nova/", views.material_request_create, name="material_request_create"),
    path("solicitacoes/minhas/", views.material_request_list, name="material_request_list"),
    path(
        "solicitacoes/<int:pk>/editar/",
        views.material_request_edit,
        name="material_request_edit",
    ),
    path("solicitacoes/<int:pk>/", views.material_request_detail, name="material_request_detail"),
    path(
        "chefia/solicitacoes/pendentes/",
        views.chief_pending_approvals,
        name="chief_pending_approvals",
    ),
    path(
        "chefia/solicitacoes/historico/",
        views.chief_request_history,
        name="chief_request_history",
    ),
    path(
        "almoxarifado/solicitacoes/aprovadas/",
        views.warehouse_approved_queue,
        name="warehouse_approved_queue",
    ),
    path(
        "almoxarifado/solicitacoes/historico/",
        views.warehouse_request_history,
        name="warehouse_request_history",
    ),
    path("notificacoes/", views.notifications_list, name="notifications_list"),
]
