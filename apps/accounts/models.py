from django.conf import settings
from django.db import models

from apps.core.models import AuditedModel


class Profile(AuditedModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    department = models.CharField(max_length=120, blank=True, default="")
    phone = models.CharField(max_length=30, blank=True, default="")

    def __str__(self) -> str:
        return f"Profile({self.user})"
