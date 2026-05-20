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
from pharmadex.config.constants import CountryPreset, CurrencyPreset
from pharmadex.tenant import TenantManager
User = get_user_model()


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
class Currency(BaseModel):
    """
    Global currencies, pre-seeded by you. Organizations pick from list.
    No per-org setup needed.
    """

    preset = models.CharField(
        max_length=3,
        choices=CurrencyPreset.choices(),
        unique=True,
        verbose_name=_("Currency"),
        blank=True, null=True,
        help_text=_("ISO 4217 code. Locked after creation.")
    )

    country = models.CharField(
        max_length=2,
        choices=CountryPreset.choices(),
        verbose_name=_("Primary Country"),
        blank=True, null=True,
        help_text=_("Main market for this currency entry.")
    )

    # Auto-populated from preset
    name = models.CharField(max_length=100, editable=False)
    code = models.CharField(max_length=3, editable=False)
    symbol = models.CharField(max_length=10, editable=False)
    decimal_places = models.PositiveSmallIntegerField(default=2, editable=False)

    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Active"),
        help_text=_("Inactive currencies are hidden from selection.")
    )
    
    is_default_for_country = models.BooleanField(
        default=False,
        verbose_name=_("Default for Country"),
        help_text=_("Auto-selected when organization picks this country."),
    )

    class Meta:
        ordering = ('-is_active', '-is_default_for_country', 'name')
        verbose_name = _("Currency")
        verbose_name_plural = _("Currencies")

    def __str__(self):
        mark = " ★" if self.is_default_for_country else ""
        return f"{self.name} ({self.code}) — {self.symbol}{mark}"

    def save(self, *args, **kwargs):
        data = CurrencyPreset.get_data(self.preset)
        if data:
            self.name = data["name"]
            self.code = data["code"]
            self.symbol = data["symbol"]
            self.decimal_places = data["decimal_places"]
        super().save(*args, **kwargs)

    def format_amount(self, amount):
        if self.decimal_places == 0:
            return f"{self.symbol}{int(amount):,}"
        return f"{self.symbol}{amount:,.{self.decimal_places}f}"


class CurrencyDenomination(BaseModel):
    """
    Pharmacies available currency denominations (notes/coins).
    """
    currency = models.ForeignKey(
        Currency, on_delete=models.PROTECT, verbose_name=_(
            "Denomination Currency"),
    )
    value = models.DecimalField(max_digits=12, decimal_places=2)
    label = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-value",]
        constraints = [
            models.UniqueConstraint(
                fields=["currency", "value"],
                name="unique_currency_denomination"
            )
        ]

    def __str__(self):
        return self.label


class OrganizationCurrency(BaseModel):
    """
    Which currencies an organization operates in.
    One default for reporting. Others for local operations.
    """

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="currencies",
    )

    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name="organization_links",
    )

    is_default = models.BooleanField(
        default=False,
        verbose_name=_("Default Reporting Currency"),
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Active"),
    )

    display_symbol_first = models.BooleanField(
        default=True,
        verbose_name=_("Symbol Before Amount"),
        help_text=_("₦500 vs 500 ₦"),
    )

    class Meta:
        unique_together = [("organization", "currency")]
        constraints = [
            models.UniqueConstraint(
                fields=["organization"],
                condition=models.Q(is_default=True, is_active=True),
                name="one_active_default_per_org",
            ),
        ]

    def __str__(self):
        mark = " [DEFAULT]" if self.is_default else ""
        return f"{self.organization.name} → {self.currency.code}{mark}"

    def clean(self):
        if self.is_default and not self.is_active:
            raise ValidationError(_("Default currency must be active."))

    def save(self, *args, **kwargs):
        # First currency for org = auto-default
        if not self.pk and not self.organization.currencies.filter(is_default=True).exists():
            self.is_default = True

        # Unset other defaults if this becomes default
        if self.is_default:
            self.organization.currencies.filter(
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)

        super().save(*args, **kwargs)


