from django.db.models.functions import Coalesce
from django.db.models import F, Sum, Count
from finances.forms import CashClosingForm, CashClosingItemFormSet
from django.utils.functional import cached_property
from decimal import Decimal
from django import forms
from django.db.models import Sum, Q, Value
from django.forms import DecimalField
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.mixins import LoginRequiredMixin
from base.views import BaseDetailView, BaseListView, BaseModelView, BaseParentChildFormView
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView
# from hr.models import PayrollTransaction
from utils import format_currency
from django.utils.decorators import method_decorator
from .models import (
    BankAccount, Bill, CashClosing, CashAccount, Currency, FinancialOperation, Invoice,
    MobileOperator, Payment
)
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.contrib.contenttypes.models import ContentType
from django.contrib import messages
from django.db.models import Sum
from django.utils import timezone
from datetime import datetime, time, timedelta
from django.contrib.auth.decorators import login_required


# Pharmacy Finances-------------------------------------------------------------------------
@login_required(login_url='accounts:login')
def finances_dashboard(request):
    pharmacy = getattr(request, "current_pharmacy", None)
    current_user_type = request.user.get_current_user_type()

    # ---- Aggregate totals safely ----
    total_revenue = (
        FinancialOperation.objects.filter(
            pharmacy=pharmacy, operation_type="revenue"
        ).aggregate(total=Sum("amount"))["total"] or 0
    )

    total_expense = (
        FinancialOperation.objects.filter(
            pharmacy=pharmacy, operation_type="expense"
        ).aggregate(total=Sum("amount"))["total"] or 0
    )

    total_balance = total_revenue - total_expense

    # total_salaries_paid = (
    #     PayrollTransaction.objects.filter(
    #         # pharmacy=pharmacy, 
    #         payment_date__isnull=False)
    #     .aggregate(total=Sum("amount"))["total"]
    #     or 0
    # )

    # ---- Calculate Monthly Growth ----
    today = timezone.now().date()
    first_day_this_month = today.replace(day=1)
    first_day_last_month = (first_day_this_month -
                            timedelta(days=1)).replace(day=1)
    last_day_last_month = first_day_this_month - timedelta(days=1)

    # This month's net balance
    this_month_revenue = (
        FinancialOperation.objects.filter(
            pharmacy=pharmacy,
            operation_type="revenue",
            date__gte=first_day_this_month,
            date__lte=today,
        ).aggregate(total=Sum("amount"))["total"]
        or 0
    )
    this_month_expense = (
        FinancialOperation.objects.filter(
            pharmacy=pharmacy,
            operation_type="expense",
            date__gte=first_day_this_month,
            date__lte=today,
        ).aggregate(total=Sum("amount"))["total"]
        or 0
    )
    this_month_balance = this_month_revenue - this_month_expense

    # Last month's net balance
    last_month_revenue = (
        FinancialOperation.objects.filter(
            pharmacy=pharmacy,
            operation_type="revenue",
            date__gte=first_day_last_month,
            date__lte=last_day_last_month,
        ).aggregate(total=Sum("amount"))["total"]
        or 0
    )
    last_month_expense = (
        FinancialOperation.objects.filter(
            pharmacy=pharmacy,
            operation_type="expense",
            date__gte=first_day_last_month,
            date__lte=last_day_last_month,
        ).aggregate(total=Sum("amount"))["total"]
        or 0
    )
    last_month_balance = last_month_revenue - last_month_expense

    # Calculate growth percentage (handle zero safely)
    if last_month_balance != 0:
        net_monthly_growth = (
            (this_month_balance - last_month_balance) / abs(last_month_balance)) * 100
    else:
        net_monthly_growth = 0

    # ---- Build display data ----
    finance_labels = [
        _("Total Revenue"),
        _("Total Expenses"),
        _("Net Balance"),
        _("Pharmacy Fees Paid"),
        _("Salaries Paid"),
        _("Net Monthly Growth"),
    ]

    finance_aggregates = [
        total_revenue,
        total_expense,
        total_balance,
        # total_salaries_paid,
        f"{net_monthly_growth:.2f}%",  # formatted as percentage
    ]

    finance_colors = ["green", "teal", "orange", "blue", "purple", "pink"]
    finance_icons = [
        "fa-money-bill",
        "fa-receipt",
        "fa-balance-scale",
        "fa-graduation-cap",
        "fa-user-tie",
        "fa-chart-line",
    ]

    data_groups = [
        {
            "label": label,
            "aggregate": format_currency(aggregate)
            if isinstance(aggregate, (int, float))
            else aggregate,
            "color": color,
            "icon": icon,
        }
        for label, aggregate, color, icon in zip(
            finance_labels, finance_aggregates, finance_colors, finance_icons
        )
    ]

    context = {
        "active_page": "finances_page",
        "title": _("Pharmacy Finance Dashboard Page"),
        "subtitle": _("View your pharmacy's finances here"),
        "header_paragraph": _(
            """
            The management of pharmacy finances covers fee collection, staff Payroll Items,
            and expense tracking — providing a clear view of the institution’s financial
            health for better planning and transparency.
            """
        ),
        "model_icon": 'fa-solid fa-coins',
        "data_groups": data_groups,
        "current_user_type": current_user_type,
    }

    return render(request, "finances/dashboard.html", context)


