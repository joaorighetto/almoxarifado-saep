"""Views HTTP da aplicação de saídas de materiais.

Este módulo concentra:
- detalhamento de saídas;
- exportação CSV.
"""

import csv
from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.accounts.models import Profile

from .models import IssueRequest, MaterialRequest, RequestNotification
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


@login_required
def material_request_create(request):
    """Renderiza a página de criação de solicitação de materiais via API REST."""
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    return render(request, "requests/material_request_form.html")


@login_required
def material_request_list(request):
    """Exibe solicitações criadas pelo usuário autenticado."""
    requests_qs = (
        MaterialRequest.objects.filter(requested_by=request.user)
        .prefetch_related("items__material")
        .order_by("-created_at", "-id")
    )
    return render(
        request, "requests/material_request_list.html", {"material_requests": requests_qs}
    )


@login_required
def chief_pending_approvals(request):
    """Exibe solicitações pendentes para aprovação da seção do chefe."""
    if not request.user.groups.filter(name="chefe_secao").exists():
        raise PermissionDenied("Apenas chefe de seção pode acessar esta página.")

    profile = Profile.objects.filter(user=request.user).only("department").first()
    department = (profile.department if profile else "").strip()
    pending_requests = (
        MaterialRequest.objects.filter(
            status=MaterialRequest.Status.SUBMITTED,
            requester_department=department,
        )
        .prefetch_related("items__material", "requested_by")
        .order_by("submitted_at", "id")
    )
    return render(
        request,
        "requests/chief_pending_approvals.html",
        {"pending_requests": pending_requests, "department": department},
    )


@login_required
def chief_request_history(request):
    """Histórico de solicitações da seção do chefe."""
    if not request.user.groups.filter(name="chefe_secao").exists():
        raise PermissionDenied("Apenas chefe de seção pode acessar esta página.")

    profile = Profile.objects.filter(user=request.user).only("department").first()
    department = (profile.department if profile else "").strip()
    related_requests = (
        MaterialRequest.objects.filter(requester_department=department)
        .select_related("requested_by", "approved_by", "rejected_by", "fulfilled_by", "issue")
        .prefetch_related("items__material")
        .order_by("-created_at", "-id")
    )
    return render(
        request,
        "requests/chief_request_history.html",
        {"related_requests": related_requests, "department": department},
    )


@login_required
def warehouse_approved_queue(request):
    """Exibe solicitações aprovadas para atendimento do almoxarifado."""
    if not request.user.groups.filter(name="almoxarifado").exists():
        raise PermissionDenied("Apenas almoxarifado pode acessar esta página.")

    approved_requests = (
        MaterialRequest.objects.filter(status=MaterialRequest.Status.APPROVED)
        .prefetch_related("items__material", "requested_by")
        .order_by("approved_at", "id")
    )
    return render(
        request,
        "requests/warehouse_approved_queue.html",
        {"approved_requests": approved_requests},
    )


@login_required
def issue_list(request):
    """Exibe histórico de saídas para o almoxarifado."""
    if not request.user.groups.filter(name="almoxarifado").exists():
        raise PermissionDenied("Apenas almoxarifado pode acessar esta página.")

    issues = IssueRequest.objects.prefetch_related("items__material").order_by("-issued_at", "-id")
    return render(request, "requests/issue_list.html", {"issues": issues})


@login_required
def warehouse_request_history(request):
    """Histórico de solicitações relacionadas ao almoxarifado."""
    if not request.user.groups.filter(name="almoxarifado").exists():
        raise PermissionDenied("Apenas almoxarifado pode acessar esta página.")

    related_requests = (
        MaterialRequest.objects.filter(
            status__in=[MaterialRequest.Status.APPROVED, MaterialRequest.Status.FULFILLED]
        )
        .select_related("requested_by", "approved_by", "rejected_by", "fulfilled_by", "issue")
        .prefetch_related("items__material")
        .order_by("-created_at", "-id")
    )
    return render(
        request,
        "requests/warehouse_request_history.html",
        {"related_requests": related_requests},
    )


def _can_view_material_request(user, material_request: MaterialRequest) -> bool:
    if material_request.requested_by_id == user.id:
        return True

    department = (material_request.requester_department or "").strip()
    profile = Profile.objects.filter(user=user).only("department").first()
    user_department = (profile.department if profile else "").strip()

    if (
        user.groups.filter(name="chefe_secao").exists()
        and department
        and department == user_department
    ):
        return True
    if user.groups.filter(name="almoxarifado").exists():
        return True
    return False


@login_required
def material_request_detail(request, pk: int):
    """Exibe detalhes de solicitação e timeline de eventos."""
    material_request = get_object_or_404(
        MaterialRequest.objects.select_related(
            "requested_by",
            "approved_by",
            "rejected_by",
            "fulfilled_by",
            "issue",
        ).prefetch_related("items__material", "events__performed_by"),
        pk=pk,
    )
    if not _can_view_material_request(request.user, material_request):
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

    notifications = (
        RequestNotification.objects.filter(user=request.user)
        .select_related("material_request")
        .order_by("is_read", "-created_at", "-id")
    )
    return render(
        request,
        "requests/notifications_list.html",
        {"notifications": notifications},
    )
