from django.db.models import Q, ForeignKey, F, Count, Sum, Max, ExpressionWrapper, DecimalField
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from openpyxl import Workbook
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.db.models import F, Sum
from django.db.models import Sum
from datetime import datetime, time
from django.db.models.functions import TruncDate, TruncHour, Coalesce
from django.db.models.functions import Abs
from django.db.models import Sum, Case, When, IntegerField
from django.utils.timezone import now, timedelta
from django.db.models.functions import TruncDay, TruncHour
from django.db.models import Sum, Count, Avg, F, Q
from django.views.decorators.http import require_POST, require_http_methods
import json
from django.db import transaction
from django.http import JsonResponse
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, UpdateView
from django.urls import reverse_lazy
from base.views import BaseListView, BaseDetailView, BaseParentChildFormView, BaseModelView
from django.utils.translation import gettext as _
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.db import models
from organizations.models import Customer, InsurancePolicy
from pharmacies.services.statistics import PharmacyStatsService
from utils import to_bool
from .forms import *
from .models import *
from django.core.paginator import Paginator
from django.db.models import Q


# -------------------------------
# F.B Views
# -------------------------------
@login_required(login_url='accounts:login')
def pharmacy_dashboard(request):
    header_paragraph = _("""
    Welcome to the pharmacy dashboard, where you can monitor and manage all aspects of the organization's pharmacy in one place.
    From tracking inventory levels and reviewing sales performance to managing products and orders, this dashboard
    provides a clear overview to help you make informed decisions and keep daily operations running smoothly.
""")

    context = {
        "active_page": "inventory_page",
        "model_icon": "fa-solid fa-store",
        "header_paragraph": header_paragraph,
        "title": _("Pharmacy dashboard"),
        "subtitle": _("Overview of the pharmacy pharmacy"),

    }
    return render(request, 'pharmacy/dashboard.html', context)


@login_required(login_url='accounts:login')
def inventory_dashboard(request):
    header_paragraph = _("""
    Welcome to the inventory dashboard. Monitor stock levels, track product availability,
    and stay informed about batch quantities and expiries in real time. Use this space to
    manage products efficiently, reduce stock issues, and support smooth day-to-day
    pharmacy operations.
    """)

    context = {
        "active_page": "inventory_page",
        "model_icon": "fa-solid fa-store",
        "header_paragraph": header_paragraph,
        "title": _("Inventory Dashboard"),
        "subtitle": _("Stock overview and control"),
    }
    return render(request, 'inventory/dashboard.html', context)


@login_required(login_url='accounts:login')
def pharmacy_reports(request):
    header_paragraph = _("""
    Welcome to the Pharmacy Analytics Center.
    Access detailed insights into product performance, category trends,
    sales growth, inventory efficiency, and revenue distribution.
    This dashboard helps you monitor key metrics, identify opportunities,
    and make data-driven decisions with confidence.
    """)

    context = {
        "active_page": "inventory_page",
        "model_icon": "fa-solid fa-chart-line",
        "header_paragraph": header_paragraph,
        "title": _("Pharmacy Analytics"),
        "subtitle": _("Product, Category & Sales Performance Insights"),
    }

    return render(request, 'pharmacy/reports.html', context)


@login_required(login_url="accounts:login")
def pharmacy_analytics(request):
    today = now().date()
    month_start = today.replace(day=1)
    last_30_days = today - timedelta(days=29)
    last_7_days = today - timedelta(days=6)
    last_24_hours = now() - timedelta(hours=24)

    header_paragraph = _(
        "Monitor real-time pharmacy performance: revenue trends, "
        "sales activity, inventory health, product demand, and losses."
    )

    # ------------------------------------------------
    # CORE COUNTS
    # ------------------------------------------------
    total_products = Product.objects.filter()
    active_products = total_products.filter(is_active=True)

    total_categories = ProductCategory.objects.count()

    sales_qs = Sale.objects.all()

    total_sales = sales_qs.count()

    avg_sale_value = sales_qs.aggregate(
        avg=Avg("total_amount")
    )["avg"] or 0

    # ------------------------------------------------
    # REVENUE
    # ------------------------------------------------
    total_revenue = sales_qs.aggregate(total=Sum("total_amount"))["total"] or 0
    today_revenue = sales_qs.filter(created_at__date=today).aggregate(
        total=Sum("total_amount"))["total"] or 0
    monthly_revenue = sales_qs.filter(created_at__date__gte=month_start).aggregate(
        total=Sum("total_amount"))["total"] or 0
    last_7_days_revenue = sales_qs.filter(created_at__date__gte=last_7_days).aggregate(
        total=Sum("total_amount"))["total"] or 0
    last_24h_revenue = sales_qs.filter(created_at__gte=last_24_hours).aggregate(
        total=Sum("total_amount"))["total"] or 0

    # ------------------------------------------------
    # INVENTORY
    # ------------------------------------------------
    batches = ProductBatch.objects.all()
    available_products = batches.filter(quantity__gt=0)
    expiring_products = batches.expiring()
    expired_products = batches.expired()
    damaged_products = batches.damaged()

    low_stock_products = batches.filter(quantity__lte=F(
        "product_stock__product__min_stock_threshold"))

    deadstock_cutoff_date = now() - timedelta(days=180)

    dead_stock_products = ProductBatch.objects.annotate(
        last_sale_date=Max("product_stock__sale_items__sale__created_at")
    ).filter(
        quantity__gt=0,   # only if ProductBatch HAS quantity field
        last_sale_date__lt=deadstock_cutoff_date
    )

    fmg_cutoff_date = now() - timedelta(days=30)

    fast_moving_products = ProductBatch.objects.annotate(
        sales_count=Count(
            "product_stock__sale_items",
            filter=models.Q(
                product_stock__sale_items__sale__created_at__gte=fmg_cutoff_date)
        )
    ).filter(
        sales_count__gte=10,   # threshold = high frequency
        quantity__gt=0
    )

    overstocked_products = batches.filter(quantity__gt=F(
        "product_stock__product__min_stock_threshold") * 3)

    # ------------------------------------------------
    # TOP PRODUCTS
    # ------------------------------------------------
    top_products = (
        SaleItem.objects.all()
        .values("product_stock__product__name")
        .annotate(quantity=Sum("quantity"), revenue=Sum("total_price"))
        .order_by("-revenue")[:5]
    )

    # ------------------------------------------------
    # SALES BY CATEGORY
    # ------------------------------------------------
    sales_by_category = (
        SaleItem.objects.all()
        .values("product_stock__product__subcategory__category__name")
        .annotate(revenue=Sum("total_price"), quantity=Sum("quantity"))
        .order_by("-revenue")
    )

    # ------------------------------------------------
    # LOSSES
    # ------------------------------------------------
    # 1️⃣ Inventory exits not caused by a sale
    movement_loss_items = InventoryMovementItem.objects.filter(
        inventory_movement__movement_type="exit",
        # inventory_movement__status="validated",
    ).exclude(inventory_movement__reason__iexact="sale")

    movement_loss_value = movement_loss_items.aggregate(
        total=Sum(F("quantity") * F("product_stock__product__cost"))
    )["total"] or 0

    # 2️⃣ Audit discrepancies (negative)
    audit_loss_items = InventoryAuditItem.objects.filter(
        inventory_audit__status="validated",
        discrepancy__lt=0
    )

    audit_loss_value = audit_loss_items.aggregate(
        total=Sum(F("discrepancy") * F("product_stock__product__cost"))
    )["total"] or 0
    audit_loss_value = abs(audit_loss_value)

    total_loss_value = movement_loss_value + audit_loss_value

    # ------------------------------------------------
    # TIME SERIES FOR CHARTS
    # ------------------------------------------------
    daily_sales = (
        sales_qs.filter(created_at__date__gte=last_30_days)
        .annotate(day=TruncDay("created_at"))
        .values("day")
        .annotate(revenue=Sum("total_amount"), sales=Count("id"))
        .order_by("day")
    )

    weekly_sales = (
        sales_qs.filter(created_at__date__gte=last_7_days)
        .annotate(day=TruncDay("created_at"))
        .values("day")
        .annotate(revenue=Sum("total_amount"), sales=Count("id"))
        .order_by("day")
    )

    last_24h_sales = (
        sales_qs
        .filter(created_at__gte=last_24_hours)
        .annotate(hour=TruncHour("created_at"))
        .values("hour")
        .annotate(
            revenue=Sum("total_amount"),
            sales=Count("id")
        )
        .order_by("hour")
    )

    context = {
        "active_page": "pharmacies_page",
        "model_icon": "fa-solid fa-chart-line",
        "title": _("Pharmacy Analytics"),
        "subtitle": _("Sales, Revenue, Inventory & Losses Overview"),
        "header_paragraph": header_paragraph,

        # KPIs
        "total_sales": total_sales,
        "avg_sale_value": avg_sale_value,
        "total_revenue": total_revenue,
        "today_revenue": today_revenue,
        "monthly_revenue": monthly_revenue,
        "last_7_days_revenue": last_7_days_revenue,
        "last_24h_revenue": last_24h_revenue,

        # Inventory
        "total_categories": total_categories,
        "total_products": total_products.count(),
        "active_products": active_products.count(),
        "available_stock_count": available_products.count(),
        "low_stock_count": low_stock_products.count(),
        "expiring_count": expiring_products.count(),
        "expired_count": expired_products.count(),
        "damaged_count": damaged_products.count(),
        "dead_stock_count": dead_stock_products.count(),
        "fast_moving_count": fast_moving_products.count(),
        "overstocked_count": overstocked_products.count(),

        # Tables
        "top_products": top_products,
        "sales_by_category": sales_by_category,

        # Losses
        "total_loss_value": total_loss_value,
        "movement_loss_value": movement_loss_value,
        "audit_loss_value": audit_loss_value,

        # Charts
        "daily_sales": list(daily_sales),
        "weekly_sales": list(weekly_sales),
        "last_24h_sales": list(last_24h_sales),
    }

    return render(request, "pharmacy/analytics.html", context)


