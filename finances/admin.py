from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import *


#  ---------------------------------------------------------
# Financial Parameters Models
#  ---------------------------------------------------------
@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    search_fields = [
        "name",
        "code",
        "symbol",
    ]

    list_filter = [
        "code",
    ]

    list_display = [
        "name",
        "code",
        "symbol",
    ]


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    search_fields = [
        "bank_name",
        "account_type",
        "account_name",
        "account_number",
        "currency__code",
    ]

    list_filter = [
        "account_type",
        "currency",
        "is_active",
    ]

    list_display = [
        "bank_name",
        "account_type",
        "account_name",
        "account_number",
        "currency",
    ]


@admin.register(MobileOperator)
class MobileOperatorAdmin(admin.ModelAdmin):
    search_fields = [
        "name",
        "service_name",
    ]

    list_filter = [
        "name",
    ]

    list_display = [
        "name",
        "service_name",
    ]


@admin.register(CashAccount)
class CashAccountAdmin(admin.ModelAdmin):
    search_fields = [
        "name",
        "code",
        "phone_number",
        "mobile_operator__name",
        "currency__code",
    ]

    list_filter = [
        "account_type",
        "currency",
        "mobile_operator",
        "is_active",
    ]

    list_display = [
        "name",
        "code",
        "account_type",
        "currency",
        "mobile_operator",
        "phone_number",
    ]


#  ---------------------------------------------------------
# Financial Operations Models
#  ---------------------------------------------------------
@admin.register(FinancialOperation)
class FinancialOperationAdmin(admin.ModelAdmin):
    search_fields = [
        "label",
        "description",
        "amount",
        "operation_type",
        "operation_subtype",
    ]
    list_filter = [
        "operation_type",
        "operation_subtype",
        "date",
    ]
    list_display = [
        "label",
        "operation_type",
        "operation_subtype",
        "amount",
        "date",
    ]


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    search_fields = [
        "invoice_number",
        "title",
        "description",
        "amount",
        "status",
    ]

    list_filter = [
        "status",
        "issue_date",
        "due_date",
    ]

    list_display = [
        "invoice_number",
        "title",
        "amount",
        "status",
        "issue_date",
        "due_date",
    ]


@admin.register(Bill)
class BillAdmin(admin.ModelAdmin):
    search_fields = [
        "bill_number",
        "title",
        "description",
        "amount",
        "status",
    ]

    list_filter = [
        "status",
        "bill_date",
        "due_date",
    ]

    list_display = [
        "bill_number",
        "title",
        "amount",
        "status",
        "bill_date",
        "due_date",
    ]


# @admin.register(Payment)
# class PaymentAdmin(admin.ModelAdmin):
#     search_fields = [
#         "amount",
#         "notes",
#         "object_id",
#     ]

#     list_filter = [
#         "payment_cause",
#         "direction",
#         "financial_account",
#         "cash_account",
#         "bank_account",
#         "date",
#     ]

#     list_display = [
#         "payment_cause",
#         "direction",
#         "amount",
#         "display_financial_account",
#         "date",
#     ]

#     readonly_fields = [
#         "content_type",
#         "object_id",
#     ]

#     def related_object(self, obj):
#         """
#         Human-readable linked document (Bill / Invoice / Sale / Purchase)
#         """
#         return str(obj.content_object) if obj.content_object else "—"

#     related_object.short_description = "Related Document"

#     def get_queryset(self, request):
#         """
#         Optimize admin queries
#         """
#         qs = super().get_queryset(request)
#         return qs.select_related(
#             "cash_account",
#             "bank_account",
#             "content_type",
#         )
        
#     @admin.display(description=_("Financial Account"))
#     def display_financial_account(self, obj):
#         return obj.display_financial_account
#     display_financial_account.short_description = "Financial Account"



@admin.register(CashClosing)
class CashClosingAdmin(admin.ModelAdmin):
    search_fields = [
        # "id",
        "comment",
        "pharmacy__name",
        "initiator__username",
        "initiator__first_name",
        "initiator__last_name",
        "validator__username",
        "validator__first_name",
        "validator__last_name",
    ]

    list_filter = [
        "pharmacy",
        "closing_date",
        "created_at",
        "validator",
    ]

    list_display = [
        # "pharmacy",
        "closing_date",
        # "created_at",
        "balance_expected",
        "balance_counted",
        "difference",
        "initiator",
        "validator",
    ]


@admin.register(CashClosingItem)
class CashClosingItemAdmin(admin.ModelAdmin):
    search_fields = [
        "cash_closing__id",
        "denomination",
        "cash_closing__pharmacy__name",
    ]

    list_filter = [
        "cash_closing__pharmacy",
        "cash_closing",
        "denomination",
    ]

    list_display = [
        "cash_closing",
        "denomination",
        "count",
        "total_amount",
    ]

