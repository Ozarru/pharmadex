from django.urls import path
from .views import *

urlpatterns = [
    # Organization URLs
    path('dashboard/', organization_dashboard, name='organization-dashboard'),
    path("export/", export_finances, name="export-finances"),
    path('organization/list/', OrganizationListView.as_view(), name='organization-list'),
    path('organization/create/', OrganizationCreateView.as_view(), name='organization-create'),
    path('organization/<uuid:pk>/detail/', OrganizationDetailView.as_view(), name='organization-detail'),
    path('organization/<uuid:pk>/update/', OrganizationUpdateView.as_view(), name='organization-update'),
    
    # Insurer URLs
    path('insurers/', InsurerListView.as_view(), name='insurer-list'),
    path('insurers/<uuid:pk>/', InsurerDetailView.as_view(), name='insurer-detail'),
    path('insurers/create/', InsurerCreateView.as_view(), name='insurer-create'),
    path('insurers/<uuid:pk>/edit/', InsurerUpdateView.as_view(), name='insurer-update'),

    # Insurance Policie URLs
    path('insurance-policies/', InsurancePolicyListView.as_view(), name='insurance-policy-list'),
    path('insurance-policies/<uuid:pk>/', InsurancePolicyDetailView.as_view(), name='insurance-policy-detail'),
    path('insurance-policies/create/', InsurancePolicyCreateView.as_view(), name='insurance-policy-create'),
    path('insurance-policies/<uuid:pk>/edit/', InsurancePolicyUpdateView.as_view(), name='insurance-policy-update'),

    # Customer URLs
    path('customers/', CustomerListView.as_view(), name='customer-list'),
    path('customers/<uuid:pk>/', CustomerDetailView.as_view(), name='customer-detail'),
    path('customers/create/', CustomerCreateView.as_view(), name='customer-create'),
    path('customers/<uuid:pk>/edit/', CustomerUpdateView.as_view(), name='customer-update'),

    # Supplier URLs
    path('suppliers/', SupplierListView.as_view(), name='supplier-list'),
    path('suppliers/<uuid:pk>/', SupplierDetailView.as_view(), name='supplier-detail'),
    path('suppliers/create/', SupplierCreateView.as_view(), name='supplier-create'),
    path('suppliers/<uuid:pk>/edit/', SupplierUpdateView.as_view(), name='supplier-update'),
]
