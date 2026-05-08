from django.db.models.signals import post_save
from django.dispatch import receiver
from finances.utils import create_financial_operation
from pharmadex.context import get_current_organization, get_current_user
from django.contrib.contenttypes.models import ContentType
from hr.models import PayrollTransaction
from finances.models import BankAccount, CashAccount,  FinancialOperation , Payment
from django.utils import timezone


#  ---------------------------------------------------------
# Payroll Transaction Signal
#  ---------------------------------------------------------
@receiver(post_save, sender=PayrollTransaction)
def finance_operation_from_payroll_transaction(sender, instance, created, **kwargs):
    if not created:
        return

    # Resolve source account (money going OUT)
    source_obj = None

    if instance.cash_account:
        source_obj = instance.cash_account
    elif instance.bank_account:
        source_obj = instance.bank_account

    create_financial_operation(
        instance=instance,
        operation_type="outflow",
        operation_subtype="salary",
        label=f"Salary payment — {instance.staff}",
        description=f"Payroll payout via {instance.get_payment_method_display()}",
        amount=instance.amount,
        date=instance.payment_date,
        source=source_obj,
        proof_file=instance.proof_file,
        audit_batch=instance.payroll_item.audit_batch if instance.payroll_item else None,
    )
