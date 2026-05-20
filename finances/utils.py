from finances.models import OperationAccount, FinancialOperation
from django.db.models import Sum, Q
from django.db.models.functions import Coalesce
from django.utils import timezone
from decimal import Decimal
from django.contrib.contenttypes.models import ContentType


def sync_financial_account(instance, account_type):

    content_type = ContentType.objects.get_for_model(instance)

    account, created = OperationAccount.objects.update_or_create(
        content_type=content_type,
        object_id=instance.pk,
        defaults={
            "account_type": account_type,
            "currency": instance.currency,
            "is_active": getattr(instance, "is_active", True),
        }
    )

    return account


def get_financial_account(obj):
    if not obj:
        return None

    content_type = ContentType.objects.get_for_model(obj)

    try:
        return OperationAccount.objects.get(
            content_type=content_type,
            object_id=obj.pk
        )
    except OperationAccount.DoesNotExist:
        return None


#  ---------------------------------------------------------
# Base Financial Transaction Signal
#  ---------------------------------------------------------
def create_financial_operation(
    *,
    instance,
    operation_type: str,
    label: str,
    description: str = "",
    amount=None,
    date=None,
    source=None,          # <-- unified input
    destination=None,     # <-- unified input
    proof_file=None,
    audit_batch=None,
    operation_subtype=None,
):

    amount = amount or getattr(instance, "amount", None)
    date = date or getattr(instance, "date", getattr(instance, "payment_date", None))
    proof_file = proof_file or getattr(instance, "proof_file", None)
    audit_batch = audit_batch or getattr(instance, "audit_batch", None)

    # ---------------------------------------------------------
    # Resolve Financial Accounts
    # ---------------------------------------------------------
    source_account = source or get_financial_account(
        getattr(instance, "source", None)
    )

    destination_account = destination or get_financial_account(
        getattr(instance, "destination", None)
    )

    operation = FinancialOperation.objects.create(
        pharmacy=instance.pharmacy,
        source_account=source_account,
        destination_account=destination_account,
        label=label,
        description=description,
        operation_type=operation_type,
        operation_subtype=operation_subtype,
        amount=amount,
        date=date,
        proof_file=proof_file,
        audit_batch=audit_batch,
        content_type=ContentType.objects.get_for_model(instance),
        object_id=instance.pk,
    )

    return operation
