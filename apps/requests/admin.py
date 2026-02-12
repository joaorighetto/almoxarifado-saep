"""Configurações do Django Admin para o app de saídas."""

from django.contrib import admin

from .models import IssueItem, IssueRequest


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
