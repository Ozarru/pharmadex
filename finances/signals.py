from django.utils import timezone
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from pharmadex.context import get_current_pharmacy, get_current_user
from django.contrib.contenttypes.models import ContentType
from .models import BankAccount, CashAccount, FinancialAccount,  FinancialOperation, Payment
from .utils import create_financial_operation, get_financial_account, sync_financial_account


#  ---------------------------------------------------------
# BankAccount Synchronization Signals
#  ---------------------------------------------------------
@receiver(post_save, sender=BankAccount)
def create_or_update_bank_account(sender, instance, **kwargs):
    sync_financial_account(instance, "bank")


@receiver(post_delete, sender=BankAccount)
def delete_bank_account(sender, instance, **kwargs):
    content_type = ContentType.objects.get_for_model(instance)

    FinancialAccount.objects.filter(
        content_type=content_type,
        object_id=instance.pk
    ).delete()


#  ---------------------------------------------------------
# CashAccount Synchronization Signals
#  ---------------------------------------------------------
@receiver(post_save, sender=CashAccount)
def create_or_update_cash_account_account(sender, instance, **kwargs):
    sync_financial_account(instance, "cash_account")


@receiver(post_delete, sender=CashAccount)
def delete_cash_account_account(sender, instance, **kwargs):
    content_type = ContentType.objects.get_for_model(instance)

    FinancialAccount.objects.filter(
        content_type=content_type,
        object_id=instance.pk
    ).delete()
    

#  ---------------------------------------------------------
#  Generic Payment Signal
#  ---------------------------------------------------------
PAYMENT_FINANCIAL_MAPPING = {
    "sale": {
        "operation_type": "inflow",
        "operation_subtype": "drug_sales",
    },
    "invoice": {
        "operation_type": "inflow",
        "operation_subtype": "other_income",
    },
    "purchase": {
        "operation_type": "outflow",
        "operation_subtype": "supplier_payment",
    },
    "bill": {
        "operation_type": "outflow",
        "operation_subtype": "utilities",
    },
    "refund": {
        "operation_type": "outflow",
        "operation_subtype": "refund",
    },
    "advance": {
        "operation_type": "outflow",
        "operation_subtype": "other_expense",
    },
}


@receiver(post_save, sender=Payment)
def create_financial_operation_for_payment(sender, instance, created, **kwargs):
    if not created:
        return

    mapping = PAYMENT_FINANCIAL_MAPPING.get(instance.payment_cause)
    if not mapping:
        return

    related_obj = instance.content_object

    label = f"{instance.payment_cause.title()} payment"
    if related_obj:
        label += f" — {str(related_obj)}"

    # ---------------------------------------------------------
    # Resolve account (single source of truth)
    # ---------------------------------------------------------
    account_obj = instance.cash_account or instance.bank_account
    account = get_financial_account(account_obj)

    if not account:
        raise ValueError("FinancialAccount could not be resolved for Payment.")

    # ---------------------------------------------------------
    # Direction handling
    # ---------------------------------------------------------
    source = None
    destination = None

    if instance.direction == "in":
        destination = account
    else:
        source = account

    # ---------------------------------------------------------
    # Create operation
    # ---------------------------------------------------------
    create_financial_operation(
        instance=instance,
        operation_type=mapping["operation_type"],
        operation_subtype=mapping["operation_subtype"],
        label=label,
        description=f"{instance.payment_cause.title()} payment recorded",
        amount=instance.amount,
        date=instance.date,
        source=source,
        destination=destination,
    )

    # ---------------------------------------------------------
    # Update related document
    # ---------------------------------------------------------
    if related_obj and hasattr(related_obj, "balance"):
        related_obj.save()


