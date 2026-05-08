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
from django.views.decorators.http import require_POST
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
from organizations.models import Customer
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
    total_products = Product.objects.filter(
        is_active=True
    ).count()

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
    stocks = (
        ProductStock.objects
        .filter(product__is_active=True)
        .annotate(quantity=Coalesce(Sum("batches__quantity"), 0))
    )

    total_stock_quantity = ProductBatch.objects.aggregate(total=Sum("quantity"))[
        "total"] or 0
    low_stock_products = stocks.filter(
        quantity__lte=F("product__min_stock_threshold")
    ).count()
    overstocked_products = stocks.filter(
        quantity__gte=F("product__max_stock_threshold")
    ).count()

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
        sales_qs.filter(created_at__gte=last_24_hours)
        .annotate(hour=TruncDay("created_at"))  # or TruncHour if needed
        .values("hour")
        .annotate(revenue=Sum("total_amount"), sales=Count("id"))
        .order_by("hour")
    )

    context = {
        "active_page": "inventory_page",
        "model_icon": "fa-solid fa-chart-line",
        "title": _("Pharmacy Analytics"),
        "subtitle": _("Sales, Revenue, Inventory & Losses Overview"),
        "header_paragraph": header_paragraph,

        # KPIs
        "total_products": total_products,
        "total_categories": total_categories,
        "total_sales": total_sales,
        "avg_sale_value": avg_sale_value,
        "total_revenue": total_revenue,
        "today_revenue": today_revenue,
        "monthly_revenue": monthly_revenue,
        "last_7_days_revenue": last_7_days_revenue,
        "last_24h_revenue": last_24h_revenue,

        # Inventory
        "total_stock_quantity": total_stock_quantity,
        "low_stock_products": low_stock_products,
        "overstocked_products": overstocked_products,

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

    if request.user.is_platform_admin():
        context["active_page"] = "pharmacy_stats_page"

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
    header_paragraph = _("View and manage pharmacies under the current organization.")
    object_crud_link = "pharmacies:pharmacy-create"
    object_crud_via_htmx = False


class PharmacyDetailView(BaseDetailView):
    model = Pharmacy
    template_name = 'pharmacy/detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_page'] = 'pharmacies_page'
        context['title'] = _('Pharmacy Details')
        context['subtitle'] = _('View pharmacy details')
        return context


class PharmacyCreateView(BaseModelView, CreateView):
    model = Pharmacy
    fields = ['name', 'code', 'address', 'phone_number', 'is_active']
    success_url = reverse_lazy('pharmacies:pharmacy-list')
    title = _("Add Pharmacy")
    subtitle = _("Create a new pharmacy under the current organization")

    def form_valid(self, form):
        form.instance.organization = self.request.user.profile.current_organization
        return super().form_valid(form)


class PharmacyUpdateView(BaseModelView, UpdateView):
    model = Pharmacy
    fields = ['name', 'code', 'address', 'phone_number', 'is_active', 'is_suspended', 'is_archived']
    success_url = reverse_lazy('pharmacies:pharmacy-list')
    title = _("Edit Pharmacy")
    subtitle = _("Update pharmacy details")


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
            context["active_page"] = "product_page"

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
            context["active_page"] = "product_page"

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
            context["active_page"] = "product_page"

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
            context["active_page"] = "product_page"

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
    active_page = 'product_page'
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
            "active_page": "product_page",
            "title": _("Product Details"),
            "subtitle": _("View product information"),
            "header_paragraph": _("This page displays product details and pricing."),
        })

        if not self.request.user.is_platform_admin():
            context["active_page"] = "product_page"

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
    active_page = "product_stock_page"
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
            context["active_page"] = "product_stock_page"

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
            context["active_page"] = "product_stock_page"
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
    active_page = 'batch_page'
    title = _("Batches Management (FEFO)")
    subtitle = _("Manage product batches")
    header_paragraph = _("View and manage all product batches.")

    def get_queryset(self):
        queryset = super().get_queryset().filter(
            quantity__gt=0,
            is_active=True,
            # pharmacy=self.request.user.pharmacy  # ✅ if needed
        ).select_related("product_stock", "product_stock__product")

        filter_type = self.request.GET.get("filter")
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

        if filter_type == "expiring":
            context.update({
                "title": _("Expiring Batches"),
                "subtitle": _("Batches nearing expiry"),
                "header_paragraph": _("Monitor batches that will expire soon."),
                "model_icon": "fa-solid fa-hourglass-half",
            })

        elif filter_type == "expired":
            context.update({
                "title": _("Expired Batches"),
                "subtitle": _("Batches past expiry"),
                "header_paragraph": _("Review and manage expired batches."),
                "model_icon": "fa-solid fa-triangle-exclamation",
            })

        elif filter_type == "alerts":
            context.update({
                "title": _("Stock Alerts"),
                "subtitle": _("Expiry risks and warnings"),
                "header_paragraph": _("View expired and near-expiry batches."),
                "model_icon": "fa-solid fa-bell",
            })

        return context


