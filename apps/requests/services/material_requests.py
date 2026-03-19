"""Workflow de solicitacoes de materiais."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework import serializers

from apps.accounts.models import (
    SECTION_CHIEF_GROUP,
    Profile,
    user_department,
    user_is_section_chief,
    user_is_warehouse,
)
from apps.inventory.models import StockBalance

from ..models import (
    IssueItem,
    IssueRequest,
    MaterialRequest,
    MaterialRequestEvent,
    MaterialRequestItem,
    RequestNotification,
)
from .export import append_issue_to_xlsx
from .stock import StockValidationError, consume_stock_for_issue


def should_auto_approve_request(user, material_request: MaterialRequest) -> bool:
    requester_department = (material_request.requester_department or "").strip()
    if user_is_warehouse(user) or user_is_section_chief(user):
        return requester_department == user_department(user)
    return False


def can_view_material_request(user, material_request: MaterialRequest) -> bool:
    if material_request.requested_by_id == getattr(user, "id", None):
        return True
    if user_is_warehouse(user):
        return True
    requester_department = (material_request.requester_department or "").strip()
    return (
        bool(requester_department)
        and user_is_section_chief(user)
        and (user_department(user) == requester_department)
    )


def can_edit_material_request(user, material_request: MaterialRequest) -> bool:
    return (
        material_request.requested_by_id == getattr(user, "id", None)
        and material_request.status == MaterialRequest.Status.DRAFT
    )


def can_submit_material_request(user, material_request: MaterialRequest) -> bool:
    return material_request.requested_by_id == getattr(user, "id", None)


def can_approve_material_request(user, material_request: MaterialRequest) -> bool:
    requester_department = (material_request.requester_department or "").strip()
    return (
        bool(requester_department)
        and user_is_section_chief(user)
        and (user_department(user) == requester_department)
    )


def can_fulfill_material_request(user) -> bool:
    return user_is_warehouse(user)


def ensure_can_delete_material_request(user, material_request: MaterialRequest) -> None:
    if material_request.requested_by_id != getattr(user, "id", None):
        raise PermissionDenied("Você só pode excluir suas próprias solicitações.")
    if material_request.status != MaterialRequest.Status.DRAFT:
        raise serializers.ValidationError(
            {"status": ["Somente solicitações em rascunho podem ser excluídas."]}
        )


def ensure_can_submit_material_request(user, material_request: MaterialRequest) -> None:
    if can_submit_material_request(user, material_request):
        return
    raise PermissionDenied("Somente o solicitante pode executar esta ação.")


def ensure_can_approve_material_request(user, material_request: MaterialRequest) -> None:
    if can_approve_material_request(user, material_request):
        return
    raise PermissionDenied("Somente o chefe da seção do solicitante pode executar esta ação.")


def ensure_can_fulfill_material_request(user) -> None:
    if can_fulfill_material_request(user):
        return
    raise PermissionDenied("Somente o almoxarifado pode executar esta ação.")


def material_request_base_queryset():
    return MaterialRequest.objects.select_related(
        "requested_by",
        "approved_by",
        "rejected_by",
        "fulfilled_by",
        "canceled_by",
        "issue",
    ).prefetch_related("items__material")


def material_request_ordered_queryset():
    return material_request_base_queryset().order_by("-created_at", "-id")


def material_request_detail_queryset():
    return material_request_base_queryset().prefetch_related("events__performed_by")


def material_requests_visible_to_user(user):
    return material_request_ordered_queryset().filter(requested_by=user)


def material_requests_pending_approval_for_user(user):
    if not user_is_section_chief(user):
        return material_request_ordered_queryset().none()
    department = user_department(user)
    return material_request_ordered_queryset().filter(
        status=MaterialRequest.Status.SUBMITTED,
        requester_department=department,
    )


def material_requests_approved_queue_for_user(user):
    if not user_is_warehouse(user):
        return material_request_ordered_queryset().none()
    return material_request_ordered_queryset().filter(status=MaterialRequest.Status.APPROVED)


def chief_pending_material_requests_for_user(user):
    if not user_is_section_chief(user):
        return material_request_base_queryset().none()
    department = user_department(user)
    return material_request_base_queryset().filter(
        status=MaterialRequest.Status.SUBMITTED,
        requester_department=department,
    ).order_by("submitted_at", "id")


def warehouse_approved_material_requests_for_user(user):
    if not user_is_warehouse(user):
        return material_request_base_queryset().none()
    return material_request_base_queryset().filter(
        status=MaterialRequest.Status.APPROVED
    ).order_by("approved_at", "id")


def material_requests_accessible_for_approval(user):
    if not user_is_section_chief(user):
        return material_request_ordered_queryset().none()
    return material_request_ordered_queryset()


def material_requests_accessible_for_fulfillment():
    return material_request_ordered_queryset()


def chief_material_request_history_for_user(user):
    department = user_department(user)
    return material_request_ordered_queryset().filter(requester_department=department)


def warehouse_material_request_history():
    return material_request_ordered_queryset().filter(
        status__in=[MaterialRequest.Status.APPROVED, MaterialRequest.Status.FULFILLED]
    )


def request_notifications_for_user(user):
    return (
        RequestNotification.objects.filter(user=user)
        .select_related("material_request")
        .order_by("is_read", "-created_at", "-id")
    )


def serialize_material_request_for_form(material_request: MaterialRequest) -> dict:
    return {
        "id": material_request.id,
        "requester_name": material_request.requester_name,
        "requester_department": material_request.requester_department,
        "notes": material_request.notes,
        "items": [
            {
                "material": item.material_id,
                "material_sku": item.material.sku,
                "material_name": item.material.name,
                "unit": item.material.unit,
                "requested_quantity": str(item.requested_quantity),
                "notes": item.notes,
            }
            for item in material_request.items.all()
        ],
    }


def material_request_form_context(user, material_request: MaterialRequest | None = None) -> dict:
    is_edit_mode = material_request is not None
    return {
        "form_mode": "edit" if is_edit_mode else "create",
        "material_request": material_request,
        "initial_material_request_data": (
            serialize_material_request_for_form(material_request) if material_request else None
        ),
        "user_department": user_department(user),
    }


def requester_identity_for_creation(
    user,
    *,
    requester_name: str = "",
    requester_department: str = "",
) -> tuple[str, str]:
    default_name = (user.get_full_name() or user.username or "").strip()
    default_department = user_department(user)

    if user_is_warehouse(user):
        return requester_name or default_name, requester_department or default_department

    return default_name, default_department


def normalize_warehouse_requester_fields(
    attrs: dict,
    *,
    user,
    method: str,
) -> dict:
    if method != "POST" or not user_is_warehouse(user):
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


def validate_material_request_items(items) -> None:
    seen_material_ids = set()
    for item in items:
        material = item.get("material")
        if not material:
            continue
        if material.id in seen_material_ids:
            raise serializers.ValidationError(
                "Não adicione o mesmo material mais de uma vez na mesma solicitação."
            )
        seen_material_ids.add(material.id)

    validate_requested_items_against_stock(items)


def validate_requested_items_against_stock(items) -> None:
    required_by_material = defaultdict(lambda: Decimal("0"))
    material_by_id = {}

    for item in items:
        material = item.get("material")
        quantity = item.get("requested_quantity") or Decimal("0")
        if not material or quantity <= 0:
            continue
        required_by_material[material.id] += quantity
        material_by_id[material.id] = material

    if not required_by_material:
        return

    balances = {
        balance.material_id: balance.quantity
        for balance in StockBalance.objects.filter(material_id__in=required_by_material.keys())
    }

    errors = []
    for material_id, required in required_by_material.items():
        material = material_by_id[material_id]
        available = balances.get(material_id, Decimal("0"))
        if available < required:
            errors.append(
                f"{material.sku} - {material.name}: disponível {available} {material.unit}, "
                f"solicitado {required} {material.unit}."
            )

    if errors:
        raise serializers.ValidationError({"items": errors})


def create_material_request_event(
    material_request: MaterialRequest,
    event_type: str,
    *,
    performed_by=None,
    notes: str = "",
) -> None:
    MaterialRequestEvent.objects.create(
        material_request=material_request,
        event_type=event_type,
        performed_by=performed_by,
        notes=notes or "",
    )


def notify_users(
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


def section_chiefs_for_department(department: str):
    dep = (department or "").strip()
    if not dep:
        return []
    return (
        Profile.objects.select_related("user")
        .filter(
            department=dep,
            user__is_active=True,
            user__groups__name=SECTION_CHIEF_GROUP,
        )
        .distinct()
    )


@transaction.atomic
def create_material_request_draft(
    *,
    user,
    notes: str,
    items_data,
    requester_name: str = "",
    requester_department: str = "",
) -> MaterialRequest:
    requester_name, requester_department = requester_identity_for_creation(
        user,
        requester_name=requester_name,
        requester_department=requester_department,
    )

    material_request = MaterialRequest.objects.create(
        requested_by=user,
        requester_name=requester_name,
        requester_department=requester_department,
        notes=notes,
    )
    if items_data:
        MaterialRequestItem.objects.bulk_create(
            [
                MaterialRequestItem(material_request=material_request, **item_data)
                for item_data in items_data
            ]
        )
    create_material_request_event(
        material_request,
        MaterialRequestEvent.EventType.CREATED,
        performed_by=user,
    )
    return material_request


@transaction.atomic
def update_material_request_draft(
    material_request: MaterialRequest,
    *,
    notes: str,
    items_data,
) -> MaterialRequest:
    if material_request.status != MaterialRequest.Status.DRAFT:
        raise serializers.ValidationError(
            {"status": ["Somente solicitações em rascunho podem ser editadas."]}
        )

    material_request.notes = notes
    material_request.save(update_fields=["notes", "updated_at"])

    if items_data is not None:
        material_request.items.all().delete()
        if items_data:
            MaterialRequestItem.objects.bulk_create(
                [
                    MaterialRequestItem(material_request=material_request, **item_data)
                    for item_data in items_data
                ]
            )
    return material_request


@transaction.atomic
def submit_material_request(material_request: MaterialRequest, *, user) -> MaterialRequest:
    if material_request.status != MaterialRequest.Status.DRAFT:
        raise serializers.ValidationError(
            {"status": ["Somente solicitações em rascunho podem ser enviadas."]}
        )
    if not material_request.items.exists():
        raise serializers.ValidationError(
            {"items": ["Adicione pelo menos um item antes de enviar para aprovação."]}
        )

    submitted_at = timezone.now()
    update_fields = ["status", "submitted_at", "updated_at"]
    material_request.status = MaterialRequest.Status.SUBMITTED
    material_request.submitted_at = submitted_at

    if should_auto_approve_request(user, material_request):
        material_request.status = MaterialRequest.Status.APPROVED
        material_request.approved_at = submitted_at
        material_request.approved_by = user
        update_fields.extend(["approved_at", "approved_by"])

    material_request.save(update_fields=update_fields)
    create_material_request_event(
        material_request,
        MaterialRequestEvent.EventType.SUBMITTED,
        performed_by=user,
    )
    if material_request.status == MaterialRequest.Status.APPROVED:
        create_material_request_event(
            material_request,
            MaterialRequestEvent.EventType.APPROVED,
            performed_by=user,
            notes="Autoaprovada por solicitação interna do próprio setor.",
        )
        return material_request

    chiefs = [
        profile.user
        for profile in section_chiefs_for_department(material_request.requester_department)
    ]
    notify_users(
        chiefs,
        material_request=material_request,
        category=RequestNotification.Category.ACTION_REQUIRED,
        title=f"Solicitação #{material_request.id} aguardando aprovação",
        message=(
            f"{material_request.requester_name or material_request.requested_by.username} "
            f"enviou uma solicitação para sua aprovação."
        ),
    )
    return material_request


@transaction.atomic
def approve_material_request(material_request: MaterialRequest, *, user) -> MaterialRequest:
    if material_request.status != MaterialRequest.Status.SUBMITTED:
        raise serializers.ValidationError(
            {"status": ["Apenas solicitações enviadas podem ser aprovadas."]}
        )

    material_request.status = MaterialRequest.Status.APPROVED
    material_request.approved_at = timezone.now()
    material_request.approved_by = user
    material_request.save(update_fields=["status", "approved_at", "approved_by", "updated_at"])
    create_material_request_event(
        material_request,
        MaterialRequestEvent.EventType.APPROVED,
        performed_by=user,
    )
    notify_users(
        [material_request.requested_by],
        material_request=material_request,
        category=RequestNotification.Category.STATUS_UPDATE,
        title=f"Solicitação #{material_request.id} aprovada",
        message="Sua solicitação foi aprovada e está na fila do almoxarifado.",
    )
    return material_request


@transaction.atomic
def reject_material_request(
    material_request: MaterialRequest, *, user, rejection_reason: str
) -> MaterialRequest:
    if material_request.status != MaterialRequest.Status.SUBMITTED:
        raise serializers.ValidationError(
            {"status": ["Apenas solicitações enviadas podem ser rejeitadas."]}
        )
    if not rejection_reason:
        raise serializers.ValidationError({"reason": ["Motivo da rejeição é obrigatório."]})

    material_request.status = MaterialRequest.Status.REJECTED
    material_request.rejected_at = timezone.now()
    material_request.rejected_by = user
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
    create_material_request_event(
        material_request,
        MaterialRequestEvent.EventType.REJECTED,
        performed_by=user,
        notes=rejection_reason,
    )
    notify_users(
        [material_request.requested_by],
        material_request=material_request,
        category=RequestNotification.Category.STATUS_UPDATE,
        title=f"Solicitação #{material_request.id} rejeitada",
        message=f"Motivo: {rejection_reason}",
    )
    return material_request


@transaction.atomic
def fulfill_material_request(material_request: MaterialRequest, *, user) -> MaterialRequest:
    if material_request.status != MaterialRequest.Status.APPROVED:
        raise serializers.ValidationError(
            {"status": ["Apenas solicitações aprovadas podem ser atendidas."]}
        )

    requested_items = list(material_request.items.select_related("material").all())
    if not requested_items:
        raise serializers.ValidationError(
            {"items": ["Solicitação sem itens não pode ser atendida."]}
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
    material_request.fulfilled_by = user
    material_request.issue = issue
    material_request.save(
        update_fields=["status", "fulfilled_at", "fulfilled_by", "issue", "updated_at"]
    )
    create_material_request_event(
        material_request,
        MaterialRequestEvent.EventType.FULFILLED,
        performed_by=user,
        notes=f"Saída gerada: #{issue.id}",
    )
    notify_users(
        [material_request.requested_by],
        material_request=material_request,
        category=RequestNotification.Category.STATUS_UPDATE,
        title=f"Solicitação #{material_request.id} atendida",
        message=f"Sua solicitação foi atendida. Saída gerada: #{issue.id}.",
    )
    return material_request
