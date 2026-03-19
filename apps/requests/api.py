"""API REST para criação e consulta de saídas de materiais."""

from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.accounts.models import Profile

from .models import IssueItem, IssueRequest
from .models import (
    MaterialRequest,
    MaterialRequestEvent,
    MaterialRequestItem,
    RequestNotification,
)
from .services import (
    StockValidationError,
    append_issue_to_xlsx,
    consume_stock_for_issue,
    search_materials,
)


class IssueItemSerializer(serializers.ModelSerializer):
    """Serializer de item com campos derivados do material."""

    material_sku = serializers.CharField(source="material.sku", read_only=True)
    material_name = serializers.CharField(source="material.name", read_only=True)
    unit = serializers.CharField(source="material.unit", read_only=True)

    class Meta:
        model = IssueItem
        fields = ["id", "material", "material_sku", "material_name", "unit", "quantity", "notes"]

    def validate_quantity(self, value):
        """Impede criação de item com quantidade zero/negativa."""
        if value is None or value <= 0:
            raise serializers.ValidationError("A quantidade deve ser maior que zero.")
        return value


class IssueRequestSerializer(serializers.ModelSerializer):
    """Serializer de saída com criação aninhada dos itens."""

    items = IssueItemSerializer(many=True)

    class Meta:
        model = IssueRequest
        fields = [
            "id",
            "requested_by_name",
            "destination",
            "document_ref",
            "issued_at",
            "notes",
            "items",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def validate_destination(self, value: str) -> str:
        """Impede criação de saída sem destino preenchido."""
        if not (value or "").strip():
            raise serializers.ValidationError("Destino é obrigatório.")
        return value

    def validate_requested_by_name(self, value: str) -> str:
        """Impede criação de saída sem solicitante preenchido."""
        if not (value or "").strip():
            raise serializers.ValidationError("Solicitante é obrigatório.")
        return value

    def validate_items(self, value):
        """Exige ao menos um item com material e quantidade positiva."""
        if not value:
            raise serializers.ValidationError("Adicione pelo menos um item.")

        seen_material_ids = set()
        duplicated_material_ids = set()
        for item in value:
            material = item.get("material")
            if not material:
                continue
            if material.id in seen_material_ids:
                duplicated_material_ids.add(material.id)
            else:
                seen_material_ids.add(material.id)

        if duplicated_material_ids:
            raise serializers.ValidationError(
                "Não adicione o mesmo material mais de uma vez na mesma saída."
            )
        return value

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop("items", [])
        issue = IssueRequest.objects.create(**validated_data)
        IssueItem.objects.bulk_create(
            [IssueItem(issue=issue, **item_data) for item_data in items_data]
        )
        items = list(issue.items.select_related("material").all())
        try:
            consume_stock_for_issue(issue, items)
        except StockValidationError as exc:
            raise serializers.ValidationError({"items": exc.messages}) from exc
        return issue


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


def _user_department(user) -> str:
    profile = Profile.objects.filter(user=user).only("department").first()
    return (profile.department if profile else "").strip()


def _is_section_chief(user, department: str) -> bool:
    if not user.is_authenticated:
        return False
    if not user.groups.filter(name="chefe_secao").exists():
        return False
    return bool(department) and _user_department(user) == department


def _is_warehouse_user(user) -> bool:
    return bool(user and user.is_authenticated and user.groups.filter(name="almoxarifado").exists())


def _should_auto_approve_request(user, material_request: MaterialRequest) -> bool:
    requester_department = (material_request.requester_department or "").strip()
    if _is_warehouse_user(user) or user.groups.filter(name="chefe_secao").exists():
        return requester_department == _user_department(user)
    return False


def _requester_identity_for_creation(
    user,
    *,
    requester_name: str = "",
    requester_department: str = "",
) -> tuple[str, str]:
    default_name = (user.get_full_name() or user.username or "").strip()
    default_department = _user_department(user)

    if _is_warehouse_user(user):
        return requester_name or default_name, requester_department or default_department

    return default_name, default_department


def _create_material_request_event(
    material_request: MaterialRequest,
    event_type: str,
    performed_by=None,
    notes: str = "",
) -> None:
    MaterialRequestEvent.objects.create(
        material_request=material_request,
        event_type=event_type,
        performed_by=performed_by,
        notes=notes or "",
    )


def _notify_users(
    users,
    *,
    material_request: MaterialRequest,
    category: str,
    title: str,
    message: str,
) -> None:
    user_ids = []
    for user in users:
        user_id = getattr(user, "id", None)
        if user_id:
            user_ids.append(user_id)
    unique_ids = sorted(set(user_ids))
    if not unique_ids:
        return

    RequestNotification.objects.bulk_create(
        [
            RequestNotification(
                user_id=user_id,
                material_request=material_request,
                category=category,
                title=title,
                message=message,
            )
            for user_id in unique_ids
        ]
    )


def _section_chiefs_for_department(department: str):
    dep = (department or "").strip()
    if not dep:
        return []
    return (
        Profile.objects.select_related("user")
        .filter(
            department=dep,
            user__is_active=True,
            user__groups__name="chefe_secao",
        )
        .distinct()
    )


class MaterialRequestItemSerializer(serializers.ModelSerializer):
    """Serializer de item solicitado com metadados do material."""

    material_sku = serializers.CharField(source="material.sku", read_only=True)
    material_name = serializers.CharField(source="material.name", read_only=True)
    unit = serializers.CharField(source="material.unit", read_only=True)

    class Meta:
        model = MaterialRequestItem
        fields = [
            "id",
            "material",
            "material_sku",
            "material_name",
            "unit",
            "requested_quantity",
            "notes",
        ]

    def validate_requested_quantity(self, value):
        if value is None or value <= 0:
            raise serializers.ValidationError("A quantidade deve ser maior que zero.")
        return value


class MaterialRequestSerializer(serializers.ModelSerializer):
    """Serializer de solicitação com itens aninhados."""

    items = MaterialRequestItemSerializer(many=True, required=False)
    requested_by_username = serializers.CharField(source="requested_by.username", read_only=True)

    class Meta:
        model = MaterialRequest
        fields = [
            "id",
            "requested_by",
            "requested_by_username",
            "requester_name",
            "requester_department",
            "status",
            "notes",
            "submitted_at",
            "approved_at",
            "approved_by",
            "rejected_at",
            "rejected_by",
            "rejection_reason",
            "fulfilled_at",
            "fulfilled_by",
            "issue",
            "canceled_at",
            "canceled_by",
            "cancellation_reason",
            "items",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "requested_by",
            "requested_by_username",
            "status",
            "submitted_at",
            "approved_at",
            "approved_by",
            "rejected_at",
            "rejected_by",
            "rejection_reason",
            "fulfilled_at",
            "fulfilled_by",
            "issue",
            "canceled_at",
            "canceled_by",
            "cancellation_reason",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        request = self.context["request"]
        if request.method != "POST" or not _is_warehouse_user(request.user):
            return attrs

        requester_name = str(attrs.get("requester_name", "")).strip()
        requester_department = str(attrs.get("requester_department", "")).strip()
        if requester_name:
            attrs["requester_name"] = requester_name
        if requester_department:
            attrs["requester_department"] = requester_department
        if bool(requester_name) != bool(requester_department):
            raise serializers.ValidationError(
                {
                    "requester_department": [
                        "Informe solicitante e departamento para solicitações de outras seções."
                    ]
                }
            )
        return attrs

    def validate_items(self, value):
        seen_material_ids = set()
        for item in value:
            material = item.get("material")
            if not material:
                continue
            if material.id in seen_material_ids:
                raise serializers.ValidationError(
                    "Não adicione o mesmo material mais de uma vez na mesma solicitação."
                )
            seen_material_ids.add(material.id)
        return value

    @transaction.atomic
    def create(self, validated_data):
        request = self.context["request"]
        user = request.user
        items_data = validated_data.pop("items", [])
        requester_name = str(validated_data.pop("requester_name", "")).strip()
        requester_department = str(validated_data.pop("requester_department", "")).strip()
        requester_name, requester_department = _requester_identity_for_creation(
            user,
            requester_name=requester_name,
            requester_department=requester_department,
        )

        material_request = MaterialRequest.objects.create(
            requested_by=user,
            requester_name=requester_name,
            requester_department=requester_department,
            **validated_data,
        )
        if items_data:
            MaterialRequestItem.objects.bulk_create(
                [
                    MaterialRequestItem(material_request=material_request, **item_data)
                    for item_data in items_data
                ]
            )
        _create_material_request_event(
            material_request,
            MaterialRequestEvent.EventType.CREATED,
            performed_by=user,
        )
        return material_request

    @transaction.atomic
    def update(self, instance, validated_data):
        if instance.status != MaterialRequest.Status.DRAFT:
            raise serializers.ValidationError(
                {"status": ["Somente solicitações em rascunho podem ser editadas."]}
            )

        items_data = validated_data.pop("items", None)
        instance.notes = validated_data.get("notes", instance.notes)
        instance.save(update_fields=["notes", "updated_at"])

        if items_data is not None:
            instance.items.all().delete()
            if items_data:
                MaterialRequestItem.objects.bulk_create(
                    [
                        MaterialRequestItem(material_request=instance, **item_data)
                        for item_data in items_data
                    ]
                )
        return instance


class MaterialRequestViewSet(viewsets.ModelViewSet):
    """API REST para solicitações de materiais com aprovação por seção."""

    serializer_class = MaterialRequestSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = MaterialRequest.objects.select_related(
        "requested_by",
        "approved_by",
        "rejected_by",
        "fulfilled_by",
        "canceled_by",
        "issue",
    ).prefetch_related("items__material")

    def get_queryset(self):
        user = self.request.user
        queryset = super().get_queryset().order_by("-created_at", "-id")

        if self.action in {"approve", "reject"}:
            if not user.groups.filter(name="chefe_secao").exists():
                return queryset.none()
            return queryset

        if self.action == "fulfill":
            return queryset

        if self.action == "pending_approval":
            if not user.groups.filter(name="chefe_secao").exists():
                return queryset.none()
            department = _user_department(user)
            return queryset.filter(
                status=MaterialRequest.Status.SUBMITTED,
                requester_department=department,
            )

        if self.action == "approved_queue":
            if not _is_warehouse_user(user):
                return queryset.none()
            return queryset.filter(status=MaterialRequest.Status.APPROVED)

        return queryset.filter(requested_by=user)

    def perform_destroy(self, instance):
        if instance.requested_by_id != self.request.user.id:
            raise PermissionDenied("Você só pode excluir suas próprias solicitações.")
        if instance.status != MaterialRequest.Status.DRAFT:
            raise serializers.ValidationError(
                {"status": ["Somente solicitações em rascunho podem ser excluídas."]}
            )
        instance.delete()

    def _ensure_owner(self, material_request: MaterialRequest) -> None:
        if material_request.requested_by_id != self.request.user.id:
            raise PermissionDenied("Somente o solicitante pode executar esta ação.")

    def _ensure_section_chief(self, material_request: MaterialRequest) -> None:
        if _is_section_chief(self.request.user, material_request.requester_department):
            return
        raise PermissionDenied("Somente o chefe da seção do solicitante pode executar esta ação.")

    def _ensure_warehouse_user(self) -> None:
        if _is_warehouse_user(self.request.user):
            return
        raise PermissionDenied("Somente o almoxarifado pode executar esta ação.")

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def submit(self, request, pk=None):
        material_request = self.get_object()
        self._ensure_owner(material_request)

        if material_request.status != MaterialRequest.Status.DRAFT:
            return Response(
                {"status": ["Somente solicitações em rascunho podem ser enviadas."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not material_request.items.exists():
            return Response(
                {"items": ["Adicione pelo menos um item antes de enviar para aprovação."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        submitted_at = timezone.now()
        update_fields = ["status", "submitted_at", "updated_at"]
        material_request.status = MaterialRequest.Status.SUBMITTED
        material_request.submitted_at = submitted_at

        if _should_auto_approve_request(request.user, material_request):
            material_request.status = MaterialRequest.Status.APPROVED
            material_request.approved_at = submitted_at
            material_request.approved_by = request.user
            update_fields.extend(["approved_at", "approved_by"])

        material_request.save(update_fields=update_fields)
        _create_material_request_event(
            material_request,
            MaterialRequestEvent.EventType.SUBMITTED,
            performed_by=request.user,
        )
        if material_request.status == MaterialRequest.Status.APPROVED:
            _create_material_request_event(
                material_request,
                MaterialRequestEvent.EventType.APPROVED,
                performed_by=request.user,
                notes="Autoaprovada por solicitação interna do próprio setor.",
            )
            return Response(self.get_serializer(material_request).data)

        chiefs = [profile.user for profile in _section_chiefs_for_department(material_request.requester_department)]
        _notify_users(
            chiefs,
            material_request=material_request,
            category=RequestNotification.Category.ACTION_REQUIRED,
            title=f"Solicitação #{material_request.id} aguardando aprovação",
            message=(
                f"{material_request.requester_name or material_request.requested_by.username} "
                f"enviou uma solicitação para sua aprovação."
            ),
        )
        return Response(self.get_serializer(material_request).data)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def approve(self, request, pk=None):
        material_request = self.get_object()
        self._ensure_section_chief(material_request)

        if material_request.status != MaterialRequest.Status.SUBMITTED:
            return Response(
                {"status": ["Apenas solicitações enviadas podem ser aprovadas."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        material_request.status = MaterialRequest.Status.APPROVED
        material_request.approved_at = timezone.now()
        material_request.approved_by = request.user
        material_request.save(
            update_fields=["status", "approved_at", "approved_by", "updated_at"]
        )
        _create_material_request_event(
            material_request,
            MaterialRequestEvent.EventType.APPROVED,
            performed_by=request.user,
        )
        _notify_users(
            [material_request.requested_by],
            material_request=material_request,
            category=RequestNotification.Category.STATUS_UPDATE,
            title=f"Solicitação #{material_request.id} aprovada",
            message="Sua solicitação foi aprovada e está na fila do almoxarifado.",
        )
        return Response(self.get_serializer(material_request).data)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def reject(self, request, pk=None):
        material_request = self.get_object()
        self._ensure_section_chief(material_request)

        if material_request.status != MaterialRequest.Status.SUBMITTED:
            return Response(
                {"status": ["Apenas solicitações enviadas podem ser rejeitadas."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        rejection_reason = str(request.data.get("reason", "")).strip()
        if not rejection_reason:
            return Response(
                {"reason": ["Motivo da rejeição é obrigatório."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        material_request.status = MaterialRequest.Status.REJECTED
        material_request.rejected_at = timezone.now()
        material_request.rejected_by = request.user
        material_request.rejection_reason = rejection_reason
        material_request.save(
            update_fields=[
                "status",
                "rejected_at",
                "rejected_by",
                "rejection_reason",
                "updated_at",
            ]
        )
        _create_material_request_event(
            material_request,
            MaterialRequestEvent.EventType.REJECTED,
            performed_by=request.user,
            notes=rejection_reason,
        )
        _notify_users(
            [material_request.requested_by],
            material_request=material_request,
            category=RequestNotification.Category.STATUS_UPDATE,
            title=f"Solicitação #{material_request.id} rejeitada",
            message=f"Motivo: {rejection_reason}",
        )
        return Response(self.get_serializer(material_request).data)

    @action(detail=False, methods=["get"])
    def pending_approval(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def approved_queue(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def fulfill(self, request, pk=None):
        self._ensure_warehouse_user()
        material_request = self.get_object()

        if material_request.status != MaterialRequest.Status.APPROVED:
            return Response(
                {"status": ["Apenas solicitações aprovadas podem ser atendidas."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        requested_items = list(material_request.items.select_related("material").all())
        if not requested_items:
            return Response(
                {"items": ["Solicitação sem itens não pode ser atendida."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        issue = IssueRequest.objects.create(
            requested_by_name=material_request.requester_name or material_request.requested_by.username,
            destination=(material_request.requester_department or "Sem departamento").strip(),
            document_ref=f"SOL-{material_request.id}",
            issued_at=timezone.now(),
            notes=material_request.notes,
        )
        IssueItem.objects.bulk_create(
            [
                IssueItem(
                    issue=issue,
                    material=item.material,
                    quantity=item.requested_quantity,
                    notes=item.notes,
                )
                for item in requested_items
            ]
        )
        issue_items = list(issue.items.select_related("material").all())

        try:
            consume_stock_for_issue(issue, issue_items)
        except StockValidationError as exc:
            raise serializers.ValidationError({"items": exc.messages}) from exc

        xlsx_file = Path(settings.EXPORT_DIR) / settings.ISSUE_EXPORT_FILENAME
        try:
            append_issue_to_xlsx(issue, issue_items, xlsx_file)
        except Exception as exc:
            raise serializers.ValidationError(
                {
                    "non_field_errors": [
                        "Não foi possível registrar a saída na planilha. Tente novamente."
                    ]
                }
            ) from exc

        material_request.status = MaterialRequest.Status.FULFILLED
        material_request.fulfilled_at = timezone.now()
        material_request.fulfilled_by = request.user
        material_request.issue = issue
        material_request.save(
            update_fields=["status", "fulfilled_at", "fulfilled_by", "issue", "updated_at"]
        )
        _create_material_request_event(
            material_request,
            MaterialRequestEvent.EventType.FULFILLED,
            performed_by=request.user,
            notes=f"Saída gerada: #{issue.id}",
        )
        _notify_users(
            [material_request.requested_by],
            material_request=material_request,
            category=RequestNotification.Category.STATUS_UPDATE,
            title=f"Solicitação #{material_request.id} atendida",
            message=f"Sua solicitação foi atendida. Saída gerada: #{issue.id}.",
        )
        return Response(self.get_serializer(material_request).data)


@api_view(["GET"])
def material_search_api(request):
    """Endpoint REST para busca de materiais por SKU/nome."""
    query = request.query_params.get("q", "").strip()
    materials, has_more = search_materials(
        query,
        offset_raw=request.query_params.get("offset"),
        limit_raw=request.query_params.get("limit"),
    )

    return Response(
        {
            "results": [
                {
                    "id": material.id,
                    "sku": material.sku,
                    "name": material.name,
                    "unit": material.unit,
                    "available_quantity": str(
                        material.stockbalance.quantity if hasattr(material, "stockbalance") else 0
                    ),
                }
                for material in materials
            ],
            "has_more": has_more,
        }
    )