# -------------------------------
# Pharmacy views
# -------------------------------
class PharmacyListView(BaseListView):
    model = Pharmacy
    template_name = 'generic/index.html'
    partial_parent_directory = 'generic'
    context_object_name = 'objects'
    active_page = 'pharmacies_page'
    title = _("Pharmacies")
    subtitle = _("Manage pharmacies (pharmacies)")
    header_paragraph = _(
        "View and manage pharmacies under the current organization.")
    object_crud_link = "pharmacies:pharmacy-create"
    object_crud_via_htmx = False


class PharmacyDetailView(BaseDetailView):
    model = Pharmacy
    template_name = "pharmacy/detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        pharmacy = self.object

        stocks = ProductStock.objects.filter(
            pharmacy=pharmacy,
            product__is_active=True,
        )

        analytics = PharmacyStatsService(stocks)

        context.update({
            **analytics.dashboard(),
            # UI
            "active_page": "pharmacies_page",
            "title": _("Pharmacy Details"),
            "subtitle": _("View pharmacy details"),
        })

        # -----------------------------
        # BASE QS
        # -----------------------------
        batches = ProductBatch.objects.filter(
            product_stock__pharmacy=pharmacy
        )

        sales_qs = Sale.objects.filter(
            pharmacy=pharmacy
        )

        sale_items_qs = SaleItem.objects.filter(
            sale__pharmacy=pharmacy
        )

        # -----------------------------
        # STOCK OVERVIEW
        # -----------------------------
        stock_items = batches.count()

        active_stock = batches.filter(quantity__gt=0).count()

        low_stock = batches.filter(
            quantity__lte=F("product_stock__product__min_stock_threshold")
        ).count()

        expiring_stock = batches.expiring().count()
        expired_stock = batches.expired().count()
        damaged_stock = batches.damaged().count()

        # -----------------------------
        # RECENT ACTIVITY (simple feed)
        # -----------------------------
        recent_sales = sales_qs.order_by("-created_at")[:5]

        recent_activity = [
            {
                "id": sale.id,
                "title": "Sale",
                "subtitle": f"Invoice #{str(sale.id)[:5]}",
                "items": f"Invoice #{sale.get_items_summary}",
                "time": sale.created_at,
                "status": sale.status,
            }
            for sale in recent_sales
        ]

        # -----------------------------
        # CONTEXT
        # -----------------------------
        context.update({
            "stock_items": stock_items,
            "active_stock": active_stock,
            "low_stock": low_stock,
            "expiring_stock": expiring_stock,
            "expired_stock": expired_stock,
            "damaged_stock": damaged_stock,

            "recent_activity": recent_activity,
        })

        return context


class PharmacyCreateView(BaseModelView, CreateView):
    model = Pharmacy
    fields = ['name', 'code', 'state_or_region', 'city', 'address', 'phone_number',
              'status', 'requires_cashier_validation']
    success_url = reverse_lazy('pharmacies:pharmacy-list')
    title = _("Add Pharmacy")
    subtitle = _("Create a new pharmacy under the current organization")

    def form_valid(self, form):
        form.instance.organization = self.request.user.profile.current_organization
        return super().form_valid(form)


class PharmacyUpdateView(BaseModelView, UpdateView):
    model = Pharmacy
    fields = ['name', 'code', 'state_or_region', 'city', 'address', 'phone_number',
              'status', 'requires_cashier_validation']
    success_url = reverse_lazy('pharmacies:pharmacy-list')
    title = _("Edit Pharmacy")
    subtitle = _("Update pharmacy details")


def pharmacy_monthly_trend(request, pk):
    pharmacy = get_object_or_404(
        Pharmacy,
        pk=pk
    )

    stocks = ProductStock.objects.filter(
        pharmacy=pharmacy,
        product__is_active=True,
    )

    analytics = PharmacyStatsService(
        stock_queryset=stocks
    )

    data = analytics.monthly_trend()

    context = {
        "pharmacy": pharmacy,
        "data": data,

        # explicit chart keys
        "labels": data.get("labels", []),
        "sales": data.get("sales", []),
        "expenditures": data.get("expenditures", []),
        "losses": data.get("losses", []),
        "profit": data.get("profit", []),
    }

    # print("\n========== MONTHLY TREND ==========")
    # print("PHARMACY:", pharmacy.name)
    # print("LABELS:", context["labels"])
    # print("SALES:", context["sales"])
    # print("EXPENDITURES:", context["expenditures"])
    # print("LOSSES:", context["losses"])
    # print("PROFIT:", context["profit"])
    # print("===================================\n")

    return JsonResponse(data)


# -------------------------------
# Product Category views
# -------------------------------
class ProductCategoryListView(BaseListView):
    model = ProductCategory
    template_name = 'generic/index.html'
    partial_parent_directory = 'generic'
    context_object_name = 'objects'
    active_page = 'inventory_page'
    title = _("Product Categories")
    subtitle = _("Manage product categories")
    header_paragraph = _("View and manage all product categories.")
    model_stats_url = model.get_stats_url()

    def get_queryset(self):
        qs = super().get_queryset()
        name = self.request.GET.get("name")

        if name:
            qs = qs.filter(name__icontains=name)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        queryset = self.get_queryset()

        total_count = queryset.count()
        active_count = queryset.filter(is_active=True).count()
        inactive_count = queryset.filter(is_active=False).count()

        context["data_groups"] = [
            (
                _("Total Categories"),
                total_count,
                "fa-solid fa-table-list",
                "blue",
            ),
            (
                _("Active Categories"),
                active_count,
                "fa-solid fa-circle-check",
                "green",
            ),
            (
                _("Inactive Categories"),
                inactive_count,
                "fa-solid fa-circle-xmark",
                "red",
            ),
            (
                _("Out of stock Categories"),
                inactive_count,
                "fa-solid fa-inbox",
                "gray",
            ),
        ]

        if not self.request.user.is_platform_admin():
            context["active_page"] = "products_page"

        return context


class ProductCategoryDetailView(BaseDetailView):
    model = ProductCategory
    template_name = "product/category/detail.html"
    context_object_name = 'category'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "active_page": "inventory_page",
            "title": _("Category Details"),
            "subtitle": _("View category information"),
            "header_paragraph": _("This page displays category details."),
        })

        if not self.request.user.is_platform_admin():
            context["active_page"] = "products_page"

        return context


class ProductCategoryCreateView(BaseModelView, CreateView):
    model = ProductCategory
    fields = ["name", "description"]
    success_url = reverse_lazy("pharmacies:product-category-list")
    title = _("Add Category")
    subtitle = _("Create a new product category")
    header_paragraph = _("Create a new category to group products.")


class ProductCategoryUpdateView(BaseModelView, UpdateView):
    model = ProductCategory
    fields = ["name", "description"]
    success_url = reverse_lazy("pharmacies:product-category-list")
    title = _("Edit Category")
    subtitle = _("Edit category details")
    header_paragraph = _("Update the category information.")


@login_required(login_url="accounts:login")
def category_analytics(request):
    today = now().date()
    last_7_days = today - timedelta(days=6)
    last_30_days = today - timedelta(days=29)

    # ================= OVERVIEW =================
    total_categories = ProductCategory.objects.count()

    sales_by_category = (
        SaleItem.objects
        .values("product_stock__product__subcategory__category__name")
        .annotate(
            quantity=models.Sum("quantity"),
            revenue=models.Sum("total_price")
        )
        .order_by("-revenue")
    )

    # ================= WEEKLY =================
    weekly_sales = (
        SaleItem.objects
        .filter(sale__created_at__date__gte=last_7_days)
        .values("sale__created_at__date")
        .annotate(revenue=models.Sum("total_price"))
        .order_by("sale__created_at__date")
    )

    # ================= MONTHLY =================
    monthly_sales = (
        SaleItem.objects
        .filter(sale__created_at__date__gte=last_30_days)
        .values("sale__created_at__date")
        .annotate(revenue=models.Sum("total_price"))
        .order_by("sale__created_at__date")
    )

    context = {
        "active_page": "category_analytics",
        "model_icon": "fa-solid fa-layer-group",
        "title": _("Category Analytics"),
        "subtitle": _("Sales performance and trends by category"),

        "total_categories": total_categories,
        "sales_by_category": sales_by_category,
        "weekly_sales": weekly_sales,
        "monthly_sales": monthly_sales,
    }

    return render(request, "product/category/analytics.html", context)