@login_required(login_url='accounts:login')
def financial_reports(request):
    pharmacy = getattr(request, "current_pharmacy", None)
    now = timezone.now().date()

    # -----------------------------------------------------------
    # REVENUE, EXPENSE, BALANCE
    # -----------------------------------------------------------
    total_revenue = FinancialOperation.objects.filter(
        pharmacy=pharmacy, operation_type="revenue"
    ).aggregate(total=Sum("amount"))["total"] or 0

    total_expense = FinancialOperation.objects.filter(
        pharmacy=pharmacy, operation_type="expense"
    ).aggregate(total=Sum("amount"))["total"] or 0

    net_balance = total_revenue - total_expense

    # -----------------------------------------------------------
    # PAYROLL
    # -----------------------------------------------------------
    # total_salaries_paid = PayrollTransaction.objects.filter(
    #     # pharmacy=pharmacy, 
    #     payment_date__isnull=False
    # ).aggregate(total=Sum("amount"))["total"] or 0

    # -----------------------------------------------------------
    # MONTHLY GROWTH
    # -----------------------------------------------------------
    first_day_this_month = now.replace(day=1)
    last_month_last_day = first_day_this_month - timedelta(days=1)
    first_day_last_month = last_month_last_day.replace(day=1)

    # This Month
    this_month_revenue = FinancialOperation.objects.filter(
        pharmacy=pharmacy,
        operation_type="revenue",
        date__gte=first_day_this_month,
        date__lte=now,
    ).aggregate(total=Sum("amount"))["total"] or 0

    this_month_expense = FinancialOperation.objects.filter(
        pharmacy=pharmacy,
        operation_type="expense",
        date__gte=first_day_this_month,
        date__lte=now,
    ).aggregate(total=Sum("amount"))["total"] or 0

    this_month_net = this_month_revenue - this_month_expense

    # Last Month
    last_month_revenue = FinancialOperation.objects.filter(
        pharmacy=pharmacy,
        operation_type="revenue",
        date__gte=first_day_last_month,
        date__lte=last_month_last_day,
    ).aggregate(total=Sum("amount"))["total"] or 0

    last_month_expense = FinancialOperation.objects.filter(
        pharmacy=pharmacy,
        operation_type="expense",
        date__gte=first_day_last_month,
        date__lte=last_month_last_day,
    ).aggregate(total=Sum("amount"))["total"] or 0

    last_month_net = last_month_revenue - last_month_expense

    # Growth %
    if last_month_net != 0:
        monthly_growth = ((this_month_net - last_month_net) /
                          abs(last_month_net)) * 100
    else:
        monthly_growth = 0

    # -----------------------------------------------------------
    # BANK ACCOUNTS — Combined Balances
    # -----------------------------------------------------------
    bank_accounts = BankAccount.objects.filter(pharmacy=pharmacy)
    total_bank_balance = sum(bank.get_balance(pharmacy)
                             for bank in bank_accounts)

    # -----------------------------------------------------------
    # CASH DESKS — On Hand Cash
    # -----------------------------------------------------------
    cash_accounts = CashAccount.objects.filter(pharmacy=pharmacy, account_type='physical')
    total_cash_account_balance = sum(cd.get_balance(pharmacy) for cd in cash_accounts)

    # -----------------------------------------------------------
    # MOBILE OPERATORS — Wallet Balances
    # -----------------------------------------------------------
    cash_accounts = CashAccount.objects.filter(pharmacy=pharmacy, account_type='electronic')
    total_mobile_money_balance = sum(
        cd.get_balance(pharmacy) for cd in cash_accounts)

    # -----------------------------------------------------------
    # DATA PACKING FOR UI
    # -----------------------------------------------------------
    labels = [
        _("Total Revenue"),
        _("Total Expenses"),
        _("Net Financial Balance"),
        _("Fees Collected"),
        _("Salaries Paid"),
        _("Monthly Growth"),
        _("Bank Account Balances"),
        _("Cash-on-Hand (Liquid)"),
        _("Mobile Money Balance"),
    ]

    values_raw = [
        total_revenue,
        total_expense,
        net_balance,
        total_salaries_paid,
        f"{monthly_growth:.2f}%",
        total_bank_balance,
        total_cash_account_balance,
        total_mobile_money_balance,
    ]

    colors = [
        "green", "red", "orange", "blue", "purple",
        "pink", "cyan", "amber", "indigo"
    ]

    icons = [
        "fa-money-bill",
        "fa-receipt",
        "fa-scale-balanced",
        "fa-wallet",
        "fa-user-tie",
        "fa-chart-line",
        "fa-university",
        "fa-cash-register",
        "fa-mobile-screen",
    ]

    data_groups = []
    for label, value, color, icon in zip(labels, values_raw, colors, icons):
        data_groups.append({
            "label": label,
            "aggregate": format_currency(value) if isinstance(value, (int, float)) else value,
            "color": color,
            "icon": icon,
        })

    # -----------------------------------------------------------
    # CONTEXT
    # -----------------------------------------------------------
    context = {
        "active_page": "finance_page",
        "title": _("Pharmacy Financial Report Overview"),
        "subtitle": _("A breakdown of all major financial metrics across the institution"),
        "header_paragraph": _(
            """
            This financial report provides a complete breakdown of your pharmacy's income,
            expenses, banking activity, cash handling, and mobile money transactions.
            It supports data-driven decision-making and transparency in pharmacy operations.
            """
        ),
        "model_icon": "fa-solid fa-chart-pie",
        "data_groups": data_groups,
    }

    return render(request, "finances/reports/index.html", context)


