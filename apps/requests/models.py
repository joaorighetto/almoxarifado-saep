"""Modelos de domínio para registro de saídas de materiais."""

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.models import AuditedModel
from apps.inventory.models import Material


class IssueRequest(AuditedModel):
    """Cabeçalho de uma retirada/saída de materiais."""

    requested_by_name = models.CharField(max_length=160)  # nome de quem retirou/solicitou
    destination = models.CharField(max_length=160, blank=True, default="")  # setor/equipe/obra
    document_ref = models.CharField(max_length=120, blank=True, default="")  # OS, requisição, etc.
    issued_at = models.DateTimeField(default=timezone.now)  # data/hora da retirada
    notes = models.TextField(blank=True, default="")

    def __str__(self) -> str:
        return f"Saída {self.id} - {self.issued_at:%Y-%m-%d %H:%M}"

    def clean(self):
        """Valida invariantes de domínio da saída."""
        super().clean()
        if not (self.destination or "").strip():
            raise ValidationError({"destination": "Destino é obrigatório."})

    def save(self, *args, **kwargs):
        """Executa validação de modelo antes de persistir."""
        self.full_clean()
        return super().save(*args, **kwargs)


class IssueItem(AuditedModel):
    """Item individual pertencente a uma saída."""

    issue = models.ForeignKey(IssueRequest, on_delete=models.CASCADE, related_name="items")
    material = models.ForeignKey(Material, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    notes = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        unique_together = [("issue", "material")]

    def __str__(self) -> str:
        return f"{self.issue_id} {self.material.sku} {self.quantity}"
