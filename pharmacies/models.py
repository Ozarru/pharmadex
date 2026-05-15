from django.db import transaction
from django.db.models import Sum
from django.core.validators import MinValueValidator
from datetime import timedelta
from decimal import Decimal
from django.db.models import F
from django.db import models, transaction
from django.conf import settings
import re
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db import models
from django.utils.translation import gettext_lazy as _
from base.models import ActivatableModel, BaseModel, OrganizationModel, ArchivableModel, PharmacyModel
from pharmadex.tenant import TenantManager


# -------------------------------
# Pharmacy
# -------------------------------
class Pharmacy(OrganizationModel):
    objects = TenantManager()

    STATUS_CHOICES = [
        ("active", _("Active")),
        ("suspended", _("Suspended")),
        ("inactive", _("Inactive")),
        ("archived", _("Archived")),
    ]

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="pharmacies",
        verbose_name=_("Organization")
    )

    name = models.CharField(
        max_length=180,
        verbose_name=_("Pharmacy Name")
    )

    code = models.CharField(
        max_length=10,
        verbose_name=_("Pharmacy Code")
    )

    state_or_region = models.CharField(
        max_length=120,
        blank=True,
        null=True,
        verbose_name=_("State / Region")
    )

    city = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_("City")
    )

    address = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_("Address")
    )

    phone_number = models.CharField(
        max_length=32,
        blank=True,
        null=True,
        verbose_name=_("Phone Number")
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active",
        verbose_name=_("Status")
    )

    clinic_enabled = models.BooleanField(
        default=False,
        verbose_name=_("Clinic Enabled")
    )

    requires_cashier_validation = models.BooleanField(
        default=False, verbose_name=_("Requires Cashier Validation"))

    model_icon = "fa-solid fa-staff-snake"

    class Meta:
        verbose_name = _("Pharmacy")
        verbose_name_plural = _("Pharmacies")
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "code"],
                name="unique_pharmacy_code_per_organization"
            )
        ]

    def __str__(self):
        return f"{self.organization.name} - {self.name}"

    @property
    def is_active(self):
        return self.status == "active"

    @property
    def is_suspended(self):
        return self.status == "suspended"

    @property
    def is_archived(self):
        return self.status == "archived"


# -------------------------------
# Product Categorization
# -------------------------------
class ProductCategory(OrganizationModel, ActivatableModel):

    objects = TenantManager()
    
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        blank=True, null=True,
        verbose_name=_("Organization"),
    )
    name = models.CharField(max_length=100, unique=True,
                            verbose_name=_("Category Name"))
    description = models.TextField(
        blank=True, null=True, verbose_name=_("Description"))

    model_icon = "fa-solid fa-tag"

    class Meta:
        verbose_name = _("Product Category")
        verbose_name_plural = _("Product Categories")

    def __str__(self):
        return self.name


class ProductSubcategory(OrganizationModel, ActivatableModel):

    objects = TenantManager()
    
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        blank=True, null=True,
        verbose_name=_("Organization"),
    )
    
    category = models.ForeignKey(
        ProductCategory, on_delete=models.PROTECT, related_name="product_subcategories")
    name = models.CharField(max_length=100, verbose_name=_("Subcategory Name"))

    model_icon = "fa-solid fa-tags"

    class Meta:
        verbose_name = _("Product Subcategory")
        verbose_name_plural = _("Product Subcategories")
        unique_together = ("category", "name")

    def __str__(self):
        return f"{self.category.name} -> {self.name}"


