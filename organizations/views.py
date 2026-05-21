from django.db.models import Count
from django.core.mail import EmailMessage
from django.utils.dateparse import parse_date
from django.http import HttpResponse, HttpResponseBadRequest
from collections import defaultdict, deque
import os
from django.http import HttpResponse, FileResponse
from io import BytesIO
import tempfile
import zipfile
from base.services.data_export_cron import export_finances_as_zip
from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse
from django.db import transaction
from django.http import HttpResponse
from django.db.models import (Count, Sum, Avg, DecimalField)
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.db.models.functions import Coalesce
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, UpdateView
from django.urls import reverse_lazy
from base.views import BaseListView, BaseDetailView, BaseModelView
from pharmacies.models import Pharmacy
from .models import InsurancePolicy, Insurer, Organization, Customer, Supplier
from django.utils.translation import gettext as _
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.db import models
from django.utils import translation


# -------------------------------
# Organization views
# -------------------------------
@login_required(login_url="accounts:login")
def organization_dashboard(request):
    profile = getattr(request.user, "profile", None)
    org = getattr(request, "current_organization", None) or getattr(
        profile, "current_organization", None)
    if not org:
        return redirect("base:home")

    pharmacies_count = Pharmacy.objects.filter(organization=org).count()
    active_pharmacies_count = Pharmacy.objects.filter(
        organization=org, status="active").count()
    inactive_pharmacies_count = Pharmacy.objects.filter(
        organization=org, status="inactive").count()
    suspended_pharmacies_count = Pharmacy.objects.filter(
        organization=org, status="suspended").count()
    customers_count = Customer.objects.filter(organization=org).count()

    context = {
        "active_page": "organizations_page",
        "model_icon": "fa-solid fa-building",
        "title": _("Organization Dashboard"),
        "subtitle": _("Overview"),
        "header_paragraph": _(
            "Track high-level activity for the current organization."
        ),
        "organization": org,
        "org_is_active": org.is_active,
        "pharmacies_count": pharmacies_count,
        "active_pharmacies_count": active_pharmacies_count,
        "inactive_pharmacies_count": inactive_pharmacies_count,
        "suspended_pharmacies_count": suspended_pharmacies_count,
        "customers_count": customers_count,
    }
    return render(request, "organization/dashboard.html", context)


class OrganizationListView(BaseListView):
    model = Organization
    template_name = 'generic/index.html'
    partial_parent_directory = 'generic'
    context_object_name = 'objects'
    active_page = 'organizations_page'
    title = _("Organizations")
    subtitle = _("Manage organizations")
    header_paragraph = _("""
        View and manage organizations (tenants) in the system.
        You can filter and search organizations by name or status.
    """)
    object_crud_link = "organizations:organization-create"
    object_crud_via_htmx = False

    def get_queryset(self):
        queryset = super().get_queryset()

        # Optional filters
        name = self.request.GET.get("name")
        active = self.request.GET.get("is_active")

        if name:
            queryset = queryset.filter(name__icontains=name)
        if active in ["true", "false"]:
            queryset = queryset.filter(is_active=(active == "true"))

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = self.get_queryset()

        context['data_groups'] = [
            (_("Active Organizations"), queryset.filter(
                is_active=True).count(), "fa-solid fa-check-circle", "green"),
            (_("Inactive Organizations"), queryset.filter(
                is_active=False).count(), "fa-solid fa-ban", "red"),
        ]

        return context


class OrganizationDetailView(BaseDetailView):
    model = Organization
    template_name = 'organization/detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        org = self.get_object()

        context['active_page'] = 'organizations_page'
        context['title'] = _('Organization Details')
        context['subtitle'] = _('View organization details')
        context['header_paragraph'] = _("""\
            This page shows all details of the organization, including contact information and staff/customer statistics.
        """)

        context['customers_count'] = Customer.objects.filter(
            organization=org).count()
        context['pharmacies_count'] = Pharmacy.objects.filter(
            organization=org).count()

        return context


class OrganizationCreateView(BaseModelView, CreateView):
    model = Organization
    fields = ['name', 'code', 'email', 'phone_number', 'address', 'is_active']
    success_url = reverse_lazy('organizations:organization-list')
    title = _("Add Organization")
    subtitle = _("Fill the form to add a new organization")
    header_paragraph = _(
        "Create a new organization and configure basic contact and operational settings.")


