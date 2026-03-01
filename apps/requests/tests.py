import unicodedata
from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from openpyxl import Workbook, load_workbook
from rest_framework.test import APIClient

from apps.inventory.models import Material, StockBalance
from apps.movements.models import Movement
from apps.requests.models import IssueItem, IssueRequest
from apps.requests.services import HEADERS

pytestmark = pytest.mark.django_db


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).lower()


def test_create_issue_request_via_api(tmp_path, settings):
    settings.EXPORT_DIR = tmp_path
    settings.GDRIVE_SYNC_ENABLED = False
    material = Material.objects.create(sku="M-001", name="Areia", unit="m3")
    StockBalance.objects.create(material=material, quantity="10.000")
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
    assert StockBalance.objects.get(material=material).quantity == Decimal("6.500")
    movement = Movement.objects.get(material=material)
    assert movement.movement_type == Movement.Type.OUT
    assert movement.quantity == Decimal("3.500")


def test_create_issue_request_via_api_rejects_when_stock_is_insufficient(tmp_path, settings):
    settings.EXPORT_DIR = tmp_path
    settings.GDRIVE_SYNC_ENABLED = False
    material = Material.objects.create(sku="M-002", name="Brita", unit="m3")
    StockBalance.objects.create(material=material, quantity="1.000")
    client = APIClient()

    payload = {
        "requested_by_name": "João",
        "destination": "Obra B",
        "document_ref": "REQ-02",
        "issued_at": (timezone.now() + timedelta(minutes=1)).isoformat(),
        "items": [
            {
                "material": material.id,
                "quantity": "3.000",
                "notes": "",
            }
        ],
    }

    response = client.post("/api/saidas/", payload, format="json")

    assert response.status_code == 400
    assert IssueRequest.objects.count() == 0
    assert StockBalance.objects.get(material=material).quantity == Decimal("1.000")
    assert Movement.objects.count() == 0


