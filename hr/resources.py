from base.resources import BaseResource
from django.contrib.contenttypes.models import ContentType
from finances.models import FinancialOperation, CashAccount, BankAccount, AuditBatch
from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget, ManyToManyWidget
from .models import (
    Currency, BankAccount, MobileOperator, CashAccount, Invoice, Bill,
    AuditBatch, Payment, PayrollItem, PayrollTransaction, Staff, SalaryScale
)

#  ------------------------------------
# User model import
#  ------------------------------------
from django.contrib.auth import get_user_model
User = get_user_model()


# -----------------------------
# SalaryScale Resource
# -----------------------------
class SalaryScaleResource(BaseResource):
    staff_group = fields.Field(
        column_name='staff_group',
        attribute='staff_group'
    )

    display_staff_group = fields.Field(
        column_name='staff_group_display'
    )

    class Meta:
        model = SalaryScale
        fields = (
            'id',
            'staff_group',
            'display_staff_group',
            'base_salary',
            'housing_allowance',
            'transport_allowance',
            'other_allowance',
            'deductions',
            'effective_from',
            'created_at',
        )
        import_id_fields = ('id',)

    def dehydrate_display_staff_group(self, obj):
        return obj.get_staff_group_display()


# -----------------------------
# PayrollItem Resource
# -----------------------------
class PayrollItemResource(BaseResource):
    salary_scale = fields.Field(
        column_name='salary_scale',
        attribute='salary_scale',
        widget=ForeignKeyWidget(SalaryScale, 'id')
    )

    class Meta:
        model = PayrollItem
        fields = (
            'id', 'staff', 'salary_scale', 'amount', 'month', 'year',
            'status', 'note', 'date', 'audit_batch', 'created_at'
        )
        import_id_fields = ('id',)


# -----------------------------
# PayrollTransaction Resourcee
# -----------------------------
class PayrollTransactionResource(BaseResource):
    staff = fields.Field(
        column_name='staff',
        attribute='staff',
        widget=ForeignKeyWidget(Staff, 'full_name')
    )
    payment = fields.Field(
        column_name='payment',
        attribute='payment',
        widget=ForeignKeyWidget(PayrollItem, 'id')
    )

    class Meta:
        model = PayrollTransaction
        fields = (
            'id', 'staff', 'payment', 'amount',
            'payment_date', 'proof_file', 'created_at'
        )
        import_id_fields = ('id',)