# ------------------------------------------------------------------------
# Currency
# ------------------------------------------------------------------------
class CurrencyListView(BaseListView):
    model = Currency
    template_name = 'generic/index.html'
    partial_parent_directory = 'generic'
    context_object_name = 'objects'
    active_page = 'finance_page'
    title = _("Currencies")
    subtitle = _(
        "Manage available currencies used across all financial accounts")
    header_paragraph = _(
        """Manage the currencies used across all financial accounts and transactions
        within the pharmacy. Configure currency names, symbols, and default settings
        to ensure accurate billing, payments, reporting, and consistency across
        all financial operations."""
    )

    object_crud_link = "finances:currency-create"
    object_crud_via_htmx = True


class CurrencyDetailView(BaseDetailView):
    model = Currency
    template_name = 'finances/currency/detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        currency = self.object

        context["currency"] = currency
        context["title"] = _("Currency Details")
        context["subtitle"] = _("View properties and usage for this currency")
        context["active_page"] = "finance_page"

        context["header_paragraph"] = """
            This page shows detailed information about this currency, including 
            its code, symbol, and linked financial accounts. 
        """

        return context


class CurrencyCreateView(BaseModelView, CreateView):
    model = Currency
    fields = ['name', 'code', 'symbol']
    success_url = reverse_lazy('finances:currency-list')
    title = _("Add Currency")
    subtitle = _("Register a new currency used in financial transactions")


class CurrencyUpdateView(BaseModelView, UpdateView):
    model = Currency
    fields = ['name', 'code', 'symbol']
    success_url = reverse_lazy('finances:currency-list')
    title = _("Edit Currency")
    subtitle = _("Modify currency properties")


# ------------------------------------------------------------------------
# Bank Account
# ------------------------------------------------------------------------
class BankAccountListView(BaseListView):
    model = BankAccount
    template_name = 'generic/index.html'
    partial_parent_directory = 'generic'
    context_object_name = 'objects'
    active_page = 'finance_page'
    title = _("Bank Accounts")
    subtitle = _("Manage all registered bank accounts")
    header_paragraph = _(
        """
    This page displays all bank accounts associated with the pharmacy. 
    You can review account details such as account numbers, currencies, 
    and activity status. Bank accounts are used for recording financial 
    transactions, receiving payments, and managing pharmacy funds securely.
    """
    )
    object_crud_link = "finances:bank-account-create"
    object_crud_via_htmx = True