class ProductBatchDetailView(BaseDetailView):
    model = ProductBatch
    template_name = "product_batch/detail.html"
    context_object_name = 'batch'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "active_page": "batch_page",
            "title": _("Batch Details"),
            "subtitle": _("View batch information"),
            "header_paragraph": _("This page displays batch details, stock, and expiry."),
        })

        if not self.request.user.is_platform_admin():
            context["active_page"] = "batch_page"

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
        "active_page": "product_page",
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


class PrescriptionListView(BaseListView):
    model = Prescription
    template_name = "generic/index.html"
    context_object_name = "objects"
    active_page = "prescription_page"
    title = _("Prescriptions")
    subtitle = _("Manage prescriptions")
    header_paragraph = _("View and manage prescriptions.")

    def get_queryset(self):
        queryset = super().get_queryset().filter(
            is_active=True,
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
            "active_page": "prescription_page",
            "title": _("Prescription Details"),
            "subtitle": _("View prescription information"),
            "header_paragraph": _("This page displays prescription details, prescribed items, and dispensing status."),
        })

        if not self.request.user.is_platform_admin():
            context["active_page"] = "prescription_page"

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

    active_page = "prescription_page"
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
    active_page = 'sale_page'
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
            context["active_page"] = "sale_page"

        return context


class SaleDetailView(BaseDetailView):
    model = Sale
    template_name = "sale/detail.html"
    context_object_name = 'sale'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "active_page": "sale_page",
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
    current_customer = None
    customer_id = request.GET.get("current_customer")

    if customer_id:
        current_customer = get_object_or_404(
            Customer, pk=customer_id)

    # Fetch all data in a lightweight, ordered way
    product_stocks = ProductStock.objects.select_related('product').filter(
        product__is_active=True
    ).order_by('product__name')
    categories = ProductCategory.objects.all().order_by('name')
    subcategories = ProductSubcategory.objects.all().order_by('name')
    customers = Customer.objects.all().order_by('last_name', 'first_name')

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
    }

    if request.user.is_platform_admin():
        context["active_page"] = "pos_page"

    return render(request, 'pharmacy/point_of_sale.html', context)


@login_required
@require_POST
def sale_checkout(request):
    """
    Processes a sale:
    - Creates a Sale and SaleItems
    - Vendor is always the logged-in user
    - Stock adjustment happens via post_save signals on SaleItem
    """
    try:
        data = json.loads(request.body)
        customer_id = data.get("customer_id")
        insured_customer = data.get("insured_customer")
        items = data.get("items", [])

        if not items:
            return JsonResponse({"success": False, "message": "Invalid payload"}, status=400)

        profile = getattr(request.user, "profile", None)
        organization = getattr(request, "current_organization", None) or getattr(profile, "current_organization", None)
        pharmacy = getattr(request, "current_pharmacy", None) or getattr(profile, "current_pharmacy", None)
        if not organization:
            return JsonResponse({"success": False, "message": "No organization selected."}, status=400)
        if not pharmacy:
            return JsonResponse({"success": False, "message": "No pharmacy selected."}, status=400)

        customer = None
        if customer_id:
            customer = get_object_or_404(Customer, pk=customer_id)
        elif isinstance(insured_customer, dict) and insured_customer.get("insurrance_id"):
            ins_id = str(insured_customer.get("insurrance_id")).strip()
            dob = insured_customer.get("date_of_birth") or None
            if isinstance(dob, str):
                dob = parse_date(dob) or None
            defaults = {
                "first_name": (insured_customer.get("first_name") or "").strip() or None,
                "last_name": (insured_customer.get("last_name") or "").strip() or None,
                "email": (insured_customer.get("email") or "").strip() or None,
                "phone_number": (insured_customer.get("phone_number") or "").strip() or None,
                "gender": insured_customer.get("gender") or None,
                "date_of_birth": dob,
                "is_active": True,
            }
            customer, _ = Customer.objects.update_or_create(
                organization=organization,
                insurrance_id=ins_id,
                defaults=defaults,
            )
        else:
            customer, _ = Customer.objects.get_or_create(
                organization=organization,
                first_name="Walk-in",
                last_name="Customer",
                defaults={"is_active": True},
            )

        validated_items = []
        total = 0

        # -----------------------------
        # STEP 1 — Validate items
        # -----------------------------
        for item in items:
            product_stock = get_object_or_404(
                ProductStock,
                pk=item["product_stock_id"]
            )

            quantity = int(item["quantity"])

            if quantity <= 0:
                return JsonResponse({
                    "success": False,
                    "message": "Invalid quantity"
                }, status=400)

            # Optional stock protection
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

        # -----------------------------
        # STEP 3 — Create sale safely
        # -----------------------------
        with transaction.atomic():

            sale = Sale.objects.create(
                organization=organization,
                pharmacy=pharmacy,
                customer=customer,
                vendor=request.user,
                created_by=request.user,
                total_amount=total
            )

            # -----------------------------
            # STEP 4 — Create items
            # -----------------------------
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
            "total": float(total)
        })

    except Exception as e:
        return JsonResponse({
            "success": False,
            "message": str(e)
        }, status=400)


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
