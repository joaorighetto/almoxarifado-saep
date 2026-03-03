"""Views HTTP da aplicação de saídas de materiais.

Este módulo concentra:
- detalhamento de saídas;
- exportação CSV.
"""

import csv
from pathlib import Path

from django.conf import settings
from django.http import HttpResponse, HttpResponseNotAllowed
from django.shortcuts import render

from .models import IssueRequest
from .services import HEADERS


def issue_create(request):
    """Renderiza a página de criação de saída (envio é feito pela API REST)."""
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    return render(request, "requests/issue_form.html")


def issue_detail(request, pk: int):
    """Exibe o detalhe de uma saída específica."""
    issue = IssueRequest.objects.prefetch_related("items__material").get(pk=pk)
    xlsx_file = str(Path(settings.EXPORT_DIR) / settings.ISSUE_EXPORT_FILENAME)
    return render(request, "requests/issue_detail.html", {"issue": issue, "xlsx_path": xlsx_file})


def issue_export_csv(request, pk: int):
    """Exporta os itens de uma saída em formato CSV."""
    issue = IssueRequest.objects.prefetch_related("items__material").get(pk=pk)

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="saida_{issue.id}.csv"'

    writer = csv.writer(response)
    writer.writerow(HEADERS)

    for item in issue.items.all():
        m = item.material
        writer.writerow(
            [
                issue.id,
                issue.issued_at.isoformat(sep=" ", timespec="minutes"),
                issue.requested_by_name,
                issue.destination,
                issue.document_ref,
                m.sku,
                m.name,
                m.unit,
                str(item.quantity),
                item.notes,
            ]
        )

    return response