class BankAccountDetailView(BaseDetailView):
    model = BankAccount
    template_name = "finances/accounts/bank/detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        bank_account = self.object

        # -----------------------------
        # Financial Operations (source of truth)
        # -----------------------------
        incoming = bank_account.destination_operations.aggregate(
            total=Coalesce(Sum("amount"), Decimal("0.00")),
            count=Count("id"),
        )

        outgoing = bank_account.source_operations.aggregate(
            total=Coalesce(Sum("amount"), Decimal("0.00")),
            count=Count("id"),
        )

        # -----------------------------
        # Balance
        # -----------------------------
        balance = incoming["total"] - outgoing["total"]

        # -----------------------------
        # Context
        # -----------------------------
        context.update({
            "bank_account": bank_account,
            "title": _("Bank Account Details"),
            "subtitle": _("View transactions and balance for this bank account"),
            "active_page": "finance_page",
            "header_paragraph": _(
                """
                This bank account is used for receiving and sending funds.
                All financial activity shown here is derived from recorded
                financial operations linked to payments, invoices, bills,
                sales, and purchases.
                """
            ),

            # UX / Stats
            "incoming_stats": incoming,
            "outgoing_stats": outgoing,
            "balance": balance,
        })

        return context


class BankAccountCreateView(BaseModelView, CreateView):
    model = BankAccount
    fields = ['bank', 'name', 'account_number', 'currency']
    success_url = reverse_lazy('finances:bank-account-list')
    title = _("Add Bank Account")
    subtitle = _("Register a new bank account")


class BankAccountUpdateView(BaseModelView, UpdateView):
    model = BankAccount
    fields = ['bank', 'name', 'account_number', 'currency']
    success_url = reverse_lazy('finances:bank-account-list')
    title = _("Edit Bank Account")
    subtitle = _("Modify details of this bank account")


# ------------------------------------------------------------------------
# Mobile Operator
# ------------------------------------------------------------------------
class MobileOperatorListView(BaseListView):
    model = MobileOperator
    template_name = 'generic/index.html'
    partial_parent_directory = 'generic'
    context_object_name = 'objects'
    active_page = 'finance_page'
    title = _("Mobile Operators")
    subtitle = _("Manage mobile money service operators used by cash_accounts")
    header_paragraph = _(
        """
    This page displays all mobile operators registered in the system. 
    These operators are used for processing mobile money payments, 
    sending notifications, and supporting communication features. 
    You can manage operator details, activation status, and integration 
    settings from this page.
    """
    )

    object_crud_link = "finances:mobile-operator-create"
    object_crud_via_htmx = True


class MobileOperatorDetailView(BaseDetailView):
    model = MobileOperator
    template_name = 'finances/mobile_operator/detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        op = self.object

        context["operator"] = op
        context["title"] = _("Mobile Operator Details")
        context["subtitle"] = _("Full details of this mobile money operator")
        context["active_page"] = "finance_page"

        context["header_paragraph"] = """
            Mobile operators are used for electronic cash_accounts. 
            Update their information here if their branding or services change.
        """

        return context


class MobileOperatorCreateView(BaseModelView, CreateView):
    model = MobileOperator
    fields = ['name', 'service_name']
    success_url = reverse_lazy('finances:mobile-operator-list')
    title = _("Add Mobile Operator")
    subtitle = _("Register a new mobile money operator")


class MobileOperatorUpdateView(BaseModelView, UpdateView):
    model = MobileOperator
    fields = ['name', 'service_name']
    success_url = reverse_lazy('finances:mobile-operator-list')
    title = _("Edit Mobile Operator")
    subtitle = _("Modify operator information")


# ------------------------------------------------------------------------
# CashAccount
# ------------------------------------------------------------------------
class CashAccountListView(BaseListView):
    model = CashAccount
    template_name = 'generic/index.html'
    partial_parent_directory = 'generic'
    context_object_name = 'objects'
    active_page = 'finance_page'
    title = _("CashAccounts")
    subtitle = _(
        "Manage physical and electronic cash_accounts used for transactions")
    header_paragraph = _(
        """
    This page lists all cash desks used by the pharmacy for handling 
    on-site cash transactions. You can monitor cash desk activity, 
    track balances, assign responsible staff, and manage daily 
    cash operations efficiently.
    """
    )

    object_crud_link = "finances:cash-account-create"
    object_crud_via_htmx = True