# -------------------------------
# Product & Stock & Batch
# -------------------------------
class Product(ActivatableModel, OrganizationModel):
    """
    Pharmacy product (drug or medical item).
    Tenant-scoped by Organization + Pharmacy.
    """

    objects = TenantManager()

    class DosageForm(models.TextChoices):
        TABLET = "tablet", _("Tablet")
        CAPSULE = "capsule", _("Capsule")
        SYRUP = "syrup", _("Syrup")
        INJECTION = "injection", _("Injection")
        CREAM = "cream", _("Cream")
        OINTMENT = "ointment", _("Ointment")
        DROPS = "drops", _("Drops")
        INHALER = "inhaler", _("Inhaler")
        SUPPOSITORY = "suppository", _("Suppository")
        POWDER = "powder", _("Powder")

    class AdministrationRoute(models.TextChoices):
        ORAL = "oral", _("Oral")
        IV = "iv", _("Intravenous")
        IM = "im", _("Intramuscular")
        SC = "sc", _("Subcutaneous")
        TOPICAL = "topical", _("Topical")
        INHALATION = "inhalation", _("Inhalation")
        RECTAL = "rectal", _("Rectal")
        OPHTHALMIC = "ophthalmic", _("Ophthalmic")
        NASAL = "nasal", _("Nasal")

    class PrescriptionType(models.TextChoices):
        OTC = "otc", _("Over The Counter")
        RX = "rx", _("Prescription Required")
        CONTROLLED = "controlled", _("Controlled Substance")

    class StorageCondition(models.TextChoices):
        ROOM_TEMP = "room_temp", _("Room Temperature")
        REFRIGERATED = "refrigerated", _("Refrigerated (2–8°C)")
        FREEZER = "freezer", _("Frozen")
        COOL_DRY = "cool_dry", _("Cool & Dry Place")
        PROTECTED_LIGHT = "protected_light", _("Protected from Light")

    # -------------------------------------------------
    # Identity
    # -------------------------------------------------
    subcategory = models.ForeignKey(
        ProductSubcategory,
        on_delete=models.PROTECT,
        related_name="products",
        verbose_name=_("Subcategory"),
    )

    name = models.CharField(
        max_length=150,
        verbose_name=_("Product Name")
    )

    generic_name = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        verbose_name=_("Generic Name")
    )

    brand = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_("Brand")
    )

    code_name = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name=_("Code Name")
    )

    barcode = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        unique=True,
        verbose_name=_("Barcode")
    )

    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Description")
    )

    image = models.ImageField(
        upload_to="products/images/",
        blank=True,
        null=True,
        verbose_name=_("Product Image")
    )

    # -------------------------------------------------
    # Pharmaceutical structure
    # -------------------------------------------------
    dosage_form = models.CharField(
        max_length=30,
        choices=DosageForm.choices,
        verbose_name=_("Dosage Form")
    )

    strength = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("Strength")
    )

    route_of_administration = models.CharField(
        max_length=30,
        choices=AdministrationRoute.choices,
        default=AdministrationRoute.ORAL,
        verbose_name=_("Route of Administration")
    )

    prescription_type = models.CharField(
        max_length=30,
        choices=PrescriptionType.choices,
        default=PrescriptionType.OTC,
        verbose_name=_("Prescription Type"))

    storage_condition = models.CharField(
        max_length=30,
        choices=StorageCondition.choices,
        default=StorageCondition.ROOM_TEMP,
        verbose_name=_("Prescription Type")
    )

    pack_size = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_("Pack Size")
    )

    # -------------------------------------------------
    # Clinical / AI-ready fields
    # -------------------------------------------------
    indications = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Indications")
    )

    symptoms_treated = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Symptoms Treated")
    )

    contraindications = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Contraindications")
    )

    side_effects = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Side Effects")
    )

    drug_interactions = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Drug Interactions")
    )

    precautions = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Precautions")
    )

    storage_instructions = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Storage Instructions")
    )

    # -------------------------------------------------
    # Commercial
    # -------------------------------------------------
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name=_("Selling Price")
    )

    cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name=_("Cost Price")
    )

    # -------------------------------------------------
    # Pharmacy rules
    # -------------------------------------------------
    is_expirable = models.BooleanField(
        default=True,
        verbose_name=_("Is Expirable")
    )

    is_prescription_required = models.BooleanField(
        default=False,
        verbose_name=_("Prescription Required")
    )

    is_controlled_substance = models.BooleanField(
        default=False,
        verbose_name=_("Controlled Substance")
    )

    # -------------------------------------------------
    # Stock management
    # -------------------------------------------------
    min_stock_threshold = models.PositiveSmallIntegerField(
        default=5,
        verbose_name=_("Minimum Stock Level")
    )

    max_stock_threshold = models.PositiveSmallIntegerField(
        default=50,
        verbose_name=_("Maximum Stock Level")
    )

    shelf_life_days = models.PositiveIntegerField(
        blank=True,
        null=True,
        verbose_name=_("Shelf Life (Days)")
    )

    # -------------------------------------------------
    # Status
    # -------------------------------------------------
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Active")
    )

    model_icon = "fa-solid fa-prescription-bottle-medical"

    class Meta:
        ordering = ('name',)
        verbose_name = _("Product")
        verbose_name_plural = _("Products")
        unique_together = ("organization", "subcategory", "name")

    def __str__(self):
        return f"{self.subcategory.name} -> {self.name}"

    def _get_initials(self, text, limit=None):
        """
        Returns uppercase initials of words.
        limit = number of words to use (optional)
        """
        words = re.findall(r'\b\w+', text)
        if limit:
            words = words[:limit]
        return ''.join(word[0].upper() for word in words if word)

    def generate_code_name(self):
        category_initial = self._get_initials(
            self.subcategory.category.name, limit=1
        )

        subcategory_initial = self._get_initials(
            self.subcategory.name, limit=1
        )

        product_initials = self._get_initials(
            self.name, limit=2
        )

        return f"{category_initial}{subcategory_initial}/{product_initials}"

    def save(self, *args, **kwargs):
        if not self.code_name:
            self.code_name = self.generate_code_name()

        super().save(*args, **kwargs)


class ProductAlternative(ActivatableModel, OrganizationModel):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="alternative_links"
    )

    alternative = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="alternative_for_links"
    )

    reason = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    priority = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = _("Product Alternative")
        verbose_name_plural = _("Product Alternatives")
        unique_together = ("product", "alternative")

    def clean(self):
        if self.alternative == self.product:
            raise ValidationError("Product cannot be its own alternative.")