class BankAccount(ActivatableModel, OrganizationModel):
    ACCOUNT_TYPE_CHOICES = [
        ('savings', _("Savings")),
        ('current', _("Current")),
        ('fix_deposit', _("Fix Deposit")),
    ]
    currency = models.ForeignKey(
        Currency, on_delete=models.PROTECT, verbose_name=_("Account Currency"),
    )
    bank_name = models.CharField(verbose_name=_("Bank Name"), max_length=255)
    account_name = models.CharField(
        verbose_name=_("Account Name"), max_length=255)
    account_number = models.CharField(
        verbose_name=_("Account Number"), max_length=255)
    account_type = models.CharField(verbose_name=_("Account Type"),
                                    max_length=20, default="current", choices=ACCOUNT_TYPE_CHOICES)
    current_balance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        verbose_name=_("Current Balance"),
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
        return f"{self.bank_name} - {self.account_name} ({self.account_number})"

    def get_balance(self):
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
        ('cash_drawer', _("Cash Drawer")),
        ('mobile_money', _("Mobile Money")),
    ]
    currency = models.ForeignKey(
        Currency, on_delete=models.PROTECT, verbose_name=_(
            "Cash Account Currency"),
    )
    name = models.CharField(verbose_name=_(
        "Cash Account Name"), max_length=100)
    code = models.CharField(
        _("Cash Account Code"), blank=True, null=True, max_length=100)
    account_type = models.CharField(
        max_length=20, choices=ACCOUNT_TYPE_CHOICES, verbose_name=_("Cash Account Type"))
    mobile_operator = models.ForeignKey(
        MobileOperator, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name=_("Mobile Operator"),
    )
    phone_number = PhoneNumberField(blank=True, null=True, verbose_name=_("Phone number")
                                    )
    current_balance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        verbose_name=_("Current Balance"),
    )
    model_icon = 'fa-solid fa-cash-register'
    model_icon_alt = 'fa-solid fa-mobile-retro'

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
        if self.account_type == 'mobile_money':
            if not self.mobile_operator:
                raise ValidationError(
                    _("A mobile operator is required for an mobile money account."))
            if not self.phone_number:
                raise ValidationError(
                    _("A phone number is required for an mobile money account."))

    def __str__(self):
        return f"{self.name} ({self.get_account_type_display()})"

    # ---------------------------------------------------------
    # Updated Cash Account properties
    # ---------------------------------------------------------
    def get_balance(self):
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


