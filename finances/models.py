from django.db.models import Sum
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
from itertools import chain
from django.db.models import Sum, Case, Q, When, F, DecimalField, Value
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from phonenumber_field.modelfields import PhoneNumberField
from calendar import monthrange
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Sum, F, Value
from django.db.models.functions import Coalesce
from base.models import ActivatableModel, ArchivableModel, BaseModel, OrganizationModel, PharmacyModel

#  ------------------------------------
# User model import
#  ------------------------------------
from django.contrib.auth import get_user_model
from clinics.models import ClinicalService
from pharmadex import settings
from pharmadex.tenant import TenantManager
from pharmacies.models import PurchaseDelivery, Sale #Purchase,
User = get_user_model()

FINANCIAL_ACCOUNT_CHOICES = [
    ("cash_account", _("Cash Desk")),
    ("bank_account", _("Bank Account")),
]

PAYMENT_STATUS_CHOICES = [
    ("unpaid", _("Unpaid")),
    ("partly_paid", _("Partly Paid")),
    ("fully_paid", _("Fully Paid")),
]

PAYMENT_METHOD_CHOICES = [
    ("cash", _("Cash")),
    ("mobile_money", _("Mobile Money")),
    ("bank_transfer", _("Bank Transfer")),
    ("cheque", _("Cheque")),
    ("other", _("Other")),
]


#  ---------------------------------------------------------
# Financial Parameters Models
#  ---------------------------------------------------------
class Currency(ActivatableModel, OrganizationModel):
    name = models.CharField(verbose_name=_("Currency Name"), max_length=100)
    code = models.CharField(verbose_name=_("Currency Code"), max_length=100)
    symbol = models.CharField(verbose_name=_(
        "Currency Symbol"), max_length=100)
    is_default = models.BooleanField(
        default=False, verbose_name=_("Is Default Currency"))

    model_icon = 'fa-solid fa-dollar-sign'

    class Meta:
        ordering = ('name',)
        verbose_name = _("Currency")
        verbose_name_plural = _("Currencies")
        permissions = [
            ("import_currency", "Can import currency"),
            ("export_currency", "Can export currency"),
            ("manage_currencie", "Can manage all currencies"),
        ]

    def __str__(self):
        return f'{self.code}-({self.symbol})'

        return self.__class__.__name__


class CurrencyDenomination(OrganizationModel):
    """
    Pharmacies available currency denominations (notes/coins).
    """
    currency = models.ForeignKey(
        Currency, on_delete=models.PROTECT, verbose_name=_(
            "Denomination Currency"),
    )
    value = models.PositiveIntegerField(unique=True)
    label = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-value"]

    def __str__(self):
        return self.label


class BankAccount(ActivatableModel, OrganizationModel):
    ACCOUNT_TYPE_CHOICES = [
        ('savings', _("Savings")),
        ('current', _("Current")),
        ('fix_deposit', _("Fix Deposit")),
    ]
    bank_name = models.CharField(verbose_name=_("Bank Name"), max_length=255)
    account_name = models.CharField(
        verbose_name=_("Account Name"), max_length=255)
    account_number = models.CharField(
        verbose_name=_("Account Number"), max_length=255)
    account_type = models.CharField(verbose_name=_("Account Type"),
                                    max_length=20, default="current", choices=ACCOUNT_TYPE_CHOICES)
    currency = models.ForeignKey(
        Currency, on_delete=models.PROTECT, verbose_name=_("Account Currency"),
    )

    model_icon = 'fa-solid fa-university'

    class Meta:
        ordering = ('account_name',)
        verbose_name = _("Bank Account")
        verbose_name_plural = _("Bank Accounts")
        permissions = [
            ("import_bankaccount", "Can import bank account"),
            ("export_bankaccount", "Can export bank account"),
            ("manage_bankaccount", "Can manage all bank accounts"),
        ]

    def toggle_active(self):
        self.is_active = not self.is_active
        self.save()

    def __str__(self):
        return f"{self.bank_name} {self.name} ({self.account_number})"

    def get_balance(self):
        from finances.models import FinancialOperation
        money_in = FinancialOperation.objects.filter(
            destination_bank=self
        ).aggregate(total=Sum("amount"))["total"] or 0

        money_out = FinancialOperation.objects.filter(
            source_bank=self
        ).aggregate(total=Sum("amount"))["total"] or 0

        return money_in - money_out