# -------------------------------
# Product Subcategory views
# -------------------------------
class ProductSubcategoryListView(BaseListView):
    model = ProductSubcategory
    template_name = 'generic/index.html'
    partial_parent_directory = 'generic'
    context_object_name = 'objects'
    active_page = 'inventory_page'
    title = _("Product Subcategories")
    subtitle = _("Manage subcategories")
    header_paragraph = _("View and manage all product subcategories.")

    def get_queryset(self):
        qs = super().get_queryset()
        name = self.request.GET.get("name")
        category = self.request.GET.get("category")

        if name:
            qs = qs.filter(name__icontains=name)
        if category:
            qs = qs.filter(category__name__icontains=category)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if not self.request.user.is_platform_admin():
            context["active_page"] = "products_page"

        return context


class ProductSubcategoryDetailView(BaseDetailView):
    model = ProductSubcategory
    template_name = "product/subcategory/detail.html"
    context_object_name = 'subcategory'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "active_page": "inventory_page",
            "title": _("Subcategory Details"),
            "subtitle": _("View subcategory information"),
            "header_paragraph": _("This page displays subcategory details."),
        })

        if not self.request.user.is_platform_admin():
            context["active_page"] = "products_page"

        return context


class ProductSubcategoryCreateView(BaseModelView, CreateView):
    model = ProductSubcategory
    fields = ["category", "name"]
    success_url = reverse_lazy("pharmacies:product-subcategory-list")
    title = _("Add Subcategory")
    subtitle = _("Create a new subcategory")
    header_paragraph = _("Create a new subcategory under a category.")


class ProductSubcategoryUpdateView(BaseModelView, UpdateView):
    model = ProductSubcategory
    fields = ["category", "name"]
    success_url = reverse_lazy("pharmacies:product-subcategory-list")
    title = _("Edit Subcategory")
    subtitle = _("Edit subcategory details")
    header_paragraph = _("Update the subcategory information.")


@login_required(login_url="accounts:login")
def subcategory_analytics(request):
    today = now().date()
    last_7_days = today - timedelta(days=6)
    last_30_days = today - timedelta(days=29)

    # ================= OVERVIEW =================
    total_subcategories = ProductSubcategory.objects.count()

    sales_by_subcategory = (
        SaleItem.objects
        .values("product_stock__product__subcategory__name")
        .annotate(
            quantity=models.Sum("quantity"),
            revenue=models.Sum("total_price")
        )
        .order_by("-revenue")
    )

    # ================= WEEKLY =================
    weekly_sales = (
        SaleItem.objects
        .filter(sale__created_at__date__gte=last_7_days)
        .values("sale__created_at__date")
        .annotate(revenue=models.Sum("total_price"))
        .order_by("sale__created_at__date")
    )

    # ================= MONTHLY =================
    monthly_sales = (
        SaleItem.objects
        .filter(sale__created_at__date__gte=last_30_days)
        .values("sale__created_at__date")
        .annotate(revenue=models.Sum("total_price"))
        .order_by("sale__created_at__date")
    )

    context = {
        "active_page": "subcategory_analytics",
        "model_icon": "fa-solid fa-tags",
        "title": _("Subcategory Analytics"),
        "subtitle": _("Sales performance and trends by subcategory"),

        "total_subcategories": total_subcategories,
        "sales_by_subcategory": sales_by_subcategory,
        "weekly_sales": weekly_sales,
        "monthly_sales": monthly_sales,
    }

    return render(request, "product/subcategory/analytics.html", context)


# -------------------------------
# Product views
# -------------------------------
class ProductListView(BaseListView):
    model = Product
    template_name = 'generic/index.html'
    partial_parent_directory = 'generic'
    context_object_name = 'objects'
    active_page = 'products_page'
    title = _("Products")
    subtitle = _("Manage products")
    header_paragraph = _("View and manage all products.")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if not self.request.user.is_platform_admin():
            context["active_page"] = "pharmacies_page"

        return context


class ProductDetailView(BaseDetailView):
    model = Product
    template_name = "product/detail.html"
    context_object_name = 'product'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "active_page": "products_page",
            "title": _("Product Details"),
            "subtitle": _("View product information"),
            "header_paragraph": _("This page displays product details and pricing."),
        })

        if not self.request.user.is_platform_admin():
            context["active_page"] = "products_page"

        return context


class ProductCreateView(BaseModelView, CreateView):
    model = Product
    fields = [
        "subcategory", "name", "code_name",
        "price", "image",  # "description",
    ]
    success_url = reverse_lazy("pharmacies:product-list")
    title = _("Add Product")
    subtitle = _("Create a new product")
    header_paragraph = _("Create a new product item.")


class ProductUpdateView(BaseModelView, UpdateView):
    model = Product
    fields = [
        "subcategory", "name", "code_name",
        "price", "image",  # "description",
    ]
    success_url = reverse_lazy("pharmacies:product-list")
    title = _("Edit Product")
    subtitle = _("Edit product details")
    header_paragraph = _("Update the product information.")


# -------------------------------
# Product Stock views
# -------------------------------
class ProductStockListView(BaseListView):
    model = ProductStock
    template_name = "generic/index.html"
    partial_parent_directory = "generic"
    context_object_name = "objects"
    active_page = "product_stocks_page"
    title = _("Product Stocks")
    subtitle = _("Manage product stock levels")
    header_paragraph = _("View and manage stock quantities for all products.")

    def get_queryset(self):
        qs = super().get_queryset().select_related(
            "product", "product__subcategory", "product__subcategory__category")
        product_name = self.request.GET.get("product_name")
        if product_name:
            qs = qs.filter(product__name__icontains=product_name)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["object_crud_link"] = None

        if not self.request.user.is_staff and self.request.user.role not in ["admin", "super_admin"]:
            context["active_page"] = "product_stocks_page"

        return context


class ProductStockDetailView(BaseDetailView):
    model = ProductStock
    template_name = "product/stock/detail.html"
    context_object_name = 'product_stock'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "active_page": "inventory_page",
            "title": _("Product Stock Details"),
            "subtitle": _("View stock information"),
            "header_paragraph": _("This page shows stock information and quantity for the product."),
        })
        if not self.request.user.is_staff and not self.request.user.is_superuser:
            context["active_page"] = "product_stocks_page"
        return context


class ProductStockUpdateView(BaseModelView, UpdateView):
    model = ProductStock
    fields = ["price", "cost"]
    success_url = reverse_lazy("pharmacies:product-stock-list")
    title = _("Edit Product Stock")
    subtitle = _("Update stock details")
    header_paragraph = _(
        "Edit the price or cost of the product stock. Quantity is managed automatically.")


# -------------------------------
# Product Stock views
# -------------------------------
class ProductBatchListView(BaseListView):
    model = ProductBatch
    template_name = 'generic/index.html'
    partial_parent_directory = 'generic'
    context_object_name = 'objects'
    active_page = 'product_batches_page'
    active_page = 'inventory_page'
    title = _("Batches Management (FEFO)")
    subtitle = _("Manage product batches")
    header_paragraph = _("View and manage all product batches.")

    def get_queryset(self):
        queryset = super().get_queryset().filter(
            pharmacy=self.request.current_pharmacy,
            # quantity__gt=0,
            # is_active=True,
        ).select_related("product_stock", "product_stock__product")

        filter_type = self.request.GET.get("filter")
        # print('filter_type : ', filter_type)
        today = timezone.now().date()
        threshold = today + timedelta(days=30)

        if filter_type == "expiring":
            queryset = queryset.filter(
                expiry_date__gte=today,
                expiry_date__lte=threshold
            ).order_by("expiry_date")

        elif filter_type == "expired":
            queryset = queryset.filter(
                expiry_date__lt=today
            ).order_by("-expiry_date")

        elif filter_type == "alerts":
            queryset = queryset.filter(
                Q(expiry_date__lt=today) |
                Q(expiry_date__lte=threshold)
            ).order_by("expiry_date")

        else:
            # default FEFO ordering
            queryset = queryset.order_by("expiry_date")

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        filter_type = self.request.GET.get("filter")

        # Always use BASE queryset for stats
        base_queryset = ProductBatch.objects.filter(
            pharmacy=self.request.current_pharmacy
        )

        today = timezone.now().date()
        threshold = today + timedelta(days=30)

        # UI header changes
        if filter_type == "expiring":
            context.update({
                "active_page": "inventory_page",
                "title": _("Expiring Batches"),
                "subtitle": _("Batches nearing expiry"),
                "header_paragraph": _("Monitor batches that will expire soon."),
                "model_icon": "fa-solid fa-triangle-exclamation",
            })

        elif filter_type == "expired":
            context.update({
                "active_page": "inventory_page",
                "title": _("Expired Batches"),
                "subtitle": _("Batches past expiry"),
                "header_paragraph": _("Review and manage expired batches."),
                "model_icon": "fa-solid fa-skull-crossbones",
            })

        elif filter_type == "alerts":
            context.update({
                "active_page": "inventory_page",
                "title": _("Stock Alerts"),
                "subtitle": _("Expiry risks and warnings"),
                "header_paragraph": _("View expired and near-expiry batches."),
                "model_icon": "fa-solid fa-bell",
            })

        else:
            # DATA GROUPS (always based on full dataset)
            total_batches = base_queryset.count()

            expired_batches = base_queryset.filter(
                expiry_date__lt=today
            ).count()

            expiring_batches = base_queryset.filter(
                expiry_date__gte=today,
                expiry_date__lte=threshold
            ).count()

            damaged_batches = base_queryset.filter(
                is_damaged=True
            ).count()

            usable_batches = base_queryset.filter(
                is_damaged=False
            ).filter(
                Q(expiry_date__gte=threshold) | Q(expiry_date__isnull=True)
            ).count()

            context["data_groups"] = [
                # (_("Total Batches"), total_batches, "fa-solid fa-layer-group", "blue"),
                (_("Usable Stock"), usable_batches,
                 "fa-solid fa-circle-check", "green"),
                (_("Damaged"), damaged_batches, "fa-solid fa-house-crack", "blue"),
                (_("Expiring Soon"), expiring_batches,
                 "fa-solid fa-triangle-exclamation", "amber"),
                (_("Expired"), expired_batches,
                 "fa-solid fa-skull-crossbones", "red"),
            ]

        return context