class ProductStock(PharmacyModel):
    """
    Logical stock container per organization.

    IMPORTANT RULE:
    - NEVER pharmacy quantity here
    - Quantity is derived from ProductBatch
    """

    objects = TenantManager()

    product = models.ForeignKey(
        "Product",
        on_delete=models.PROTECT,
        related_name="stocks",
        editable=False
    )

    # -----------------------------
    # Pricing overrides (optional)
    # -----------------------------
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True
    )

    cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True
    )

    model_icon = "fa-solid fa-boxes-stacked"

    class Meta:
        verbose_name = _("Product Stock")
        verbose_name_plural = _("Product Stocks")
        constraints = [
            models.UniqueConstraint(
                fields=["pharmacy", "product"],
                name="uniq_pharmacy_product_stock"
            )
        ]
        indexes = [
            models.Index(fields=["product"]),
        ]

    def __str__(self):
        return f"{self.pharmacy.name} - {self.product.name} Stock"
    
    # -----------------------------
    # STOCK STATUS (derived from batches)
    # -----------------------------

    @property
    def today(self):
        return timezone.now().date()


    @property
    def expired_batches(self):
        """
        Batches already expired.
        """
        return self.batches.filter(
            expiry_date__lt=self.today
        )


    @property
    def expiring_batches(self):
        """
        Batches expiring within 30 days.
        """
        return self.batches.filter(
            expiry_date__gte=self.today,
            expiry_date__lte=self.today + timedelta(days=30)
        )


    @property
    def damaged_batches(self):
        """
        Damaged batches.
        """
        return self.batches.filter(
            is_damaged=True
        )


    @property
    def usable_batches(self):
        """
        Batches safe for dispensing.
        """
        return self.batches.filter(
            expiry_date__gt=self.today,
            quantity__gt=0,
            is_active=True,
            is_damaged=False,
        )


    # -----------------------------
    # BOOLEAN HELPERS
    # -----------------------------

    @property
    def has_expired_stock(self):
        return self.expired_batches.exists()


    @property
    def has_expiring_stock(self):
        return self.expiring_batches.exists()


    @property
    def has_damaged_stock(self):
        return self.damaged_batches.exists()


    @property
    def has_usable_stock(self):
        return self.usable_batches.exists()


    # -----------------------------
    # STOCK STATUS
    # -----------------------------

    @property
    def stock_status(self):
        """
        Overall stock usability status.

        Priority:
        out_of_stock > expired > damaged > expiring > usable
        """

        if self.quantity <= 0:
            return "out_of_stock"

        if self.has_expired_stock:
            return "expired"

        if self.has_damaged_stock:
            return "damaged"

        if self.has_expiring_stock:
            return "expiring"

        return "usable"


    # -----------------------------
    # QUANTITY STATUS
    # -----------------------------

    @property
    def quantity_status(self):
        """
        Inventory quantity health.
        """

        if self.quantity <= 0:
            return "out_of_stock"

        if self.quantity <= 10:
            return "low_stock"

        return "in_stock"

    # -----------------------------
    # STOCK (derived from batches)
    # -----------------------------

    @property
    def quantity(self):
        """
        Total usable stock across valid batches only.
        Excludes:
        - expired batches
        - damaged batches
        - inactive batches
        """

        today = timezone.now().date()

        return (
            self.batches.filter(
                expiry_date__gt=today,
                is_damaged=False,
                is_active=True,
            ).aggregate(
                total=Sum("quantity")
            )["total"] or 0
        )

    @property
    def available_batches(self):
        """
        Only usable (non-empty, non-expired handled at batch level if needed)
        """
        return self.batches.filter(quantity__gt=0)

    @property
    def is_available(self):
        return self.quantity > 0

    # -----------------------------
    # Pricing logic
    # -----------------------------

    @property
    def effective_price(self):
        if self.price is not None:
            return self.price
        if self.product.price is not None:
            return self.product.price
        return Decimal("0.00")

    @property
    def effective_cost(self):
        if self.cost is not None:
            return self.cost
        if self.product.cost is not None:
            return self.product.cost
        return Decimal("0.00")

    # -----------------------------
    # Convenience accessors
    # -----------------------------

    @property
    def image(self):
        return self.product.image

    @property
    def product_name(self):
        return self.product.name

    @property
    def product_categorization(self):
        sub = getattr(self.product, "subcategory", None)
        if not sub:
            return "Uncategorized"

        cat = getattr(sub, "category", None)
        if not cat:
            return sub.name

        return f"{cat.name} -> {sub.name}"
    

class ProductBatchQuerySet(models.QuerySet):
    def expired(self):
        today = timezone.now().date()
        return self.filter(expiry_date__lt=today)

    def expiring(self, days=30):
        today = timezone.now().date()
        return self.filter(
            expiry_date__gte=today,
            expiry_date__lte=today + timedelta(days=days)
        )

    def usable(self):
        today = timezone.now().date()
        return self.filter(expiry_date__gt=today + timedelta(days=30))

    def damaged(self):
        return self.filter(is_damaged=True)  # requires field below