class MobileOperator(ActivatableModel, OrganizationModel):
    name = models.CharField(verbose_name=_("Mobile Operator Name"),
                            max_length=100, unique=True)
    service_name = models.CharField(
        _("Operator Service Alias (Name)"), max_length=100)

    model_icon = 'fa-solid fa-tower-cell'

    class Meta:
        ordering = ('name',)
        verbose_name = _("Mobile Operator")
        verbose_name_plural = _("Mobile Operators")
        permissions = [
            ("import_mobileoperator", "Can import mobile operator"),
            ("export_mobileoperator", "Can export mobile operator"),
            ("manage_mobileoperator", "Can manage all mobile operators"),
        ]

    def __str__(self):
        return f"{self.name} ({self.service_name})"

        return self.__class__.__name__


class CashAccount(ActivatableModel, PharmacyModel):
    ACCOUNT_TYPE_CHOICES = [
        ('electronic', _("Electronic")),
        ('physical', _("Physical")),
    ]
    name = models.CharField(verbose_name=_("Cash Account Name"), max_length=100)
    code = models.CharField(
        _("Cash Account Code"), blank=True, null=True, max_length=100)
    account_type = models.CharField(verbose_name=_("Cash Account Type"),
                                     max_length=20, choices=ACCOUNT_TYPE_CHOICES)
    mobile_operator = models.ForeignKey(
        MobileOperator, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name=_("Mobile Operator"),
    )
    phone_number = PhoneNumberField(blank=True, null=True, verbose_name=_("Phone number")
                                    )
    currency = models.ForeignKey(
        Currency, on_delete=models.PROTECT, verbose_name=_(
            "Cash Account Currency"),
    )

    model_icon = 'fa-solid fa-cash-register'
    model_icon_alt = 'fa-solid fa-cash-register'

    class Meta:
        ordering = ('name',)
        verbose_name = _("Cash Desk")
        verbose_name_plural = _("Cash Desks")
        constraints = [
            models.UniqueConstraint(
                fields=['pharmacy', 'code'],
                name='unique_cash_account_code_per_pharmacy'
            )
        ]
        permissions = [
            ("import_cash_account", "Can import cash_account"),
            ("export_cash_account", "Can export cash_account"),
            ("manage_cash_account", "Can manage all cash_accounts"),
        ]

    def clean(self):
        if self.account_type == 'electronic':
            if not self.operator:
                raise ValidationError(
                    _("An operator is required for an electronic cash_account."))
            if not self.phone:
                raise ValidationError(
                    _("A phone number is required for an electronic cash_account."))

    def __str__(self):
        return f"{self.name} ({self.get_account_type_display()})"

    # ---------------------------------------------------------
    # Updated Cash Account properties
    # ---------------------------------------------------------
    def get_balance(self):
        from finances.models import FinancialOperation
        money_in = FinancialOperation.objects.filter(
            pharmacy=self.pharmacy,
            destination_cash_account=self
        ).aggregate(total=Sum("amount"))["total"] or 0

        money_out = FinancialOperation.objects.filter(
            pharmacy=self.pharmacy,
            source_cash_account=self
        ).aggregate(total=Sum("amount"))["total"] or 0

        return money_in - money_out

    @property
    def operations_count(self):
        """
        Total number of operations where this cash_account is source or destination.
        """
        return FinancialOperation.objects.filter(
            Q(source_cash_account=self) | Q(destination_cash_account=self)
        ).count()

    @property
    def revenue_operations_count(self):
        """
        Total number of revenue operations where this cash_account is involved.
        """
        return FinancialOperation.objects.filter(
            Q(source_cash_account=self) | Q(destination_cash_account=self),
            operation_type='revenue'
        ).count()

    @property
    def expense_operations_count(self):
        """
        Total number of expense operations where this cash_account is involved.
        """
        return FinancialOperation.objects.filter(
            Q(source_cash_account=self) | Q(destination_cash_account=self),
            operation_type='expense'
        ).count()

    @property
    def transfer_operations_count(self):
        """
        Total number of transfer operations involving this cash_account.
        """
        return FinancialOperation.objects.filter(
            Q(source_cash_account=self) | Q(destination_cash_account=self),
            operation_type='transfer'
        ).count()

    @property
    def total_revenue(self):
        """
        Sum of all revenue amounts where this cash_account is source or destination.
        """
        return FinancialOperation.objects.filter(
            Q(source_cash_account=self) | Q(destination_cash_account=self),
            operation_type='revenue'
        ).aggregate(total=Sum('amount'))['total'] or 0

    @property
    def total_expenses(self):
        """
        Sum of all expense amounts where this cash_account is source or destination.
        """
        return FinancialOperation.objects.filter(
            Q(source_cash_account=self) | Q(destination_cash_account=self),
            operation_type='expense'
        ).aggregate(total=Sum('amount'))['total'] or 0

    @property
    def total_balance(self):
        """
        Net balance for this cash_account: revenue minus expenses.
        """
        return self.total_revenue - self.total_expenses


