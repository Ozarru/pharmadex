from django.urls import path
from .views import *

app_name = "pharmacies"

urlpatterns = [
    path("dashboard/", pharmacy_dashboard, name="pharmacy-dashboard"),
    path("inventory-dashboard/", inventory_dashboard, name="inventory-dashboard"),
    path("report/", pharmacy_reports, name="pharmacy-reports"),
    path("analytics/", pharmacy_analytics, name="pharmacy-analytics"),
    path("point-of-sale/", point_of_sale, name="point-of-sale"),
    path("cashier-validation/", cashier_validation, name="cashier-validation"),
    path("sale-validation/<uuid:pk>/", sale_validation_view, name="sale-validation"),
    path("prescription-queue/", prescription_queue, name="prescription-queue"),
    path("profit-and-loss-reports", point_of_sale, name="profit-and-loss-reports"),

    # Pharmacy URLs
    path('pharmacy/list/', PharmacyListView.as_view(), name='pharmacy-list'),
    path('pharmacy/create/', PharmacyCreateView.as_view(), name='pharmacy-create'),
    path('pharmacy/<uuid:pk>/detail/', PharmacyDetailView.as_view(), name='pharmacy-detail'),
    path('pharmacy/<uuid:pk>/update/', PharmacyUpdateView.as_view(), name='pharmacy-update'),
    path("pharmacy/analytics/", pharmacy_analytics, name="pharmacy-analytics"),
    path("pharmacy/monthly-trend/<uuid:pk>/", pharmacy_monthly_trend, name="pharmacy-monthly-trend"),
    
    # Product Category URLs
    path('product-category/list/', ProductCategoryListView.as_view(), name='product-category-list'),
    path('product-category/create/', ProductCategoryCreateView.as_view(), name='product-category-create'),
    path('product-category/<uuid:pk>/detail/', ProductCategoryDetailView.as_view(), name='product-category-detail'),
    path('product-category/<uuid:pk>/update/', ProductCategoryUpdateView.as_view(), name='product-category-update'),
    path("product-category/analytics/", category_analytics, name="product-category-analytics"),

    # Product Subcategory URLs
    path('product-subcategory/list/', ProductSubcategoryListView.as_view(), name='product-subcategory-list'),
    path('product-subcategory/create/', ProductSubcategoryCreateView.as_view(), name='product-subcategory-create'),
    path('product-subcategory/<uuid:pk>/detail/', ProductSubcategoryDetailView.as_view(), name='product-subcategory-detail'),
    path('product-subcategory/<uuid:pk>/update/', ProductSubcategoryUpdateView.as_view(), name='product-subcategory-update'),
    path("product-subcategory/analytics/", subcategory_analytics, name="product-subcategory-analytics"),

    # Product URLs
    path('product/list/', ProductListView.as_view(), name='product-list'),
    path('product/create/', ProductCreateView.as_view(), name='product-create'),
    path('product/<uuid:pk>/detail/', ProductDetailView.as_view(), name='product-detail'),
    path('product/<uuid:pk>/update/', ProductUpdateView.as_view(), name='product-update'),
    path("product/analytics/", product_analytics, name="product-analytics"),
    
    # ProductStock URLs
    path('product-stock/list/', ProductStockListView.as_view(), name='product-stock-list'),
    path('product-stock/<uuid:pk>/detail/', ProductStockDetailView.as_view(), name='product-stock-detail'),
    path('product-stock/<uuid:pk>/update/', ProductStockUpdateView.as_view(), name='product-stock-update'),
    path("product-stock/analytics/", product_analytics, name="product-stock-analytics"),
    path("synchronize-stock", synchronize_stock, name="synchronize-stock"),
    
    # ProductBatch URLs
    path('product-batch/list/', ProductBatchListView.as_view(), name='product-batch-list'),
    path('product-batch/create/', ProductBatchCreateView.as_view(), name='product-batch-create'),
    path('product-batch/<uuid:pk>/detail/', ProductBatchDetailView.as_view(), name='product-batch-detail'),
    path('product-batch/<uuid:pk>/update/', ProductBatchUpdateView.as_view(), name='product-batch-update'),
    
    # Prescription URLs
    path("prescription/list/",PrescriptionListView.as_view(),name="prescription-list"),
    path('prescription/<uuid:pk>/detail/', PrescriptionDetailView.as_view(), name='prescription-detail'),
    path("prescription/create/", PrescriptionUpsertView.as_view(), name="prescription-create"),
    path("prescription/<uuid:pk>/update/", PrescriptionUpsertView.as_view(), name="prescription-update"),
    
    # Sale URLs
    path('sale/list/', SaleListView.as_view(), name='sale-list'),
    path("sale/checkout/", sale_checkout, name="sale-checkout"),
    path('sale/<uuid:pk>/detail/', SaleDetailView.as_view(), name='sale-detail'),
    path("sale/analytics/", sale_analytics, name="sale-analytics"),
    
    # Purchase URLs
    path('purchase/list/', PurchaseListView.as_view(), name='purchase-list'),
    path('purchase/<uuid:pk>/detail/', PurchaseDetailView.as_view(), name='purchase-detail'),
    path("purchase/analytics/", purchase_analytics, name="purchase-analytics"),

    # Inventory URLs ------------------------------------------
    path("inventory-performance/", inventory_performance, name="inventory-performance"),
    path("inventory-entry/list/", InventoryEntryListView.as_view(), name="inventory-entry-list"),
    path("inventory-exit/list/", InventoryExitListView.as_view(), name="inventory-exit-list"),
    path("inventory/expiring-products/", ExpiringProductsListView.as_view(), name="expiring-products"),
    path("inventory/expired-products/", ExpiredProductsListView.as_view(), name="expired-products"),
    path("inventory/stock-reconciliation/", stock_reconciliation, name="stock-reconciliation"),
    
    # Inventory Movement
    path('inventory-movement/list/', InventoryMovementListView.as_view(), name='inventory-movement-list'),
    path('inventory-movement/<uuid:pk>/detail/', InventoryMovementDetailView.as_view(), name='inventory-movement-detail'),
    path("inventory-movement/create/", InventoryMovementUpsertView.as_view(), name="inventory-movement-create"),
    path("inventory-movement/<uuid:pk>/update/", InventoryMovementUpsertView.as_view(), name="inventory-movement-update"),
    path("inventory-movement/analytics/", inventory_movement_analytics, name="inventory-movement-analytics"),

    # Inventory Audit
    path('inventory-audit/list/', InventoryAuditListView.as_view(), name='inventory-audit-list'),
    path('inventory-audit/<uuid:pk>/detail/', InventoryAuditDetailView.as_view(), name='inventory-audit-detail'),
    path("inventory-audit/create/", InventoryAuditUpsertView.as_view(), name="inventory-audit-create"),
    path("inventory-audit/<uuid:pk>/update/", InventoryAuditUpsertView.as_view(), name="inventory-audit-update"),
    path("inventory-audit/analytics/", inventory_audit_analytics, name="inventory-audit-analytics"),

]
