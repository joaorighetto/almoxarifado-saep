"""Configurações do Django Admin para o app de saídas."""

from django.contrib import admin

from .models import (
    IssueItem,
    IssueRequest,
    MaterialRequest,
    MaterialRequestEvent,
    MaterialRequestItem,
    RequestNotification,
)


class IssueItemInline(admin.TabularInline):
    """Itens exibidos em linha dentro do admin da saída."""

    model = IssueItem
    extra = 1


@admin.register(IssueRequest)
class IssueRequestAdmin(admin.ModelAdmin):
    """Admin de saídas com inlines e filtros de busca."""

    list_display = ("id", "issued_at", "requested_by_name", "destination", "document_ref")
    search_fields = ("requested_by_name", "destination", "document_ref")
    inlines = [IssueItemInline]


class MaterialRequestItemInline(admin.TabularInline):
    """Itens exibidos em linha dentro do admin da solicitação."""

    model = MaterialRequestItem
    extra = 1


@admin.register(MaterialRequest)
class MaterialRequestAdmin(admin.ModelAdmin):
    """Admin de solicitações com status e aprovadores."""

    list_display = ("id", "status", "requested_by", "requester_department", "submitted_at")
    list_filter = ("status", "requester_department")
    search_fields = ("requested_by__username", "requester_name", "requester_department")
    inlines = [MaterialRequestItemInline]


@admin.register(MaterialRequestEvent)
class MaterialRequestEventAdmin(admin.ModelAdmin):
    """Admin do histórico de eventos da solicitação."""

    list_display = ("id", "material_request", "event_type", "performed_by", "created_at")
    list_filter = ("event_type",)
    search_fields = ("material_request__id", "performed_by__username", "notes")


@admin.register(RequestNotification)
class RequestNotificationAdmin(admin.ModelAdmin):
    """Admin das notificações internas do fluxo."""

    list_display = ("id", "user", "category", "title", "is_read", "created_at")
    list_filter = ("category", "is_read")
    search_fields = ("user__username", "title", "message")