class ProductBatchDetailView(BaseDetailView):
    model = ProductBatch
    template_name = "product_batch/detail.html"
    context_object_name = 'batch'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "active_page": "product_batches_page",
            "title": _("Batch Details"),
            "subtitle": _("View batch information"),
            "header_paragraph": _("This page displays batch details, stock, and expiry."),
        })

        if not self.request.user.is_platform_admin():
            context["active_page"] = "product_batches_page"

        return context


class ProductBatchCreateView(BaseModelView, CreateView):
    model = ProductBatch
    fields = [
        "product_stock",
        "batch_number",
        "expiry_date",
        "manufacturing_date",
        "quantity",
        "is_active",
    ]
    success_url = reverse_lazy("pharmacies:batch-list")
    title = _("Add Batch")
    subtitle = _("Create a new batch")
    header_paragraph = _("Create a new product batch.")


class ProductBatchUpdateView(BaseModelView, UpdateView):
    model = ProductBatch
    fields = [
        "product_stock",
        "batch_number",
        "expiry_date",
        "manufacturing_date",
        "quantity",
        "is_active",
    ]
    success_url = reverse_lazy("pharmacies:batch-list")
    title = _("Edit Batch")
    subtitle = _("Edit batch details")
    header_paragraph = _("Update the batch information.")


@login_required(login_url="accounts:login")
def product_analytics(request):
    today = now().date()
    last_30_days = today - timedelta(days=29)
    last_7_days = today - timedelta(days=6)

    # ======================================================
    # BASE QUERYSETS
    # ======================================================
    products_qs = Product.objects.filter(
        is_active=True
    )

    sale_items_qs = SaleItem.objects.all()

    stocks_qs = (
        ProductStock.objects
        .filter(product__is_active=True)
        .annotate(quantity=Coalesce(Sum("batches__quantity"), 0))
    )

    # ======================================================
    # CORE KPIs
    # ======================================================
    total_products = products_qs.count()

    total_stock_quantity = ProductBatch.objects.filter(
        product_stock__product__is_active=True
    ).aggregate(total=Sum("quantity"))["total"] or 0

    low_stock_products = stocks_qs.filter(
        quantity__lte=F("product__min_stock_threshold")
    ).count()

    overstocked_products = stocks_qs.filter(
        quantity__gte=F("product__max_stock_threshold")
    ).count()

    products_with_no_sales = products_qs.exclude(
        id__in=sale_items_qs.values("product_stock__product_id")
    ).count()

    # ======================================================
    # SALES PERFORMANCE
    # ======================================================
    product_sales = (
        sale_items_qs
        .values(
            "product_stock__product__id",
            "product_stock__product__name"
        )
        .annotate(
            quantity_sold=Sum("quantity"),
            revenue=Sum("total_price"),
            sales_count=Count("sale", distinct=True),
        )
        .order_by("-revenue")
    )

    top_products = product_sales[:5]
    worst_products = product_sales.order_by("revenue")[:5]

    # ======================================================
    # LOSSES (Inventory exits NOT linked to sales + audit discrepancies)
    # ======================================================

    # 1️⃣ Inventory exits not tied to a sale
    inventory_losses = (
        InventoryMovementItem.objects.filter(
            inventory_movement__movement_type="exit",
            # inventory_movement__status="validated",
        )
        .exclude(
            inventory_movement__reference__startswith="SALE"
        )
        .values("product_stock__product__name")
        .annotate(
            lost_quantity=Sum("quantity")
        )
    )

    # 2️⃣ Audit discrepancies (negative only)
    audit_losses = (
        InventoryAuditItem.objects.filter(
            discrepancy__lt=0
        )
        .values("product_stock__product__name")
        .annotate(
            lost_quantity=Sum(F("discrepancy") * -1)
        )
    )

    # ======================================================
    # SALES BY CATEGORY & SUBCATEGORY
    # ======================================================
    sales_by_category = (
        sale_items_qs
        .values("product_stock__product__subcategory__category__name")
        .annotate(
            revenue=Sum("total_price"),
            quantity=Sum("quantity"),
        )
        .order_by("-revenue")
    )

    sales_by_subcategory = (
        sale_items_qs
        .values("product_stock__product__subcategory__name")
        .annotate(
            revenue=Sum("total_price"),
            quantity=Sum("quantity"),
        )
        .order_by("-revenue")
    )

    # ======================================================
    # TIME SERIES (FOR CHARTS)
    # ======================================================
    daily_product_sales = (
        sale_items_qs
        .filter(sale__created_at__date__gte=last_30_days)
        .annotate(day=TruncDay("sale__created_at"))
        .values("day")
        .annotate(
            quantity=Sum("quantity"),
            revenue=Sum("total_price"),
        )
        .order_by("day")
    )

    weekly_product_sales = (
        sale_items_qs
        .filter(sale__created_at__date__gte=last_7_days)
        .annotate(day=TruncDay("sale__created_at"))
        .values("day")
        .annotate(
            quantity=Sum("quantity"),
            revenue=Sum("total_price"),
        )
        .order_by("day")
    )

    # ======================================================
    # CONTEXT
    # ======================================================
    context = {
        "active_page": "products_page",
        "model_icon": "fa-solid fa-boxes-stacked",
        "title": _("Product Analytics"),
        "subtitle": _("Stock, Sales & Loss Performance"),
        "header_paragraph": _(
            "Understand product performance, inventory health, "
            "sales efficiency, and loss patterns."
        ),

        # KPIs
        "total_products": total_products,
        "total_stock_quantity": total_stock_quantity,
        "low_stock_products": low_stock_products,
        "overstocked_products": overstocked_products,
        "products_with_no_sales": products_with_no_sales,

        # Tables
        "top_products": top_products,
        "worst_products": worst_products,

        # Losses
        "inventory_losses": inventory_losses,
        "audit_losses": audit_losses,

        # Breakdowns
        "sales_by_category": sales_by_category,
        "sales_by_subcategory": sales_by_subcategory,

        # Charts
        "daily_product_sales": list(daily_product_sales),
        "weekly_product_sales": list(weekly_product_sales),
    }

    if request.user.is_platform_admin():
        context["active_page"] = "product_stats_page"

    return render(request, "product/analytics.html", context)


@login_required
@user_passes_test(lambda u: u.is_staff or u.is_superuser)
def synchronize_stock(request):
    today = timezone.now().date()

    batches = ProductBatch.objects.all()

    expired_count = 0
    damaged_count = 0
    updated_count = 0

    for batch in batches:
        updated = False

        # 1. Expired stock
        if batch.expiry_date and batch.expiry_date < today:
            if batch.is_active:
                batch.is_active = False
                updated = True
            if hasattr(batch, "status"):
                batch.status = "expired"
            expired_count += 1

        # 2. Damaged stock
        if hasattr(batch, "is_damaged") and batch.is_damaged:
            if batch.is_active:
                batch.is_active = False
                updated = True
            if hasattr(batch, "status"):
                batch.status = "damaged"
            damaged_count += 1

        # 3. Zero stock cleanup
        if hasattr(batch, "quantity") and batch.quantity <= 0:
            if batch.is_active:
                batch.is_active = False
                updated = True

        if updated:
            batch.save()
            updated_count += 1

    # optional: you can still keep a message via session
    request.session["sync_message"] = (
        f"Sync complete: {expired_count} expired, "
        f"{damaged_count} damaged, {updated_count} updated."
    )

    # return to previous page
    return redirect(request.META.get("HTTP_REFERER", "base:home"))


@login_required
@user_passes_test(lambda u: u.is_staff or u.is_superuser)
def export_problem_stock_excel(request):
    today = timezone.now().date()

    # Get relevant batches
    batches = ProductBatch.objects.filter(
        models.Q(expiry_date__lt=today) | models.Q(is_damaged=True)
    )

    # Create Excel workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Problem Stock"

    # Header row
    headers = [
        "Product",
        "Batch No",
        "Quantity",
        "Expiry Date",
        "Damaged",
        "Status"
    ]
    ws.append(headers)

    # Fill rows
    for batch in batches:
        # Determine status clearly
        if getattr(batch, "is_damaged", False):
            status = "DAMAGED"
        elif batch.expiry_date and batch.expiry_date < today:
            status = "EXPIRED"
        else:
            status = "UNKNOWN"

        ws.append([
            str(batch.product) if hasattr(batch, "product") else "",
            getattr(batch, "batch_number", ""),
            getattr(batch, "quantity", 0),
            batch.expiry_date if batch.expiry_date else "",
            "YES" if getattr(batch, "is_damaged", False) else "NO",
            status
        ])

    # Response as Excel file
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="problem_stock.xlsx"'

    wb.save(response)
    return response


