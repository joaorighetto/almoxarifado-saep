from django import forms
from django.forms import inlineformset_factory

from .models import IssueRequest, IssueItem


class IssueRequestForm(forms.ModelForm):
    issued_at = forms.DateTimeField(widget=forms.DateTimeInput(attrs={"type": "datetime-local"}))

    class Meta:
        model = IssueRequest
        fields = ["requested_by_name", "destination", "document_ref", "issued_at", "notes"]


class IssueItemForm(forms.ModelForm):
    material_display = forms.CharField(label="Material", required=False)

    class Meta:
        model = IssueItem
        fields = ["material", "material_display", "quantity", "notes"]
        widgets = {"material": forms.HiddenInput()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["material"].widget.attrs.update({"class": "material-id-field"})
        self.fields["material_display"].widget.attrs.update(
            {
                "class": "material-display-field",
                "autocomplete": "off",
                "placeholder": "Digite nome ou SKU",
            }
        )

        bound_material_display = self.data.get(self.add_prefix("material_display")) if self.is_bound else None
        if bound_material_display is not None:
            self.fields["material_display"].initial = bound_material_display
            return

        material = None
        if self.instance.pk and self.instance.material_id:
            material = self.instance.material
        elif self.initial.get("material"):
            material = self.fields["material"].queryset.filter(pk=self.initial["material"]).first()

        if material:
            self.fields["material_display"].initial = f"{material.sku} - {material.name}"


IssueItemFormSet = inlineformset_factory(
    IssueRequest,
    IssueItem,
    form=IssueItemForm,
    extra=1,
    can_delete=True,
)