class FinancialAccount(ActivatableModel, OrganizationModel):

    ACCOUNT_TYPE_CHOICES = [
        ("bank", _("Bank Account")),
        ("cash", _("Cash Account")),
    ]

    pharmacy = models.ForeignKey(
        "pharmacies.Pharmacy",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="financial_accounts",
        verbose_name=_("Pharmacy")
    )

    account_type = models.CharField(
        max_length=20,
        choices=ACCOUNT_TYPE_CHOICES
    )

    # Generic relation → BankAccount OR CashAccount
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE
    )
    object_id = models.CharField(max_length=36)
    account_object = GenericForeignKey("content_type", "object_id")

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("content_type", "object_id")
        verbose_name = _("Financial Account")
        verbose_name_plural = _("Financial Accounts")

    def __str__(self):
        return f"{self.get_account_type_display()} - {self.account_object}"

    # ---------------------------------------------------------
    # BALANCE (unified)
    # ---------------------------------------------------------
    def get_balance(self):

        money_in = FinancialOperation.objects.filter(
            destination_account=self
        ).aggregate(total=Sum("amount"))["total"] or 0

        money_out = FinancialOperation.objects.filter(
            source_account=self
        ).aggregate(total=Sum("amount"))["total"] or 0

        return money_in - money_out


# ----------------------------------------------------------
# Auditing Models
# ----------------------------------------------------------
class AuditBatch(PharmacyModel, ArchivableModel):
    name = models.CharField(max_length=255)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='created_batches')
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_batches')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=50, choices=[
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], default='pending')

    model_icon = 'fa-solid fa-stamp'

    class Meta:
        ordering = ('name',)
        verbose_name = _("Audit Batch")
        verbose_name_plural = _("Audit Batches")
        permissions = [
            ("import_auditbatch", "Can import audit batch"),
            ("export_auditbatch", "Can export audit batch"),
            ("manage_auditbatch", "Can manage all audit batches"),
        ]

    def __str__(self):
        return f"Audit Batch #{self.id} - {self.name}"

    def get_all_items(self):
        """Dynamically return all related objects for this batch."""
        items = {}
        for rel in self._meta.related_objects:
            related_name = rel.get_accessor_name()
            manager = getattr(self, related_name, None)
            if manager is not None:
                items[related_name] = manager.all()
        return items

    def all_finance_records(self):
        """Return a single iterable of all finance records in this batch."""
        all_items = self.get_all_items()
        return list(chain.from_iterable(all_items.values()))

    def approve(self, reviewer):
        self.status = 'approved'
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.save()

    def reject(self, reviewer):
        self.status = 'rejected'
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.save()


