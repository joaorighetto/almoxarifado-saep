from decimal import Decimal

import pytest
from django.core.management import call_command

from apps.inventory.models import Material, StockBalance

pytestmark = pytest.mark.django_db


def test_import_materials_csv_creates_and_updates(tmp_path):
    csv_file = tmp_path / "materiais.csv"
    csv_file.write_text(
        "\n".join(
            [
                "CADPRO;DISC1;UNID1;QUAN3",
                "000;GERAL;;0",
                "000.000.001;ABRACADEIRA;UN;10,5",
                "000.000.002;ANEL;PC;",
            ]
        ),
        encoding="utf-8",
    )

    call_command("import_materials_csv", str(csv_file))

    m1 = Material.objects.get(sku="000.000.001")
    assert m1.name == "ABRACADEIRA"
    assert m1.unit == "UN"
    assert m1.description == ""
    assert StockBalance.objects.get(material=m1).quantity == Decimal("10.5")

    m2 = Material.objects.get(sku="000.000.002")
    assert m2.description == ""
    assert StockBalance.objects.get(material=m2).quantity == Decimal("0")
    assert not Material.objects.filter(sku="000").exists()

    csv_file.write_text(
        "\n".join(
            [
                "CADPRO;DISC1;UNID1;QUAN3",
                "000.000.001;ABRACADEIRA NOVA;UN;20,0",
            ]
        ),
        encoding="utf-8",
    )
    call_command("import_materials_csv", str(csv_file))

    m1.refresh_from_db()
    assert m1.name == "ABRACADEIRA NOVA"
    assert m1.description == ""
    assert StockBalance.objects.get(material=m1).quantity == Decimal("20.0")


def test_import_materials_csv_reset_deactivates_missing_materials(tmp_path):
    old = Material.objects.create(
        sku="OLD-001",
        name="Antigo",
        unit="UN",
        description="Item antigo",
        is_active=True,
    )
    StockBalance.objects.create(material=old, quantity=Decimal("7"))

    csv_file = tmp_path / "materiais_reset.csv"
    csv_file.write_text(
        "\n".join(
            [
                "CADPRO;DISC1;UNID1;QUAN3",
                "NEW-001;Novo;UN;3,0",
            ]
        ),
        encoding="utf-8",
    )

    call_command("import_materials_csv", str(csv_file), "--reset")

    old.refresh_from_db()
    assert old.is_active is False
    assert not StockBalance.objects.filter(material=old).exists()

    new = Material.objects.get(sku="NEW-001")
    assert new.is_active is True
    assert StockBalance.objects.get(material=new).quantity == Decimal("3.0")