class PrescriptionListView(BaseListView):
    model = Prescription
    template_name = "generic/index.html"
    context_object_name = "objects"
    active_page = "prescriptions_page"
    title = _("Prescriptions")
    subtitle = _("Manage prescriptions")
    header_paragraph = _("View and manage prescriptions.")

    def get_queryset(self):
        queryset = super().get_queryset().filter(
            # pharmacy=self.request.user.pharmacy  # ✅ if multi-tenant
        ).prefetch_related("items", "items__product")

        status = self.request.GET.get("status")
        search = self.request.GET.get("q")

        # 🔹 Filter by status (queue behavior)
        if status:
            queryset = queryset.filter(status=status)

        # 🔹 Optional search
        if search:
            queryset = queryset.filter(
                Q(patient_name__icontains=search) |
                Q(rx_number__icontains=search)
            )

        return queryset.order_by("-issued_date")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["object_crud_via_htmx"] = False

        status = self.request.GET.get("status")

        if status == "pending":
            context.update({
                "title": _("Pending Prescriptions"),
                "subtitle": _("Awaiting review"),
                "header_paragraph": _("New prescriptions waiting to be processed."),
            })

        elif status == "processing":
            context.update({
                "title": _("Processing Prescriptions"),
                "subtitle": _("Currently being prepared"),
                "header_paragraph": _("Prescriptions being filled and verified."),
            })

        elif status == "ready":
            context.update({
                "title": _("Ready for Pickup"),
                "subtitle": _("Awaiting collection"),
                "header_paragraph": _("Completed prescriptions ready for patients."),
            })

        elif status == "completed":
            context.update({
                "title": _("Completed Prescriptions"),
                "subtitle": _("Dispensed records"),
                "header_paragraph": _("All completed and dispensed prescriptions."),
            })

        elif status == "on_hold":
            context.update({
                "title": _("On Hold Prescriptions"),
                "subtitle": _("Requires attention"),
                "header_paragraph": _("Prescriptions with issues or pending actions."),
            })

        return context


class PrescriptionDetailView(BaseDetailView):
    model = Prescription
    template_name = "prescription/detail.html"
    context_object_name = 'prescription'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "active_page": "prescriptions_page",
            "title": _("Prescription Details"),
            "subtitle": _("View prescription information"),
            "header_paragraph": _("This page displays prescription details, prescribed items, and dispensing status."),
        })

        if not self.request.user.is_platform_admin():
            context["active_page"] = "prescriptions_page"

        return context


class PrescriptionUpsertView(BaseParentChildFormView):

    model = Prescription
    form_class = PrescriptionForm
    formset_class = PrescriptionItemFormSet
    template_name = "generic/parent_child_form.html"

    title_create = _("Create Prescription")
    subtitle_create = _("Add a new prescription with multiple medications.")
    title_update = _("Edit Prescription")
    subtitle_update = _("Modify prescription details and items.")

    active_page = "prescriptions_page"
    header_paragraph = _(
        "Use this form to create and manage prescriptions and their items."
    )

    success_url_name = "pharmacies:prescription-detail"

    def get_formset_kwargs(self, request, parent_obj, data=None):
        return {"pharmacy": self.get_pharmacy(request)}

    def set_parent_fields(self, request, parent_obj, is_create: bool):
        parent_obj = super().set_parent_fields(request, parent_obj, is_create)
        parent_obj.created_by = request.user
        return parent_obj

        child_obj.prescription = parent_obj
        return child_obj


# -------------------------------
# Sale views
# -------------------------------
class SaleListView(BaseListView):
    model = Sale
    template_name = 'generic/index.html'
    partial_parent_directory = 'generic'
    context_object_name = 'objects'
    active_page = 'sales_page'
    title = _("Sales")
    subtitle = _("Sales history")
    header_paragraph = _("View recorded sales transactions.")

    def get_queryset(self):
        qs = super().get_queryset()
        pharmacy = self.request.GET.get("pharmacy")

        if pharmacy:
            qs = qs.filter(pharmacy__name__icontains=pharmacy)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["object_crud_link"] = None
        context["model_update_url"] = None

        if not self.request.user.is_platform_admin():
            context["active_page"] = "sales_page"

        return context


class SaleDetailView(BaseDetailView):
    model = Sale
    template_name = "sale/detail.html"
    context_object_name = 'sale'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "active_page": "sales_page",
            "title": _("Sale Details"),
            "subtitle": _("View sale information"),
            "header_paragraph": _("This page displays sale transaction details."),
        })

        if not self.request.user.is_platform_admin():
            context["active_page"] = "stats_page"

        context["object_crud_link"] = None

        return context


@login_required(login_url='accounts:login')
def point_of_sale(request):
    customer_id = request.GET.get("current_customer")
    current_customer = None
    current_pharma = request.current_pharmacy

    # If customer passed explicitly
    if customer_id:
        current_customer = get_object_or_404(Customer, pk=customer_id)

    else:
        # Get first customer
        current_customer = Customer.objects.order_by(
            'last_name',
            'first_name'
        ).first()

        # Create default customer if none exists
        if not current_customer:
            current_customer = Customer.objects.create(
                first_name="Walk-in",
                last_name="Customer",
            )

    # Fetch all data
    product_stocks = (
        ProductStock.objects
        .select_related('product')
        .filter(
            pharmacy=current_pharma,
            product__is_active=True,
        )
        .order_by('product__name')
    )

    categories = ProductCategory.objects.all().order_by('name')
    subcategories = ProductSubcategory.objects.all().order_by('name')
    customers = Customer.objects.all().order_by(
        '-created_at',
        'last_name',
        'first_name'
    )
    insurance_policies = InsurancePolicy.objects.all().order_by('insurer__name', 'name')

    header_paragraph = _(
        "This page allows you to process sales at the point of sale. "
        "Select products, assign customers, confirm quantities, and "
        "complete transactions efficiently while keeping inventory "
        "levels automatically updated."
    )

    context = {
        "model_icon": "fa-solid fa-store",
        "active_page": "inventory_page",
        "title": _("Point of Sale"),
        "subtitle": _("Create and process sales quickly"),
        "header_paragraph": header_paragraph,
        "product_stocks": product_stocks,
        "categories": categories,
        "subcategories": subcategories,
        "customers": customers,
        "current_customer": current_customer,
        "insurance_policies": insurance_policies,
    }

    if request.user.is_platform_admin():
        context["active_page"] = "pos_page"

    return render(request, 'pharmacy/point_of_sale.html', context)


@login_required
@require_POST
def sale_checkout(request):
    try:
        data = json.loads(request.body)

        customer_id = data.get("customer_id")
        new_customer = data.get("new_customer")  # 👈 NEW
        insured_customer = data.get("insured_customer")
        items = data.get("items", [])

        is_backordered = to_bool(data.get("is_backordered"))
        is_insured = to_bool(data.get("is_insured"))
        insurance_policy_id = data.get("insurance_policy_id")
        
        print('is_backordered : ', is_backordered)

        if not items:
            return JsonResponse({"success": False, "message": "Invalid payload"}, status=400)

        # -------------------------
        # CONTEXT RESOLUTION
        # -------------------------
        profile = getattr(request.user, "profile", None)
        organization = getattr(request, "current_organization", None) or getattr(profile, "current_organization", None)
        pharmacy = getattr(request, "current_pharmacy", None) or getattr(profile, "current_pharmacy", None)

        if not organization:
            return JsonResponse({"success": False, "message": "No organization selected."}, status=400)

        if not pharmacy:
            return JsonResponse({"success": False, "message": "No pharmacy selected."}, status=400)

        # -------------------------
        # CUSTOMER RESOLUTION (CLEANED)
        # -------------------------
        customer = None

        # 1. Existing customer
        if customer_id:
            customer = get_object_or_404(Customer, pk=customer_id)

        # 2. New customer creation
        elif isinstance(new_customer, dict) and new_customer.get("first_name"):
            customer = Customer.objects.create(
                organization=organization,
                first_name=(new_customer.get("first_name") or "").strip(),
                last_name=(new_customer.get("last_name") or "").strip(),
                phone_number=(new_customer.get("phone_number") or "").strip() or None,
            )

        # 3. Insurance-based customer (legacy fallback)
        elif isinstance(insured_customer, dict) and insured_customer.get("insurance_id"):
            ins_id = str(insured_customer.get("insurance_id")).strip()

            dob = insured_customer.get("date_of_birth")
            if isinstance(dob, str):
                dob = parse_date(dob) or None

            customer, _ = Customer.objects.update_or_create(
                organization=organization,
                insurance_id=ins_id,
                defaults={
                    "first_name": (insured_customer.get("first_name") or "").strip() or None,
                    "last_name": (insured_customer.get("last_name") or "").strip() or None,
                    "phone_number": (insured_customer.get("phone_number") or "").strip() or None,
                    "date_of_birth": dob,
                },
            )

        # 4. Walk-in fallback
        if not customer:
            customer, _ = Customer.objects.get_or_create(
                organization=organization,
                first_name="Walk-in",
                last_name="Customer",
            )

        # -------------------------
        # ITEM VALIDATION
        # -------------------------
        validated_items = []
        total = 0

        for item in items:
            product_stock = get_object_or_404(ProductStock, pk=item["product_stock_id"])
            quantity = int(item["quantity"])

            if quantity <= 0:
                return JsonResponse({"success": False, "message": "Invalid quantity"}, status=400)

            if product_stock.quantity < quantity:
                return JsonResponse({
                    "success": False,
                    "message": f"Not enough stock for {product_stock.product.name}"
                }, status=400)

            unit_price = product_stock.effective_price
            line_total = unit_price * quantity

            total += line_total

            validated_items.append({
                "product_stock": product_stock,
                "quantity": quantity,
                "unit_price": unit_price,
                "line_total": line_total
            })

        # -------------------------
        # INSURANCE
        # -------------------------
        insurance_policy = None
        if is_insured and insurance_policy_id:
            insurance_policy = get_object_or_404(InsurancePolicy, pk=insurance_policy_id)

        # -------------------------
        # SALE CREATION
        # -------------------------
        with transaction.atomic():

            requires_validation = pharmacy.requires_cashier_validation

            sale = Sale.objects.create(
                organization=organization,
                pharmacy=pharmacy,
                customer=customer,
                vendor=request.user,
                created_by=request.user,
                total_amount=total,

                status="backordered" if is_backordered
                else ("pending" if requires_validation else "completed"),

                insurance_policy=insurance_policy,
                insurance_coverage_percent=getattr(insurance_policy, "coverage_percent", None),
                insurance_max_coverage_amount=getattr(insurance_policy, "max_coverage_amount", None),
                insurance_applied=bool(insurance_policy),
            )

            for item in validated_items:
                SaleItem.objects.create(
                    sale=sale,
                    product_stock=item["product_stock"],
                    quantity=item["quantity"],
                    unit_price=item["unit_price"],
                    total_price=item["line_total"]
                )

        return JsonResponse({
            "success": True,
            "sale_id": sale.id,
            "total": float(total),
            "status": sale.status
        })

    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)}, status=400)

