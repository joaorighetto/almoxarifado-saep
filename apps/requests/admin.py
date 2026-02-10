from django.contrib import admin
from .models import IssueRequest, IssueItem


class IssueItemInline(admin.TabularInline):
    model = IssueItem
    extra = 1


@admin.register(IssueRequest)
class IssueRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "issued_at", "requested_by_name", "destination", "document_ref")
    search_fields = ("requested_by_name", "destination", "document_ref")
    inlines = [IssueItemInline]
