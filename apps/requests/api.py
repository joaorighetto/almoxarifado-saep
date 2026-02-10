from pathlib import Path

from django.conf import settings
from django.db import transaction
from rest_framework import serializers, viewsets

from .models import IssueItem, IssueRequest
from .services import append_issue_to_xlsx


class IssueItemSerializer(serializers.ModelSerializer):
    material_sku = serializers.CharField(source="material.sku", read_only=True)
    material_name = serializers.CharField(source="material.name", read_only=True)
    unit = serializers.CharField(source="material.unit", read_only=True)

    class Meta:
        model = IssueItem
        fields = ["id", "material", "material_sku", "material_name", "unit", "quantity", "notes"]


class IssueRequestSerializer(serializers.ModelSerializer):
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

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop("items", [])
        issue = IssueRequest.objects.create(**validated_data)
        IssueItem.objects.bulk_create([IssueItem(issue=issue, **item_data) for item_data in items_data])
        return issue


class IssueRequestViewSet(viewsets.ModelViewSet):
    queryset = IssueRequest.objects.prefetch_related("items__material").order_by("-issued_at", "-id")
    serializer_class = IssueRequestSerializer

    def perform_create(self, serializer):
        issue = serializer.save()
        xlsx_file = Path(settings.EXPORT_DIR) / settings.ISSUE_EXPORT_FILENAME
        append_issue_to_xlsx(issue, issue.items.select_related("material").all(), xlsx_file)
