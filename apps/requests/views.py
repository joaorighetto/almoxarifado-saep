"""Views HTTP da aplicação de saídas de materiais.

Este módulo concentra:
- fluxo de criação e detalhamento de saídas;
- exportação CSV;
- endpoint web de busca de materiais.
"""

import csv
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from .forms import IssueItemFormSet, IssueRequestForm
from .material_search import search_materials
from .models import IssueRequest
from .services import append_issue_to_xlsx
from .stock import StockValidationError, consume_stock_for_issue


def _render_issue_form_response(
    request,
    form,
    formset,
    *,
    status: int = 200,
    stock_error: bool = False,
):
    """Renderiza resposta do formulário completo/parcial conforme tipo da requisição."""
    context = {"form": form, "formset": formset, "stock_error": stock_error}
    if request.headers.get("HX-Request") == "true":
        return render(
            request,
            "requests/partials/issue_form_inner.html",
            context,
            status=status,
        )
    return render(request, "requests/issue_form.html", context)


def _attach_stock_errors_to_formset(formset, exc: StockValidationError) -> None:
    """Anexa erro por item para destacar campo de quantidade no frontend."""
    details_by_material = {detail["material_id"]: detail for detail in exc.details}
    for form in formset.forms:
        if not hasattr(form, "cleaned_data"):
            continue
        if form.cleaned_data.get("DELETE"):
            continue

        material = form.cleaned_data.get("material")
        quantity = form.cleaned_data.get("quantity")
        if not material or quantity is None:
            continue

        detail = details_by_material.get(material.id)
        if not detail:
            continue

        available = detail["available"]
        required = detail["required"]
        unit = detail["unit"]
        form.add_error(
            "quantity",
            f"Saldo disponível: {available} {unit}. Solicitado: {required} {unit}.",
        )


def issue_create(request):
    """Renderiza e processa o formulário de criação de saída.

    Também atualiza a planilha mestre XLSX após salvar os itens.
    """
    if request.method == "POST":
        form = IssueRequestForm(request.POST)
        formset = IssueItemFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    issue = form.save()
                    formset.instance = issue
                    formset.save()

                    items = list(issue.items.select_related("material").all())
                    consume_stock_for_issue(issue, items)

                    xlsx_file = Path(settings.EXPORT_DIR) / settings.ISSUE_EXPORT_FILENAME
                    append_issue_to_xlsx(issue, items, xlsx_file)
            except StockValidationError as exc:
                formset._non_form_errors = formset.error_class(exc.messages)
                _attach_stock_errors_to_formset(formset, exc)
                return _render_issue_form_response(
                    request,
                    form,
                    formset,
                    status=422,
                    stock_error=True,
                )

            if request.headers.get("HX-Request") == "true":
                return render(request, "requests/partials/issue_created.html", {"issue": issue})

            return redirect(reverse("requests:issue_detail", args=[issue.id]))

        if request.headers.get("HX-Request") == "true":
            return _render_issue_form_response(request, form, formset, status=422)
    else:
        form = IssueRequestForm()
        formset = IssueItemFormSet()

    return render(request, "requests/issue_form.html", {"form": form, "formset": formset})


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
    writer.writerow(
        [
            "ID_SAIDA",
            "DATA_HORA",
            "SOLICITANTE",
            "DESTINO",
            "DOCUMENTO_REF",
            "SKU",
            "NOME",
            "UNIDADE",
            "QUANTIDADE",
            "OBS_ITEM",
        ]
    )

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


def material_search(request):
    """Busca materiais por SKU/nome com paginação e ranqueamento fuzzy."""
    query = request.GET.get("q", "").strip()
    materials, has_more = search_materials(
        query,
        offset_raw=request.GET.get("offset"),
        limit_raw=request.GET.get("limit"),
    )

    results = [
        {
            "id": material.id,
            "sku": material.sku,
            "name": material.name,
            "unit": material.unit,
            "label": f"{material.sku} - {material.name}",
        }
        for material in materials
    ]
    return JsonResponse({"results": results, "has_more": has_more})