#  ---------------------------------------------------------
# Financial Operations Models
#  ---------------------------------------------------------
class FinancialOperation(PharmacyModel, ArchivableModel):

    OPERATION_TYPE_CHOICES = [
        ("revenue", _("Revenue")),  # Money coming in
        ("expense", _("Expense")),  # Money going out
        ("transfer", _("Transfer")),  # Internal movement of money
        ("financing", _("Financing")),  # Owner equity/loans/drawings
    ]

    OPERATION_SUBTYPE_CHOICES = [
        # --- Revenue ---
        ("product_sale", _("Product Sales")),
        ("consultation", _("Consultation Fees")),
        ("insurance_reimbursement", _("Insurance Reimbursement")),
        ("other_income", _("Other Income")),

        # --- Expenses ---
        ("product_purchase", _("Product Purchase")),
        ("salary", _("Salary Expense")),
        ("rent", _("Rent")),
        ("utilities", _("Utilities")),
        ("equipment", _("Equipment Purchase")),
        ("other_expense", _("Other Expense")),

        # --- Transfers (internal movement) ---
        ("cash_account_to_cash_account", _("Cash Account → Cash Account")),
        ("cash_account_to_bank", _("Cash Account → Bank")),
        ("bank_to_cash_account", _("Bank → Cash Account")),
        ("bank_to_bank", _("Bank → Bank")),

        # --- Financing ---
        ("owner_equity", _("Owner Equity Injection")),
        ("owner_loan", _("Owner Loan to Pharmacy")),
        ("loan_repayment", _("Loan Repayment")),
        ("owner_withdrawal", _("Owner Withdrawal")),   # Drawings
    ]

    # ---------------------------------------------------------
    # UNIFIED ACCOUNTS
    # ---------------------------------------------------------
    source_account = models.ForeignKey(
        "finances.FinancialAccount",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="outgoing_operations",
        verbose_name=_("Source Account")
    )

    destination_account = models.ForeignKey(
        "finances.FinancialAccount",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="incoming_operations",
        verbose_name=_("Destination Account")
    )

    # ---------------------------------------------------------
    # CORE FIELDS
    # ---------------------------------------------------------
    label = models.CharField(_("Operation Label"), max_length=100)
    description = models.TextField(_("Operation Description"), max_length=255)

    operation_type = models.CharField(
        _("Operation Type"),
        max_length=20,
        choices=OPERATION_TYPE_CHOICES
    )

    operation_subtype = models.CharField(
        _("Operation Subtype"),
        max_length=40,
        choices=OPERATION_SUBTYPE_CHOICES,
        blank=True,
        null=True
    )

    amount = models.DecimalField(
        _("Amount"),
        max_digits=12,
        decimal_places=2
    )

    date = models.DateField(_("Operation Date"))

    # ---------------------------------------------------------
    # OPTIONAL LINK (invoice, sale, etc.)
    # ---------------------------------------------------------
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        blank=True,
        null=True
    )
    object_id = models.CharField(max_length=36, blank=True, null=True)
    content_object = GenericForeignKey("content_type", "object_id")

    # ---------------------------------------------------------
    # META / TRACKING
    # ---------------------------------------------------------
    proof_file = models.FileField(
        upload_to="finances/operations/proof_files",
        blank=True,
        null=True,
        verbose_name=_("Proof File")
    )

    audit_batch = models.ForeignKey(
        "finances.AuditBatch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="financial_operations"
    )

    reference = models.CharField(
        _("Reference"),
        max_length=50,
        unique=True
    )

    model_icon = "fa-solid fa-money-bill-transfer"

    class Meta:
        ordering = ("-date", "-created_at")
        verbose_name = _("Financial Operation")
        verbose_name_plural = _("Financial Operations")
        permissions = [
            ("export_financialoperation", "Can export financial operation"),
            ("manage_financialoperation", "Can manage all financial operations"),
        ]

    def __str__(self):
        return f"{self.label} - {self.amount} ({self.date})"

    # ---------------------------------------------------------
    # VALIDATION
    # ---------------------------------------------------------
    def clean(self):

        if self.amount <= 0:
            raise ValidationError(_("Amount must be greater than zero."))

        # -----------------------------
        # TRANSFER
        # -----------------------------
        if self.operation_type == "transfer":

            if not self.source_account or not self.destination_account:
                raise ValidationError(
                    _("Transfer must have both source and destination accounts.")
                )

            if self.source_account == self.destination_account:
                raise ValidationError(
                    _("Source and destination accounts cannot be the same.")
                )

            return

        # -----------------------------
        # INFLOW (money coming in)
        # -----------------------------
        if self.operation_type == "inflow":

            if not self.destination_account:
                raise ValidationError(
                    _("Money In operations must have a destination account.")
                )

            if self.source_account:
                raise ValidationError(
                    _("Money In operations should not have a source account.")
                )

        # -----------------------------
        # OUTFLOW (money going out)
        # -----------------------------
        if self.operation_type == "outflow":

            if not self.source_account:
                raise ValidationError(
                    _("Money Out operations must have a source account.")
                )

            if self.destination_account:
                raise ValidationError(
                    _("Money Out operations should not have a destination account.")
                )

    # ---------------------------------------------------------
    # CONVENIENCE
    # ---------------------------------------------------------
    @property
    def is_transfer(self):
        return self.operation_type == "transfer"

    @property
    def is_inflow(self):
        return self.operation_type == "inflow"

    @property
    def is_outflow(self):
        return self.operation_type == "outflow"

    @property
    def source(self):
        return self.source_account.account_object if self.source_account else None

    @property
    def destination(self):
        return self.destination_account.account_object if self.destination_account else None


