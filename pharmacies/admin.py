from django.contrib import admin
from .models import *
from django.contrib.admin import SimpleListFilter, RelatedOnlyFieldListFilter


@admin.register(Pharmacy)
class PharmacyAdmin(admin.ModelAdmin):
    search_fields = [
        "name",
        "code",
        "address",
        "phone_number",
        "organization__name",
    ]

    list_filter = [
        "organization",
        "status",
    ]

    list_display = [
        "organization",
        "name",
        "code",
        "phone_number",
        "status",
    ]


@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    search_fields = [
        "name",
        "description",
    ]

    list_filter = [
        "is_active",
    ]

    list_display = [
        "name",
        "is_active",
    ]


@admin.register(ProductSubcategory)
class ProductSubcategoryAdmin(admin.ModelAdmin):
    search_fields = [
        "name",
        "category__name",
    ]

    list_filter = [
        "category",
        "is_active",
    ]

    list_display = [
        "category",
        "name",
        "is_active",
    ]


class ProductCategoryFilter(admin.SimpleListFilter):
    title = "Category"
    parameter_name = "category"  # must be a simple GET key

    def lookups(self, request, model_admin):
        # Only include categories that have products
        categories = ProductCategory.objects.filter(
            product_subcategories__products__isnull=False
        ).distinct()
        return [(c.id, c.name) for c in categories]

    def queryset(self, request, queryset):
        if self.value():  # value comes from GET
            # Filter Product → Subcategory → Category
            return queryset.filter(subcategory__category_id=self.value())
        return queryset
    

class BatchQuantityStatusFilter(SimpleListFilter):
    title = "Quantity"
    parameter_name = "quantity_status"

    def lookups(self, request, model_admin):
        return [
            ("available", "Available (>0)"),
            ("empty", "Empty (=0)"),
        ]

    def queryset(self, request, queryset):
        if self.value() == "available":
            return queryset.filter(quantity__gt=0)
        if self.value() == "empty":
            return queryset.filter(quantity=0)
        return queryset


class BatchUsabilityStatusFilter(SimpleListFilter):
    title = "Usability"
    parameter_name = "usability_status"

    def lookups(self, request, model_admin):
        return [
            ("usable", "Usable"),
            ("expired", "Expired"),
        ]

    def queryset(self, request, queryset):
        from django.utils import timezone

        today = timezone.now().date()
        if self.value() == "usable":
            return queryset.filter(quantity__gt=0, expiry_date__gte=today)
        if self.value() == "expired":
            return queryset.filter(expiry_date__lt=today, quantity__gt=0)
        return queryset


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    search_fields = [
        "name",
        "brand",
        "code_name",
        "description",
        "organization__name",
        "subcategory__name",
        "subcategory__category__name",
    ]

    list_filter = [
        # "organization",
        "subcategory__category",
        "subcategory",
        "is_active",
    ]

    list_display = [
        # "image",
        "name",
        "code_name",
        "subcategory",
        # "cost",
        "price",
        "is_active",
    ]


@admin.register(ProductStock)
class ProductStockAdmin(admin.ModelAdmin):
    # Search by related product fields
    search_fields = [
        "product__name",
        "product__brand",
        "product__code_name",
        "product__description",
        "product__organization__name",
        "product__subcategory__name",
        "product__subcategory__category__name",
    ]

    # Filters in the sidebar
    list_filter = [
        "product__organization",
        "product__subcategory__category",
        "product__subcategory",
        "product__is_active",
    ]

    # Columns to display in the changelist
    list_display = [
        "image",
        "product_name",
        "product_categorization",
        "quantity",
        # "cost",
        "price",
        # "get_progress",
    ]

    # Optional: make quantity, cost, price read-only in admin
    readonly_fields = [
        "quantity",
        "cost",
        "price",
    ]
    
    list_display_image_fields = {"image"}


@admin.register(ProductBatch)
class ProductBatchAdmin(admin.ModelAdmin):

    search_fields = [
        "batch_number",
        "product_stock__product__name",
        "product_stock__product__code_name",
    ]

    list_filter = [
        "is_active",
        BatchQuantityStatusFilter,
        BatchUsabilityStatusFilter,
        "expiry_date",
        "product_stock__product__subcategory__category",
        "product_stock__product__subcategory",
        "product_stock__product",
    ]

    list_display = [
        "product_stock__product__name",
        # "batch_number",
        "quantity",
        "expiry_date",
        "days_to_expiry_display",
        "quantity_status",
        "usability_status",
        "is_active",
    ]

    ordering = ["expiry_date"]

    list_select_related = ("product_stock__product",)
    
    # ---------------------------
    # Days
    # ---------------------------
    def product_stock__product__name(self, obj):
        return obj.product_stock.product.name
    product_stock__product__name.short_description = "Product"
    
    def days_to_expiry_display(self, obj):
        return obj.days_to_expiry
    days_to_expiry_display.short_description = "Days to Expiry"


