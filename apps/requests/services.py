from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Iterable

from openpyxl import Workbook, load_workbook

from .models import IssueRequest, IssueItem

HEADERS = [
    "ISSUE_ID",
    "ISSUED_AT",
    "REQUESTED_BY",
    "DESTINATION",
    "DOCUMENT_REF",
    "SKU",
    "NAME",
    "UNIT",
    "QTY",
    "ITEM_NOTES",
]


def _ensure_workbook(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        wb = load_workbook(path)
        ws = wb.active
        # Se estiver vazio (ou sem cabeçalho), cria cabeçalho
        if ws.max_row == 0 or (ws.max_row == 1 and ws["A1"].value is None):
            ws.append(HEADERS)
        return wb, ws

    wb = Workbook()
    ws = wb.active
    ws.title = "SAIDAS"
    ws.append(HEADERS)
    return wb, ws


def append_issue_to_xlsx(issue: IssueRequest, items: Iterable[IssueItem], xlsx_path: Path) -> None:
    wb, ws = _ensure_workbook(xlsx_path)

    # Append: 1 linha por item
    for item in items:
        m = item.material
        ws.append(
            [
                issue.id,
                issue.issued_at.strftime("%Y-%m-%d %H:%M"),
                issue.requested_by_name,
                issue.destination,
                issue.document_ref,
                m.sku,
                m.name,
                m.unit,
                float(item.quantity),  # Excel-friendly
                item.notes,
            ]
        )

    # Escrita mais segura: salva em arquivo temporário e substitui
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx", dir=str(xlsx_path.parent)) as tmp:
        tmp_path = Path(tmp.name)

    wb.save(tmp_path)
    os.replace(tmp_path, xlsx_path)
