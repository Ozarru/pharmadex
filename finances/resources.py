from base.resources import BaseResource
from django.contrib.contenttypes.models import ContentType
from finances.models import FinancialOperation, CashAccount, BankAccount, AuditBatch
from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget, ManyToManyWidget
from .models import (
    Currency, BankAccount, MobileOperator, CashAccount, Invoice, Bill,
    AuditBatch, Payment #, Payment
)

#  ------------------------------------
# User model import
#  ------------------------------------
from django.contrib.auth import get_user_model
User = get_user_model()


# -----------------------------
# Currency Resource
# -----------------------------
class CurrencyResource(BaseResource):
    class Meta:
        model = Currency
        fields = ('id', 'name', 'code', 'symbol', 'created_at', 'updated_at')
        import_id_fields = ('id',)


# -----------------------------
# BankAccount Resource
# -----------------------------
class BankAccountResource(BaseResource):
    currency = fields.Field(
        column_name='currency',
        attribute='currency',
        widget=ForeignKeyWidget(Currency, 'code')
    )

    class Meta:
        model = BankAccount
        fields = ('id', 'bank_name','account_name', 'account_number',
                  'currency', 'created_at', 'updated_at')
        import_id_fields = ('id',)


# -----------------------------
# MobileOperator Resource
# -----------------------------
class MobileOperatorResource(BaseResource):
    class Meta:
        model = MobileOperator
        fields = ('id', 'name', 'service_name', 'created_at', 'updated_at')
        import_id_fields = ('id',)


# -----------------------------
# CashAccount Resource
# -----------------------------
class CashAccountResource(BaseResource):
    currency = fields.Field(
        column_name='currency',
        attribute='currency',
        widget=ForeignKeyWidget(Currency, 'code')
    )
    mobile_operator = fields.Field(
        column_name='mobile_operator',
        attribute='mobile_operator',
        widget=ForeignKeyWidget(MobileOperator, 'name')
    )

    class Meta:
        model = CashAccount
        fields = ('id', 'unique_id', 'name', 'type', 'phone_number', 'currency', 'mobile_operator',
                  'created_at', 'updated_at')
        import_id_fields = ('id',)


# -----------------------------
# AuditBatch Resource
# -----------------------------
class AuditBatchResource(BaseResource):
    created_by = fields.Field(
        column_name='created_by',
        attribute='created_by',
        widget=ForeignKeyWidget(User, 'username')
    )
    reviewed_by = fields.Field(
        column_name='reviewed_by',
        attribute='reviewed_by',
        widget=ForeignKeyWidget(User, 'username')
    )

    class Meta:
        model = AuditBatch
        fields = ('id', 'name', 'created_by', 'created_at',
                  'reviewed_by', 'reviewed_at', 'status')
        import_id_fields = ('id',)


# -----------------------------
# FinancialOperation Resource
# -----------------------------
class FinancialOperationResource(BaseResource):
    source_cash_account = fields.Field(
        column_name='source_cash_account',
        attribute='source_cash_account',
        widget=ForeignKeyWidget(CashAccount, 'name')
    )
    source_bank = fields.Field(
        column_name='source_bank',
        attribute='source_bank',
        widget=ForeignKeyWidget(BankAccount, 'account_number')
    )
    destination_cash_account = fields.Field(
        column_name='destination_cash_account',
        attribute='destination_cash_account',
        widget=ForeignKeyWidget(CashAccount, 'name')
    )
    destination_bank = fields.Field(
        column_name='destination_bank',
        attribute='destination_bank',
        widget=ForeignKeyWidget(BankAccount, 'account_number')
    )
    audit_batch = fields.Field(
        column_name='audit_batch',
        attribute='audit_batch',
        widget=ForeignKeyWidget(AuditBatch, 'id')
    )

    class Meta:
        model = FinancialOperation
        fields = (
            'id', 'label', 'description', 'operation_type', 'operation_subtype',
            'amount', 'source_cash_account', 'source_bank', 'destination_cash_account',
            'destination_bank', 'date', 'proof_file', 'audit_batch', 'created_at'
        )
        import_id_fields = ('id',)


# -----------------------------
# Invoice Resource
# -----------------------------
class InvoiceResource(BaseResource):
    content_type = fields.Field(
        column_name='content_type',
        attribute='content_type',
        widget=ForeignKeyWidget(ContentType, 'model')
    )

    class Meta:
        model = Invoice
        fields = (
            'id', 'invoice_number', 'title', 'description', 'amount', 'issue_date',
            'due_date', 'status', 'proof_file', 'content_type',
            'object_id', 'created_at'
        )
        import_id_fields = ('id',)
        
        
# -----------------------------
# Bill Resource 
# -----------------------------
class BillResource(BaseResource):
    content_type = fields.Field(
        column_name='content_type',
        attribute='content_type',
        widget=ForeignKeyWidget(ContentType, 'model')
    )

    class Meta:
        model = Bill
        fields = (
            'id', 'bill_number', 'title', 'description', 'amount', 'bill_date',
            'due_date', 'status', 'proof_file', 'content_type',
            'object_id', 'created_at'
        )
        import_id_fields = ('id',)
        

# -----------------------------
# Generic Payment Resource
# -----------------------------
class PaymentResource(BaseResource):
    content_type = fields.Field(
        column_name="content_type",
        attribute="content_type",
        widget=ForeignKeyWidget(ContentType, "model"),
    )

    cash_account = fields.Field(
        column_name="cash_account",
        attribute="cash_account",
        widget=ForeignKeyWidget(CashAccount, "name"),
    )

    bank_account = fields.Field(
        column_name="bank_account",
        attribute="bank_account",
        widget=ForeignKeyWidget(BankAccount, "account_number"),
    )

    class Meta:
        model = Payment
        fields = (
            "id",
            "pharmacy",
            "payment_cause",
            "direction",
            "content_type",
            "object_id",
            "amount",
            "financial_account",
            "cash_account",
            "bank_account",
            "date",
            "notes",
            "created_at",
        )
        import_id_fields = ("id",)

    def before_import_row(self, row, **kwargs):
        if row.get("financial_account") == "cash_account" and not row.get("cash_account"):
            raise ValueError("CashAccount is required when financial_account is cash_account")

        if row.get("financial_account") == "bank_account" and not row.get("bank_account"):
            raise ValueError("Bank account is required when financial_account is bank_account")
