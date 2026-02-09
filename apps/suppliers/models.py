from django.db import models

from apps.core.models import AuditedModel


class Supplier(AuditedModel):
    name = models.CharField(max_length=200)
    trade_name = models.CharField(max_length=200, blank=True, default="")
    document = models.CharField(max_length=30, blank=True, default="")  # CNPJ/CPF (sem validação agora)
    email = models.EmailField(blank=True, default="")
    phone = models.CharField(max_length=30, blank=True, default="")

    notes = models.TextField(blank=True, default="")

    def __str__(self) -> str:
        return self.trade_name or self.name
