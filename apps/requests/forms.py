"""Formulários da aplicação de saídas.

Inclui o formulário principal de retirada e o formset de itens.
"""

from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory

from .models import IssueItem, IssueRequest


class IssueRequestForm(forms.ModelForm):
    """Formulário principal de dados da saída."""

    class Meta:
        model = IssueRequest
        fields = ["requested_by_name", "destination", "notes"]
        labels = {
            "requested_by_name": "Solicitante",
            "destination": "Destino",
            "notes": "Observações",
        }
        error_messages = {
            "requested_by_name": {
                "required": "Informe o solicitante para continuar.",
            },
            "destination": {"required": "Informe o destino para continuar."},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["destination"].required = True
        for name, field in self.fields.items():
            css_class = "input-control"
            if name == "notes":
                field.widget.attrs.update({"rows": 3})
            field.widget.attrs.update({"class": css_class})


class IssueItemForm(forms.ModelForm):
    """Formulário de item da saída com campo de busca textual de material."""

    material_display = forms.CharField(label="Material", required=False)

    class Meta:
        model = IssueItem
        fields = ["material", "material_display", "quantity", "notes"]
        widgets = {"material": forms.HiddenInput()}
        labels = {
            "quantity": "Quantidade",
            "notes": "Observações",
        }
        error_messages = {
            "material": {"required": "Selecione um material válido da lista."},
            "quantity": {"required": "Informe a quantidade."},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["material"].widget.attrs.update({"class": "material-id-field"})
        self.fields["material_display"].widget.attrs.update(
            {
                "class": "input-control material-display-field",
                "autocomplete": "off",
                "placeholder": "Digite nome ou SKU",
                "size": 80,
            }
        )
        self.fields["quantity"].widget.attrs.update({"class": "input-control"})
        self.fields["notes"].widget.attrs.update({"class": "input-control"})

        bound_material_display = (
            self.data.get(self.add_prefix("material_display")) if self.is_bound else None
        )
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

    def clean(self):
        """Valida coerência entre campo de busca textual e FK de material."""
        cleaned_data = super().clean()
        if cleaned_data.get("DELETE"):
            return cleaned_data

        material = cleaned_data.get("material")
        material_display = (cleaned_data.get("material_display") or "").strip()
        quantity = cleaned_data.get("quantity")

        if not material and (material_display or quantity is not None):
            self.add_error("material_display", "Selecione um material válido da lista.")

        if quantity is not None and quantity <= 0:
            self.add_error("quantity", "A quantidade deve ser maior que zero.")

        return cleaned_data


class IssueItemFormSetBase(BaseInlineFormSet):
    """Garante que a saída tenha ao menos um item materializado."""

    def clean(self):
        super().clean()
        if any(self.errors):
            return

        has_valid_item = False
        for form in self.forms:
            if not hasattr(form, "cleaned_data"):
                continue
            if form.cleaned_data.get("DELETE"):
                continue
            material = form.cleaned_data.get("material")
            quantity = form.cleaned_data.get("quantity")
            if material and quantity is not None and quantity > 0:
                has_valid_item = True
                break

        if not has_valid_item:
            raise forms.ValidationError(
                "Adicione pelo menos um material com quantidade maior que zero."
            )


IssueItemFormSet = inlineformset_factory(
    IssueRequest,
    IssueItem,
    form=IssueItemForm,
    formset=IssueItemFormSetBase,
    extra=1,
    can_delete=True,
)
