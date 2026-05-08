from django.forms.models import BaseInlineFormSet
from django import forms
from django.forms.models import BaseInlineFormSet, inlineformset_factory
from django.utils.translation import gettext_lazy as _
from .models import *

# -------------------------------
# Cash Closing forms
# -------------------------------
class CashClosingForm(forms.ModelForm):
    class Meta:
        model = CashClosing
        fields = ["closing_date", "comment"]


class CashClosingItemForm(forms.ModelForm):
    class Meta:
        model = CashClosingItem
        fields = ["denomination", "count"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Denomination should not be editable
        self.fields["denomination"].disabled = True

    def has_changed(self):
        # Force save even if count = 0
        return True


class BaseCashClosingItemFormSet(BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        kwargs.pop("pharmacy", None)
        parent_instance = kwargs.get("instance")

        # CREATE MODE
        if not parent_instance or not parent_instance.pk:
            # Create initial rows for all denominations
            initial_data = [
                {"denomination": denom, "count": 0}
                for denom, _ in CashClosingItem.FCFA_DENOMINATIONS
            ]
            kwargs["queryset"] = CashClosingItem.objects.none()
            kwargs["initial"] = initial_data

            # Dynamically set extra so the forms actually render
            self.extra = len(initial_data)

        # UPDATE MODE
        else:
            # Ensure all denominations exist exactly once
            existing_items = CashClosingItem.objects.filter(
                cash_closing=parent_instance
            )
            existing_denoms = set(
                existing_items.values_list("denomination", flat=True)
            )

            for denom, _ in CashClosingItem.FCFA_DENOMINATIONS:
                if denom not in existing_denoms:
                    CashClosingItem.objects.create(
                        cash_closing=parent_instance,
                        denomination=denom,
                        count=0
                    )

            kwargs["queryset"] = CashClosingItem.objects.filter(
                cash_closing=parent_instance
            ).order_by("denomination")

        super().__init__(*args, **kwargs)


CashClosingItemFormSet = inlineformset_factory(
    CashClosing,
    CashClosingItem,
    form=CashClosingItemForm,
    formset=BaseCashClosingItemFormSet,
    extra=0,
    can_delete=False,
)
