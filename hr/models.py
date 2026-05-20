
from django.db.models import Max
from django.db.models import Sum, Case, Q, When, F, DecimalField, Value
from django.utils.translation import gettext_lazy as _
from base.models import ActivatableModel, BaseModel, OrganizationModel, ArchivableModel
from base.utils import CURRENT_YEAR, GENDER_CHOICES, MONTH_CHOICES, YEAR_CHOICES
from decimal import Decimal
from django.db import models
from django.db.models import Sum
from django.utils import timezone
from django.core.exceptions import ValidationError
from phonenumber_field.modelfields import PhoneNumberField
from pharmadex import settings
from pharmadex.tenant import TenantManager


#  ------------------------------------
# User model import
#  ------------------------------------
from django.contrib.auth import get_user_model
User = get_user_model()


class Staff(OrganizationModel, ActivatableModel):
    """
    Staff member linked to system user account.
    """

    objects = TenantManager()

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="staff_profile",
        verbose_name=_("User")
    )

    staff_id = models.CharField(
        max_length=50,
        db_index=True,
        blank=True, null=True,
        verbose_name=_("Staff ID")
    )

    model_icon = "fa-solid fa-user-tie"

    class Meta:
        verbose_name = _("Staff")
        verbose_name_plural = _("Staff")
        unique_together = ('organization', 'staff_id')

    @property
    def full_name(self):
        return self.user.full_name

    def __str__(self):
        return f"{self.staff_id} - {self.full_name}"


# ---------------------------------------------------------
# Salary Scale
# ---------------------------------------------------------
class SalaryScale(OrganizationModel):

    GROUP_CHOICES = [
        ('pharmacist', _('Pharmacist')),
        ('doctor', _('Doctor')),
        ('cashier', _('Cashier')),
        ('pharmacy_manager', _('Pharmacy Manager')),
        ('inventory_manager', _('Inventory Manager')),
        ('vendor', _('Vendor')),
        ('support_staff', _('Support Staff')),
    ]

    staff_group = models.CharField(
        max_length=50,
        choices=GROUP_CHOICES,
    )

    base_salary = models.DecimalField(max_digits=12, decimal_places=2)

    # ---- Allowances (pharmacy-relevant) ----
    housing_allowance = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)
    transport_allowance = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)

    # Added pharmacy-specific allowances
    risk_allowance = models.DecimalField(  # exposure to meds / chemicals
        max_digits=12, decimal_places=2, default=0
    )
    shift_allowance = models.DecimalField(  # night / weekend shifts
        max_digits=12, decimal_places=2, default=0
    )
    other_allowance = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)

    # ---- Deductions ----
    deductions = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )

    effective_from = models.DateField()

    model_icon = 'fa-solid fa-money-check-dollar'

    class Meta:
        ordering = ['-effective_from']
        unique_together = ('staff_group', 'effective_from')

    def __str__(self):
        return f"{self.get_staff_group_display()} — {self.effective_from}"

    # ---- Salary Calculations ----
    @property
    def gross_salary(self):
        return (
            self.base_salary
            + self.housing_allowance
            + self.transport_allowance
            + self.risk_allowance
            + self.shift_allowance
            + self.other_allowance
        )

    @property
    def net_salary(self):
        return self.gross_salary - self.deductions


# ---------------------------------------------------------
# Payroll (Payslip / Obligation)
# ---------------------------------------------------------
def payslip_upload_path(instance, filename):
    return f"payroll/payslips/staff_{instance.staff_id}/{filename}"


class PayrollItem(ArchivableModel, OrganizationModel):

    staff = models.ForeignKey(
        "hr.Staff",
        on_delete=models.PROTECT,
        related_name="payroll_items",
    )

    salary_scale = models.ForeignKey(
        SalaryScale,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    payroll_month = models.PositiveSmallIntegerField(choices=MONTH_CHOICES)
    payroll_year = models.PositiveSmallIntegerField(choices=YEAR_CHOICES)

    # Optional override (if needed)
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    approved_on = models.DateField(default=timezone.now)

    # NEW: Payslip file
    payslip_file = models.FileField(
        upload_to=payslip_upload_path,
        blank=True,
        null=True
    )

    note = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ("-payroll_year", "-payroll_month", "-created_at")
        unique_together = ('staff', 'payroll_month', 'payroll_year')

    def __str__(self):
        return f"{self.staff} — {self.payroll_month}/{self.payroll_year}"

    # -------------------------
    # Computed fields
    # -------------------------
    @property
    def total_paid(self):
        return self.transactions.filter(status="completed").aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0.00")

    @property
    def balance(self):
        return max(self.amount - self.total_paid, Decimal("0.00"))

    @property
    def status(self):
        if self.total_paid == 0:
            return "pending"
        elif self.total_paid < self.amount:
            return "partial"
        return "fully_paid"
    
    def save(self, *args, **kwargs):
        if not self.amount and self.salary_scale:
            self.amount = self.salary_scale.net_salary
        super().save(*args, **kwargs)


# ---------------------------------------------------------
# Payroll Breakdown (Earnings & Deductions)
# ---------------------------------------------------------
class PayrollItemLine(BaseModel):

    LINE_TYPE = (
        ("earning", "Earning"),
        ("deduction", "Deduction"),
    )

    payroll_item = models.ForeignKey(
        PayrollItem,
        related_name="lines",
        on_delete=models.CASCADE
    )

    line_type = models.CharField(max_length=20, choices=LINE_TYPE)
    name = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.name} ({self.line_type}) - {self.amount}"


# ---------------------------------------------------------
# Payroll Transactions (Payments)
# ---------------------------------------------------------
def payroll_proof_upload_path(instance, filename):
    return f"payroll/payments/staff_{instance.payroll_item.staff_id}/{filename}"


class PayrollTransaction(ArchivableModel):

    PAYMENT_STATUS = [
        ("pending", "Pending"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("reversed", "Reversed"),
    ]

    payroll_item = models.ForeignKey(
        "PayrollItem",
        on_delete=models.PROTECT,
        related_name="transactions",
    )

    financial_account = models.ForeignKey(
        "finances.OperationAccount",
        on_delete=models.PROTECT,
        related_name="transactions",
    )

    status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS,
        default="completed"
    )

    payment_date = models.DateField(default=timezone.now)

    amount = models.DecimalField(max_digits=12, decimal_places=2)

    reference = models.CharField(max_length=100, blank=True, null=True)

    receipt_number = models.CharField(max_length=50, unique=True, blank=True)

    # Improved proof file path
    proof_file = models.FileField(
        upload_to=payroll_proof_upload_path,
        blank=True,
        null=True,
    )

    class Meta:
        ordering = ("-payment_date", "-created_at")

    def __str__(self):
        return f"{self.payroll_item.staff} — {self.amount}"

    def clean(self):
        super().clean()

        if not self.financial_account:
            raise ValidationError("Financial account is required.")

    def save(self, *args, **kwargs):
        if not self.receipt_number:
            # Auto-generate: SAL-ORG_CODE-YYYY-XXXXX
            org_code = self.payroll_item.organization.code if hasattr(
                self.payroll_item, 'organization') else 'XXX'
            year = timezone.now().year
            prefix = f"SAL-{org_code}-{year}-"

            # Get max sequence
            last = PayrollTransaction.objects.filter(
                receipt_number__startswith=prefix
            ).aggregate(max_num=Max('receipt_number'))['max_num']

            if last:
                last_num = int(last.split('-')[-1])
                next_num = last_num + 1
            else:
                next_num = 1

            self.receipt_number = f"{prefix}{next_num:05d}"

        super().save(*args, **kwargs)