class OperationAccount(ActivatableModel, OrganizationModel):

    ACCOUNT_TYPE_CHOICES = [
        ("bank", _("Bank Account")),
        ("cash_drawer", _("Cash Drawer")),
    ]

    pharmacy = models.ForeignKey(
        "pharmacies.Pharmacy",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="financial_accounts",
        verbose_name=_("Pharmacy"),
    )

    account_type = models.CharField(
        max_length=40,
        choices=ACCOUNT_TYPE_CHOICES,
        verbose_name=_("Account Type"),
    )

    # -----------------------------
    # LINKS TO OPERATIONAL ACCOUNTS
    # -----------------------------
    cash_account = models.OneToOneField(
        "finances.CashAccount",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="financial_account",
        verbose_name=_("Cash Account"),
    )

    bank_account = models.OneToOneField(
        "finances.BankAccount",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="financial_account",
        verbose_name=_("Bank Account"),
    )

    class Meta:
        verbose_name = _("Financial Account")
        verbose_name_plural = _("Financial Accounts")

    def __str__(self):
        return f"{self.get_account_type_display()}"

    def clean(self):
        if self.account_type == "cash_drawer":
            if not self.cash_account:
                raise ValidationError(
                    _("Cash account is required for cash drawers."))
            if self.bank_account:
                raise ValidationError(
                    _("Cash drawers cannot have bank accounts."))

        if self.account_type == "bank":
            if not self.bank_account:
                raise ValidationError(
                    _("Bank account is required for bank accounts."))
            if self.cash_account:
                raise ValidationError(
                    _("Bank accounts cannot have cash accounts."))

        if not self.cash_account and not self.bank_account:
            raise ValidationError(
                _("A financial account must be linked to either cash or bank."))

    @property
    def account_object(self):
        """Returns the actual CashAccount or BankAccount instance"""
        if self.account_type == "cash_drawer" and self.cash_account:
            return self.cash_account
        elif self.account_type == "bank" and self.bank_account:
            return self.bank_account
        return None


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
        "finances.OperationAccount",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="outgoing_operations",
        verbose_name=_("Source Account")
    )

    destination_account = models.ForeignKey(
        "finances.OperationAccount",
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
        # FINANCING
        # -----------------------------
        if self.operation_type == "financing":

            if not self.destination_account:
                raise ValidationError(
                    _("FIancing must have a destination account.")
                )

            if self.source_account:
                raise ValidationError(
                    _("Financing cannot have an internal source account.")
                )

            return

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
        if self.operation_type == "revenue":

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
        if self.operation_type == "expense":

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
    def is_financing(self):
        return self.operation_type == "financing"

    @property
    def is_transfer(self):
        return self.operation_type == "transfer"

    @property
    def is_revenue(self):
        return self.operation_type == "revenue"

    @property
    def is_expense(self):
        return self.operation_type == "expense"

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

    @property
    def computed_status(self):
        paid = self.total_paid
        if paid <= 0:
            return "unpaid"
        elif paid < self.amount:
            return "partially_paid"
        else:
            return "fully_paid"

    def save(self, *args, **kwargs):
        # Don't touch status here
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

    @property
    def computed_status(self):
        paid = self.total_paid
        if paid <= 0:
            return "unpaid"
        elif paid < self.amount:
            return "partially_paid"
        else:
            return "fully_paid"

    def save(self, *args, **kwargs):
        # Don't touch status here
        super().save(*args, **kwargs)


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

    # -----------------------------------
    # BUSINESS MEANING
    # -----------------------------------
    payment_cause = models.CharField(
        max_length=32,
        choices=PAYMENT_CAUSE_CHOICES,
        verbose_name=_("Payment Cause"),
    )

    direction = models.CharField(
        max_length=3,
        choices=PAYMENT_DIRECTION_CHOICES,
        verbose_name=_("Payment Direction"),
    )

    # -----------------------------------
    # LINK TO BUSINESS OBJECT
    # -----------------------------------
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        verbose_name=_("Related Object Type"),
    )

    object_id = models.CharField(
        max_length=36,
        verbose_name=_("Related Object ID"),
    )

    content_object = GenericForeignKey("content_type", "object_id")

    # -----------------------------------
    # CORE FINANCIAL DATA
    # -----------------------------------
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name=_("Amount"),
    )

    operation_account = models.ForeignKey(
        "finances.OperationAccount",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        verbose_name=_("Operation Account"),
    )

    date = models.DateField(
        verbose_name=_("Payment Date"),
    )

    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Notes"),
    )

    proof_file = models.FileField(
        upload_to="finances/payments/proof_files",
        blank=True,
        null=True,
        verbose_name=_("Proof File"),
    )

    model_icon = "fa-solid fa-hand-holding-dollar"

    class Meta:
        ordering = ("-date",)
        verbose_name = _("Payment")
        verbose_name_plural = _("Payments")

    def __str__(self):
        return f"{self.payment_cause} - {self.amount} ({self.date})"

    # -----------------------------------
    # VALIDATION
    # -----------------------------------
    def clean(self):
        if self.amount <= 0:
            raise ValidationError(_("Amount must be greater than zero."))

        if not self.operation_account:
            raise ValidationError(_("Operation account is required."))

        if self.payment_cause in ("sale", "invoice", "clinical_service") and self.direction != "in":
            raise ValidationError(
                _("This payment type must be incoming.")
            )

        if self.payment_cause in ("purchase", "bill") and self.direction != "out":
            raise ValidationError(
                _("This payment type must be outgoing.")
            )

    # -----------------------------------
    # SAVE → GENERATE LEDGER ENTRY
    # -----------------------------------
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        if FinancialOperation.objects.filter(content_object=self).exists():
            return

        # Determine operation type from payment cause
        op_type = {
            "sale": "revenue",
            "invoice": "revenue",
            "clinical_service": "revenue",
            "purchase": "expense",
            "bill": "expense",
            "refund": "expense",  # or revenue depending on direction
            "advance": "financing",
        }.get(self.payment_cause, "revenue")

        # Get pharmacy/org from operation_account
        pharmacy = self.operation_account.pharmacy if self.operation_account else None
        org = self.operation_account.organization if self.operation_account else None

        FinancialOperation.objects.create(
            label=f"Payment - {self.payment_cause}",
            amount=self.amount,
            date=self.date,
            content_object=self,
            operation_type=op_type,
            operation_subtype=f"{self.payment_cause}_{self.direction}",
            source_account=None if self.direction == "in" else self.operation_account,
            destination_account=self.operation_account if self.direction == "in" else None,
            pharmacy=pharmacy,
            organization=org,
            reference=f"PAY-{self.id}",
        )

    # -----------------------------------
    # DISPLAY HELPERS
    # -----------------------------------
    @property
    def display_operation_account(self):
        return str(self.operation_account)

    @property
    def is_incoming(self):
        return self.direction == "in"

    @property
    def is_outgoing(self):
        return self.direction == "out"


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
