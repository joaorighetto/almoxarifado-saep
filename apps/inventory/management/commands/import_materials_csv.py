"""Comando para carga de materiais e saldos a partir do CSV de posicao de estoque."""

import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.inventory.models import Material, StockBalance


class Command(BaseCommand):
    help = (
        "Importa Material e StockBalance a partir de CSV com colunas "
        "CADPRO, DISC1, UNID1 e QUAN3."
    )

    def add_arguments(self, parser):
        """Define argumentos de execução do comando."""
        parser.add_argument("csv_path", type=str, help="Caminho do CSV.")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Executa validação sem persistir alterações no banco.",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help=(
                "Reset seguro: zera StockBalance e desativa todos os materiais antes de importar "
                "(sem apagar Material referenciado por historico)."
            ),
        )

    def handle(self, *args, **options):
        """Executa importação de materiais e de saldos de estoque."""
        csv_path = Path(options["csv_path"]).expanduser()
        dry_run = options["dry_run"]
        reset = options["reset"]

        if not csv_path.exists() or not csv_path.is_file():
            raise CommandError(f"Arquivo não encontrado: {csv_path}")

        created_material = 0
        updated_material = 0
        created_balance = 0
        updated_balance = 0

        with transaction.atomic():
            if reset:
                StockBalance.objects.all().delete()
                Material.objects.all().update(is_active=False)

            with csv_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
                reader = csv.DictReader(csv_file, delimiter=";")
                required_cols = {"CADPRO", "DISC1", "UNID1", "QUAN3"}
                fieldnames = set(reader.fieldnames or [])
                missing = sorted(required_cols - fieldnames)
                if missing:
                    raise CommandError(f"CSV sem colunas obrigatórias: {', '.join(missing)}")

                for line_no, row in enumerate(reader, start=2):
                    sku = (row.get("CADPRO") or "").strip()
                    if not sku:
                        self.stdout.write(
                            self.style.WARNING(f"Linha {line_no}: CADPRO vazio, ignorada.")
                        )
                        continue

                    name = (row.get("DISC1") or "").strip()
                    unit = (row.get("UNID1") or "").strip()
                    if not name or not unit:
                        self.stdout.write(
                            self.style.WARNING(
                                f"Linha {line_no}: sem DISC1/UNID1 preenchidos, ignorada."
                            )
                        )
                        continue

                    estoque = self._parse_decimal(row.get("QUAN3"), line_no)

                    material, was_created = Material.objects.update_or_create(
                        sku=sku,
                        defaults={
                            "name": name[:255],
                            "unit": unit[:10],
                            "description": "",
                            "is_active": True,
                        },
                    )
                    if was_created:
                        created_material += 1
                    else:
                        updated_material += 1

                    balance, balance_created = StockBalance.objects.get_or_create(
                        material=material,
                        defaults={"quantity": estoque},
                    )
                    if balance_created:
                        created_balance += 1
                    else:
                        if balance.quantity != estoque:
                            balance.quantity = estoque
                            balance.save(update_fields=["quantity", "updated_at"])
                            updated_balance += 1

            if dry_run:
                transaction.set_rollback(True)

        mode = "DRY-RUN" if dry_run else "IMPORT"
        self.stdout.write(
            self.style.SUCCESS(
                f"[{mode}] materiais criados={created_material}, atualizados={updated_material}; "
                f"saldos criados={created_balance}, atualizados={updated_balance}"
            )
        )

    def _parse_decimal(self, value, line_no):
        """Converte números no formato local (vírgula decimal) para Decimal."""
        text = (value or "").strip()
        if not text:
            return Decimal("0")

        normalized = text.replace(".", "").replace(",", ".")
        try:
            return Decimal(normalized)
        except InvalidOperation as exc:
            raise CommandError(f"Linha {line_no}: valor invalido em QUAN3: '{text}'.") from exc