class ProductBatch(PharmacyModel):
    """
    Represents a physical batch of a product in stock.

    IMPORTANT:
    - Quantity = inventory dimension
    - Expiry = safety dimension
    - Active = business/system dimension

    These are independent.
    """
    is_damaged = models.BooleanField(default=False)

    product_stock = models.ForeignKey(
        "ProductStock",
        on_delete=models.CASCADE,
        related_name="batches"
    )

    batch_number = models.CharField(max_length=50)
    expiry_date = models.DateField()
    quantity = models.PositiveIntegerField(default=0)
    manufacturing_date = models.DateField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    # attach custom manager
    objects = ProductBatchQuerySet.as_manager()

    model_icon = "fa-solid fa-cart-flatbed"

    class Meta:
        verbose_name = _("Product Batch")
        verbose_name_plural = _("Product Batches")
        constraints = [
            models.UniqueConstraint(
                fields=["product_stock", "batch_number"],
                name="uniq_batch_per_stock"
            )
        ]
        indexes = [
            models.Index(fields=["expiry_date"]),
            models.Index(fields=["batch_number"]),
        ]

    def __str__(self):
        return f"{self.product_stock.product.name} - Batch {self.batch_number}"

    # -----------------------------
    # CORE COMPUTATIONS
    # -----------------------------
    @property
    def today(self):
        return timezone.now().date()

    @property
    def days_to_expiry(self):
        return (self.expiry_date - self.today).days

    @property
    def product_name(self):
        return self.product_stock.product.name

    # -----------------------------
    # USABILITY (expiry-based)
    # -----------------------------
    @property
    def usability_status(self):
        if self.is_damaged:
            return "damaged"

        if self.expiry_date < self.today:
            return "expired"

        if self.expiry_date <= self.today + timedelta(days=30):
            return "expiring"

        return "usable"

    @property
    def is_expired(self):
        return self.usability_status == self.UsabilityStatus.EXPIRED

    # -----------------------------
    # QUANTITY (inventory-based)
    # -----------------------------
    @property
    def quantity_status(self):
        if self.quantity <= 0:
            return "out_of_stock"

        if self.quantity <= 10:
            return "low_stock"

        return "in_stock"

    @property
    def is_low_stock(self):
        return self.quantity_status == self.QuantityStatus.LOW_STOCK

    # -----------------------------
    # COMBINED BUSINESS LOGIC
    # -----------------------------
    @property
    def is_usable(self):
        """
        Can this batch be used for dispensing?
        """
        return (
            self.is_active and
            self.quantity > 0 and
            not self.is_expired
        )

    @property
    def is_dispensable(self):
        """
        Alias for clarity in business logic.
        """
        return self.is_usable

    # -----------------------------
    # UI HELPERS (BADGES / COLORS)
    # -----------------------------
    @property
    def usability_label(self):
        return dict(self.UsabilityStatus.CHOICES).get(self.usability_status)

    @property
    def quantity_label(self):
        return dict(self.QuantityStatus.CHOICES).get(self.quantity_status)
    
    
    @property
    def days_to_expiry_display(self):
        return self.days_to_expiry

    @property
    def usability_color(self):
        return {
            "expired": "red",
            "expiring": "orange",
            "usable": "green",
        }.get(self.usability_status, "gray")

    @property
    def quantity_color(self):
        return {
            "out_of_stock": "red",
            "low_stock": "yellow",
            "in_stock": "green",
        }.get(self.quantity_status, "gray")

    # -----------------------------
    # VALIDATION
    # -----------------------------
    def clean(self):
        errors = {}

        if self.quantity < 0:
            errors["quantity"] = _("Batch quantity cannot be negative.")

        if errors:
            raise ValidationError(errors)

    # -----------------------------
    # STOCK OPERATIONS
    # -----------------------------
    def decrease_stock(self, qty):
        if qty <= 0:
            raise ValidationError(_("Quantity must be positive."))

        if self.quantity < qty:
            raise ValidationError(_("Insufficient batch stock."))

        self.quantity -= qty
        self.save(update_fields=["quantity"])

    def increase_stock(self, qty):
        if qty <= 0:
            raise ValidationError(_("Quantity must be positive."))

        self.quantity += qty
        self.save(update_fields=["quantity"])


# -------------------------------
# Prescription & Dispensation
# -------------------------------
class Prescription(PharmacyModel):
    """
    Represents a patient's prescription issued by a prescriber.
    """

    OORIGIN_CHOICES = [
        ("internal", _("Internal Prescription")),
        ("external", _("External Prescription")),
    ]

    STATUS_CHOICES = [
        ("pending", _("Pending")),
        ("processing", _("Processing")),
        ("on_hold", _("On Hold")),
        ("completed", _("Completed")),
        ("cancelled", _("Cancelled")),
    ]

    origin = models.CharField(
        max_length=20,
        choices=OORIGIN_CHOICES,
        default="internal",
        verbose_name=_("Prescription Type")
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
        verbose_name=_("Status")
    )

    rx_number = models.CharField(
        max_length=50,
        unique=True,
        verbose_name=_("Prescription Number")
    )

    rx_file = models.FileField(
        upload_to="prescriptions/documents/",
        blank=True,
        null=True,
        verbose_name=_("Prescription File")
    )

    patient = models.ForeignKey(
        "organizations.Customer",
        on_delete=models.PROTECT,
        related_name="prescriptions",
        verbose_name=_("Patient")
    )

    issued_date = models.DateField(
        default=timezone.now,
        verbose_name=_("Issued Date")
    )

    valid_until = models.DateField(
        blank=True,
        null=True,
        verbose_name=_("Valid Until")
    )

    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Notes")
    )

    model_icon = "fa-solid fa-file-prescription"

    class Meta:
        verbose_name = _("Prescription")
        verbose_name_plural = _("Prescriptions")
        ordering = ["-issued_date"]

    def __str__(self):
        return f"{self.origin}-RX-{self.rx_number}"

    def clean(self):
        if self.valid_until and self.valid_until < self.issued_date:
            raise ValidationError(
                _("Valid until date cannot be before issued date.")
            )


class PrescriptionItem(PharmacyModel):
    """
    Individual drug/item inside a prescription.
    """

    prescription = models.ForeignKey(
        Prescription,
        on_delete=models.CASCADE,
        related_name="items"
    )

    product = models.ForeignKey(
        "Product",
        on_delete=models.CASCADE
    )

    quantity = models.PositiveIntegerField()

    dosage = models.CharField(
        max_length=255,
        help_text="e.g. 1 tablet twice daily"
    )

    duration_days = models.PositiveIntegerField(
        blank=True,
        null=True
    )

    instructions = models.TextField(blank=True, null=True)

    model_icon = "fa-solid fa-prescription-bottle-medical"

    class Meta:
        verbose_name = _("Prescription Item")
        verbose_name_plural = _("Prescription Items")
        unique_together = ("prescription", "product")

    def __str__(self):
        return f"{self.product.name} ({self.quantity})"


class Dispensation(PharmacyModel):
    """
    Represents the actual dispensing of medication to a patient
    based on a prescription item.
    """

    prescription = models.ForeignKey(
        "Prescription",
        on_delete=models.PROTECT,
        related_name="dispensations",
        verbose_name=_("Prescription")
    )

    dispensed_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Dispensed At")
    )

    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Notes")
    )

    model_icon = "fa-solid fa-pills"

    class Meta:
        verbose_name = _("Dispensation")
        verbose_name_plural = _("Dispensations")
        ordering = ["-dispensed_at"]

    def __str__(self):
        return f"Dispensation #{self.id} - {self.prescription.rx_number}"