from django.db.models import Q
@login_required
def cashier_validation(request):

    profile = getattr(request.user, "profile", None)
    organization = getattr(request, "current_organization", None) or getattr(
        profile, "current_organization", None)
    pharmacy = getattr(request, "current_pharmacy", None) or getattr(
        profile, "current_pharmacy", None)

    # Guard clause: if feature is disabled, redirect back safely
    if not pharmacy or not pharmacy.requires_cashier_validation:
        return redirect(request.META.get("HTTP_REFERER", "base:home"))

    sales = Sale.objects.filter(
        Q(organization=organization),
        Q(pharmacy=pharmacy),
        Q(status="pending")|Q(status="backordered"),
    ).order_by("-created_at")

    return render(request, "pharmacy/cashier_validation.html", {
        "sales": sales,
        "active_page": "cashier_validation_page",
        "title": "Cashier Validation",
        "subtitle": "Approve sales & clinical transactions",
    })


@login_required
@require_http_methods(["GET", "POST"])
def sale_validation_view(request, pk):

    sale = get_object_or_404(Sale, id=pk)

    profile = getattr(request.user, "profile", None)
    organization = getattr(request, "current_organization", None) or getattr(
        profile, "current_organization", None)
    pharmacy = getattr(request, "current_pharmacy", None) or getattr(
        profile, "current_pharmacy", None)

    # ----------------------------
    # SAFETY CHECKS
    # ----------------------------
    if sale.status not in "pending, backordered":
        return redirect("pharmacies:cashier-validation")

    if not sale.requires_cashier_validation:
        return redirect("pharmacies:cashier-validation")

    # ----------------------------
    # GET → RENDER TEMPLATE
    # ----------------------------
    if request.method == "GET":
        context={
            "active_page": "cashier_validation_page",
            "title": "Sale validation",
            "subtitle": "Approve pending and backordered sales here",
            "sale": sale
            
        }
        return render(request, "pharmacy/sale_validation.html", context)

    # ----------------------------
    # POST → VALIDATE SALE
    # ----------------------------
    data = json.loads(request.body)
    action = data.get("action")

    with transaction.atomic():

        if action == "approve":

            new_total = 0

            for item in data.get("items", []):
                product_stock = get_object_or_404(
                    ProductStock, id=item["product_stock_id"])
                quantity = int(item["quantity"])

                if quantity <= 0:
                    continue

                if product_stock.quantity < quantity:
                    return JsonResponse({
                        "success": False,
                        "message": f"Not enough stock for {product_stock.product.name}"
                    }, status=400)

                line_total = product_stock.effective_price * quantity

                SaleItem.objects.create(
                    sale=sale,
                    product_stock=product_stock,
                    quantity=quantity,
                    unit_price=product_stock.effective_price,
                    total_price=line_total
                )

                new_total += line_total

            sale.total_amount = new_total
            sale.status = "completed"
            sale.cashier = request.user
            sale.validated_at = timezone.now()
            sale.save()

            return JsonResponse({"success": True})

        elif action == "reject":
            sale.status = "cancelled"
            sale.cashier = request.user
            sale.validated_at = timezone.now()
            sale.save()

            return JsonResponse({"success": True})

    return JsonResponse({"success": False, "message": "Invalid action"})


@login_required(login_url="accounts:login")
def sale_analytics(request):
    today = now().date()
    month_start = today.replace(day=1)
    last_7_days = today - timedelta(days=6)
    last_24_hours = now() - timedelta(days=1)

    # -----------------------------
    # CORE KPIs
    # -----------------------------
    total_sales = Sale.objects.count()
    total_revenue = Sale.objects.aggregate(
        total=Sum("total_amount"))["total"] or 0
    today_revenue = Sale.objects.filter(created_at__date=today).aggregate(
        total=Sum("total_amount"))["total"] or 0
    monthly_revenue = Sale.objects.filter(created_at__date__gte=month_start).aggregate(
        total=Sum("total_amount"))["total"] or 0
    last_7_days_revenue = Sale.objects.filter(
        created_at__date__gte=last_7_days).aggregate(total=Sum("total_amount"))["total"] or 0
    last_24h_revenue = Sale.objects.filter(created_at__gte=last_24_hours).aggregate(
        total=Sum("total_amount"))["total"] or 0

    # -----------------------------
    # TOP PRODUCTS
    # -----------------------------
    top_products = (
        SaleItem.objects.values("product_stock__product__name")
        .annotate(quantity=Sum("quantity"), revenue=Sum("total_price"))
        .order_by("-revenue")[:5]
    )

    # -----------------------------
    # SALES BY CATEGORY
    # -----------------------------
    sales_by_category = (
        SaleItem.objects.values(
            "product_stock__product__subcategory__category__name")
        .annotate(quantity=Sum("quantity"), revenue=Sum("total_price"))
        .order_by("-revenue")
    )

    # -----------------------------
    # SALES BY SUBCATEGORY
    # -----------------------------
    sales_by_subcategory = (
        SaleItem.objects.values("product_stock__product__subcategory__name")
        .annotate(
            revenue=Sum("total_price"),
            quantity=Sum("quantity"),
        )
        .order_by("-revenue")
    )

    # -----------------------------
    # TIME SERIES (CHARTS)
    # -----------------------------
    # Daily sales for last 30 days
    daily_sales = (
        Sale.objects.filter(created_at__date__gte=today - timedelta(days=29))
        .annotate(day=TruncDay("created_at"))
        .values("day")
        .annotate(revenue=Sum("total_amount"), sales=Count("id"))
        .order_by("day")
    )

    # Weekly sales (last 7 days)
    weekly_sales = (
        Sale.objects.filter(created_at__date__gte=last_7_days)
        .annotate(day=TruncDay("created_at"))
        .values("day")
        .annotate(revenue=Sum("total_amount"), sales=Count("id"))
        .order_by("day")
    )

    # Last 24h hourly sales
    last_24h_sales = (
        Sale.objects.filter(created_at__gte=last_24_hours)
        .annotate(hour=TruncHour("created_at"))
        .values("hour")
        .annotate(revenue=Sum("total_amount"), sales=Count("id"))
        .order_by("hour")
    )

    # -----------------------------
    # LOSSES (exit movements not tied to sales + audit discrepancies)
    # -----------------------------
    total_losses = (
        InventoryMovement.objects.filter(
            movement_type="loss",
        )
        .aggregate(total=Sum("items__quantity"))["total"] or 0
    )

    context = {
        "active_page": "inventory_page",
        "model_icon": "fa-solid fa-tag",
        "title": _("Sales Analytics"),
        "subtitle": _("Revenue, Trends & Product Performance"),
        "header_paragraph": _(
            "Analyze detailed sales performance, revenue trends, and best-selling products."
        ),

        # KPIs
        "total_sales": total_sales,
        "total_revenue": total_revenue,
        "today_revenue": today_revenue,
        "monthly_revenue": monthly_revenue,
        "last_7_days_revenue": last_7_days_revenue,
        "last_24h_revenue": last_24h_revenue,
        "total_loss_value": total_losses,

        # Tables
        "top_products": top_products,
        "sales_by_category": sales_by_category,
        "sales_by_subcategory": sales_by_subcategory,

        # Charts
        "daily_sales": list(daily_sales),
        "weekly_sales": list(weekly_sales),
        "last_24h_sales": list(last_24h_sales),
    }

    if request.user.is_platform_admin():
        context["active_page"] = "sale_stats_page"

    return render(request, "sale/analytics.html", context)


# -------------------------------
# Purchase views
# -------------------------------
class PurchaseListView(BaseListView):
    # model = Purchase
    template_name = 'generic/index.html'
    partial_parent_directory = 'generic'
    context_object_name = 'objects'
    active_page = 'purchase_page'
    title = _("Purchases")
    subtitle = _("Purchase history")
    header_paragraph = _("View recorded purchase transactions.")

    def get_queryset(self):
        qs = super().get_queryset()
        pharmacy = self.request.GET.get("pharmacy")

        if pharmacy:
            qs = qs.filter(pharmacy__name__icontains=pharmacy)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["object_crud_link"] = None
        context["model_update_url"] = None

        if not self.request.user.is_platform_admin():
            context["active_page"] = "stats_page"

        return context


