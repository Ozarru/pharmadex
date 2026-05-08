from import_export import fields
from import_export.widgets import ForeignKeyWidget
from decimal import Decimal
from django.contrib.auth import get_user_model
from base.resources import BaseResource
from .models import (
    Pharmacy,
    ProductCategory,
    ProductSubcategory,
    Product,
    ProductStock,
    Sale,
    SaleItem,
    Purchase,
    InventoryMovement,
    InventoryMovementItem,
    InventoryAudit,
    InventoryAuditItem,
)
from organizations.models import Organization
from organizations.models import Customer
from django.utils.translation import gettext_lazy as _

User = get_user_model()


# -------------------------------
# Pharmacy Resource
# -------------------------------
class PharmacyResource(BaseResource):
    organization = fields.Field(
        column_name="organization",
        attribute="organization",
        widget=ForeignKeyWidget(Organization, "slug")
    )

    class Meta(BaseResource.Meta):
        model = Pharmacy
        import_id_fields = ("name",
                            "organization")
        fields = (
            "id",
            "created_at",
            "created_by",            
            "organization",
            "name",
            "address",
            "is_active")
        export_order = fields


# -------------------------------
# Product Categorization Resources
# -------------------------------
class ProductCategoryResource(BaseResource):
    class Meta(BaseResource.Meta):
        model = ProductCategory
        import_id_fields = ("name",)
        fields = (
            "id",
            "created_at",
            "created_by",            
            "name",
            "description",
            "is_active")
        export_order = fields


class ProductSubcategoryResource(BaseResource):
    category = fields.Field(
        column_name="category",
        attribute="category",
        widget=ForeignKeyWidget(ProductCategory, "name")
    )

    class Meta(BaseResource.Meta):
        model = ProductSubcategory
        import_id_fields = ("category",
                            "name")
        fields = (
            "id",
            "created_at",
            "created_by",            
            "category",
            "name",
            "is_active")
        export_order = fields


# -------------------------------
# Product & Stock Resources
# -------------------------------
class ProductResource(BaseResource):
    subcategory = fields.Field(
        column_name="subcategory",
        attribute="subcategory",
        widget=ForeignKeyWidget(ProductSubcategory, "name")
    )
    organization = fields.Field(
        column_name="organization",
        attribute="organization",
        widget=ForeignKeyWidget(Organization, "slug")
    )

    class Meta(BaseResource.Meta):
        model = Product
        import_id_fields = ("subcategory",
                            "name",
                            "organization")
        fields = (
            "id",
            "created_at_date",
            "created_at_time",
            "organization",
            "subcategory",
            "brand",
            "name",
            "code_name",
            "description",
            "price",
            "cost",
            "is_active",
            "min_stock_threshold",
            "max_stock_threshold",
        )
        export_order = fields


class ProductStockResource(BaseResource):
    product = fields.Field(
        column_name="product",
        attribute="product",
        widget=ForeignKeyWidget(Product, "code_name")
    )
    organization = fields.Field(
        column_name="organization",
        attribute="organization",
        widget=ForeignKeyWidget(Organization, "slug")
    )

    class Meta(BaseResource.Meta):
        model = ProductStock
        import_id_fields = ("organization",
                            "product")
        fields = (
            "id",
            "created_at",
            "created_by",            
            "organization",
            "product",
            "quantity",
            "price",
            "cost")
        export_order = fields


# -------------------------------
# Sale Resources
# -------------------------------
class SaleResource(BaseResource):

    pharmacy = fields.Field(
        column_name="pharmacy",
        attribute="pharmacy",
        widget=ForeignKeyWidget(Pharmacy, "name")
    )
    vendor = fields.Field(
        column_name=_("Vendor"),
        attribute="vendor",
    )
    customer = fields.Field(
        column_name="customer",
        attribute="customer",
        widget=ForeignKeyWidget(Customer, "email")
    )
    items = fields.Field(
        column_name="items",
        attribute="items",
    )

    def dehydrate_vendor(self, obj):
        user = obj.vendor
        if not user:
            return ""

        full_name = f"{user.first_name} {user.last_name}".strip()
        email = user.email

        if full_name:
            return f"{full_name} ({email})"
        return email

    def dehydrate_items(self, obj: Sale):
        """
        Returns a string listing all items in the sale with
        quantity, unit price, and total price.
        """
        lines = []
        for item in obj.items.all():
            lines.append(
                f"{item.product_stock.product.name} x{item.quantity} @ {item.unit_price:.2f} = {item.total_price:.2f}")
        # separates items by pipe, you can use comma or newline
        return " | ".join(lines)

    class Meta(BaseResource.Meta):
        model = Sale
        import_id_fields = ("id",)
        fields = (
            "id",
            "created_at",
            "created_by",
            "pharmacy",
            "vendor",
            "customer",
            "items",        # new column with product summary
            "total_amount",
            "notes",
        )
        export_order = fields


