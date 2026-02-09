import pytest
from apps.inventory.models import Material

pytestmark = pytest.mark.django_db

def test_create_material():
    m = Material.objects.create(sku="TEST-001", name="Material Teste", unit="un")
    assert m.pk is not None
    assert m.sku == "TEST-001"