class Invoice(PharmacyModel, ArchivableModel):
    invoice_number = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        null=True,
        verbose_name=_("Unique invoice identifier (e.g., INV-2025-001)"),
    )

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    amount = models.DecimalField(max_digits=12, decimal_places=2)

    issue_date = models.DateField()
    due_date = models.DateField()

    proof_file = models.FileField(
        upload_to="finances/invoices/proof_files",
        blank=True,
        null=True,
        verbose_name=_("Proof File"),
    )

    content_type = models.ForeignKey(
        ContentType,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        verbose_name=_("Related Object Type"),
    )
    object_id = models.CharField(max_length=36, blank=True, null=True)
    content_object = GenericForeignKey("content_type", "object_id")

    status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default="unpaid",
        verbose_name=_("Status"),
    )

    model_icon = "fa-solid fa-file-invoice-dollar"

    class Meta:
        ordering = ("-created_at",)
        verbose_name = _("Invoice")
        verbose_name_plural = _("Invoices")
        permissions = [
            ("import_invoice", "Can import invoice"),
            ("export_invoice", "Can export invoice"),
            ("manage_invoice", "Can manage all invoices"),
        ]

    def __str__(self):
        return f"Invoice {self.invoice_number or self.pk}: {self.title}"

    @property
    def payments(self):
        from finances.utils import get_payments_for
        return get_payments_for(self)

    @property
    def total_paid(self):
        return sum(p.amount for p in self.payments)

    @property
    def balance(self):
        return self.amount - self.total_paid

    def save(self, *args, **kwargs):
        # Set status automatically on save
        if self.total_paid <= 0:
            self.status = "unpaid"
        elif self.total_paid > 0 and self.total_paid < self.amount:
            self.status = "partially_paid"
        else:
            self.status = "fully_paid"

        super().save(*args, **kwargs)


