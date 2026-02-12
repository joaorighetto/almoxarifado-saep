"""Modelos de inventário: materiais, lotes, localizações e saldos."""

from django.db import models

from apps.core.models import AuditedModel
from apps.suppliers.models import Supplier


class Location(AuditedModel):
    """Endereço físico de armazenagem dentro do almoxarifado."""

    code = models.CharField(max_length=50, unique=True)  # ex: A-01-02
    description = models.CharField(max_length=200, blank=True, default="")

    def __str__(self) -> str:
        return self.code


class Material(AuditedModel):
    """Cadastro mestre de material consumido/estocado."""

    sku = models.CharField(max_length=60, unique=True)  # código interno/SCPI, etc.
    name = models.CharField(max_length=255)
    unit = models.CharField(max_length=10)  # un, m, kg, l etc.
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)

    notes = models.TextField(blank=True, default="")

    def __str__(self) -> str:
        return f"{self.sku} - {self.name}"


class StockLot(AuditedModel):
    """Lote de entrada de material para rastreabilidade de origem."""

    material = models.ForeignKey(Material, on_delete=models.PROTECT)
    supplier = models.ForeignKey(Supplier, null=True, blank=True, on_delete=models.SET_NULL)
    location = models.ForeignKey(Location, null=True, blank=True, on_delete=models.SET_NULL)

    document_ref = models.CharField(max_length=120, blank=True, default="")  # NF-e / empenho / etc.
    received_at = models.DateField(null=True, blank=True)

    def __str__(self) -> str:
        return f"Lot({self.material.sku})"


class StockBalance(AuditedModel):
    """Saldo consolidado atual por material."""

    material = models.OneToOneField(Material, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=14, decimal_places=3, default=0)

    def __str__(self) -> str:
        return f"{self.material.sku}: {self.quantity}"
