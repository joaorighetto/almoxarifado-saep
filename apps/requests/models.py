"""Modelos de domínio para registro de saídas de materiais."""

from django.conf import settings
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


class MaterialRequest(AuditedModel):
    """Solicitação de materiais com fluxo de aprovação e atendimento."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Rascunho"
        SUBMITTED = "submitted", "Enviada"
        APPROVED = "approved", "Aprovada"
        REJECTED = "rejected", "Rejeitada"
        FULFILLED = "fulfilled", "Atendida"
        CANCELED = "canceled", "Cancelada"

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="material_requests",
    )
    requester_name = models.CharField(max_length=160, blank=True, default="")
    requester_department = models.CharField(max_length=120, blank=True, default="")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    notes = models.TextField(blank=True, default="")

    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_material_requests",
    )
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="rejected_material_requests",
    )
    rejection_reason = models.CharField(max_length=300, blank=True, default="")
    fulfilled_at = models.DateTimeField(null=True, blank=True)
    fulfilled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="fulfilled_material_requests",
    )
    issue = models.ForeignKey(
        IssueRequest,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="material_requests",
    )
    canceled_at = models.DateTimeField(null=True, blank=True)
    canceled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="canceled_material_requests",
    )
    cancellation_reason = models.CharField(max_length=300, blank=True, default="")

    def __str__(self) -> str:
        return f"Solicitação {self.id} - {self.get_status_display()}"

    def clean(self):
        """Valida consistência mínima entre status e metadados de workflow."""
        super().clean()

        if self.status == self.Status.SUBMITTED and not self.submitted_at:
            raise ValidationError({"submitted_at": "Solicitação enviada precisa de data de envio."})

        if self.status == self.Status.APPROVED:
            if not self.approved_by:
                raise ValidationError({"approved_by": "Solicitação aprovada precisa de aprovador."})
            if not self.approved_at:
                raise ValidationError({"approved_at": "Solicitação aprovada precisa de data de aprovação."})

        if self.status == self.Status.REJECTED:
            if not self.rejected_by:
                raise ValidationError({"rejected_by": "Solicitação rejeitada precisa de responsável."})
            if not self.rejected_at:
                raise ValidationError({"rejected_at": "Solicitação rejeitada precisa de data de rejeição."})
            if not self.rejection_reason.strip():
                raise ValidationError(
                    {"rejection_reason": "Motivo da rejeição é obrigatório."}
                )

        if self.status == self.Status.FULFILLED:
            if not self.fulfilled_by:
                raise ValidationError({"fulfilled_by": "Solicitação atendida precisa de responsável."})
            if not self.fulfilled_at:
                raise ValidationError({"fulfilled_at": "Solicitação atendida precisa de data de atendimento."})
            if not self.issue_id:
                raise ValidationError({"issue": "Solicitação atendida precisa estar vinculada a uma saída."})

        if self.status == self.Status.CANCELED:
            if not self.canceled_by:
                raise ValidationError({"canceled_by": "Solicitação cancelada precisa de responsável."})
            if not self.canceled_at:
                raise ValidationError({"canceled_at": "Solicitação cancelada precisa de data de cancelamento."})
            if not self.cancellation_reason.strip():
                raise ValidationError(
                    {"cancellation_reason": "Motivo do cancelamento é obrigatório."}
                )

    def save(self, *args, **kwargs):
        """Executa validação de modelo antes de persistir."""
        self.full_clean()
        return super().save(*args, **kwargs)


class MaterialRequestItem(AuditedModel):
    """Item de material solicitado em uma solicitação."""

    material_request = models.ForeignKey(
        MaterialRequest,
        on_delete=models.CASCADE,
        related_name="items",
    )
    material = models.ForeignKey(Material, on_delete=models.PROTECT)
    requested_quantity = models.DecimalField(max_digits=14, decimal_places=3)
    notes = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["material_request", "material"],
                name="uq_material_request_item_material",
            )
        ]

    def __str__(self) -> str:
        return f"{self.material_request_id} {self.material.sku} {self.requested_quantity}"

    def clean(self):
        """Impede solicitação com quantidade zero/negativa."""
        super().clean()
        if self.requested_quantity is None or self.requested_quantity <= 0:
            raise ValidationError({"requested_quantity": "Quantidade deve ser maior que zero."})

    def save(self, *args, **kwargs):
        """Executa validação de modelo antes de persistir."""
        self.full_clean()
        return super().save(*args, **kwargs)


class MaterialRequestEvent(AuditedModel):
    """Histórico de eventos relevantes da solicitação."""

    class EventType(models.TextChoices):
        CREATED = "created", "Criada"
        SUBMITTED = "submitted", "Enviada"
        APPROVED = "approved", "Aprovada"
        REJECTED = "rejected", "Rejeitada"
        FULFILLED = "fulfilled", "Atendida"
        CANCELED = "canceled", "Cancelada"

    material_request = models.ForeignKey(
        MaterialRequest,
        on_delete=models.CASCADE,
        related_name="events",
    )
    event_type = models.CharField(max_length=20, choices=EventType.choices, db_index=True)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="material_request_events",
    )
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ("created_at", "id")

    def __str__(self) -> str:
        return f"{self.material_request_id} {self.event_type}"


class RequestNotification(AuditedModel):
    """Notificação interna para ações do fluxo de solicitações."""

    class Category(models.TextChoices):
        ACTION_REQUIRED = "action_required", "Ação necessária"
        STATUS_UPDATE = "status_update", "Atualização de status"
        INFO = "info", "Informação"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="request_notifications",
    )
    material_request = models.ForeignKey(
        MaterialRequest,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.INFO)
    title = models.CharField(max_length=180)
    message = models.TextField(blank=True, default="")
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at", "-id")

    def __str__(self) -> str:
        return f"{self.user_id} {self.title}"