class Bill(PharmacyModel, ArchivableModel):
    bill_number = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        null=True,
        verbose_name=_("Bill Number"),
    )

    title = models.CharField(max_length=255, verbose_name=_("Title"))
    description = models.TextField(blank=True, null=True)

    amount = models.DecimalField(max_digits=12, decimal_places=2)

    bill_date = models.DateField(verbose_name=_("Issue Date"))
    due_date = models.DateField(verbose_name=_("Due Date"))

    proof_file = models.FileField(
        upload_to="finances/bills/proof_files",
        blank=True,
        null=True,
        verbose_name=_("Proof File"),
    )

    # What this bill is for (purchase, supplier, service, etc.)
    content_type = models.ForeignKey(
        ContentType,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        verbose_name=_("Related Object Type"),
    )
    object_id = models.CharField(max_length=36, blank=True, null=True)
    content_object = GenericForeignKey("content_type", "object_id")

    status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default="unpaid",
        verbose_name=_("Status"),
    )

    model_icon = "fa-solid fa-file-invoice"

    class Meta:
        ordering = ("-created_at",)
        verbose_name = _("Bill")
        verbose_name_plural = _("Bills")
        permissions = [
            ("import_bill", "Can import bill"),
            ("export_bill", "Can export bill"),
            ("manage_bill", "Can manage all bills"),
        ]

    def __str__(self):
        return f"Bill {self.bill_number or self.pk}: {self.title}"

    @property
    def payments(self):
        from finances.utils import get_payments_for
        return get_payments_for(self)

    @property
    def total_paid(self):
        return sum(p.amount for p in self.payments)

    @property
    def balance(self):
        return self.amount - self.total_paid

    def save(self, *args, **kwargs):
        # Set status automatically on save
        if self.total_paid <= 0:
            self.status = "unpaid"
        elif self.total_paid > 0 and self.total_paid < self.amount:
            self.status = "partially_paid"
        else:
            self.status = "fully_paid"

        super().save(*args, **kwargs)


ALLOWED_PAYMENT_MODELS = {
    "sale": Sale,
    "purchase": PurchaseDelivery,
    "service": ClinicalService,
    "invoice": Invoice,
    "bill": Bill,
}


class Payment(PharmacyModel, ArchivableModel):

    PAYMENT_DIRECTION_CHOICES = (
        ("in", _("Incoming")),
        ("out", _("Outgoing")),
    )

    PAYMENT_CAUSE_CHOICES = (
        ("sale", _("Sale")),
        ("purchase", _("Purchase")),
        ("invoice", _("Invoice")),
        ("bill", _("Bill")),
        ("refund", _("Refund")),
        ("advance", _("Advance Payment")),
        ("clinical_service", _("Clinical Service")),
    )

    # Semantic meaning (WHY this payment exists)
    payment_cause = models.CharField(
        max_length=32, choices=PAYMENT_CAUSE_CHOICES, verbose_name=_("Payment Cause"))

    # Direction of money
    direction = models.CharField(
        max_length=3, choices=PAYMENT_DIRECTION_CHOICES, verbose_name=_("Payment Direction"))

    # Generic link to payable / receivable object
    content_type = models.ForeignKey(
        ContentType, on_delete=models.PROTECT, verbose_name=_("Related Object Type"))

    object_id = models.CharField(
        max_length=36, verbose_name=_("Related Object ID"))

    content_object = GenericForeignKey("content_type", "object_id")

    amount = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name=_("Amount"))

    financial_account = models.CharField(
        max_length=50, choices=FINANCIAL_ACCOUNT_CHOICES, default="cash_account", verbose_name=_("Financial Account"))

    cash_account = models.ForeignKey("finances.CashAccount", on_delete=models.SET_NULL,
                                 null=True, blank=True, related_name="payments", verbose_name=_("CashAccount"))

    bank_account = models.ForeignKey("finances.BankAccount", on_delete=models.SET_NULL,
                                     null=True, blank=True, related_name="payments", verbose_name=_("Bank Account"))

    date = models.DateField(verbose_name=_("Payment Date"))

    notes = models.TextField(blank=True, null=True)

    proof_file = models.FileField(
        upload_to="finances/payments/proof_files",
        blank=True,
        null=True
    )

    model_icon = 'fa-solid fa-hand-holding-dollar'

    class Meta:
        ordering = ("-date",)
        verbose_name = _("Payment")
        verbose_name_plural = _("Payments")

    def clean(self):
        # Validate payment source
        if self.financial_account == "cash_account" and not self.cash_account:
            raise ValidationError(verbose_name=_(
                "Cash Account is required for cash payments."))

        if self.financial_account == "bank_account" and not self.bank_account:
            raise ValidationError(
                _("Bank account is required for bank payments."))

        # Validate cause ↔ model consistency
        model = ALLOWED_PAYMENT_MODELS.get(self.payment_cause)
        if not model:
            raise ValidationError(verbose_name=_("Invalid payment cause."))

        expected_ct = ContentType.objects.get_for_model(model)
        if self.content_type != expected_ct:
            raise ValidationError(
                _("Payment cause does not match related document type.")
            )

        # Validate direction
        if self.payment_cause in ("sale", "invoice") and self.direction != "in":
            raise ValidationError(
                _("Sales and invoices must be incoming payments."))
            
        if self.payment_cause == "clinical_service" and self.direction != "in":
            raise ValidationError(
                _("Clinical service payments must be incoming.")
            )

        if self.payment_cause in ("purchase", "bill") and self.direction != "out":
            raise ValidationError(
                _("Purchases and bills must be outgoing payments."))

    @property
    def display_financial_account(self):
        """
        Combines financial_account with bank or cash_account info.
        """
        fin_info = ""
        if self.financial_account:
            if self.bank_account:
                fin_info = f"Bank Account | {self.bank_account}"
            elif self.cash_account:
                fin_info = f"Cash Account | {self.cash_account}"
            return fin_info
        return "—"


