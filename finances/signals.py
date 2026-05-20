from django.utils import timezone
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from pharmacies.models import Sale
from pharmadex.context import get_current_pharmacy, get_current_user
from django.contrib.contenttypes.models import ContentType
from .models import BankAccount, CashAccount, OperationAccount,  FinancialOperation, Payment
from .utils import create_financial_operation, get_financial_account, sync_financial_account


@receiver(post_save, sender=BankAccount)
def sync_bank_account(sender, instance, **kwargs):
    sync_financial_account(instance, "bank")


@receiver(post_delete, sender=BankAccount)
def delete_bank_account(sender, instance, **kwargs):
    content_type = ContentType.objects.get_for_model(instance)

    OperationAccount.objects.filter(
        content_type=content_type,
        object_id=instance.pk
    ).delete()


@receiver(post_save, sender=CashAccount)
def sync_cash_account(sender, instance, **kwargs):
    sync_financial_account(instance, "cash_drawer")


@receiver(post_delete, sender=CashAccount)
def delete_cash_account(sender, instance, **kwargs):
    content_type = ContentType.objects.get_for_model(instance)

    OperationAccount.objects.filter(
        content_type=content_type,
        object_id=instance.pk
    ).delete()


@receiver(post_save, sender=Payment)
def create_financial_operation_for_payment(sender, instance, created, **kwargs):
    if not created:
        return

    related_obj = instance.content_object

    label = f"{instance.payment_cause.title()} payment"
    if related_obj:
        label += f" — {related_obj}"

    account_obj = instance.cash_account or instance.bank_account
    account = get_financial_account(account_obj)

    if not account:
        raise ValueError("OperationAccount could not be resolved for Payment.")

    is_inflow = instance.direction == "in"

    create_financial_operation(
        instance=instance,
        operation_type="revenue" if is_inflow else "expense",
        operation_subtype=instance.payment_cause,  # 👈 reuse same taxonomy
        label=label,
        description=f"{instance.payment_cause} payment",
        amount=instance.amount,
        date=instance.date,
        source=None if is_inflow else account,
        destination=account if is_inflow else None,
    )


@receiver(post_save, sender=Sale)
def create_financial_operation_for_sale(sender, instance, created, **kwargs):

    # ---------------------------------------
    # Only act on FINAL state
    # ---------------------------------------
    if instance.status != "completed":
        return

    if instance.is_on_credit:
        return

    if not instance.cash_account:
        return

    # ---------------------------------------
    # Prevent duplicates (VERY important)
    # ---------------------------------------
    exists = FinancialOperation.objects.filter(
        content_type=ContentType.objects.get_for_model(instance),
        object_id=str(instance.id),
    ).exists()

    if exists:
        return

    # ---------------------------------------
    # Create label
    # ---------------------------------------
    label = f"Sale #{instance.id} - Cash Payment"

    # ---------------------------------------
    # Create Financial Operation
    # ---------------------------------------
    create_financial_operation(
        instance=instance,
        operation_type="revenue",
        operation_subtype="product_sale",
        label=label,
        description="Cash sale completed",
        amount=instance.total_amount,
        date=instance.created_at.date() if hasattr(instance, "created_at") else timezone.now().date(),

        source=None,
        destination=instance.cash_account,
    )