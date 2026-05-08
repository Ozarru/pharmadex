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
from .models import Organization, Customer
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
    org = getattr(request, "current_organization", None) or getattr(profile, "current_organization", None)
    if not org:
        return redirect("base:home")

    pharmacies_count = Pharmacy.objects.filter(organization=org).count()
    active_pharmacies_count = Pharmacy.objects.filter(organization=org, status="active").count()
    inactive_pharmacies_count = Pharmacy.objects.filter(organization=org, status="inactive").count()
    suspended_pharmacies_count = Pharmacy.objects.filter(organization=org, status="suspended").count()
    customers_count = Customer.objects.filter(organization=org).count()

    context = {
        "active_page": "organization_page",
        "model_icon": "fa-solid fa-building",
        "title": _("Organization Dashboard"),
        "subtitle": _("Overview"),
        "header_paragraph": _(
            "Track high-level activity for the current organization."
        ),
        "organization": org,
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

        context['active_page'] = 'organization_page'
        context['title'] = _('Organization Details')
        context['subtitle'] = _('View organization details')
        context['header_paragraph'] = _("""\
            This page shows all details of the organization, including contact information and staff/customer statistics.
        """)

        context['customers_count'] = Customer.objects.filter(organization=org).count()
        context['pharmacies_count'] = Pharmacy.objects.filter(organization=org).count()

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
