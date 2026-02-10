from datetime import timedelta

import pytest
from django.utils import timezone
from django.urls import reverse
from rest_framework.test import APIClient

from apps.inventory.models import Material
from apps.requests.models import IssueRequest


pytestmark = pytest.mark.django_db


def test_create_issue_request_via_api():
    material = Material.objects.create(sku="M-001", name="Areia", unit="m3")
    client = APIClient()

    payload = {
        "requested_by_name": "João",
        "destination": "Obra A",
        "document_ref": "REQ-01",
        "issued_at": (timezone.now() + timedelta(minutes=1)).isoformat(),
        "notes": "urgente",
        "items": [
            {
                "material": material.id,
                "quantity": "3.500",
                "notes": "frente",
            }
        ],
    }

    response = client.post("/api/saidas/", payload, format="json")

    assert response.status_code == 201
    issue = IssueRequest.objects.get(pk=response.data["id"])
    assert issue.items.count() == 1
    assert issue.items.first().material_id == material.id


def test_material_search_filters_by_sku_and_name(client):
    Material.objects.create(sku="CIMENTO-001", name="Cimento", unit="sc")
    Material.objects.create(sku="AREIA-001", name="Areia Fina", unit="m3")
    Material.objects.create(sku="BRITA-001", name="Brita", unit="m3")

    response_by_sku = client.get(reverse("requests:material_search"), {"q": "AREIA"})
    assert response_by_sku.status_code == 200
    results_by_sku = response_by_sku.json()["results"]
    assert len(results_by_sku) == 1
    assert results_by_sku[0]["sku"] == "AREIA-001"

    response_by_name = client.get(reverse("requests:material_search"), {"q": "mento"})
    assert response_by_name.status_code == 200
    results_by_name = response_by_name.json()["results"]
    assert len(results_by_name) == 1
    assert results_by_name[0]["name"] == "Cimento"