class CashAccountDetailView(BaseDetailView):
    model = CashAccount
    template_name = "finances/accounts/cash/detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cash_account = self.object

        # -----------------------------
        # Financial Operations (source of truth)
        # -----------------------------
        incoming = cash_account.destination_operations.aggregate(
            total=Coalesce(Sum("amount"), Decimal("0.00")),
            count=Count("id"),
        )

        outgoing = cash_account.source_operations.aggregate(
            total=Coalesce(Sum("amount"), Decimal("0.00")),
            count=Count("id"),
        )

        # -----------------------------
        # Balance
        # -----------------------------
        balance = incoming["total"] - outgoing["total"]

        # -----------------------------
        # Context
        # -----------------------------
        context.update({
            "cash_account": cash_account,
            "title": _("CashAccount Details"),
            "subtitle": _("View transactions and balance for this cash_account"),
            "active_page": "finance_page",
            "header_paragraph": _(
                """
                This cash_account records all cash inflows and outflows.
                The figures shown here are calculated from financial
                operations linked to payments, sales, purchases,
                invoices, and bills.
                """
            ),

            # UX stats
            "incoming_stats": incoming,
            "outgoing_stats": outgoing,
            "balance": balance,
        })

        return context


class CashAccountCreateView(BaseModelView, CreateView):
    model = CashAccount
    fields = [
        'name', 'code', 'account_type', 'mobile_operator', 'phone_number', 'currency',
    ]
    success_url = reverse_lazy('finances:cash-account-list')
    title = _("Add CashAccount")
    subtitle = _("Register a new cash_account for pharmacy transactions")


class CashAccountUpdateView(BaseModelView, UpdateView):
    model = CashAccount
    fields = [
        'name', 'code', 'account_type', 'mobile_operator', 'phone_number', 'currency',
    ]
    success_url = reverse_lazy('finances:cash-account-list')
    title = _("Edit CashAccount")
    subtitle = _("Update information for this cash_account")


# ------------------------------------------------------------------------
# PAYMENT CREATION (FinancialOperation)
# ------------------------------------------------------------------------
class PaymentListView(BaseListView):
    model = Payment
    template_name = 'generic/index.html'
    partial_parent_directory = 'generic'
    context_object_name = 'objects'
    active_page = 'finance_page'
    title = _("Payments")
    subtitle = _("View and manage all recorded payments")
    object_crud_link = "finances:payment-create"
    object_crud_via_htmx = True

    header_paragraph = _(
        """
        This page lists all payments recorded in the system.
        You can review payment amounts, dates, sources, and
        the users who recorded them.
        """
    )


    def get_queryset(self):
        # Limit to current pharmacy
        qs = super().get_queryset()
        current_pharmacy = self.request.user.profile.current_pharmacy
        return qs.filter(pharmacy=current_pharmacy).order_by('-date')


class PaymentDetailView(BaseDetailView):
    model = Payment
    template_name = 'finances/payment_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        payment = self.object
        context.update({
            "payment": payment,
            "related_object": payment.content_object,
            "title": _("Payment Details"),
            "subtitle": _("Full details of this payment"),
            "active_page": "finance_page",
            "header_paragraph": _(
                """
                This page shows complete details about the payment,
                including the linked object, payment method,
                amount, and the user who recorded it.
                """
            ),
        })
        return context


