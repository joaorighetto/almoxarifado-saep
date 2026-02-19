"""Views HTTP da aplicação de saídas de materiais.

Este módulo concentra:
- fluxo de criação e detalhamento de saídas;
- exportação CSV;
- endpoint de busca de materiais com paginação e fuzzy ranking.
"""

import csv
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from apps.inventory.models import Material

from .forms import IssueItemFormSet, IssueRequestForm
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
    offset = _parse_non_negative_int(request.GET.get("offset"), default=0)
    limit = _parse_non_negative_int(request.GET.get("limit"), default=20)
    if limit < 1:
        limit = 1
    limit = min(limit, 50)

    materials_qs = Material.objects.all().order_by("sku")

    if not query:
        materials = list(materials_qs[offset : offset + limit])
        has_more = materials_qs.count() > offset + len(materials)
    else:
        matched = _fuzzy_material_matches(query, materials_qs, limit=None)
        materials = matched[offset : offset + limit]
        has_more = len(matched) > offset + len(materials)

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


def _parse_non_negative_int(raw_value, default: int = 0) -> int:
    """Converte valor em inteiro não negativo, com fallback padrão."""
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return default
    return max(value, 0)


def _normalize_search_text(value: str) -> str:
    """Normaliza texto para comparação (casefold, sem acento e sem pontuação)."""
    normalized = unicodedata.normalize("NFKD", value or "")
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = normalized.lower()
    normalized = "".join(ch if (ch.isalnum() or ch.isspace()) else " " for ch in normalized)
    return " ".join(normalized.split()).strip()


def _compact_search_text(value: str) -> str:
    """Versão compacta para comparar textos sem espaços."""
    return "".join(_normalize_search_text(value).split())


def _fuzzy_material_matches(query: str, materials_qs, limit: int | None = 20):
    """Retorna materiais ranqueados por similaridade com prioridade para match exato."""
    needle = _normalize_search_text(query)
    if not needle:
        return []

    compact_needle = _compact_search_text(query)
    needle_tokens = needle.split()
    ranked = []
    for material in materials_qs.only("id", "sku", "name", "unit").iterator():
        sku = _normalize_search_text(material.sku)
        name = _normalize_search_text(material.name)
        label = f"{sku} {name}".strip()
        compact_sku = _compact_search_text(material.sku)
        compact_name = _compact_search_text(material.name)
        compact_label = _compact_search_text(label)

        base_ratio = max(
            SequenceMatcher(None, needle, sku).ratio(),
            SequenceMatcher(None, needle, name).ratio(),
            SequenceMatcher(None, needle, label).ratio(),
            SequenceMatcher(None, compact_needle, compact_sku).ratio(),
            SequenceMatcher(None, compact_needle, compact_name).ratio(),
            SequenceMatcher(None, compact_needle, compact_label).ratio(),
        )

        token_score = 0.0
        label_tokens = label.split()
        for token in label_tokens:
            token_score = max(token_score, SequenceMatcher(None, needle, token).ratio())

        partial_token_score = 0.0
        for n_token in needle_tokens:
            partial_token_score = max(
                partial_token_score, SequenceMatcher(None, n_token, sku).ratio()
            )
            partial_token_score = max(
                partial_token_score, SequenceMatcher(None, n_token, name).ratio()
            )
            for token in label_tokens:
                partial_token_score = max(
                    partial_token_score, SequenceMatcher(None, n_token, token).ratio()
                )

        score = max(base_ratio, token_score, partial_token_score)

        # Prioriza resultados que cobrem todos os termos da busca.
        all_tokens_in_name = bool(needle_tokens) and all(token in name for token in needle_tokens)
        all_tokens_in_label = bool(needle_tokens) and all(token in label for token in needle_tokens)
        phrase_in_name = needle in name
        phrase_in_label = needle in label
        compact_phrase_in_name = compact_needle and compact_needle in compact_name
        compact_phrase_in_label = compact_needle and compact_needle in compact_label

        if phrase_in_name:
            score = max(score, 1.4)
        elif phrase_in_label:
            score = max(score, 1.3)
        elif compact_phrase_in_name:
            score = max(score, 1.2)
        elif compact_phrase_in_label:
            score = max(score, 1.1)
        elif all_tokens_in_name:
            score = max(score, 1.05)
        elif all_tokens_in_label:
            score = max(score, 0.98)

        # Depois aplica prioridade para matches exatos/parciais simples.
        exact_match = needle == sku or needle == name
        contains_match = needle in sku or needle in name or needle in label
        startswith_match = (
            sku.startswith(needle) or name.startswith(needle) or label.startswith(needle)
        )
        token_contains_match = any(token in sku or token in name for token in needle_tokens)
        if exact_match:
            score = max(score, 1.2)
        elif contains_match:
            score = max(score, 1.0)
        elif startswith_match:
            score = max(score, 0.95)
        elif token_contains_match:
            score = max(score, 0.8)

        ranked.append((score, material.sku, material))

    ranked.sort(key=lambda item: (-item[0], item[1]))
    filtered = [item for item in ranked if item[0] >= 0.6]
    items = [item[2] for item in filtered]
    if limit is None:
        return items
    return items[:limit]