# -------------------------------
# Cash Closing
# -------------------------------
class CashClosing(ArchivableModel, PharmacyModel):
    """
    End-of-day cash count for a pharmacy, broken down by notes and coins.
    """
    TENANT_FILTER = "pharmacy"
    closing_date = models.DateField(default=timezone.localdate, verbose_name=_("Date of Activity"),
                                    help_text="The date for which this cash closing applies."
                                    )
    initiator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                  blank=True, null=True, related_name='cash_closings_initiated')
    validator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                  blank=True, null=True, related_name='cash_closings_validated')

    balance_expected = models.BigIntegerField(
        default=0, editable=False, verbose_name=_("Expected Balance"))
    balance_counted = models.BigIntegerField(
        default=0, verbose_name=_("Counted Balance"))
    difference = models.BigIntegerField(
        default=0, verbose_name=_("Difference"))

    comment = models.TextField(blank=True, null=True)

    model_icon = "fa-solid fa-cash-register"

    class Meta:
        ordering = ['-closing_date']
        verbose_name = "Cash Closing"
        verbose_name_plural = "Cash Closings"

    def __str__(self):
        return f"{self.pharmacy} | {self.closing_date} | Δ {self.difference}"

    def save(self, *args, **kwargs):
        # Sum total from items if present
        if hasattr(self, "items"):
            self.balance_counted = sum(
                item.total_amount for item in self.items.all())
        self.difference = self.balance_counted - (self.balance_expected or 0)
        super().save(*args, **kwargs)


class CashClosingItem(ArchivableModel):
    TENANT_FILTER = "cash_closing__pharmacy"
    objects = TenantManager()

    cash_closing = models.ForeignKey(
        CashClosing,
        on_delete=models.CASCADE,
        related_name="items"
    )

    denomination = models.ForeignKey(
        CurrencyDenomination,
        on_delete=models.PROTECT,
        related_name="cash_items"
    )

    count = models.PositiveIntegerField(default=0)
    total_amount = models.BigIntegerField(default=0, editable=False)

    model_icon = "fa-solid fa-money-bills"

    class Meta:
        ordering = ['denomination__value']
        constraints = [
            models.UniqueConstraint(
                fields=["cash_closing", "denomination"],
                name="unique_denomination_per_closure"
            )
        ]

    def save(self, *args, **kwargs):
        self.total_amount = self.denomination.value * self.count
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.count} x {self.denomination.label} = {self.total_amount}"
