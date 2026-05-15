from django.db.models import (
    Sum,
    Count,
    F,
    Avg,
    DecimalField,
    ExpressionWrapper,
)
from django.db.models.functions import (
    Coalesce,
    TruncDay,
)
from datetime import timedelta
from django.utils.timezone import now
from collections import defaultdict
from pharmacies.models import *

MONEY_FIELD = DecimalField(
    max_digits=12,
    decimal_places=2
)

class PharmacyStatsService:
    """
    Centralized analytics service.

    Accepts a scoped ProductStock queryset.
    Everything derives from this queryset.
    """

    def __init__(self, stock_queryset):
        self.stock_queryset = stock_queryset

        self.sale_items = SaleItem.objects.filter(
            product_stock__in=self.stock_queryset
        )

        self.sales = Sale.objects.filter(
            items__product_stock__in=self.stock_queryset
        ).distinct()

        self.movements = InventoryMovementItem.objects.filter(
            product_stock__in=self.stock_queryset
        )

        self.audits = InventoryAuditItem.objects.filter(
            product_stock__in=self.stock_queryset
        )

    # =====================================================
    # STOCK STATS
    # =====================================================
    def stock_stats(self):
        return self.stock_queryset.aggregate(
            total_stock=Coalesce(
                Sum("batches__quantity"),
                0
            ),
            total_stock_records=Count("id")
        )

    # =====================================================
    # SALES STATS
    # =====================================================
    def sales_stats(self):
        return self.sale_items.aggregate(
            total_units_sold=Coalesce(
                Sum("quantity"),
                0
            ),

            total_revenue=Coalesce(
                Sum("total_price"),
                0,
                output_field=DecimalField()
            ),

            avg_sale_value=Coalesce(
                Avg("total_price"),
                0,
                output_field=DecimalField()
            ),
        )

    # =====================================================
    # MOVEMENT STATS
    # =====================================================
    def movement_stats(self):
        entries = self.movements.filter(
            inventory_movement__movement_type="entry"
        ).aggregate(
            total=Coalesce(Sum("quantity"), 0)
        )

        exits = self.movements.filter(
            inventory_movement__movement_type="exit"
        ).aggregate(
            total=Coalesce(Sum("quantity"), 0)
        )

        return {
            "total_entries": entries["total"],
            "total_exits": exits["total"],
        }

    # =====================================================
    # AUDIT STATS
    # =====================================================
    def audit_stats(self):
        return self.audits.aggregate(
            total_discrepancy=Coalesce(
                Sum("discrepancy"),
                0
            ),
        )

    # =====================================================
    # REVENUE STATS
    # =====================================================
    def revenue_stats(self):
        today = now().date()

        month_start = today.replace(day=1)

        last_7_days = today - timedelta(days=6)

        last_24_hours = now() - timedelta(hours=24)

        return {
            "today_revenue": self.sales.filter(
                created_at__date=today
            ).aggregate(
                total=Coalesce(
                    Sum("total_amount"),
                    0,
                    output_field=MONEY_FIELD
                )
            )["total"],

            "monthly_revenue": self.sales.filter(
                created_at__date__gte=month_start
            ).aggregate(
                total=Coalesce(
                    Sum("total_amount"),
                    0,
                    output_field=MONEY_FIELD
                )
            )["total"],

            "last_7_days_revenue": self.sales.filter(
                created_at__date__gte=last_7_days
            ).aggregate(
                total=Coalesce(
                    Sum("total_amount"),
                    0,
                    output_field=MONEY_FIELD
                )
            )["total"],

            "last_24h_revenue": self.sales.filter(
                created_at__gte=last_24_hours
            ).aggregate(
                total=Coalesce(
                    Sum("total_amount"),
                    0,
                    output_field=MONEY_FIELD
                )
            )["total"],
        }
    # =====================================================
    # TOP PRODUCTS
    # =====================================================
    def top_products(self, limit=5):
        return (
            self.sale_items
            .values(
                "product_stock__product__name"
            )
            .annotate(
                quantity=Sum("quantity"),
                revenue=Sum("total_price"),
            )
            .order_by("-revenue")[:limit]
        )

    # =====================================================
    # SALES BY CATEGORY
    # =====================================================
    def sales_by_category(self):
        return (
            self.sale_items
            .values(
                "product_stock__product__subcategory__category__name"
            )
            .annotate(
                revenue=Sum("total_price"),
                quantity=Sum("quantity"),
            )
            .order_by("-revenue")
        )

    # =====================================================
    # CHARTS
    # =====================================================
    def chart_stats(self):
        today = now().date()

        last_30_days = today - timedelta(days=29)
        last_7_days = today - timedelta(days=6)

        last_24_hours = now() - timedelta(hours=24)

        daily_sales = (
            self.sales
            .filter(created_at__date__gte=last_30_days)
            .annotate(day=TruncDay("created_at"))
            .values("day")
            .annotate(
                revenue=Sum("total_amount"),
                sales=Count("id"),
            )
            .order_by("day")
        )

        weekly_sales = (
            self.sales
            .filter(created_at__date__gte=last_7_days)
            .annotate(day=TruncDay("created_at"))
            .values("day")
            .annotate(
                revenue=Sum("total_amount"),
                sales=Count("id"),
            )
            .order_by("day")
        )

        last_24h_sales = (
            self.sales
            .filter(created_at__gte=last_24_hours)
            .annotate(day=TruncDay("created_at"))
            .values("day")
            .annotate(
                revenue=Sum("total_amount"),
                sales=Count("id"),
            )
            .order_by("day")
        )

        return {
            "daily_sales": list(daily_sales),
            "weekly_sales": list(weekly_sales),
            "last_24h_sales": list(last_24h_sales),
        }

    def monthly_trend(self):
        today = now().date()

        last_30_days = today - timedelta(days=29)

        # ------------------------------------------------
        # SALES
        # ------------------------------------------------
        sales = (
            self.sales
            .filter(created_at__date__gte=last_30_days)
            .annotate(day=TruncDay("created_at"))
            .values("day")
            .annotate(
                total=Sum("total_amount")
            )
            .order_by("day")
        )

        # ------------------------------------------------
        # EXPENDITURES (cost basis)
        # ------------------------------------------------
        expenditures = (
            self.sale_items
            .filter(sale__created_at__date__gte=last_30_days)
            .annotate(day=TruncDay("sale__created_at"))
            .values("day")
            .annotate(
                total=Sum(
                    ExpressionWrapper(
                        F("quantity") *
                        F("product_stock__cost"),
                        output_field=DecimalField()
                    )
                )
            )
            .order_by("day")
        )

        # ------------------------------------------------
        # LOSSES
        # expired + damaged inventory
        # ------------------------------------------------
        loss_batches = ProductBatch.objects.filter(
            product_stock__in=self.stock_queryset
        ).filter(
            models.Q(expiry_date__lt=today) |
            models.Q(is_damaged=True)
        )

        losses = (
            loss_batches
            .annotate(day=TruncDay("updated_at"))
            .values("day")
            .annotate(
                total=Sum(
                    ExpressionWrapper(
                        F("quantity") *
                        F("product_stock__cost"),
                        output_field=DecimalField()
                    )
                )
            )
            .order_by("day")
        )

        # ------------------------------------------------
        # NORMALIZE
        # ------------------------------------------------
        chart = defaultdict(lambda: {
            "sales": 0,
            "expenditures": 0,
            "losses": 0,
        })

        for row in sales:
            chart[row["day"].date()]["sales"] = float(
                row["total"] or 0
            )

        for row in expenditures:
            chart[row["day"].date()]["expenditures"] = float(
                row["total"] or 0
            )

        for row in losses:
            chart[row["day"].date()]["losses"] = float(
                row["total"] or 0
            )

        # ------------------------------------------------
        # FINAL SERIES
        # ------------------------------------------------
        labels = []

        sales_data = []
        expenditures_data = []
        losses_data = []
        profit_data = []

        for i in range(30):
            day = last_30_days + timedelta(days=i)

            item = chart[day]

            sales_value = item["sales"]
            expenditures_value = item["expenditures"]
            losses_value = item["losses"]

            profit_value = (
                sales_value -
                expenditures_value -
                losses_value
            )

            labels.append(
                day.strftime("%b %d")
            )

            sales_data.append(sales_value)
            expenditures_data.append(expenditures_value)
            losses_data.append(losses_value)
            profit_data.append(profit_value)

        return {
            "labels": labels,
            "sales": sales_data,
            "expenditures": expenditures_data,
            "losses": losses_data,
            "profit": profit_data,
        }
    
    # =====================================================
    # FULL DASHBOARD
    # =====================================================
    def dashboard(self):
        data = {}

        try:
            data.update(self.stock_stats())
        except Exception as e:
            data["stock_error"] = str(e)

        try:
            data.update(self.sales_stats())
        except Exception as e:
            data["sales_error"] = str(e)

        try:
            data.update(self.movement_stats())
        except Exception as e:
            data["movement_error"] = str(e)

        try:
            data.update(self.audit_stats())
        except Exception as e:
            data["audit_error"] = str(e)

        try:
            data.update(self.revenue_stats())
        except Exception as e:
            data["revenue_error"] = str(e)

        try:
            data.update(self.chart_stats())
        except Exception as e:
            data["chart_error"] = str(e)

        data["top_products"] = self.top_products()
        data["sales_by_category"] = self.sales_by_category()

        return data