class PurchaseDetailView(BaseDetailView):
    # model = Purchase
    template_name = "purchases/detail.html"
    context_object_name = 'purchase'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "active_page": "purchase_page",
            "title": _("Purchase Details"),
            "subtitle": _("View purchase information"),
            "header_paragraph": _("This page displays purchase transaction details."),
        })

        if not self.request.user.is_platform_admin():
            context["active_page"] = "stats_page"

        return context


@login_required(login_url="accounts:login")
def purchase_analytics(request):
    total_purchases = Purchase.objects.count()

    total_cost = Purchase.objects.aggregate(
        total=models.Sum("total_amount")
    )["total"] or 0

    context = {
        "active_page": "inventory_page",
        "model_icon": "fa-solid fa-truck",
        "title": _("Purchase Analytics"),
        "header_paragraph": _(
            "Review purchase activity, inventory costs, and supplier transactions."
        ),
        "total_purchases": total_purchases,
        "total_cost": total_cost,
    }

    if request.user.is_platform_admin():
        context["active_page"] = "purchase_stats_page"

    return render(request, "purchase/analytics.html", context)


@login_required(login_url="accounts:login")
def inventory_performance(request):
    today = now().date()
    week_start = today - timedelta(days=6)
    month_start = today.replace(day=1)

    # -------------------------
    # Today totals
    # -------------------------
    today_data = (
        InventoryMovementItem.objects
        .filter(inventory_movement__created_at__date=today)
        .values("inventory_movement__movement_type")
        .annotate(total=Sum("quantity"))
    )

    today_entries = sum(
        i["total"] for i in today_data if i["inventory_movement__movement_type"] == "entry"
    ) or 0

    today_exits = sum(
        i["total"] for i in today_data if i["inventory_movement__movement_type"] == "exit"
    ) or 0

    # -------------------------
    # Weekly trend (last 7 days)
    # -------------------------
    weekly_data = (
        InventoryMovementItem.objects
        .filter(inventory_movement__created_at__date__gte=week_start)
        .annotate(day=TruncDate("inventory_movement__created_at"))
        .values("day", "inventory_movement__movement_type")
        .annotate(total=Sum("quantity"))
        .order_by("day")
    )

    weekly_labels = []
    weekly_entries = []
    weekly_exits = []

    for i in range(7):
        day = week_start + timedelta(days=i)
        weekly_labels.append(day.strftime("%d %b"))

        entry_qty = sum(
            d["total"] for d in weekly_data
            if d["day"] == day and d["inventory_movement__movement_type"] == "entry"
        ) or 0

        exit_qty = sum(
            d["total"] for d in weekly_data
            if d["day"] == day and d["inventory_movement__movement_type"] == "exit"
        ) or 0

        weekly_entries.append(entry_qty)
        weekly_exits.append(exit_qty)

    # -------------------------
    # Monthly totals
    # -------------------------
    monthly_data = (
        InventoryMovementItem.objects
        .filter(inventory_movement__created_at__date__gte=month_start)
        .values("inventory_movement__movement_type")
        .annotate(total=Sum("quantity"))
    )

    monthly_entries = sum(
        i["total"] for i in monthly_data if i["inventory_movement__movement_type"] == "entry"
    ) or 0

    monthly_exits = sum(
        i["total"] for i in monthly_data if i["inventory_movement__movement_type"] == "exit"
    ) or 0

    context = {
        "active_page": "inventory_analytics",
        "title": _("Inventory Performance"),
        "header_paragraph": _("Track inventory entries and exits over time."),

        "today_entries": today_entries,
        "today_exits": today_exits,
        "monthly_entries": monthly_entries,
        "monthly_exits": monthly_exits,

        "weekly_labels": weekly_labels,
        "weekly_entries": weekly_entries,
        "weekly_exits": weekly_exits,
    }

    return render(request, "inventory/performance.html", context)


# -------------------------------
# Inventory Movement views
# -------------------------------
class InventoryMovementListView(BaseListView):
    model = InventoryMovement
    template_name = 'generic/index.html'
    partial_parent_directory = 'generic'
    context_object_name = 'objects'
    active_page = 'inventory_page'
    title = _("Inventory Movements")
    subtitle = _("Movement history (entries & exits)")
    header_paragraph = _("View all recorded stock movements for products.")

    def get_queryset(self):
        qs = super().get_queryset()
        pharmacy = self.request.GET.get("pharmacy")
        movement_type = self.request.GET.get("movement_type")

        if pharmacy:
            qs = qs.filter(pharmacy__name__icontains=pharmacy)
        if movement_type in ["entry", "exit"]:
            qs = qs.filter(movement_type=movement_type)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["object_crud_via_htmx"] = False

        if not self.request.user.is_platform_admin():
            context["active_page"] = "inventory_movement_page"

        return context


class InventoryMovementDetailView(BaseDetailView):
    model = InventoryMovement
    template_name = "inventory/movement/detail.html"
    context_object_name = 'inventory_movement'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "active_page": "inventory_page",
            "title": _("Inventory Movement Details"),
            "subtitle": _("View stock movement information"),
            "header_paragraph": _("This page displays detailed information about the stock movement."),
        })

        if not self.request.user.is_platform_admin():
            context["active_page"] = "inventory_movement_page"

        return context


class InventoryMovementUpsertView(BaseParentChildFormView):

    model = InventoryMovement
    form_class = InventoryMovementForm
    formset_class = InventoryMovementItemFormSet
    template_name = "generic/parent_child_form.html"

    title_create = _("Create Stock Movement")
    subtitle_create = _("Add or remove stock from multiple products at once.")
    title_update = _("Edit Stock Movement")
    subtitle_update = _("Modify the items included in this movement.")

    active_page = "inventory_page"
    header_paragraph = _(
        "Use this form to adjust stock quantities for one or more products."
    )

    success_url_name = "pharmacies:inventory-movement-detail"

    # ---------------------------
    # Pass pharmacy to formset
    # ---------------------------
    def get_formset_kwargs(self, request, parent_obj, data=None):
        return {"pharmacy": self.get_pharmacy(request)}

    # ---------------------------
    # Set parent fields
    # ---------------------------
    def set_parent_fields(self, request, parent_obj, is_create: bool):
        parent_obj.created_by = request.user
        parent_obj.pharmacy = getattr(
            request, "current_pharmacy", None) or request.user.profile.current_pharmacy
        return parent_obj

    # ---------------------------
    # Set child fields
    # ---------------------------
    def set_child_fields(self, request, child_obj, parent_obj, is_create: bool):
        child_obj.inventory_movement = parent_obj
        return child_obj


@login_required(login_url="accounts:login")
def inventory_movement_analytics(request):
    pharmacy = getattr(request, "current_pharmacy",
                       None) or request.user.profile.current_pharmacy
    today = now()
    last_24h = today - timedelta(hours=24)
    last_7_days = today - timedelta(days=6)
    last_30_days = today - timedelta(days=29)

    movements = InventoryMovementItem.objects.filter(
        inventory_movement__pharmacy=pharmacy,
    ).select_related("inventory_movement")

    # --------------------------------------------------
    # KPI TOTALS
    # --------------------------------------------------
    totals = movements.aggregate(
        total_entries=Sum(
            Case(
                When(inventory_movement__movement_type="entry", then="quantity"),
                default=0,
                output_field=IntegerField(),
            )
        ),
        total_exits=Sum(
            Case(
                When(inventory_movement__movement_type="exit", then="quantity"),
                default=0,
                output_field=IntegerField(),
            )
        ),
    )

    # --------------------------------------------------
    # LAST 24 HOURS (HOURLY)
    # --------------------------------------------------
    hourly = (
        movements.filter(inventory_movement__created_at__gte=last_24h)
        .annotate(hour=TruncHour("inventory_movement__created_at"))
        .values("hour")
        .annotate(
            entries=Sum(
                Case(
                    When(inventory_movement__movement_type="entry", then="quantity"),
                    default=0,
                    output_field=IntegerField(),
                )
            ),
            exits=Sum(
                Case(
                    When(inventory_movement__movement_type="exit", then="quantity"),
                    default=0,
                    output_field=IntegerField(),
                )
            ),
        )
        .order_by("hour")
    )

    # --------------------------------------------------
    # LAST 7 DAYS (DAILY)
    # --------------------------------------------------
    weekly = (
        movements.filter(
            inventory_movement__created_at__date__gte=last_7_days.date())
        .annotate(day=TruncDay("inventory_movement__created_at"))
        .values("day")
        .annotate(
            entries=Sum(
                Case(
                    When(inventory_movement__movement_type="entry", then="quantity"),
                    default=0,
                    output_field=IntegerField(),
                )
            ),
            exits=Sum(
                Case(
                    When(inventory_movement__movement_type="exit", then="quantity"),
                    default=0,
                    output_field=IntegerField(),
                )
            ),
        )
        .order_by("day")
    )

    # --------------------------------------------------
    # LAST 30 DAYS (DAILY)
    # --------------------------------------------------
    monthly = (
        movements.filter(
            inventory_movement__created_at__date__gte=last_30_days.date())
        .annotate(day=TruncDay("inventory_movement__created_at"))
        .values("day")
        .annotate(
            entries=Sum(
                Case(
                    When(inventory_movement__movement_type="entry", then="quantity"),
                    default=0,
                    output_field=IntegerField(),
                )
            ),
            exits=Sum(
                Case(
                    When(inventory_movement__movement_type="exit", then="quantity"),
                    default=0,
                    output_field=IntegerField(),
                )
            ),
        )
        .order_by("day")
    )

    context = {
        "active_page": "inventory_page",
        "model_icon": "fa-solid fa-warehouse",
        "title": _("Inventory Performance"),
        "subtitle": _("Stock Entries vs Exits Over Time"),

        # KPIs
        "total_entries": totals["total_entries"] or 0,
        "total_exits": totals["total_exits"] or 0,

        # Charts
        "hourly_movements": list(hourly),
        "weekly_movements": list(weekly),
        "monthly_movements": list(monthly),
    }

    if request.user.is_platform_admin():
        context["active_page"] = "inventory_stats_page"

    return render(request, "inventory/movement/analytics.html", context)