class SaleItemResource(BaseResource):
    sale = fields.Field(
        column_name="sale",
        attribute="sale",
        widget=ForeignKeyWidget(Sale, "id")
    )
    product_stock = fields.Field(
        column_name="product_stock",
        attribute="product_stock",
        widget=ForeignKeyWidget(ProductStock, "id")
    )

    class Meta(BaseResource.Meta):
        model = SaleItem
        import_id_fields = ("id",)
        fields = (
            "id",
            "created_at",
            "created_by",
            "sale",
            "product_stock",
            "quantity",
            "unit_price",
            "total_price")
        export_order = fields


# -------------------------------
# Purchase Resource
# -------------------------------
class PurchaseResource(BaseResource):
    organization = fields.Field(
        column_name="organization",
        attribute="organization",
        widget=ForeignKeyWidget(Organization, "slug")
    )

    class Meta(BaseResource.Meta):
        model = Purchase
        import_id_fields = ("id",)
        fields = (
            "id",
            "created_at",
            "created_by",
            "organization",
            "items",
            "total_amount",
            "status",
            "received_at",
            "notes")
        export_order = fields


# -------------------------------
# Inventory Movement Resources
# -------------------------------
class InventoryMovementResource(BaseResource):
    pharmacy = fields.Field(
        column_name="pharmacy",
        attribute="pharmacy",
        widget=ForeignKeyWidget(Pharmacy, "name")
    )
    validated_by = fields.Field(
        column_name="validated_by",
        attribute="validated_by",
        widget=ForeignKeyWidget(User, "email")
    )

    class Meta(BaseResource.Meta):
        model = InventoryMovement
        import_id_fields = ("id",)
        fields = (
            "id",
            "created_at",
            "created_by",
            "pharmacy",
            "reference",
            "movement_type",
            "status",
            "reason",
            "comment")
        export_order = fields


class InventoryMovementItemResource(BaseResource):
    inventory_movement = fields.Field(
        column_name="inventory_movement",
        attribute="inventory_movement",
        widget=ForeignKeyWidget(InventoryMovement, "id")
    )
    product_stock = fields.Field(
        column_name="product_stock",
        attribute="product_stock",
        widget=ForeignKeyWidget(ProductStock, "id")
    )

    class Meta(BaseResource.Meta):
        model = InventoryMovementItem
        import_id_fields = ("id",)
        fields = (
            "id",
            "created_at",
            "created_by",
            "inventory_movement",
            "product_stock",
            "quantity",
            "comment")
        export_order = fields


# -------------------------------
# Inventory Audit Resources
# -------------------------------
class InventoryAuditResource(BaseResource):
    pharmacy = fields.Field(
        column_name="pharmacy",
        attribute="pharmacy",
        widget=ForeignKeyWidget(Pharmacy, "name")
    )
    validated_by = fields.Field(
        column_name="validated_by",
        attribute="validated_by",
        widget=ForeignKeyWidget(User, "email")
    )

    class Meta(BaseResource.Meta):
        model = InventoryAudit
        import_id_fields = ("id",)
        fields = (
            "id",
            "created_at",
            "created_by",            
            "validated_by",
            "pharmacy",
            "status",
            "validated_by",
            "validated_at",
            "reason",
            "comment",
            "stock_snapshot_at")
        export_order = fields


class InventoryAuditItemResource(BaseResource):
    inventory_audit = fields.Field(
        column_name="inventory_audit",
        attribute="inventory_audit",
        widget=ForeignKeyWidget(InventoryAudit, "id")
    )
    product_stock = fields.Field(
        column_name="product_stock",
        attribute="product_stock",
        widget=ForeignKeyWidget(ProductStock, "id")
    )

    class Meta(BaseResource.Meta):
        model = InventoryAuditItem
        import_id_fields = ("id",)
        fields = (
            "id",
            "created_at",
            "created_by",            
            "inventory_audit",
            "product_stock",
            "quantity_expected",
            "quantity_found",
            "discrepancy",
            "comment")
        export_order = fields