class PrescriptionItemInline(admin.TabularInline):
    model = PrescriptionItem
    extra = 1

    fields = [
        "product",
        "quantity",
        "dosage",
        "duration_days",
        "dispensed_quantity",
    ]
    
@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):

    search_fields = [
        "rx_number",
        "patient__last_name",
        "patient__first_name",
    ]

    list_filter = [
        "status",
        "issued_date",
    ]

    list_display = [
        "patient",
        "status",
        "issued_date",
    ]

    inlines = [PrescriptionItemInline]

    ordering = ["-issued_date"]


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    search_fields = [
        # "id",
        "vendor__username",
        "vendor__first_name",
        "vendor__last_name",
        "customer__first_name",
        "customer__last_name",
        "customer__email",
        "customer__phone_number",
        "notes",
    ]

    list_filter = [
        "organization",
        "vendor",
        "customer",
        "created_at",
    ]

    list_display = [
        "created_at",
        "vendor",
        "customer",
        "total_items",
        "total_amount",
        "status",
    ]


@admin.register(SaleItem)
class SaleItemAdmin(admin.ModelAdmin):
    search_fields = [
        "sale__id",
        "product_stock__product__name",
        "product_stock__product__brand",
        "sale__customer__last_name",
        "sale__customer__first_name",
        "sale__customer__email",
        "sale__vendor__username",
    ]

    list_filter = [
        "sale__organization",
        "product_stock",
    ]

    list_display = [
        "sale",
        "product_stock",
        "quantity",
        "unit_price",
        "total_price",
    ]


# @admin.register(Purchase)
# class PurchaseAdmin(admin.ModelAdmin):
#     search_fields = [
#         "id",
#         "supplier__username",
#         "supplier__first_name",
#         "supplier__last_name",
#         "notes",
#     ]

#     list_filter = [
#         "organization",
#         "supplier",
#         "status",
#         "created_at",
#         "received_at",
#     ]

#     list_display = [
#         "id",
#         "supplier",
#         "organization",
#         "total_amount",
#         "status",
#         "received_at",
#         "created_at",
#     ]


@admin.register(InventoryMovement)
class InventoryMovementAdmin(admin.ModelAdmin):
    search_fields = [
        "reference",
        "reason",
        "comment",
        "organization__name",
    ]

    list_filter = [
        "movement_type",
        "pharmacy",
        "created_at",
        "created_by",
    ]

    list_display = [
        "created_at",
        "created_by",
        "movement_type",
        # "pharmacy",
    ]


@admin.register(InventoryMovementItem)
class InventoryMovementItemAdmin(admin.ModelAdmin):
    search_fields = [
        "inventory_movement__id",
        "product_stock__product__name",
        "product_stock__product__brand",
        "product_stock__product__code_name",
        "comment",
        "inventory_movement__organization__name",
    ]

    list_filter = [
        "inventory_movement__organization",
        "inventory_movement",
        "product_stock",
        "created_at",
    ]

    list_display = [
        "inventory_movement",
        "product_stock",
        "quantity",
        "comment",
    ]
    
    
@admin.register(InventoryAudit)
class InventoryAuditAdmin(admin.ModelAdmin):
    search_fields = [
        # "id",
        "reason",
        "comment",
        "organization__name",
        "validated_by__username",
        "validated_by__first_name",
        "validated_by__last_name",
    ]

    list_filter = [
        # "organization",
        "status",
        "stock_snapshot_at",
        "created_at",
        "created_by",
        "validated_at",
    ]

    list_display = [
        # "id",
        # "organization",
        "status",
        "stock_snapshot_at",
        "validated_by",
        "validated_at",
        "created_at",
        "created_by",
    ]


@admin.register(InventoryAuditItem)
class InventoryAuditItemAdmin(admin.ModelAdmin):
    search_fields = [
        "inventory_audit__id",
        "product_stock__product__name",
        "product_stock__product__brand",
        "product_stock__product__code_name",
        "comment",
        "inventory_audit__organization__name",
    ]

    list_filter = [
        "inventory_audit__organization",
        "inventory_audit",
        "product_stock",
        "created_at",
    ]

    list_display = [
        "inventory_audit",
        "product_stock",
        "quantity_expected",
        "quantity_found",
        "discrepancy",
        "comment",
    ]


