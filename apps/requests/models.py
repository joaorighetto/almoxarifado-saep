from django.db import models

from apps.core.models import AuditedModel
from apps.inventory.models import Material


class IssueRequest(AuditedModel):
    requested_by_name = models.CharField(max_length=160)  # nome de quem retirou/solicitou
    destination = models.CharField(max_length=160, blank=True, default="")  # setor/equipe/obra
    document_ref = models.CharField(max_length=120, blank=True, default="")  # OS, requisição, etc.
    issued_at = models.DateTimeField()  # data/hora da retirada
    notes = models.TextField(blank=True, default="")

    def __str__(self) -> str:
        return f"Saída {self.id} - {self.issued_at:%Y-%m-%d %H:%M}"


class IssueItem(AuditedModel):
    issue = models.ForeignKey(IssueRequest, on_delete=models.CASCADE, related_name="items")
    material = models.ForeignKey(Material, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    notes = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        unique_together = [("issue", "material")]

    def __str__(self) -> str:
        return f"{self.issue_id} {self.material.sku} {self.quantity}"
