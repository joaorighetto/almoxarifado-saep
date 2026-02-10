from datetime import timedelta

import pytest
from django.utils import timezone
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
