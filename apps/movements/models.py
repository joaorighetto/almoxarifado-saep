"""Modelos de movimentação de estoque (entrada/saída/ajuste)."""

from django.db import models

from apps.core.models import AuditedModel
from apps.inventory.models import Material, StockLot


class Movement(AuditedModel):
    """Evento de movimentação que altera estoque de um material."""

    class Type(models.TextChoices):
        """Tipos de movimentação suportados pelo domínio."""

        IN = "IN", "Entrada"
        OUT = "OUT", "Saída"
        ADJ = "ADJ", "Ajuste"

    movement_type = models.CharField(max_length=3, choices=Type.choices)
    material = models.ForeignKey(Material, on_delete=models.PROTECT)
    lot = models.ForeignKey(StockLot, null=True, blank=True, on_delete=models.SET_NULL)

    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    document_ref = models.CharField(max_length=120, blank=True, default="")
    notes = models.TextField(blank=True, default="")

    occurred_at = models.DateTimeField()

    def __str__(self) -> str:
        return f"{self.get_movement_type_display()} {self.material.sku} {self.quantity}"