# -------------------------------
# Inventory Audit views
# -------------------------------
class InventoryAuditListView(BaseListView):
    model = InventoryAudit
    template_name = 'generic/index.html'
    partial_parent_directory = 'generic'
    context_object_name = 'objects'
    active_page = 'inventory_page'
    title = _("Inventory Audits")
    subtitle = _("Audit sessions")
    header_paragraph = _("View inventory audit sessions.")

    def get_queryset(self):
        qs = super().get_queryset()
        status = self.request.GET.get("status")

        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["object_crud_via_htmx"] = False

        if not self.request.user.is_platform_admin():
            context["active_page"] = "inventory_audit_page"

        return context


class InventoryAuditDetailView(BaseDetailView):
    model = InventoryAudit
    template_name = "inventory/audit/detail.html"
    context_object_name = 'inventory_audit'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "active_page": "inventory_page",
            "title": _("Inventory Audit Details"),
            "subtitle": _("View audit session"),
            "header_paragraph": _("This page displays inventory audit information."),
        })

        if not self.request.user.is_platform_admin():
            context["active_page"] = "inventory_audit_page"

        return context


class InventoryAuditUpsertView(BaseParentChildFormView):
    model = InventoryAudit
    form_class = InventoryAuditForm
    formset_class = InventoryAuditItemFormSet
    template_name = "generic/parent_child_form.html"

    title_create = "Create Inventory Audit"
    subtitle_create = "Conduct an inventory audit and record stock quantities."
    title_update = "Edit Inventory Audit"
    subtitle_update = "Modify the details of an existing inventory audit."

    active_page = "inventory_page"
    header_paragraph = (
        "Use this form to review and audit the stock quantities "
        "for one or more products in your inventory."
    )

    success_url_name = "pharmacies:inventory-audit-detail"

    can_add_item = False  # CRITICAL

    # ---------------------------
    # Pass pharmacy to formset
    # ---------------------------
    def get_formset_kwargs(self, request, parent_obj, data=None):
        return {"pharmacy": self.get_pharmacy(request)}

    # ---------------------------
    # Set parent fields
    # ---------------------------
    def set_parent_fields(self, request, parent_obj, is_create: bool):
        parent_obj.created_by = request.user
        parent_obj.pharmacy = getattr(
            request, "current_pharmacy", None) or request.user.profile.current_pharmacy
        return parent_obj

    # ---------------------------
    # Set child fields
    # ---------------------------
    def set_child_fields(self, request, child_obj, parent_obj, is_create: bool):
        child_obj.inventory_audit = parent_obj
        return child_obj


@login_required(login_url="accounts:login")
def inventory_audit_analytics(request):
    today = now().date()
    month_start = today.replace(day=1)

    # -------------------------
    # Audit counts
    # -------------------------
    total_audits = InventoryAudit.objects.count()

    audits_by_status = (
        InventoryAudit.objects
        .values("status")
        .annotate(total=Count("id"))
    )

    audits_this_month = InventoryAudit.objects.filter(
        created_at__date__gte=month_start
    ).count()

    # -------------------------
    # Discrepancy stats
    # -------------------------
    audits_with_discrepancies = (
        InventoryAudit.objects
        .exclude(items__discrepancy=0)
        .distinct()
        .count()
    )

    discrepancy_totals = InventoryAuditItem.objects.aggregate(
        total_discrepancy=Sum(Abs("discrepancy")),
        total_expected=Sum("quantity_expected"),
        total_found=Sum("quantity_found"),
    )

    # -------------------------
    # Last audits discrepancy trend
    # -------------------------
    recent_audits = (
        InventoryAudit.objects
        .order_by("-created_at")[:7]
        .prefetch_related("items")
    )

    audit_labels = []
    audit_discrepancies = []

    for audit in reversed(recent_audits):
        total_disc = audit.items.aggregate(
            total=Sum(Abs("discrepancy"))
        )["total"] or 0

        audit_labels.append(
            audit.stock_snapshot_at.strftime("%d %b %H:%M")
        )
        audit_discrepancies.append(total_disc)

    context = {
        "active_page": "inventory_audit_analytics",
        "title": _("Inventory Audit Analytics"),
        "header_paragraph": _("Monitor audit progress, discrepancies, and stock accuracy."),

        "total_audits": total_audits,
        "audits_this_month": audits_this_month,
        "audits_with_discrepancies": audits_with_discrepancies,

        "audits_by_status": audits_by_status,

        "total_expected": discrepancy_totals["total_expected"] or 0,
        "total_found": discrepancy_totals["total_found"] or 0,
        "total_discrepancy": discrepancy_totals["total_discrepancy"] or 0,

        "audit_labels": audit_labels,
        "audit_discrepancies": audit_discrepancies,
    }

    return render(request, "inventory/audit/analytics.html", context)


@login_required(login_url="accounts:login")
def prescription_queue(request):
    context = {
        "active_page": "rx_queue_page",
        "model_icon": "fa-solid fa-notes-medical",
        "title": _("Prescription Queue"),
        "subtitle": _("Queue"),
        "header_paragraph": _(
            "Manage queued prescriptions for dispensing."
        ),
    }
    return render(request, "pharmacy/prescription_queue.html", context)


class InventoryEntryListView(InventoryMovementListView):
    active_page = "stock_entry_page"
    title = _("Stock Entries (Purchases)")
    subtitle = _("Entries history")
    header_paragraph = _("View stock entries recorded in inventory movements.")

    def get_queryset(self):
        return super().get_queryset().filter(movement_type="entry")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["model_list_url"] = "pharmacies:inventory-entry-list"
        context["pagination_url"] = "pharmacies:inventory-entry-list"
        return context


class InventoryExitListView(InventoryMovementListView):
    active_page = "stock_exit_page"
    title = _("Stock Exits")
    subtitle = _("Exits history")
    header_paragraph = _("View stock exits recorded in inventory movements.")

    def get_queryset(self):
        return super().get_queryset().filter(movement_type="exit")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["model_list_url"] = "pharmacies:inventory-exit-list"
        context["pagination_url"] = "pharmacies:inventory-exit-list"
        return context


class ExpiringProductsListView(BaseListView):
    model = ProductBatch
    template_name = "generic/index.html"
    partial_parent_directory = "generic"
    context_object_name = "objects"
    active_page = "expiry_page"
    title = _("Expiring Soon")
    subtitle = _("Batches nearing expiry")
    header_paragraph = _("View batches expiring soon.")

    def get_queryset(self):
        qs = super().get_queryset()
        today = timezone.now().date()
        try:
            days = int(self.request.GET.get("days", 30))
        except (TypeError, ValueError):
            days = 30
        cutoff = today + timedelta(days=days)
        return (
            qs.filter(
                quantity__gt=0,
                expiry_date__gte=today,
                expiry_date__lte=cutoff,
                product_stock__product__is_expirable=True,
            )
            .select_related("product_stock", "product_stock__product")
            .order_by("expiry_date")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["model_list_url"] = "pharmacies:expiring-products"
        context["pagination_url"] = "pharmacies:expiring-products"
        return context


class ExpiredProductsListView(BaseListView):
    model = ProductBatch
    template_name = "generic/index.html"
    partial_parent_directory = "generic"
    context_object_name = "objects"
    active_page = "expired_page"
    title = _("Expired Stock")
    subtitle = _("Batches past expiry")
    header_paragraph = _("View expired batches still in stock.")

    def get_queryset(self):
        qs = super().get_queryset()
        today = timezone.now().date()
        return (
            qs.filter(
                quantity__gt=0,
                expiry_date__lt=today,
                product_stock__product__is_expirable=True,
            )
            .select_related("product_stock", "product_stock__product")
            .order_by("expiry_date")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["model_list_url"] = "pharmacies:expired-products"
        context["pagination_url"] = "pharmacies:expired-products"
        return context


@login_required(login_url="accounts:login")
def stock_reconciliation(request):
    context = {
        "active_page": "recon_page",
        "model_icon": "fa-solid fa-scale-balanced",
        "title": _("Stock Reconciliation"),
        "subtitle": _("Reconcile and correct stock"),
        "header_paragraph": _(
            "Review batch quantities and reconcile inventory discrepancies."
        ),
    }
    return render(request, "inventory/stock_reconciliation.html", context)