class PaymentCreateView(BaseModelView, CreateView):
    model = Payment
    fields = ['payment_cause', 'object_id', 'content_type', 'direction', 'amount', 'financial_account', 'cash_account', 'bank_account', 'date', 'notes']
    success_url = reverse_lazy('finances:payment-list')
    title = _("Record Payment")
    subtitle = _("Add a new payment for any financial object")

    def get_initial(self):
        """
        Pre-fill form fields from GET parameters (content_type, object_id, direction).
        """
        initial = super().get_initial()
        object_id = self.request.GET.get('object_id')
        model_name = self.request.GET.get('model_name')
        direction = self.request.GET.get('direction')

        if object_id and model_name:
            try:
                content_type = ContentType.objects.get(model=model_name.lower())
                initial['object_id'] = object_id
                initial['content_type'] = content_type.id
            except ContentType.DoesNotExist:
                pass  # fail silently if content_type is invalid

        if direction in dict(Payment.PAYMENT_DIRECTION_CHOICES):
            initial['direction'] = direction

        return initial

    def get_form(self, *args, **kwargs):
        """
        Remove fields from the form if we already have them in GET.
        """
        form = super().get_form(*args, **kwargs)
        object_id = self.request.GET.get('object_id')
        model_name = self.request.GET.get('model_name')
        direction = self.request.GET.get('direction')
        payment_cause = self.request.GET.get('payment_cause')

        # Hide prefilled fields
        if object_id and model_name:
            form.fields["object_id"].widget = forms.HiddenInput()
            form.fields["object_id"].label = ""
            form.fields["content_type"].widget = forms.HiddenInput()
            form.fields["content_type"].label = ""

        if direction in dict(Payment.PAYMENT_DIRECTION_CHOICES):
            form.fields["direction"].widget = forms.HiddenInput()
            form.fields["direction"].label = ""
            
        if payment_cause in dict(Payment.PAYMENT_CAUSE_CHOICES):
            form.fields["payment_cause"].widget = forms.HiddenInput()
            form.fields["payment_cause"].label = ""

        return form

    def form_valid(self, form):
        print("Form data:", form.cleaned_data)
        print("Form errors:", form.errors)
        # Always set the pharmacy
        form.instance.pharmacy = self.request.user.profile.current_pharmacy

        # If content_type/object_id passed via GET, set them on instance
        object_id = self.request.GET.get('object_id')
        model_name = self.request.GET.get('model_name')
        direction = self.request.GET.get('direction')
        payment_cause = self.request.GET.get('payment_cause')

        if object_id and model_name:
            content_type = ContentType.objects.get(model=model_name.lower())
            form.instance.content_type = content_type
            form.instance.object_id = object_id

        if direction in dict(Payment.PAYMENT_DIRECTION_CHOICES):
            form.instance.direction = direction
            
        if payment_cause in dict(Payment.PAYMENT_CAUSE_CHOICES):
            form.instance.payment_cause = payment_cause

        return super().form_valid(form)
    
    def form_invalid(self, form):
        print("Form errors:", form.errors)
        return super().form_invalid(form)


class PaymentUpdateView(BaseModelView, UpdateView):
    model = Payment
    fields = [
        'amount',
        'financial_account',
        'cash_account',
        'bank_account',
        'date',
        'notes',
    ]
    success_url = reverse_lazy('finances:payment-list')
    title = _("Edit Payment")
    subtitle = _("Update payment details")


# ------------------------------------------------------------------------
# FinancialOperation
# ------------------------------------------------------------------------
class FinancialOperationListView(BaseListView):
    model = FinancialOperation
    template_name = 'generic/index.html'
    partial_parent_directory = 'generic'
    context_object_name = 'objects'
    active_page = 'finance_page'
    title = _("Financial Operations")
    subtitle = _("View and manage all invoices issued by the pharmacy")
    header_paragraph = _(
        """This page lists all financial operations recorded by the pharmacy, 
    including payments, receipts, adjustments, and other monetary movements. 
    You can review each transaction, inspect its source document, and 
    monitor the financial audit trail.
    """)


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["object_crud_link"] = None
        return context


class FinancialOperationDetailView(BaseDetailView):
    model = FinancialOperation
    template_name = 'finances/operation/detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        operation = self.object
        context["object_crud_link"] = None
        context["operation"] = operation
        context["title"] = _("Financial Operation Details")
        context["subtitle"] = _("Complete financial details of this operation")
        context["active_page"] = "finance_page"
        context["header_paragraph"] = """
            This page displays full information about this operation, including 
            its amount, due date, payment history, and audit status. You may 
            edit the operation, upload proof files, or record payments here.
        """

        return context


class FinancialOperationCreateView(BaseModelView, CreateView):
    model = FinancialOperation
    fields = '__all__'
    success_url = reverse_lazy('finances:fiancial-operation-list')
    title = _("Add Financial Operation")
    subtitle = _("Fill in the form to record a new financial operation")


class FinancialOperationUpdateView(BaseModelView, UpdateView):
    model = FinancialOperation
    fields = '__all__'
    success_url = reverse_lazy('finances:fiancial-operation-list')
    title = _("Edit Financial Operation")
    subtitle = _("Fill in the form to update the financial operation")


