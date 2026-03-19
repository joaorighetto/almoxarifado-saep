"""Views HTML do fluxo de solicitações e saídas de materiais."""

import csv

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.accounts.models import (
    user_department,
    user_is_section_chief,
    user_is_warehouse,
)

from .models import MaterialRequest, RequestNotification
from .services import (
    HEADERS,
    can_edit_material_request,
    can_view_material_request,
    chief_material_request_history_for_user,
    chief_pending_material_requests_for_user,
    issue_csv_rows,
    issue_detail_context,
    issue_detail_queryset,
    issue_ordered_queryset,
    material_request_detail_queryset,
    material_request_form_context,
    material_requests_visible_to_user,
    request_notifications_for_user,
    warehouse_approved_material_requests_for_user,
    warehouse_material_request_history,
)


def _require_get(request):
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    return None


def issue_create(request):
    """Renderiza a página de criação de saída (envio é feito pela API REST)."""
    method_not_allowed = _require_get(request)
    if method_not_allowed:
        return method_not_allowed
    return render(request, "requests/issue_form.html")


def issue_detail(request, pk: int):
    """Exibe o detalhe de uma saída específica."""
    issue = get_object_or_404(issue_detail_queryset(), pk=pk)
    return render(request, "requests/issue_detail.html", issue_detail_context(issue))


def issue_export_csv(request, pk: int):
    """Exporta os itens de uma saída em formato CSV."""
    issue = get_object_or_404(issue_detail_queryset(), pk=pk)

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="saida_{issue.id}.csv"'

    writer = csv.writer(response)
    writer.writerow(HEADERS)
    for row in issue_csv_rows(issue):
        writer.writerow(row)

    return response


@login_required
def material_request_create(request):
    """Renderiza a página de criação de solicitação de materiais via API REST."""
    method_not_allowed = _require_get(request)
    if method_not_allowed:
        return method_not_allowed
    return render(
        request,
        "requests/material_request_form.html",
        material_request_form_context(request.user),
    )


@login_required
def material_request_edit(request, pk: int):
    """Renderiza a página de edição de solicitação em rascunho."""
    method_not_allowed = _require_get(request)
    if method_not_allowed:
        return method_not_allowed

    material_request = get_object_or_404(
        MaterialRequest.objects.prefetch_related("items__material"),
        pk=pk,
        requested_by=request.user,
    )
    if not can_edit_material_request(request.user, material_request):
        raise PermissionDenied("Somente solicitações em rascunho podem ser editadas.")
    return render(
        request,
        "requests/material_request_form.html",
        material_request_form_context(request.user, material_request),
    )


@login_required
def material_request_list(request):
    """Exibe solicitações criadas pelo usuário autenticado."""
    return render(
        request,
        "requests/material_request_list.html",
        {"material_requests": material_requests_visible_to_user(request.user)},
    )


@login_required
def chief_pending_approvals(request):
    """Exibe solicitações pendentes para aprovação da seção do chefe."""
    if not user_is_section_chief(request.user):
        raise PermissionDenied("Apenas chefe de seção pode acessar esta página.")

    department = user_department(request.user)
    return render(
        request,
        "requests/chief_pending_approvals.html",
        {
            "pending_requests": chief_pending_material_requests_for_user(request.user),
            "department": department,
        },
    )


@login_required
def chief_request_history(request):
    """Histórico de solicitações da seção do chefe."""
    if not user_is_section_chief(request.user):
        raise PermissionDenied("Apenas chefe de seção pode acessar esta página.")

    department = user_department(request.user)
    return render(
        request,
        "requests/chief_request_history.html",
        {
            "related_requests": chief_material_request_history_for_user(request.user),
            "department": department,
        },
    )


@login_required
def warehouse_approved_queue(request):
    """Exibe solicitações aprovadas para atendimento do almoxarifado."""
    if not user_is_warehouse(request.user):
        raise PermissionDenied("Apenas almoxarifado pode acessar esta página.")

    return render(
        request,
        "requests/warehouse_approved_queue.html",
        {"approved_requests": warehouse_approved_material_requests_for_user(request.user)},
    )


@login_required
def issue_list(request):
    """Exibe histórico de saídas para o almoxarifado."""
    if not user_is_warehouse(request.user):
        raise PermissionDenied("Apenas almoxarifado pode acessar esta página.")

    return render(request, "requests/issue_list.html", {"issues": issue_ordered_queryset()})


@login_required
def warehouse_request_history(request):
    """Histórico de solicitações relacionadas ao almoxarifado."""
    if not user_is_warehouse(request.user):
        raise PermissionDenied("Apenas almoxarifado pode acessar esta página.")

    return render(
        request,
        "requests/warehouse_request_history.html",
        {"related_requests": warehouse_material_request_history()},
    )


@login_required
def material_request_detail(request, pk: int):
    """Exibe detalhes de solicitação e timeline de eventos."""
    material_request = get_object_or_404(
        material_request_detail_queryset(),
        pk=pk,
    )
    if not can_view_material_request(request.user, material_request):
        raise PermissionDenied("Você não tem permissão para visualizar esta solicitação.")

    return render(
        request,
        "requests/material_request_detail.html",
        {"material_request": material_request},
    )


@login_required
def notifications_list(request):
    """Lista notificações do usuário e permite marcar como lida."""
    if request.method == "POST":
        if request.POST.get("mark_all") == "1":
            RequestNotification.objects.filter(user=request.user, is_read=False).update(
                is_read=True,
                read_at=timezone.now(),
            )
            return redirect("requests:notifications_list")

        notification_id = request.POST.get("notification_id")
        notification = get_object_or_404(RequestNotification, pk=notification_id, user=request.user)
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = timezone.now()
            notification.save(update_fields=["is_read", "read_at", "updated_at"])
        return redirect("requests:notifications_list")

    return render(
        request,
        "requests/notifications_list.html",
        {"notifications": request_notifications_for_user(request.user)},
    )
