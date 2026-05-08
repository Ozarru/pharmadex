from django.forms.models import BaseInlineFormSet
from django import forms
from django.forms.models import BaseInlineFormSet, inlineformset_factory
from django.utils.translation import gettext_lazy as _
from .models import *


# -------------------------------
# Inventory Movement forms
# -------------------------------
class InventoryMovementForm(forms.ModelForm):
    class Meta:
        model = InventoryMovement
        # movement_type = 'entry' or 'exit'
        fields = ["movement_type", "reason", "comment"]


class InventoryMovementItemForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        self.pharmacy = kwargs.pop("pharmacy", None)
        super().__init__(*args, **kwargs)

        # Always filter product_stock by pharmacy
        if self.pharmacy:
            self.fields["product_stock"].queryset = ProductStock.objects.filter(
                pharmacy=self.pharmacy,
                product__is_active=True
            ).order_by("product__name")
        else:
            self.fields["product_stock"].queryset = ProductStock.objects.none()

    class Meta:
        model = InventoryMovementItem
        fields = ["product_stock", "quantity", "comment"]


class BaseInventoryMovementItemFormSet(BaseInlineFormSet):

    def __init__(self, *args, **kwargs):
        self.pharmacy = kwargs.pop("pharmacy", None)
        super().__init__(*args, **kwargs)

    # Pass pharmacy to every form (including empty_form)
    def get_form_kwargs(self, index):
        kwargs = super().get_form_kwargs(index)
        kwargs["pharmacy"] = self.pharmacy
        return kwargs

    def clean(self):
        super().clean()

        seen = set()

        for form in self.forms:
            if not hasattr(form, "cleaned_data"):
                continue

            if form.cleaned_data.get("DELETE"):
                continue

            stock = form.cleaned_data.get("product_stock")

            if not stock:
                continue

            if stock in seen:
                raise forms.ValidationError(
                    _("The same product cannot be added more than once.")
                )

            seen.add(stock)


InventoryMovementItemFormSet = inlineformset_factory(
    InventoryMovement,
    InventoryMovementItem,
    form=InventoryMovementItemForm,
    formset=BaseInventoryMovementItemFormSet,
    can_delete=True,
)


# -------------------------------
# Inventory Audit views
# -------------------------------
class InventoryAuditForm(forms.ModelForm):
    class Meta:
        model = InventoryAudit
        fields = ["reason", "comment"]


class InventoryAuditItemForm(forms.ModelForm):

    class Meta:
        model = InventoryAuditItem
        fields = ["product_stock", "quantity_found", "comment"]

    def __init__(self, *args, **kwargs):
        self.pharmacy = kwargs.pop("pharmacy", None)
        super().__init__(*args, **kwargs)

        self.fields["product_stock"].disabled = True

        if self.pharmacy:
            self.fields["product_stock"].queryset = ProductStock.objects.filter(
                pharmacy=self.pharmacy,
                product__is_active=True
            )
        else:
            self.fields["product_stock"].queryset = ProductStock.objects.none()

    def get_expected_quantity(self):
        stock = self.cleaned_data.get("product_stock")
        if not stock:
            return 0

        return stock.batches.aggregate(
            total=models.Sum("quantity")
        )["total"] or 0

    def clean(self):
        cleaned = super().clean()

        # override expected dynamically
        if "product_stock" in cleaned:
            self.instance.quantity_expected = self.get_expected_quantity()

        return cleaned


class BaseInventoryAuditItemFormSet(BaseInlineFormSet):

    def __init__(self, *args, **kwargs):
        self.pharmacy = kwargs.pop("pharmacy", None)

        if not self.pharmacy:
            raise ValueError("Pharmacy must be passed.")

        parent_instance = kwargs.get("instance", None)

        # CREATE
        if not parent_instance:
            product_stocks = ProductStock.objects.filter(
                pharmacy=self.pharmacy
            ).order_by("product__name")

            kwargs["queryset"] = InventoryAuditItem.objects.none()

            initial = [
                {
                    "product_stock": ps,
                    "quantity_expected": ps.batches.aggregate(
                        total=models.Sum("quantity")
                    )["total"] or 0,
                }
                for ps in product_stocks
            ]

            kwargs["initial"] = initial
            self.extra = len(initial)

        # UPDATE
        else:
            kwargs["queryset"] = InventoryAuditItem.objects.filter(
                inventory_audit=parent_instance
            )
            self.extra = 0

        super().__init__(*args, **kwargs)

    def get_form_kwargs(self, index):
        kwargs = super().get_form_kwargs(index)
        kwargs["pharmacy"] = self.pharmacy
        return kwargs


InventoryAuditItemFormSet = inlineformset_factory(
    InventoryAudit,
    InventoryAuditItem,
    form=InventoryAuditItemForm,
    formset=BaseInventoryAuditItemFormSet,
    extra=0,
    can_delete=False,
)


# -------------------------------
# Prescription views
# -------------------------------
class PrescriptionForm(forms.ModelForm):
    class Meta:
        model = Prescription
        fields = [
            "patient",
            "issued_date",
            "notes",
        ]


class PrescriptionItemForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        self.pharmacy = kwargs.pop("pharmacy", None)
        super().__init__(*args, **kwargs)

        # Filter products by pharmacy
        if self.pharmacy:
            self.fields["product"].queryset = Product.objects.filter(
                organization=self.pharmacy.organization,
                is_active=True
            ).order_by("name")
        else:
            self.fields["product"].queryset = Product.objects.none()

    class Meta:
        model = PrescriptionItem
        fields = [
            "product",
            "quantity",
            "dosage",
            "duration_days",
            "instructions",
        ]


class BasePrescriptionItemFormSet(BaseInlineFormSet):

    def __init__(self, *args, **kwargs):
        self.pharmacy = kwargs.pop("pharmacy", None)
        super().__init__(*args, **kwargs)

    # Pass pharmacy to each form
    def get_form_kwargs(self, index):
        kwargs = super().get_form_kwargs(index)
        kwargs["pharmacy"] = self.pharmacy
        return kwargs

    def clean(self):
        super().clean()

        seen = set()

        for form in self.forms:
            if not hasattr(form, "cleaned_data"):
                continue

            if form.cleaned_data.get("DELETE"):
                continue

            product = form.cleaned_data.get("product")
            quantity = form.cleaned_data.get("quantity")

            if not product:
                continue

            # Prevent duplicate products
            if product in seen:
                raise forms.ValidationError(
                    _("The same product cannot be added more than once.")
                )

            seen.add(product)

            # Prevent zero or negative quantities
            if quantity is not None and quantity <= 0:
                raise forms.ValidationError(
                    _("Quantity must be greater than zero.")
                )

      
PrescriptionItemFormSet = inlineformset_factory(
    Prescription,
    PrescriptionItem,
    form=PrescriptionItemForm,
    formset=BasePrescriptionItemFormSet,
    can_delete=True,
)