# ------------------------------------------------------------------------
# Invoice
# ------------------------------------------------------------------------
class InvoiceListView(BaseListView):
    model = Invoice
    template_name = 'generic/index.html'
    partial_parent_directory = 'generic'
    context_object_name = 'objects'
    active_page = 'finance_page'
    title = _("Invoices")
    subtitle = _("View and manage all invoices issued by the pharmacy")
    header_paragraph = _(
        """
    This page provides an overview of all invoices issued by the pharmacy. 
    You can review invoice details such as amounts, due dates, payment 
    history, and status. You may also edit invoices, upload proof files, 
    or record payments here.
    """
    )

    object_crud_link = "finances:invoice-create"
    object_crud_via_htmx = True


class InvoiceDetailView(BaseDetailView):
    model = Invoice
    template_name = 'invoice/detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        invoice = self.object

        context["invoice"] = invoice
        context["title"] = _("Invoice Details")
        context["subtitle"] = _("Complete financial details of this invoice")
        context["active_page"] = "finance_page"
        context["header_paragraph"] = """
            This page displays full information about this invoice, including 
            its amount, due date, payment history, and audit status. You may 
            edit the invoice, upload proof files, or record payments here.
        """

        return context


class InvoiceCreateView(BaseModelView, CreateView):
    model = Invoice
    fields = [
        'invoice_number', 'title', 'description', 'amount', 'issue_date', 'due_date', 'proof_file',
    ]
    success_url = reverse_lazy('finances:invoice-list')
    title = _("Create Invoice")
    subtitle = _("Record a new invoice issued by the pharmacy")


class InvoiceUpdateView(BaseModelView, UpdateView):
    model = Invoice
    fields = [
        'invoice_number', 'title', 'amount', 'issue_date', 'due_date', 'proof_file','description',
    ]
    success_url = reverse_lazy('finances:invoice-list')
    title = _("Edit Invoice")
    subtitle = _("Modify details of this invoice")


# ------------------------------------------------------------------------
# Bill
# ------------------------------------------------------------------------
class BillListView(BaseListView):
    model = Bill
    template_name = 'generic/index.html'
    partial_parent_directory = 'generic'
    context_object_name = 'objects'
    active_page = 'finance_page'
    title = _("Bills")
    subtitle = _("View and manage all pharmacy bills and expenses")
    object_crud_link = "finances:bill-create"
    object_crud_via_htmx = True
    header_paragraph = _(
        """
    This page displays all pharmacy bills and expense records. You can 
    track amounts, vendors, due dates, payment progress, and auditing 
    status. Bills can be edited, updated with attachments, or marked 
    as paid.
    """
    )


class BillDetailView(BaseDetailView):
    model = Bill
    template_name = 'bill/detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        bill = self.object

        context["bill"] = bill
        context["title"] = _("Bill Details")
        context["subtitle"] = _("Complete financial details of this bill")
        context["active_page"] = "finance_page"
        context["related_payments"] = bill.payments.all()

        context["header_paragraph"] = """
            This page provides comprehensive details about this bill, including 
            its total amount, due date, payment history, and proof files. You 
            may edit the bill or record payments to update its status.
        """

        return context


class BillCreateView(BaseModelView, CreateView):
    model = Bill
    fields = [
        'bill_number', 'title', 'description', 'amount', 'bill_date', 'due_date', 'proof_file',
    ]
    success_url = reverse_lazy('finances:bill-list')
    title = _("Create Bill")
    subtitle = _("Record a new expense or vendor bill")


class BillUpdateView(BaseModelView, UpdateView):
    model = Bill
    fields = [
        'bill_number', 'title', 'amount', 'bill_date', 'due_date', 'proof_file', 'description',
    ]
    success_url = reverse_lazy('finances:bill-list')
    title = _("Edit Bill")
    subtitle = _("Update details of this bill")