# -------------------------------
# Product Sale
# -------------------------------
class Sale(PharmacyModel, ArchivableModel):

    objects = TenantManager()

    STATUS_CHOICES = [
        ("pending", _("Pending")),
        ("backordered", _("Backordered")),
        ("on_credit", _("On Credit")),
        ("completed", _("Completed")),
        ("refunded", _("Refunded")),
        ("cancelled", _("Cancelled")),
    ]

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="completed",
        blank=True, null=True,
        verbose_name=_("Status")
    )
    pharmacy = models.ForeignKey(
        "Pharmacy", on_delete=models.PROTECT, blank=True, null=True, related_name="sales")
    vendor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sales")
    cashier = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="validated_sales",
        verbose_name=_("Cashier"),
    )
    customer = models.ForeignKey(
        "organizations.Customer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales",
        verbose_name=_("Customer"),
    )
    total_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True, null=True)
    validated_at = models.DateTimeField(null=True, blank=True)

    # -----------------------------
    # INSURANCE SNAPSHOT (IMPORTANT)
    # -----------------------------
    insurance_policy = models.ForeignKey(
        "organizations.InsurancePolicy",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales",
        verbose_name=_("Insurance Policy"),
    )

    insurance_coverage_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("Percentage Covered"),
    )

    insurance_max_coverage_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("Maximum Amount Covered"),
    )

    insurance_applied = models.BooleanField(default=False,
        verbose_name=_("Insurrance Applied"),)

    model_icon = "fa-solid fa-cart-shopping"

    class Meta:
        verbose_name = _("Sale")
        verbose_name_plural = _("Sales")
        
    @property
    def requires_cashier_validation(self):
        return bool(
            self.pharmacy and self.pharmacy.requires_cashier_validation
        )

    @property
    def insurance_covered_amount(self):
        if not self.insurance_applied or not self.insurance_policy:
            return 0

        coverage_percent = self.insurance_coverage_percent or 0
        max_cover = self.insurance_max_coverage_amount

        covered = (self.total_amount * coverage_percent) / 100

        if max_cover is not None:
            covered = min(covered, max_cover)

        return min(covered, self.total_amount)
    
    @property
    def patient_payable_amount(self):
        return max(self.total_amount - self.insurance_covered_amount, 0)
    
    @property
    def net_total_check(self):
        return self.patient_payable_amount + self.insurance_covered_amount

    @property
    def total_items(self):
        return self.items.count()

    @property
    def is_cancelled(self):
        return self.status == "cancelled"
    
    @property
    def is_backordered(self):
        return self.status == "backordered"
    
    @property
    def total_profit(self):
        return sum(
            (item.unit_price - item.product_stock.cost) * item.quantity
            for item in self.items.select_related("product_stock")
        )

    def __str__(self):
        return f"Sale #{self.id} by {self.vendor}"

    def recalculate_total(self):
        total = sum(item.total_price for item in self.items.all())

        if self.total_amount != total:
            self.total_amount = total
            self.save(update_fields=["total_amount"])

    @property
    def get_items_summary(self):
        return " | ".join(
            f"{item.product_stock.product.name} x{item.quantity} @ {item.unit_price:.2f} = {item.total_price:.2f}"
            for item in self.items.all()
        )
        
    def clean(self):
        if self.status == "backordered" and not self.customer:
            raise ValidationError("Backordered sales must have a customer.")

        if self.insurance_applied and not self.customer:
            raise ValidationError("Insured sales must have a customer.")


class SaleItem(ArchivableModel):
    TENANT_FILTER = "sale__pharmacy__organization"
    objects = TenantManager()

    sale = models.ForeignKey(
        Sale, on_delete=models.CASCADE, related_name="items")

    product_stock = models.ForeignKey(
        ProductStock, null=True, on_delete=models.CASCADE, related_name="sale_items")

    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    total_price = models.DecimalField(max_digits=12, decimal_places=2)

    model_icon = "fa-solid fa-box"

    def save(self, *args, **kwargs):
        if self.product_stock is None:
            raise ValueError("SaleItem must have a ProductStock assigned.")
        if self.unit_price is None:
            raise ValueError(f"Unit price not set for {self.product_stock}")

        # Use the effective_price fallback to avoid None errors
        self.unit_price = self.product_stock.effective_price
        self.total_price = self.unit_price * self.quantity
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = _("Sale Item")
        verbose_name_plural = _("Sale Items")

    def __str__(self):
        return f"{self.quantity} x {self.product_stock.product.name}"


class SaleValidationLog(PharmacyModel):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    action = models.CharField(max_length=50)  
    # added_item, removed_item, qty_changed, approved, rejected

    details = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    model_icon = "fa-solid fa-notes-medical"

    class Meta:
        verbose_name = _("Sale Validation Log")
        verbose_name_plural = _("Sale Validation Logs")

    def __str__(self):
        return f"Sale: {self.sale} , validation log by user: {self.user}"


