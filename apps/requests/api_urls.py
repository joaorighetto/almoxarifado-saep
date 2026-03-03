"""Rotas REST para operações de saída de materiais."""

from django.urls import path
from rest_framework.routers import DefaultRouter

from .api import IssueRequestViewSet, MaterialRequestViewSet, material_search_api

router = DefaultRouter()
router.register("saidas", IssueRequestViewSet, basename="issue-request")
router.register("solicitacoes-materiais", MaterialRequestViewSet, basename="material-request")

urlpatterns = [
    path("materiais/search/", material_search_api, name="api_material_search"),
    *router.urls,
]
