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
            # "dosage",
            # "duration_days",
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


# -------------------------------
# Purchase Order forms
# -------------------------------
class PurchaseOrderForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrder
        fields = ["supplier", "reference", "expected_delivery_date", "notes", "order_file"]


class PurchaseOrderItemForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        self.pharmacy = kwargs.pop("pharmacy", None)
        super().__init__(*args, **kwargs)

        # Filter products by pharmacy's organization
        if self.pharmacy:
            self.fields["product"].queryset = Product.objects.filter(
                organization=self.pharmacy.organization,
                is_active=True
            ).order_by("name")
        else:
            self.fields["product"].queryset = Product.objects.none()

    class Meta:
        model = PurchaseOrderItem
        fields = ["product", "quantity_ordered", "expected_unit_cost"]


class BasePurchaseOrderItemFormSet(BaseInlineFormSet):

    def __init__(self, *args, **kwargs):
        self.pharmacy = kwargs.pop("pharmacy", None)
        super().__init__(*args, **kwargs)

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

            if not product:
                continue

            if product in seen:
                raise forms.ValidationError(
                    _("The same product cannot be ordered more than once.")
                )

            seen.add(product)


PurchaseOrderItemFormSet = inlineformset_factory(
    PurchaseOrder,
    PurchaseOrderItem,
    form=PurchaseOrderItemForm,
    formset=BasePurchaseOrderItemFormSet,
    can_delete=True,
)


# -------------------------------
# Purchase Delivery forms
# -------------------------------
class PurchaseDeliveryForm(forms.ModelForm):
    class Meta:
        model = PurchaseDelivery
        fields = ["purchase_order", "notes", "delivery_proof"]


class PurchaseDeliveryItemForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        self.purchase_order = kwargs.pop("purchase_order", None)
        super().__init__(*args, **kwargs)

        # Filter items by purchase order
        if self.purchase_order:
            self.fields["purchase_order_item"].queryset = PurchaseOrderItem.objects.filter(
                purchase_order=self.purchase_order
            ).select_related("product").order_by("product__name")
        else:
            self.fields["purchase_order_item"].queryset = PurchaseOrderItem.objects.none()

    class Meta:
        model = PurchaseDeliveryItem
        fields = ["purchase_order_item", "expiry_date", "received_quantity", "received_unit_cost"]


class BasePurchaseDeliveryItemFormSet(BaseInlineFormSet):

    def __init__(self, *args, **kwargs):
        self.purchase_order = kwargs.pop("purchase_order", None)
        super().__init__(*args, **kwargs)

    def get_form_kwargs(self, index):
        kwargs = super().get_form_kwargs(index)
        kwargs["purchase_order"] = self.purchase_order
        return kwargs

    def clean(self):
        super().clean()

        seen = set()

        for form in self.forms:
            if not hasattr(form, "cleaned_data"):
                continue

            if form.cleaned_data.get("DELETE"):
                continue

            po_item = form.cleaned_data.get("purchase_order_item")

            if not po_item:
                continue

            if po_item in seen:
                raise forms.ValidationError(
                    _("The same purchase order item cannot be received more than once per delivery.")
                )

            # Validate received quantity against pending
            received_qty = form.cleaned_data.get("received_quantity", 0)
            pending = po_item.pending_quantity

            if received_qty > pending:
                raise forms.ValidationError(
                    _("Received quantity (%(received)s) exceeds pending quantity (%(pending)s) for %(product)s."),
                    params={
                        "received": received_qty,
                        "pending": pending,
                        "product": po_item.product.name,
                    }
                )

            seen.add(po_item)


PurchaseDeliveryItemFormSet = inlineformset_factory(
    PurchaseDelivery,
    PurchaseDeliveryItem,
    form=PurchaseDeliveryItemForm,
    formset=BasePurchaseDeliveryItemFormSet,
    can_delete=True,
)


# -------------------------------
# Sale Edit forms
# -------------------------------
class SaleEditForm(forms.ModelForm):
    """Minimal form for sale header fields."""
    class Meta:
        model = Sale
        fields = ["notes"]
        widgets = {
            "notes": forms.Textarea(attrs={
                "rows": 2,
                "class": "form-control",
                "placeholder": _("Optional notes for this sale..."),
            }),
        }


class SaleItemForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        self.pharmacy = kwargs.pop("pharmacy", None)
        super().__init__(*args, **kwargs)

        if self.pharmacy:
            self.fields["product_stock"].queryset = ProductStock.objects.filter(
                pharmacy=self.pharmacy,
                product__is_active=True,
            ).select_related("product").order_by("product__name")
        else:
            self.fields["product_stock"].queryset = ProductStock.objects.none()

    class Meta:
        model = SaleItem
        fields = ["product_stock", "quantity"]


class BaseSaleItemFormSet(BaseInlineFormSet):

    def __init__(self, *args, **kwargs):
        self.pharmacy = kwargs.pop("pharmacy", None)
        super().__init__(*args, **kwargs)

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

            if stock.id in seen:
                raise forms.ValidationError(
                    _("%(product)s appears multiple times. Combine or remove duplicates.") % {
                        "product": stock.product.name
                    }
                )
            seen.add(stock.id)


SaleItemFormSet = inlineformset_factory(
    Sale,
    SaleItem,
    form=SaleItemForm,
    formset=BaseSaleItemFormSet,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)