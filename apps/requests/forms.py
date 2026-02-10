from django import forms
from django.forms import inlineformset_factory

from .models import IssueRequest, IssueItem


class IssueRequestForm(forms.ModelForm):
    issued_at = forms.DateTimeField(widget=forms.DateTimeInput(attrs={"type": "datetime-local"}))

    class Meta:
        model = IssueRequest
        fields = ["requested_by_name", "destination", "document_ref", "issued_at", "notes"]


class IssueItemForm(forms.ModelForm):
    class Meta:
        model = IssueItem
        fields = ["material", "quantity", "notes"]


IssueItemFormSet = inlineformset_factory(
    IssueRequest,
    IssueItem,
    form=IssueItemForm,
    extra=1,
    can_delete=True,
)
