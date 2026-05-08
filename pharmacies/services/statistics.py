from django.db.models import Sum, Count, F, DecimalField, ExpressionWrapper
from django.db.models.functions import Coalesce
from pharmacies.models import *


class BasePharmacyStatsService:
    """
    Heavy lifting happens here.
    Accepts a ProductStock queryset already scoped.
    """

    def __init__(self, stock_queryset):
        self.stock_queryset = stock_queryset

    # -------------------------
    # STOCK STATS
    # -------------------------
    def stock_stats(self):
        return self.stock_queryset.aggregate(
            total_stock=Coalesce(Sum("quantity"), 0),
            total_stock_records=Count("id")
        )

    # -------------------------
    # SALES STATS
    # -------------------------
    def sales_stats(self):
        sale_items = SaleItem.objects.filter(
            product_stock__in=self.stock_queryset
        )

        return sale_items.aggregate(
            total_units_sold=Coalesce(Sum("quantity"), 0),
            total_revenue=Coalesce(Sum("total_price"), 0),
        )

    # -------------------------
    # INVENTORY MOVEMENTS
    # -------------------------
    def movement_stats(self):
        movements = InventoryMovementItem.objects.filter(
            product_stock__in=self.stock_queryset
        )

        entries = movements.filter(
            inventory_movement__movement_type="entry"
        ).aggregate(total=Coalesce(Sum("quantity"), 0))

        exits = movements.filter(
            inventory_movement__movement_type="exit"
        ).aggregate(total=Coalesce(Sum("quantity"), 0))

        return {
            "total_entries": entries["total"],
            "total_exits": exits["total"],
        }

    # -------------------------
    # INVENTORY AUDITS
    # -------------------------
    def audit_stats(self):
        audits = InventoryAuditItem.objects.filter(
            product_stock__in=self.stock_queryset
        )

        return audits.aggregate(
            total_discrepancy=Coalesce(Sum("discrepancy"), 0),
        )

    # -------------------------
    # FULL OVERVIEW
    # -------------------------
    def full_stats(self):
        data = {}
        data.update(self.stock_stats())
        data.update(self.sales_stats())
        data.update(self.movement_stats())
        data.update(self.audit_stats())
        return data