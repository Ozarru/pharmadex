from django.db.models import Q
import re
from django.core.validators import MinValueValidator, MaxValueValidator
from phonenumber_field.modelfields import PhoneNumberField
from django.core.exceptions import ValidationError
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils.text import slugify
from base.models import BaseModel, ActivatableModel, OrganizationModel
from base.utils import GENDER_CHOICES
from pharmadex.tenant import TenantManager


class Organization(BaseModel):
    """
    Tenant root.
    Everything (inventory, sales, purchases, staff visibility) is scoped to an Organization.
    """

    name = models.CharField(max_length=180, unique=True,
                            verbose_name=_("Name"))
    code = models.CharField(
        max_length=4,
        unique=True,
        verbose_name=_("Code"),
        help_text=_("Short code used in identifiers and reports."),
    )
    slug = models.SlugField(max_length=200, unique=True,
                            blank=True, verbose_name=_("Slug"))
    # Optional contact info
    email = models.EmailField(blank=True, null=True, verbose_name=_("Email"))
    phone_number = models.CharField(
        max_length=32, blank=True, null=True, verbose_name=_("Phone"))
    address = models.CharField(
        max_length=255, blank=True, null=True, verbose_name=_("Address"))

    is_active = models.BooleanField(default=True, verbose_name=_("Active"))

    model_icon = 'fa-solid fa-building'

    class Meta:
        verbose_name = _("Organization")
        verbose_name_plural = _("Organizations")
        ordering = ("name",)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:200]

        # Auto-generate prefix only if not set
        if not self.code:
            words = re.findall(r"[A-Za-z]+", self.name)

            if len(words) >= 2:
                # Take first letter of each word
                prefix = "".join(word[0] for word in words[:4])
            else:
                # Single word → take first 3–4 letters
                prefix = words[0][:4]

            self.code = prefix.upper()

        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.code:
            code = self.code.strip().upper()
            if not (3 <= len(code) <= 4):
                raise ValidationError(
                    {"code": _("Code must be 3 or 4 characters long.")})
            self.code = code


# -------------------------------
# Insurer & InsurancePolicy
# -------------------------------
class Insurer(OrganizationModel, ActivatableModel):
    """
    Insurance provider (e.g., Allianz, AXA, NHIS, etc.)
    """

    objects = TenantManager()

    name = models.CharField(
        max_length=255,
        verbose_name=_("Name")
    )

    code = models.CharField(
        max_length=50,
        verbose_name=_("Code")
    )

    email = models.EmailField(
        blank=True,
        null=True,
        verbose_name=_("Contact Email")
    )

    phone_number = PhoneNumberField(
        blank=True,
        null=True,
        verbose_name=_("Phone Number")
    )

    address = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Address")
    )

    model_icon = 'fa-solid fa-shield-halved'

    class Meta:
        verbose_name = _("Insurer")
        verbose_name_plural = _("Insurers")
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "code"],
                name="unique_insurer_code_per_org"
            )
        ]

    def __str__(self):
        return self.name


class InsurancePolicy(OrganizationModel, ActivatableModel):
    """
    Defines an insurance plan (e.g. Gold Plan, Basic Plan)
    """

    insurer = models.ForeignKey(
        "Insurer",
        on_delete=models.CASCADE,
        related_name="policies",
        verbose_name=_("Insurer")
    )

    name = models.CharField(max_length=255, verbose_name=_("Policy Name"))
    code = models.CharField(max_length=24, verbose_name=_("Policy Code"))
    coverage_percent = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name=_("Coverage Percentage"))
    max_coverage_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("Maximum Amount Covered")
    )
    annual_coverage_limit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("Annual Coverage Limit")
    )

    model_icon = 'fa-solid fa-file-shield'

    class Meta:
        verbose_name = _("Insurance Policy")
        verbose_name_plural = _("Insurance Policies")
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "insurer", "code"],
                name="unique_policy_code_per_org"
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"


# -------------------------------
# Customer
# -------------------------------
class Customer(OrganizationModel):
    """
    Extra pharmacy-specific fields for a customer/patient.
    """

    objects = TenantManager()

    first_name = models.CharField(
        max_length=150, blank=True, null=True, verbose_name=_("First Name")
    )

    last_name = models.CharField(
        max_length=150, blank=True, null=True, verbose_name=_("Last Name")
    )

    email = models.EmailField(
        blank=True, null=True, verbose_name=_("Email")
    )

    city = models.CharField(
        max_length=120, blank=True, null=True, verbose_name=_("City")
    )
    
    state_or_region = models.CharField(
        max_length=120,
        blank=True,
        null=True,
        verbose_name=_("State / Region")
    )

    country = models.CharField(
        max_length=100, blank=True, null=True, verbose_name=_("Country")
    )

    phone_number = PhoneNumberField(
        blank=True, null=True, verbose_name=_("Phone number")
    )

    gender = models.CharField(
        max_length=10, choices=GENDER_CHOICES,
        blank=True, null=True, verbose_name=_("Gender")
    )

    date_of_birth = models.DateField(
        blank=True, null=True, verbose_name=_("Date of Birth")
    )

    has_insurance = models.BooleanField(
        default=True, verbose_name=_("Has  Insurrance"))

    insurance_id = models.CharField(
        max_length=50,
        null=True,
        blank=True
    )

    insurance_policy = models.ForeignKey(
        "InsurancePolicy",
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    model_icon = 'fa-solid fa-user'

    class Meta:
        verbose_name = _("Customer")
        verbose_name_plural = _("Customers")

    @property
    def full_name(self):
        return f"{self.last_name or ''} {self.first_name or ''}".strip()

    def __str__(self):
        return f"Customer: {self.full_name}"

    def clean(self):
        if self.insurance_policy and not self.insurance_id:
            raise ValidationError(
                "Insurance ID is required when policy is set.")


# -------------------------------
# Supplier
# -------------------------------
class Supplier(OrganizationModel, ActivatableModel):

    objects = TenantManager()

    name = models.CharField(
        max_length=255,
        verbose_name=_("Name")
    )

    phone_number = PhoneNumberField(
        blank=True,
        null=True,
        verbose_name=_("Phone Number")
    )

    email = models.EmailField(
        blank=True,
        null=True,
        verbose_name=_("Email Address")
    )

    address = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Street Address")
    )

    city = models.CharField(
        max_length=120,
        blank=True,
        null=True,
        verbose_name=_("City")
    )

    state_or_region = models.CharField(
        max_length=120,
        blank=True,
        null=True,
        verbose_name=_("State / Region")
    )

    country = models.CharField(
        max_length=120,
        blank=True,
        null=True,
        verbose_name=_("Country")
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At")
    )

    model_icon = "fa-solid fa-truck-field"

    class Meta:
        verbose_name = _("Supplier")
        verbose_name_plural = _("Suppliers")
        ordering = ("name",)

    def __str__(self):
        return self.name

    @property
    def full_address(self):
        parts = [self.address, self.city, self.state_or_region, self.country]
        return ", ".join([p for p in parts if p])