# -------------------------------
# Product Purchase / Procurment
# -------------------------------
class PurchaseOrder(PharmacyModel, ArchivableModel):
    """
    Represents a purchase order sent from a pharmacy to a supplier.
    """
    objects = TenantManager()

    STATUS_CHOICES = [
        ("draft", _("Draft")),
        ("sent", _("Sent to Supplier")),
        ("partially_received", _("Partially Received")),
        ("received", _("Received")),
        ("cancelled", _("Cancelled")),
        ("closed", _("Closed")),
    ]

    pharmacy = models.ForeignKey(
        "Pharmacy",
        on_delete=models.PROTECT,
        related_name="purchase_orders",
        verbose_name=_("Pharmacy")
    )

    supplier = models.ForeignKey(
        "organizations.Supplier",
        on_delete=models.PROTECT,
        related_name="purchase_orders",
        verbose_name=_("Supplier")
    )

    reference = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        verbose_name=_("Reference")
    )

    order_date = models.DateField(
        auto_now_add=True,
        verbose_name=_("Order Date")
    )

    expected_delivery_date = models.DateField(
        blank=True,
        null=True,
        verbose_name=_("Expected Delivery Date")
    )

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="draft",
        verbose_name=_("Status")
    )

    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Notes")
    )

    order_file = models.FileField(
        upload_to="purchase_orders/orders/",
        blank=True,
        null=True,
        verbose_name=_("Order File")
    )

    expected_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name=_("Expected Total")
    )

    model_icon = "fa-solid fa-cart-shopping"

    class Meta:
        verbose_name = _("Purchase Order")
        verbose_name_plural = _("Purchase Orders")
        ordering = ("-created_at",)

    def __str__(self):
        return f"PO #{self.id}"

    @property
    def subtotal(self):
        return sum(item.line_total or 0 for item in self.items.all())

    @property
    def total(self):
        return self.subtotal

    @property
    def is_fully_received(self):
        return self.items.exists() and all(
            item.quantity_received >= item.quantity_ordered
            for item in self.items.all()
        )


class PurchaseOrderItem(ArchivableModel):

    purchase_order = models.ForeignKey(
        "PurchaseOrder",
        related_name="items",
        on_delete=models.CASCADE,
        verbose_name=_("Purchase Order")
    )

    product = models.ForeignKey(
        "pharmacies.Product",
        on_delete=models.PROTECT,
        related_name="purchase_order_items",
        verbose_name=_("Product")
    )

    quantity_ordered = models.PositiveIntegerField(
        verbose_name=_("Quantity Ordered")
    )

    quantity_received = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Quantity Received")
    )

    expected_unit_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name=_("Expected Unit Cost")
    )

    class Meta:
        verbose_name = _("Purchase Order Item")
        verbose_name_plural = _("Purchase Order Items")

    def __str__(self):
        return str(self.product)

    @property
    def pending_quantity(self):
        return max(0, self.quantity_ordered - self.quantity_received)

    @property
    def line_total(self):
        if self.expected_unit_cost:
            return self.quantity_ordered * self.expected_unit_cost
        return 0


class PurchaseDelivery(PharmacyModel, ArchivableModel):
    objects = TenantManager()

    STATUS_CHOICES = [
        ("draft", _("Draft")),
        ("received", _("Received")),
        ("cancelled", _("Cancelled")),
    ]

    pharmacy = models.ForeignKey(
        "Pharmacy",
        on_delete=models.PROTECT,
        related_name="purchase_deliveries",
        verbose_name=_("Pharmacy")
    )

    purchase_order = models.ForeignKey(
        "PurchaseOrder",
        on_delete=models.PROTECT,
        related_name="deliveries",
        verbose_name=_("Purchase Order")
    )

    delivery_date = models.DateField(
        auto_now_add=True,
        verbose_name=_("Delivery Date")
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
        verbose_name=_("Status")
    )

    # NEW: proof of delivery (GRN / signed note / photo / PDF)
    delivery_proof = models.FileField(
        upload_to="purchase_deliveries/proofs/",
        blank=True,
        null=True,
        verbose_name=_("Delivery Proof")
    )

    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Notes")
    )

    model_icon = "fa-solid fa-box-open"

    class Meta:
        verbose_name = _("Purchase Delivery")
        verbose_name_plural = _("Purchase Deliveries")
        ordering = ("-created_at",)

    def __str__(self):
        return f"Delivery #{self.id}"


class PurchaseDeliveryItem(ArchivableModel):

    delivery = models.ForeignKey(
        "PurchaseDelivery",
        related_name="items",
        on_delete=models.CASCADE,
        verbose_name=_("Delivery")
    )

    purchase_order_item = models.ForeignKey(
        "PurchaseOrderItem",
        related_name="delivery_items",
        on_delete=models.PROTECT,
        verbose_name=_("Purchase Order Item")
    )

    batch_number = models.CharField(
        max_length=100,
        verbose_name=_("Batch Number")
    )

    expiry_date = models.DateField(
        verbose_name=_("Expiry Date")
    )

    received_quantity = models.PositiveIntegerField(
        verbose_name=_("Received Quantity")
    )

    received_unit_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_("Received Unit Cost")
    )

    class Meta:
        verbose_name = _("Purchase Delivery Item")
        verbose_name_plural = _("Purchase Delivery Items")

    def __str__(self):
        return str(self.purchase_order_item.product)

    @property
    def line_total(self):
        return self.received_quantity * self.received_unit_cost

    def clean(self):
        pending = self.purchase_order_item.pending_quantity

        if self.received_quantity > pending:
            raise ValidationError(
                _("Received quantity exceeds remaining ordered quantity.")
            )


