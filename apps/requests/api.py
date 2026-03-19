"""API REST para criação e consulta de saídas de materiais."""

from pathlib import Path

from django.conf import settings
from django.db import transaction
from rest_framework import permissions, serializers, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.response import Response

from .models import IssueRequest, MaterialRequest
from .serializers import (
    IssueRequestSerializer,
    MaterialRequestReadSerializer,
    MaterialRequestWriteSerializer,
    MaterialSearchResultSerializer,
)
from .services import (
    append_issue_to_xlsx,
    approve_material_request,
    ensure_can_approve_material_request,
    ensure_can_delete_material_request,
    ensure_can_fulfill_material_request,
    ensure_can_submit_material_request,
    fulfill_material_request,
    material_request_base_queryset,
    material_requests_accessible_for_approval,
    material_requests_accessible_for_fulfillment,
    material_requests_approved_queue_for_user,
    material_requests_pending_approval_for_user,
    material_requests_visible_to_user,
    reject_material_request,
    search_materials,
    submit_material_request,
)


class IssueRequestViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD de saídas com exportação automática para XLSX."""

    queryset = IssueRequest.objects.prefetch_related("items__material").order_by(
        "-issued_at", "-id"
    )
    serializer_class = IssueRequestSerializer

    @transaction.atomic
    def perform_create(self, serializer):
        issue = serializer.save()
        xlsx_file = Path(settings.EXPORT_DIR) / settings.ISSUE_EXPORT_FILENAME
        try:
            append_issue_to_xlsx(issue, issue.items.select_related("material").all(), xlsx_file)
        except Exception as exc:
            raise serializers.ValidationError(
                {
                    "non_field_errors": [
                        "Não foi possível registrar a saída na planilha. Tente novamente."
                    ]
                }
            ) from exc


class MaterialRequestViewSet(viewsets.ModelViewSet):
    """API REST para solicitações de materiais com aprovação por seção."""

    serializer_class = MaterialRequestReadSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = material_request_base_queryset()

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return MaterialRequestWriteSerializer
        return MaterialRequestReadSerializer

    def get_queryset(self):
        user = self.request.user

        if self.action in {"approve", "reject"}:
            return material_requests_accessible_for_approval(user)

        if self.action == "fulfill":
            return material_requests_accessible_for_fulfillment()

        if self.action == "pending_approval":
            return material_requests_pending_approval_for_user(user)

        if self.action == "approved_queue":
            return material_requests_approved_queue_for_user(user)

        return material_requests_visible_to_user(user)

    def perform_destroy(self, instance):
        ensure_can_delete_material_request(self.request.user, instance)
        instance.delete()

    def _allow_any_detail_action(self, material_request: MaterialRequest) -> None:
        return None

    def _ensure_submit_allowed(self, material_request: MaterialRequest) -> None:
        ensure_can_submit_material_request(self.request.user, material_request)

    def _ensure_approval_allowed(self, material_request: MaterialRequest) -> None:
        ensure_can_approve_material_request(self.request.user, material_request)

    def _submit_material_request(self, material_request: MaterialRequest) -> MaterialRequest:
        return submit_material_request(material_request, user=self.request.user)

    def _approve_material_request(self, material_request: MaterialRequest) -> MaterialRequest:
        return approve_material_request(material_request, user=self.request.user)

    def _reject_material_request(self, material_request: MaterialRequest) -> MaterialRequest:
        rejection_reason = str(self.request.data.get("reason", "")).strip()
        return reject_material_request(
            material_request,
            user=self.request.user,
            rejection_reason=rejection_reason,
        )

    def _fulfill_material_request(self, material_request: MaterialRequest) -> MaterialRequest:
        return fulfill_material_request(material_request, user=self.request.user)

    def _run_detail_action(self, permission_check, service_call):
        material_request = self.get_object()
        permission_check(material_request)
        material_request = service_call(material_request)
        return Response(self.get_serializer(material_request).data)

    def _list_action_response(self):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def submit(self, request, pk=None):
        return self._run_detail_action(self._ensure_submit_allowed, self._submit_material_request)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def approve(self, request, pk=None):
        return self._run_detail_action(
            self._ensure_approval_allowed,
            self._approve_material_request,
        )

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def reject(self, request, pk=None):
        return self._run_detail_action(self._ensure_approval_allowed, self._reject_material_request)

    @action(detail=False, methods=["get"])
    def pending_approval(self, request):
        return self._list_action_response()

    @action(detail=False, methods=["get"])
    def approved_queue(self, request):
        return self._list_action_response()

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def fulfill(self, request, pk=None):
        ensure_can_fulfill_material_request(request.user)
        return self._run_detail_action(
            self._allow_any_detail_action, self._fulfill_material_request
        )


@api_view(["GET"])
def material_search_api(request):
    """Endpoint REST para busca de materiais por SKU/nome."""
    query = request.query_params.get("q", "").strip()
    materials, has_more = search_materials(
        query,
        offset_raw=request.query_params.get("offset"),
        limit_raw=request.query_params.get("limit"),
    )
    serializer = MaterialSearchResultSerializer(materials, many=True)

    return Response(
        {
            "results": serializer.data,
            "has_more": has_more,
        }
    )