class OrganizationUpdateView(BaseModelView, UpdateView):
    model = Organization
    fields = ['name', 'code', 'email', 'phone_number', 'address', 'is_active']
    success_url = reverse_lazy('organizations:organization-list')
    title = _("Edit Organization")
    subtitle = _("Edit details of an existing organization")
    header_paragraph = _(
        "Update organization information and operational settings.")


# ═══════════════════════════════════════════════════════════════
# INSURER VIEWS
# ═══════════════════════════════════════════════════════════════
class InsurerListView(BaseListView):
    model = Insurer
    template_name = 'generic/index.html'
    partial_parent_directory = 'generic'
    context_object_name = 'objects'
    active_page = 'organizations_page'
    title = _("Insurers")
    subtitle = _("Manage insurance providers")
    header_paragraph = _("""
        View and manage insurance providers. Filter by name, code, or status.
    """)
    object_crud_link = "organizations:insurer-create"
    object_crud_via_htmx = False

    def get_queryset(self):
        queryset = super().get_queryset()
        name = self.request.GET.get("name")
        code = self.request.GET.get("code")
        active = self.request.GET.get("is_active")

        if name:
            queryset = queryset.filter(name__icontains=name)
        if code:
            queryset = queryset.filter(code__icontains=code)
        if active in ["true", "false"]:
            queryset = queryset.filter(is_active=(active == "true"))

        return queryset.annotate(policy_count=Count('policies'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = self.get_queryset()

        context['data_groups'] = [
            (_("Active Insurers"), queryset.filter(is_active=True).count(),
             "fa-solid fa-check-circle", "green"),
            (_("Inactive Insurers"), queryset.filter(
                is_active=False).count(), "fa-solid fa-ban", "red"),
        ]
        return context


class InsurerDetailView(BaseDetailView):
    model = Insurer
    template_name = 'organization/detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        insurer = self.get_object()

        context['active_page'] = 'organizations_page'
        context['title'] = _('Insurer Details')
        context['subtitle'] = _('View insurer and policy information')
        context['header_paragraph'] = _("""
            Details of the insurance provider, including contact information and associated policies.
        """)

        context['policies_count'] = insurer.policies.count()
        context['policies'] = insurer.policies.all()

        return context


class InsurerCreateView(BaseModelView, CreateView):
    model = Insurer
    fields = ['name', 'code', 'email', 'phone_number', 'address', 'is_active']
    success_url = reverse_lazy('organizations:insurer-list')
    title = _("Add Insurer")
    subtitle = _("Create a new insurance provider")
    header_paragraph = _(
        "Register a new insurer with contact details and activation status.")


class InsurerUpdateView(BaseModelView, UpdateView):
    model = Insurer
    fields = ['name', 'code', 'email', 'phone_number', 'address', 'is_active']
    success_url = reverse_lazy('organizations:insurer-list')
    title = _("Edit Insurer")
    subtitle = _("Update insurance provider details")
    header_paragraph = _("Modify insurer information and contact settings.")


# ═══════════════════════════════════════════════════════════════
# INSURANCE POLICY VIEWS
# ═══════════════════════════════════════════════════════════════
class InsurancePolicyListView(BaseListView):
    model = InsurancePolicy
    template_name = 'generic/index.html'
    partial_parent_directory = 'generic'
    context_object_name = 'objects'
    active_page = 'organizations_page'
    title = _("Insurance Policies")
    subtitle = _("Manage insurance plans")
    header_paragraph = _("""
        View and manage insurance policies. Filter by insurer, coverage, or status.
    """)
    object_crud_link = "organizations:insurance-policy-create"
    object_crud_via_htmx = False

    def get_queryset(self):
        queryset = super().get_queryset().select_related('insurer')
        insurer = self.request.GET.get("insurer")
        name = self.request.GET.get("name")
        active = self.request.GET.get("is_active")

        if insurer:
            queryset = queryset.filter(insurer__id=insurer)
        if name:
            queryset = queryset.filter(name__icontains=name)
        if active in ["true", "false"]:
            queryset = queryset.filter(is_active=(active == "true"))

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = self.get_queryset()

        context['data_groups'] = [
            (_("Active Policies"), queryset.filter(is_active=True).count(),
             "fa-solid fa-check-circle", "green"),
            (_("Inactive Policies"), queryset.filter(
                is_active=False).count(), "fa-solid fa-ban", "red"),
        ]
        context['insurers'] = Insurer.objects.filter(is_active=True)
        return context


class InsurancePolicyDetailView(BaseDetailView):
    model = InsurancePolicy
    template_name = 'organization/detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        policy = self.get_object()

        context['active_page'] = 'organizations_page'
        context['title'] = _('Policy Details')
        context['subtitle'] = _('View insurance plan coverage')
        context['header_paragraph'] = _("""
            Coverage details, limits, and insurer information for this policy.
        """)

        context['customers_count'] = Customer.objects.filter(
            insurance_policy=policy).count()

        return context


class InsurancePolicyCreateView(BaseModelView, CreateView):
    model = InsurancePolicy
    fields = ['insurer', 'name', 'code', 'coverage_percent',
              'max_coverage_amount', 'annual_coverage_limit', 'is_active']
    success_url = reverse_lazy('organizations:insurance-policy-list')
    title = _("Add Insurance Policy")
    subtitle = _("Create a new insurance plan")
    header_paragraph = _(
        "Define coverage percentage, limits, and link to an insurer.")


class InsurancePolicyUpdateView(BaseModelView, UpdateView):
    model = InsurancePolicy
    fields = ['insurer', 'name', 'code', 'coverage_percent',
              'max_coverage_amount', 'annual_coverage_limit', 'is_active']
    success_url = reverse_lazy('organizations:insurance-policy-list')
    title = _("Edit Insurance Policy")
    subtitle = _("Update insurance plan details")
    header_paragraph = _(
        "Modify coverage terms, limits, and insurer association.")


# ═══════════════════════════════════════════════════════════════
# CUSTOMER VIEWS
# ═══════════════════════════════════════════════════════════════
class CustomerListView(BaseListView):
    model = Customer
    template_name = 'generic/index.html'
    partial_parent_directory = 'generic'
    context_object_name = 'objects'
    active_page = 'organizations_page'
    title = _("Customers")
    subtitle = _("Manage patients and clients")
    header_paragraph = _("""
        View and manage customers. Search by name, phone, insurance, or location.
    """)
    object_crud_link = "organizations:customer-create"
    object_crud_via_htmx = False

    def get_queryset(self):
        queryset = super().get_queryset()
        name = self.request.GET.get("name")
        phone = self.request.GET.get("phone")
        insured = self.request.GET.get("has_insurance")
        city = self.request.GET.get("city")

        if name:
            queryset = queryset.filter(
                models.Q(first_name__icontains=name) |
                models.Q(last_name__icontains=name)
            )
        if phone:
            queryset = queryset.filter(phone_number__icontains=phone)
        if insured in ["true", "false"]:
            queryset = queryset.filter(has_insurance=(insured == "true"))
        if city:
            queryset = queryset.filter(city__icontains=city)

        return queryset.select_related('insurance_policy')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = self.get_queryset()

        context['data_groups'] = [
            (_("Insured Customers"), queryset.filter(
                has_insurance=True).count(), "fa-solid fa-shield-halved", "blue"),
            (_("Uninsured Customers"), queryset.filter(
                has_insurance=False).count(), "fa-solid fa-user", "gray"),
        ]
        
        return context


class CustomerDetailView(BaseDetailView):
    model = Customer
    template_name = 'organization/detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        customer = self.get_object()

        context['active_page'] = 'organizations_page'
        context['title'] = _('Customer Details')
        context['subtitle'] = _('View patient information and history')
        context['header_paragraph'] = _("""
            Customer profile, contact details, insurance coverage, and purchase history.
        """)

        context['sales_count'] = customer.sales.count(
        ) if hasattr(customer, 'sales') else 0

        return context


class CustomerCreateView(BaseModelView, CreateView):
    model = Customer
    fields = [
        'first_name', 'last_name', 'email', 'phone_number',
        'date_of_birth', 'gender', 'city', 'state_or_region', 'country',
        'has_insurance', 'insurance_policy', 'insurance_id'
    ]
    success_url = reverse_lazy('organizations:customer-list')
    title = _("Add Customer")
    subtitle = _("Register a new patient")
    header_paragraph = _(
        "Create a customer profile with contact and insurance details.")


class CustomerUpdateView(BaseModelView, UpdateView):
    model = Customer
    fields = [
        'first_name', 'last_name', 'email', 'phone_number',
        'date_of_birth', 'gender', 'city', 'state_or_region', 'country',
        'has_insurance', 'insurance_policy', 'insurance_id'
    ]
    success_url = reverse_lazy('organizations:customer-list')
    title = _("Edit Customer")
    subtitle = _("Update patient information")
    header_paragraph = _(
        "Modify customer details, insurance, and contact information.")


# ═══════════════════════════════════════════════════════════════
# SUPPLIER VIEWS
# ═══════════════════════════════════════════════════════════════
class SupplierListView(BaseListView):
    model = Supplier
    template_name = 'generic/index.html'
    partial_parent_directory = 'generic'
    context_object_name = 'objects'
    active_page = 'organizations_page'
    title = _("Suppliers")
    subtitle = _("Manage product vendors")
    header_paragraph = _("""
        View and manage suppliers. Filter by name, location, or status.
    """)
    object_crud_link = "organizations:supplier-create"
    object_crud_via_htmx = False

    def get_queryset(self):
        queryset = super().get_queryset()
        name = self.request.GET.get("name")
        city = self.request.GET.get("city")
        active = self.request.GET.get("is_active")

        if name:
            queryset = queryset.filter(name__icontains=name)
        if city:
            queryset = queryset.filter(city__icontains=city)
        if active in ["true", "false"]:
            queryset = queryset.filter(is_active=(active == "true"))

        return queryset.annotate(po_count=Count('purchase_orders'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = self.get_queryset()

        context['data_groups'] = [
            (_("Active Suppliers"), queryset.filter(
                is_active=True).count(), "fa-solid fa-check-circle", "green"),
            (_("Inactive Suppliers"), queryset.filter(
                is_active=False).count(), "fa-solid fa-ban", "red"),
        ]
        return context


class SupplierDetailView(BaseDetailView):
    model = Supplier
    template_name = 'organization/detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        supplier = self.get_object()

        context['active_page'] = 'organizations_page'
        context['title'] = _('Supplier Details')
        context['subtitle'] = _('View vendor information and orders')
        context['header_paragraph'] = _("""
            Supplier profile, contact details, and purchase order history.
        """)

        context['purchase_orders_count'] = supplier.purchase_orders.count()
        context['recent_orders'] = supplier.purchase_orders.order_by(
            '-order_date')[:5]

        return context


class SupplierCreateView(BaseModelView, CreateView):
    model = Supplier
    fields = ['name', 'phone_number', 'email', 'address',
              'city', 'state_or_region', 'country', 'is_active']
    success_url = reverse_lazy('organizations:supplier-list')
    title = _("Add Supplier")
    subtitle = _("Register a new vendor")
    header_paragraph = _(
        "Create a supplier with contact and location details.")


class SupplierUpdateView(BaseModelView, UpdateView):
    model = Supplier
    fields = ['name', 'phone_number', 'email', 'address',
              'city', 'state_or_region', 'country', 'is_active']
    success_url = reverse_lazy('organizations:supplier-list')
    title = _("Edit Supplier")
    subtitle = _("Update vendor information")
    header_paragraph = _(
        "Modify supplier contact details and activation status.")


@login_required(login_url='accounts:login')
def export_finances(request):
    if not (request.user.is_superuser or request.user.is_platform_admin()):
        return HttpResponseForbidden()
    if request.method != "POST":
        return redirect("base:home")

    date = request.POST.get("date")
    email = request.POST.get("email")

    if not email:
        messages.error(request, "Email is required.")
        return redirect("base:home")

    parsed_date = parse_date(date) if date else None

    try:
        zip_paths, base_dir = export_finances_as_zip(parsed_date)

        # Format time nicely
        now = timezone.localtime()
        formatted_time = now.strftime("%d/%m/%Y à %H:%M")

        # Your message
        message = f"""
            Export des données

            Bonjour,

            Veuillez trouver en pièce jointe l’export des données.

            Généré à : {formatted_time}

            Cordialement,
            Votre système
        """

        # Send email
        mail = EmailMessage(
            subject="Export des données",
            body=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email],
        )

        # Attach ZIP files
        for path in zip_paths:
            mail.attach_file(path)

        mail.send()

        messages.success(request, f"Export envoyé à {email}")

    except Exception as e:
        messages.error(request, f"Export échoué : {str(e)}")

    return redirect("organizations:organization-dashboard")
