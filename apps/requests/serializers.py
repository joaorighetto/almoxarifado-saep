"""Serializers da API de solicitações, saídas e busca de materiais."""

from rest_framework import serializers

from apps.inventory.models import Material

from .models import IssueItem, IssueRequest, MaterialRequest, MaterialRequestItem
from .services import (
    create_issue_request,
    create_material_request_draft,
    normalize_warehouse_requester_fields,
    update_material_request_draft,
    validate_issue_request_items,
    validate_material_request_items,
)


class MaterialSearchResultSerializer(serializers.ModelSerializer):
    """Serializer de leitura para resultados da busca de materiais."""

    available_quantity = serializers.SerializerMethodField()

    class Meta:
        model = Material
        fields = ["id", "sku", "name", "unit", "available_quantity"]

    def get_available_quantity(self, obj) -> str:
        stock_balance = getattr(obj, "stockbalance", None)
        return str(stock_balance.quantity if stock_balance else 0)


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
        """Exige ao menos um item válido na saída."""
        validate_issue_request_items(value)
        return value

    def create(self, validated_data):
        return create_issue_request(validated_data)


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


class MaterialRequestReadSerializer(serializers.ModelSerializer):
    """Serializer de leitura da solicitação."""

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
        read_only_fields = fields


class MaterialRequestWriteSerializer(serializers.ModelSerializer):
    """Serializer de escrita da solicitação."""

    items = MaterialRequestItemSerializer(many=True, required=False)

    class Meta:
        model = MaterialRequest
        fields = [
            "id",
            "requester_name",
            "requester_department",
            "notes",
            "items",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        request = self.context["request"]
        return normalize_warehouse_requester_fields(
            attrs,
            user=request.user,
            method=request.method,
        )

    def validate_items(self, value):
        validate_material_request_items(value)
        return value

    def create(self, validated_data):
        request = self.context["request"]
        user = request.user
        items_data = validated_data.pop("items", [])
        requester_name = str(validated_data.pop("requester_name", "")).strip()
        requester_department = str(validated_data.pop("requester_department", "")).strip()
        return create_material_request_draft(
            user=user,
            notes=validated_data.get("notes", ""),
            items_data=items_data,
            requester_name=requester_name,
            requester_department=requester_department,
        )

    def update(self, instance, validated_data):
        items_data = validated_data.pop("items", None)
        return update_material_request_draft(
            instance,
            notes=validated_data.get("notes", instance.notes),
            items_data=items_data,
        )