class SupplierInvoice(PharmacyModel, ArchivableModel):
    """
    Supplier invoice linked to a purchase order.
    Simple financial record for tracking and payment.
    """

    objects = TenantManager()

    pharmacy = models.ForeignKey(
        "Pharmacy",
        on_delete=models.PROTECT,
        related_name="supplier_invoices",
        verbose_name=_("Pharmacy")
    )

    supplier = models.ForeignKey(
        "organizations.Supplier",
        on_delete=models.PROTECT,
        related_name="invoices",
        verbose_name=_("Supplier")
    )

    purchase_order = models.ForeignKey(
        "PurchaseOrder",
        on_delete=models.PROTECT,
        related_name="supplier_invoices",
        verbose_name=_("Purchase Order")
    )

    delivery = models.ForeignKey(
        "PurchaseDelivery",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoices",
        verbose_name=_("Related Delivery")
    )

    invoice_number = models.CharField(
        max_length=100,
        verbose_name=_("Invoice Number")
    )

    invoice_date = models.DateField(
        verbose_name=_("Invoice Date")
    )

    due_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Due Date")
    )

    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name=_("Total Amount")
    )

    invoice_file = models.FileField(
        upload_to="supplier_invoices/",
        blank=True,
        null=True,
        verbose_name=_("Invoice File")
    )

    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Notes")
    )

    model_icon = "fa-solid fa-file-invoice"

    class Meta:
        verbose_name = _("Supplier Invoice")
        verbose_name_plural = _("Supplier Invoices")
        ordering = ("-invoice_date",)

    def __str__(self):
        return f"{self.invoice_number}"


# -------------------------------
# Inventory Movement
# -------------------------------
class InventoryMovement(PharmacyModel, ArchivableModel):
    """
    Represents a batch of inventory movements (entries or exits) applied immediately.
    """

    objects = TenantManager()

    pharmacy = models.ForeignKey("Pharmacy", on_delete=models.PROTECT,
                                 blank=True, null=True, related_name="inventory_movements")
    reference = models.CharField(
        max_length=64, blank=True, null=True, verbose_name=_("External Reference"))

    MOVEMENT_TYPE_CHOICES = [
        ("entry", _("Entry")),
        ("exit", _("Exit")),
    ]

    movement_type = models.CharField(
        max_length=5, choices=MOVEMENT_TYPE_CHOICES, verbose_name=_("Movement Type"))

    created_by = models.ForeignKey("accounts.CustomUser", on_delete=models.SET_NULL, null=True,
                                   blank=True, related_name="created_inventory_movements", verbose_name=_("Created By"))
    reason = models.CharField(
        max_length=512, verbose_name=_("Reason / Comment"))

    comment = models.TextField(
        blank=True, null=True, verbose_name=_("General Comments"))

    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name=_("Created At"))

    model_icon = "fa-solid fa-up-down"

    class Meta:
        verbose_name = _("Inventory Movement")
        verbose_name_plural = _("Inventory Movements")
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.get_movement_type_display()} Batch #{self.id}"


class InventoryMovementItem(ArchivableModel):
    """
    Represents a single product movement applied to batches (NOT ProductStock).
    """

    TENANT_FILTER = "inventory_movement__pharmacy__organization"
    objects = TenantManager()

    inventory_movement = models.ForeignKey(
        InventoryMovement,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name=_("Inventory Movement")
    )

    product_stock = models.ForeignKey(
        ProductStock,
        null=True,
        on_delete=models.CASCADE,
        related_name="movement_items",
        verbose_name=_("Product Stock")
    )

    quantity = models.PositiveIntegerField(
        verbose_name=_("Quantity")
    )

    comment = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    class Meta:
        verbose_name = _("Inventory Movement Item")
        verbose_name_plural = _("Inventory Movement Items")
        constraints = [
            models.UniqueConstraint(
                fields=["inventory_movement", "product_stock"],
                name="unique_product_per_movement",
            )
        ]

    def __str__(self):
        return f"{self.product_stock.product.name} | Qty: {self.quantity}"

    # -----------------------------
    # CORE LOGIC (FIXED)
    # -----------------------------

    def apply_movement(self):
        """
        Applies stock movement using BATCHES (FEFO logic).
        """
        movement_type = self.inventory_movement.movement_type

        batches = self.product_stock.batches.select_for_update().order_by("expiry_date")

        remaining = self.quantity

        if movement_type == "exit":
            # FEFO: deduct from earliest expiry first
            for batch in batches:
                if remaining <= 0:
                    break

                if batch.quantity <= 0:
                    continue

                deduct = min(batch.quantity, remaining)
                batch.quantity -= deduct
                batch.save(update_fields=["quantity"])
                remaining -= deduct

            if remaining > 0:
                raise ValidationError(
                    f"Not enough stock in batches for {self.product_stock.product.name}"
                )

        else:
            # entry → add to newest batch OR unspecified batch
            # (you may refine later with batch selection rules)
            batch = batches.last()

            if not batch:
                raise ValidationError("No batch exists for stock entry.")

            batch.quantity += self.quantity
            batch.save(update_fields=["quantity"])

    def save(self, *args, **kwargs):
        with transaction.atomic():
            is_new = self._state.adding
            super().save(*args, **kwargs)

            if is_new:
                self.apply_movement()