def test_issue_create_via_htmx_shows_stock_error_feedback(client, settings):
    settings.GDRIVE_SYNC_ENABLED = False
    material = Material.objects.create(sku="M-HTMX-001", name="Areia Fina", unit="m3")
    StockBalance.objects.create(material=material, quantity="1.000")

    payload = {
        "requested_by_name": "João",
        "destination": "Obra C",
        "notes": "",
        "items-TOTAL_FORMS": "1",
        "items-INITIAL_FORMS": "0",
        "items-MIN_NUM_FORMS": "0",
        "items-MAX_NUM_FORMS": "1000",
        "items-0-material": str(material.id),
        "items-0-material_display": f"{material.sku} - {material.name}",
        "items-0-quantity": "3.000",
        "items-0-notes": "",
    }

    response = client.post(
        reverse("requests:issue_create"),
        payload,
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 422
    content = response.content.decode("utf-8")
    assert "A saída ultrapassa o saldo disponível" in content
    assert "Saldo disponível: 1.000 m3. Solicitado: 3.000 m3." in content
    assert 'id="stock-validation-flag"' in content
    assert IssueRequest.objects.count() == 0
    assert StockBalance.objects.get(material=material).quantity == Decimal("1.000")
    assert Movement.objects.count() == 0


def test_issue_create_via_htmx_returns_form_partial_on_validation_error(client):
    payload = {
        "requested_by_name": "",
        "destination": "",
        "notes": "",
        "items-TOTAL_FORMS": "1",
        "items-INITIAL_FORMS": "0",
        "items-MIN_NUM_FORMS": "0",
        "items-MAX_NUM_FORMS": "1000",
        "items-0-material": "",
        "items-0-material_display": "",
        "items-0-quantity": "",
        "items-0-notes": "",
    }

    response = client.post(
        reverse("requests:issue_create"),
        payload,
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 422
    content = response.content.decode("utf-8")
    assert "Não foi possível salvar." in content
    assert "Solicitante" in content
    assert "Destino" in content


def test_material_search_filters_by_sku_and_name(client):
    Material.objects.create(sku="CIMENTO-001", name="Cimento", unit="sc")
    Material.objects.create(sku="AREIA-001", name="Areia Fina", unit="m3")
    Material.objects.create(sku="BRITA-001", name="Brita", unit="m3")

    response_by_sku = client.get(reverse("requests:material_search"), {"q": "AREIA"})
    assert response_by_sku.status_code == 200
    results_by_sku = response_by_sku.json()["results"]
    assert results_by_sku
    assert results_by_sku[0]["sku"] == "AREIA-001"

    response_by_name = client.get(reverse("requests:material_search"), {"q": "mento"})
    assert response_by_name.status_code == 200
    results_by_name = response_by_name.json()["results"]
    assert results_by_name
    assert results_by_name[0]["name"] == "Cimento"


def test_api_material_search_returns_paginated_results(client):
    Material.objects.create(sku="API-001", name="Cimento API", unit="sc")
    Material.objects.create(sku="API-002", name="Areia API", unit="m3")

    response = client.get("/api/materiais/search/", {"q": "API", "offset": 0, "limit": 1})
    assert response.status_code == 200

    payload = response.json()
    assert len(payload["results"]) == 1
    assert payload["has_more"] is True
    assert payload["results"][0]["sku"].startswith("API-")


def test_material_search_returns_fuzzy_matches_by_default(client):
    Material.objects.create(sku="CIMENTO-001", name="Cimento", unit="sc")
    Material.objects.create(sku="AREIA-001", name="Areia Fina", unit="m3")

    response = client.get(reverse("requests:material_search"), {"q": "cimnto"})
    assert response.status_code == 200

    results = response.json()["results"]
    assert results
    assert results[0]["name"] == "Cimento"


def test_material_search_matches_sku_without_punctuation(client):
    Material.objects.create(sku="000.000.001", name="Abracadeira", unit="un")
    Material.objects.create(sku="000.000.010", name="Outro Material", unit="un")

    response = client.get(reverse("requests:material_search"), {"q": "000000001"})
    assert response.status_code == 200

    results = response.json()["results"]
    assert results
    assert results[0]["sku"] == "000.000.001"


def test_material_search_supports_pagination_for_show_more(client):
    for i in range(1, 26):
        Material.objects.create(sku=f"MAT-{i:03d}", name=f"Material {i:03d}", unit="un")

    response_page_1 = client.get(
        reverse("requests:material_search"),
        {"q": "MAT", "offset": 0, "limit": 20},
    )
    assert response_page_1.status_code == 200
    payload_1 = response_page_1.json()
    assert len(payload_1["results"]) == 20
    assert payload_1["has_more"] is True

    response_page_2 = client.get(
        reverse("requests:material_search"),
        {"q": "MAT", "offset": 20, "limit": 20},
    )
    assert response_page_2.status_code == 200
    payload_2 = response_page_2.json()
    assert len(payload_2["results"]) == 5
    assert payload_2["has_more"] is False


def test_material_search_prioritizes_full_phrase_matches(client):
    Material.objects.create(
        sku="000.012.987",
        name="Papel A3 297 MM X 420 MM (500 FOLHAS)",
        unit="un",
    )
    Material.objects.create(
        sku="000.029.744",
        name="Toalha de Papel Interfolhada (PCT 800 FOLHAS)",
        unit="un",
    )
    Material.objects.create(sku="010.000.112", name="Papel Higiênico (4 RL)", unit="un")
    Material.objects.create(sku="010.000.113", name="Papel Higiênico Fino (4 RL)", unit="un")
    Material.objects.create(sku="010.000.114", name="Papel Toalha (WC) Branco, 2 Dobras", unit="un")

    response = client.get(reverse("requests:material_search"), {"q": "papel higienico"})
    assert response.status_code == 200

    results = response.json()["results"]
    assert results
    assert "higienico" in _normalize_text(results[0]["name"])
    assert any("higienico" in _normalize_text(item["name"]) for item in results[:2])


def test_material_search_prioritizes_items_covering_all_search_tokens(client):
    Material.objects.create(sku="001", name="Papel", unit="un")
    Material.objects.create(sku="002", name="Higienico", unit="un")
    Material.objects.create(sku="003", name="Papel Higiênico Folha Dupla", unit="un")
    Material.objects.create(sku="004", name="Toalha de Papel", unit="un")

    response = client.get(reverse("requests:material_search"), {"q": "papel higienico"})
    assert response.status_code == 200

    results = response.json()["results"]
    assert results
    assert results[0]["sku"] == "003"


def test_verify_issue_spreadsheet_reinserts_missing_rows_in_order(tmp_path):
    material_1 = Material.objects.create(sku="MAT-001", name="Material 1", unit="un")
    material_2 = Material.objects.create(sku="MAT-002", name="Material 2", unit="un")

    issue_1 = IssueRequest.objects.create(
        requested_by_name="Joao",
        destination="ETA 1",
        issued_at=timezone.now() - timedelta(hours=1),
    )
    issue_2 = IssueRequest.objects.create(
        requested_by_name="Maria",
        destination="ETA 2",
        issued_at=timezone.now(),
    )

    IssueItem.objects.create(issue=issue_1, material=material_1, quantity="2", notes="")
    item_2 = IssueItem.objects.create(issue=issue_2, material=material_2, quantity="3", notes="")

    xlsx_path = tmp_path / "controle_saidas.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "SAIDAS"
    ws.append(HEADERS)
    # Simula planilha com a linha do primeiro issue apagada manualmente.
    ws.append(
        [
            item_2.issue.id,
            item_2.issue.issued_at.strftime("%Y-%m-%d %H:%M"),
            item_2.issue.requested_by_name,
            item_2.issue.destination,
            item_2.issue.document_ref,
            item_2.material.sku,
            item_2.material.name,
            item_2.material.unit,
            float(item_2.quantity),
            item_2.notes,
        ]
    )
    wb.save(xlsx_path)

    call_command(
        "verify_issue_spreadsheet",
        "--path",
        str(xlsx_path),
        "--no-sync-drive",
    )

    repaired = load_workbook(xlsx_path, data_only=True)
    ws_repaired = repaired.active

    assert ws_repaired.max_row == 3  # header + 2 linhas do banco
    assert ws_repaired.cell(row=2, column=1).value == issue_1.id
    assert ws_repaired.cell(row=3, column=1).value == issue_2.id
