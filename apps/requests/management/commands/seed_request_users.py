"""Provisiona usuários base para fluxo de solicitações de materiais."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

from apps.accounts.models import Profile


class Command(BaseCommand):
    help = (
        "Cria/atualiza usuários padrão de solicitação de materiais "
        "(solicitante, chefe de seção e almoxarifado)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--department", default="ETA Centro", help="Departamento padrão.")

        parser.add_argument("--solicitante-username", default="solicitante")
        parser.add_argument("--solicitante-password", default="solicitante123")

        parser.add_argument("--chefe-username", default="chefe_secao")
        parser.add_argument("--chefe-password", default="chefe123")

        parser.add_argument("--almox-username", default="almoxarifado")
        parser.add_argument("--almox-password", default="almox123")

    def handle(self, *args, **options):
        department = str(options["department"]).strip() or "ETA Centro"
        user_model = get_user_model()

        chief_group, _ = Group.objects.get_or_create(name="chefe_secao")
        warehouse_group, _ = Group.objects.get_or_create(name="almoxarifado")

        requester = self._upsert_user(
            user_model=user_model,
            username=options["solicitante_username"],
            raw_password=options["solicitante_password"],
            department=department,
            group_names=[],
        )

        chief = self._upsert_user(
            user_model=user_model,
            username=options["chefe_username"],
            raw_password=options["chefe_password"],
            department=department,
            group_names=[chief_group.name],
        )

        warehouse = self._upsert_user(
            user_model=user_model,
            username=options["almox_username"],
            raw_password=options["almox_password"],
            department="ALMOXARIFADO",
            group_names=[warehouse_group.name],
        )

        self.stdout.write(self.style.SUCCESS("Usuários provisionados com sucesso:"))
        self.stdout.write(f"- solicitante: {requester.username} / {options['solicitante_password']}")
        self.stdout.write(f"- chefe_secao: {chief.username} / {options['chefe_password']}")
        self.stdout.write(f"- almoxarifado: {warehouse.username} / {options['almox_password']}")

    def _upsert_user(self, user_model, username: str, raw_password: str, department: str, group_names: list[str]):
        username = str(username).strip()
        if not username:
            raise ValueError("Username não pode ser vazio.")

        user, _created = user_model.objects.get_or_create(
            username=username,
            defaults={"is_active": True},
        )
        user.is_active = True
        user.set_password(raw_password)
        user.save(update_fields=["is_active", "password"])

        Profile.objects.update_or_create(
            user=user,
            defaults={"department": department},
        )

        user.groups.clear()
        if group_names:
            groups = list(Group.objects.filter(name__in=group_names))
            user.groups.add(*groups)
        return user