# -------------------------------
# Inventory Audit
# -------------------------------
class InventoryAudit(PharmacyModel, ArchivableModel):
    """
    Represents a full inventory audit session.

    Audits OBSERVE stock state.
    Stock adjustments must be applied explicitly.
    """

    objects = TenantManager()

    pharmacy = models.ForeignKey("Pharmacy", on_delete=models.PROTECT,
                                 blank=True, null=True, related_name="inventory_audits")

    INVENTORY_STATUS_CHOICES = [
        ("pending", _("Pending")),
        ("in_progress", _("In Progress")),
        ("validated", _("Validated")),
        ("unvalidated", _("Unvalidated")),
    ]

    status = models.CharField(max_length=12, choices=INVENTORY_STATUS_CHOICES,
                              default="pending", verbose_name=_("Status"))

    created_by = models.ForeignKey("accounts.CustomUser", on_delete=models.SET_NULL, null=True,
                                   blank=True, related_name="created_inventory_audits", verbose_name=_("Created By"))

    validated_by = models.ForeignKey("accounts.CustomUser", on_delete=models.SET_NULL, null=True,
                                     blank=True, related_name="validated_inventory_audits", verbose_name=_("Validated By"))

    validated_at = models.DateTimeField(
        null=True, blank=True, verbose_name=_("Validated At"))

    reason = models.CharField(max_length=512, verbose_name=_("Audit Reason"))

    comment = models.TextField(
        blank=True, null=True, verbose_name=_("General Comments"))

    stock_snapshot_at = models.DateTimeField(default=timezone.now, verbose_name=_(
        "Stock Snapshot Time"), help_text=_("Time at which expected quantities were captured."))

    model_icon = "fa-solid fa-clipboard-check"

    class Meta:
        ordering = ("-created_at",)
        verbose_name = _("Inventory Audit")
        verbose_name_plural = _("Inventory Audits")
        permissions = [
            ("import_inventoryaudit", "Can import inventory audits"),
            ("export_inventoryaudit", "Can export inventory audits"),
            ("manage_inventoryaudit", "Can manage all inventory audits"),
        ]

    def __str__(self):
        return f"Inventory Audit #{self.id} ({self.status})"

    # -----------------------------------------------------
    # VALIDATION RULES
    # -----------------------------------------------------

    def clean(self):
        super().clean()

        # If audit is marked as validated, enforce rules
        if self.status == "validated":

            if not self.validated_by:
                raise ValidationError(
                    _("A validated audit must have a validator.")
                )

            if self.items.exclude(discrepancy=0).exists():
                raise ValidationError(
                    _("This audit cannot be validated because there are unresolved discrepancies.")
                )

    # -----------------------------------------------------
    # STOCK ADJUSTMENT
    # -----------------------------------------------------

    def apply_adjustments(self):
        """
        Applies stock corrections for all items with discrepancies.
        Must be called explicitly before validation if discrepancies exist.
        """
        with transaction.atomic():
            for item in self.items.select_related("product_stock"):
                if item.discrepancy != 0:
                    stock = item.product_stock
                    delta = int(item.discrepancy)

                    if delta > 0:
                        audit_batch, _ = ProductBatch.objects.get_or_create(
                            product_stock=stock,
                            batch_number=f"AUDIT-{self.id}",
                            defaults={
                                "organization": self.organization,
                                "pharmacy": self.pharmacy,
                                "expiry_date": timezone.now().date() + timedelta(days=3650),
                                "quantity": 0,
                            },
                        )
                        audit_batch.quantity += delta
                        audit_batch.save(update_fields=["quantity"])
                        continue

                    remaining = abs(delta)
                    batches = stock.batches.select_for_update().order_by("expiry_date")
                    for batch in batches:
                        if remaining <= 0:
                            break
                        if batch.quantity <= 0:
                            continue
                        deduct = min(batch.quantity, remaining)
                        batch.quantity -= deduct
                        batch.save(update_fields=["quantity"])
                        remaining -= deduct

                    if remaining > 0:
                        raise ValidationError(
                            _("Not enough stock in batches for %(product)s") % {
                                "product": stock.product.name}
                        )

    # -----------------------------------------------------
    # VALIDATION ACTION
    # -----------------------------------------------------

    def validate_audit(self, user):
        """
        Validates the audit.
        Audit cannot be validated if discrepancies exist.
        """

        if self.items.exclude(discrepancy=0).exists():
            raise ValidationError(
                _("Cannot validate audit with unresolved discrepancies.")
            )

        self.status = "validated"
        self.validated_by = user
        self.validated_at = timezone.now()

        self.save(update_fields=[
            "status",
            "validated_by",
            "validated_at",
            "updated_at",
        ])


class InventoryAuditItem(ArchivableModel):
    """
    Compares physical count vs computed batch stock.
    """

    TENANT_FILTER = "inventory_audit__pharmacy__organization"
    objects = TenantManager()

    inventory_audit = models.ForeignKey(
        InventoryAudit,
        on_delete=models.CASCADE,
        related_name="items"
    )

    product_stock = models.ForeignKey(
        ProductStock,
        on_delete=models.CASCADE,
        related_name="inventory_audit_items"
    )
    product_batch = models.ForeignKey(
        ProductBatch,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    quantity_expected = models.PositiveIntegerField(default=0)
    quantity_found = models.PositiveIntegerField(default=0)

    discrepancy = models.IntegerField(editable=False)

    comment = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    class Meta:
        verbose_name = _("Inventory Audit Item")
        verbose_name_plural = _("Inventory Audit Items")
        ordering = ("product_stock__product__name",)
        constraints = [
            models.UniqueConstraint(
                fields=["inventory_audit", "product_stock"],
                name="uniq_audit_product_stock",
            )
        ]

    def __str__(self):
        return f"{self.product_stock.product.name}"

    # -----------------------------
    # FIXED LOGIC
    # -----------------------------

    def compute_expected_quantity(self):
        """
        Derived from batches (NOT ProductStock field)
        """
        return self.product_stock.batches.aggregate(
            total=models.Sum("quantity")
        )["total"] or 0

    def save(self, *args, **kwargs):
        if not self.pk:
            self.quantity_expected = self.compute_expected_quantity()

        self.discrepancy = self.quantity_found - self.quantity_expected
        super().save(*args, **kwargs)
