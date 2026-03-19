"""Modelos auxiliares de contas de usuário."""

from django.conf import settings
from django.db import models

from apps.core.models import AuditedModel

SECTION_CHIEF_GROUP = "chefe_secao"
WAREHOUSE_GROUP = "almoxarifado"


class Profile(AuditedModel):
    """Perfil complementar do usuário do sistema."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    department = models.CharField(max_length=120, blank=True, default="")
    phone = models.CharField(max_length=30, blank=True, default="")

    def __str__(self) -> str:
        return f"Profile({self.user})"

    @property
    def is_section_chief(self) -> bool:
        return user_is_section_chief(self.user)

    @property
    def is_warehouse(self) -> bool:
        return user_is_warehouse(self.user)


def get_user_profile(user):
    if not getattr(user, "is_authenticated", False):
        return None
    return Profile.objects.filter(user=user).only("department").first()


def user_department(user) -> str:
    profile = get_user_profile(user)
    return (profile.department if profile else "").strip()


def user_is_section_chief(user) -> bool:
    return bool(
        user
        and getattr(user, "is_authenticated", False)
        and user.groups.filter(name=SECTION_CHIEF_GROUP).exists()
    )


def user_is_warehouse(user) -> bool:
    return bool(
        user
        and getattr(user, "is_authenticated", False)
        and user.groups.filter(name=WAREHOUSE_GROUP).exists()
    )


def user_is_section_chief_for_department(user, department: str) -> bool:
    return bool(department) and user_is_section_chief(user) and user_department(user) == department
