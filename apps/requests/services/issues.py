"""Workflow e consultas de saídas de materiais."""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.db import transaction
from rest_framework import serializers

from ..models import IssueItem, IssueRequest
from .stock import StockValidationError, consume_stock_for_issue


def validate_issue_request_items(items) -> None:
    """Exige ao menos um item e impede materiais duplicados na mesma saída."""
    if not items:
        raise serializers.ValidationError("Adicione pelo menos um item.")

    seen_material_ids = set()
    duplicated_material_ids = set()
    for item in items:
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


@transaction.atomic
def create_issue_request(validated_data):
    """Cria saída com itens e consome estoque de forma transacional."""
    items_data = validated_data.pop("items", [])
    issue = IssueRequest.objects.create(**validated_data)
    IssueItem.objects.bulk_create([IssueItem(issue=issue, **item_data) for item_data in items_data])
    items = list(issue.items.select_related("material").all())
    try:
        consume_stock_for_issue(issue, items)
    except StockValidationError as exc:
        raise serializers.ValidationError({"items": exc.messages}) from exc
    return issue


def issue_queryset():
    """Query base de saídas com itens e materiais pré-carregados."""
    return IssueRequest.objects.prefetch_related("items__material")


def issue_ordered_queryset():
    """Lista de saídas ordenada da mais recente para a mais antiga."""
    return issue_queryset().order_by("-issued_at", "-id")


def issue_detail_queryset():
    """Query usada no detalhe e exportação de uma saída."""
    return issue_queryset()


def issue_detail_context(issue: IssueRequest) -> dict:
    """Contexto da página de detalhe de uma saída."""
    return {
        "issue": issue,
        "xlsx_path": str(Path(settings.EXPORT_DIR) / settings.ISSUE_EXPORT_FILENAME),
    }


def issue_csv_rows(issue: IssueRequest):
    """Linhas CSV exportadas para uma saída."""
    for item in issue.items.all():
        material = item.material
        yield [
            issue.id,
            issue.issued_at.isoformat(sep=" ", timespec="minutes"),
            issue.requested_by_name,
            issue.destination,
            issue.document_ref,
            material.sku,
            material.name,
            material.unit,
            str(item.quantity),
            item.notes,
        ]