# ------------------------------------------------------------------------
# Cash Closing views
# ------------------------------------------------------------------------
class CashClosingListView(BaseListView):
    model = CashClosing
    template_name = "generic/index.html"
    partial_parent_directory = "generic"
    context_object_name = "objects"
    active_page = "pharmacy_page"

    title = _("Cash Closings")
    subtitle = _("End-of-day cash counts")
    header_paragraph = _("View and manage daily cash closing sessions.")

    def get_queryset(self):
        qs = super().get_queryset()

        if not self.request.user.is_platform_admin:
            return qs

        return qs.filter(
            pharmacy=self.request.user.profile.current_pharmacy
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["object_crud_via_htmx"] = False

        if not self.request.user.is_platform_admin:
            context["active_page"] = "cash_closing_page"

        return context


class CashClosingDetailView(BaseDetailView):
    model = CashClosing
    template_name = "cash_closing/detail.html"
    context_object_name = "cash_closing"

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)

        # Recalculate balance_counted and difference on every view
        total_counted = obj.items.aggregate(
            total=Sum(F("denomination") * F("count"))
        )["total"] or 0

        if obj.balance_counted != total_counted or obj.difference != (total_counted - obj.balance_expected):
            obj.balance_counted = total_counted
            obj.difference = total_counted - (obj.balance_expected or 0)
            obj.save(update_fields=["balance_counted", "difference"])

        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context.update({
            "active_page": "pharmacy_page",
            "title": _("Cash Closing Details"),
            "subtitle": _("View closing session"),
            "header_paragraph": _("This page displays detailed denomination counts."),
        })

        if not self.request.user.is_platform_admin:
            context["active_page"] = "cash_closing_page"

        return context


class CashClosingUpsertView(BaseParentChildFormView):
    model = CashClosing
    form_class = CashClosingForm
    formset_class = CashClosingItemFormSet
    template_name = "generic/parent_child_form.html"

    title_create = "Create Cash Closing"
    subtitle_create = "Record end-of-day denomination counts."
    title_update = "Edit Cash Closing"
    subtitle_update = "Modify an existing cash closing."

    active_page = "pharmacy_page"
    header_paragraph = (
        "Use this form to count and validate all denominations "
        "before finalizing the daily cash closing."
    )

    success_url_name = "finances:cash-closing-detail"
    can_add_item = False  

    # ---------------------------
    # Set child fields
    # ---------------------------
    def set_child_fields(self, request, child_obj, parent_obj, is_create: bool):
        child_obj.cash_closing = parent_obj
        return child_obj

    # ---------------------------
    # Override form_valid to update totals after children saved
    # ---------------------------
    def form_valid(self, form, formset):
        # Save parent first
        self.object = form.save(commit=False)
        self.set_parent_fields(self.request, self.object,
                               is_create=not self.object.pk)
        self.object.save()

        # Save all child forms
        formset.instance = self.object
        formset.save()

        # Recalculate balance_counted and difference now that children exist
        total_counted = self.object.items.aggregate(
            total=Sum(F("denomination") * F("count"))
        )["total"] or 0

        print("goooooooooo")
        self.object.balance_counted = total_counted
        self.object.difference = total_counted - self.object.balance_expected
        self.object.save(update_fields=["balance_counted", "difference"])

        return super().form_valid(form, formset)


from django.utils.timezone import now, timedelta
@login_required(login_url="accounts:login")
def cash_closing_analytics(request):
    today = now().date()
    month_start = today.replace(day=1)

    org = request.user.profile.current_pharmacy

    qs = CashClosing.objects.filter(pharmacy=org)

    total_closings = qs.count()

    closings_this_month = qs.filter(
        closing_gate__date__gte=month_start
    ).count()

    total_difference = qs.aggregate(
        total_diff=Sum("difference")
    )["total_diff"] or 0

    total_expected = qs.aggregate(
        total_exp=Sum("balance_expected")
    )["total_exp"] or 0

    total_counted = qs.aggregate(
        total_cnt=Sum("balance_counted")
    )["total_cnt"] or 0

    # Last 7 closings trend
    recent = qs.order_by("-closing_date")[:7]

    labels = []
    differences = []

    for closing in reversed(recent):
        labels.append(closing.closing_date)
        differences.append(closing.difference)

    context = {
        "active_page": "cash_closing_analytics",
        "title": _("Cash Closing Analytics"),
        "header_paragraph": _("Monitor daily cash balancing performance."),

        "total_closings": total_closings,
        "closings_this_month": closings_this_month,
        "total_difference": total_difference,
        "total_expected": total_expected,
        "total_counted": total_counted,

        "labels": labels,
        "differences": differences,
    }

    return render(request, "cash/closing/analytics.html", context)
