"""API REST para criação e consulta de saídas de materiais."""

from pathlib import Path

from django.conf import settings
from django.db import transaction
from rest_framework import serializers, viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import IssueItem, IssueRequest
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

    def perform_create(self, serializer):
        issue = serializer.save()
        xlsx_file = Path(settings.EXPORT_DIR) / settings.ISSUE_EXPORT_FILENAME
        append_issue_to_xlsx(issue, issue.items.select_related("material").all(), xlsx_file)


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
