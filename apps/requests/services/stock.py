"""Serviços de estoque para processar saídas de materiais."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from decimal import Decimal

from apps.inventory.models import StockBalance
from apps.movements.models import Movement


class StockValidationError(Exception):
    """Erro de domínio para saldo insuficiente na saída."""

    def __init__(self, messages: list[str], details: list[dict] | None = None):
        self.messages = messages
        self.details = details or []
        super().__init__("; ".join(messages))


def consume_stock_for_issue(issue, items: Iterable) -> None:
    """Valida e aplica baixa de estoque para os itens de uma saída."""
    issue_items = list(items)
    if not issue_items:
        return

    required_by_material = defaultdict(lambda: Decimal("0"))
    material_by_id = {}

    for item in issue_items:
        quantity = item.quantity or Decimal("0")
        if quantity <= 0:
            continue
        required_by_material[item.material_id] += quantity
        material_by_id[item.material_id] = item.material

    if not required_by_material:
        return

    balances = {
        balance.material_id: balance
        for balance in StockBalance.objects.select_for_update()
        .select_related("material")
        .filter(material_id__in=required_by_material.keys())
    }

    errors = []
    error_details: list[dict] = []
    for material_id, required in required_by_material.items():
        balance = balances.get(material_id)
        available = balance.quantity if balance else Decimal("0")
        if available < required:
            material = material_by_id[material_id]
            errors.append(
                f"{material.sku} - {material.name}: disponível {available} {material.unit}, "
                f"solicitado {required} {material.unit}."
            )
            error_details.append(
                {
                    "material_id": material_id,
                    "sku": material.sku,
                    "name": material.name,
                    "available": available,
                    "required": required,
                    "unit": material.unit,
                }
            )

    if errors:
        raise StockValidationError(errors, details=error_details)

    for material_id, required in required_by_material.items():
        balance = balances[material_id]
        balance.quantity = balance.quantity - required
        balance.save(update_fields=["quantity", "updated_at"])

    Movement.objects.bulk_create(
        [
            Movement(
                movement_type=Movement.Type.OUT,
                material=item.material,
                quantity=item.quantity,
                document_ref=issue.document_ref,
                notes=item.notes,
                occurred_at=issue.issued_at,
            )
            for item in issue_items
            if item.quantity and item.quantity > 0
        ]
    )
