import csv
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.conf import settings
from pathlib import Path

from .forms import IssueRequestForm, IssueItemFormSet
from .models import IssueRequest
from .services import append_issue_to_xlsx



def issue_create(request):
    if request.method == "POST":
        form = IssueRequestForm(request.POST)
        formset = IssueItemFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            issue = form.save()
            formset.instance = issue
            formset.save()

            items = issue.items.select_related("material").all()
            xlsx_file = Path(settings.EXPORT_DIR) / settings.ISSUE_EXPORT_FILENAME
            append_issue_to_xlsx(issue, items, xlsx_file)

            return redirect(reverse("requests:issue_detail", args=[issue.id]))
    else:
        form = IssueRequestForm()
        formset = IssueItemFormSet()

    return render(request, "requests/issue_form.html", {"form": form, "formset": formset})


def issue_detail(request, pk: int):
    issue = IssueRequest.objects.prefetch_related("items__material").get(pk=pk)
    xlsx_file = str(Path(settings.EXPORT_DIR) / settings.ISSUE_EXPORT_FILENAME)
    return render(request, "requests/issue_detail.html", {"issue": issue, "xlsx_path": xlsx_file})


def issue_export_csv(request, pk: int):
    issue = IssueRequest.objects.prefetch_related("items__material").get(pk=pk)

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="saida_{issue.id}.csv"'

    writer = csv.writer(response)
    writer.writerow(["ISSUE_ID", "ISSUED_AT", "REQUESTED_BY", "DESTINATION", "DOCUMENT_REF", "SKU", "NAME", "UNIT", "QTY", "ITEM_NOTES"])

    for item in issue.items.all():
        m = item.material
        writer.writerow([
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
        ])

    return response
