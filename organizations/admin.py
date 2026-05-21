from django.contrib import admin
from .models import (
    Organization,
    Insurer,
    InsurancePolicy,
    Customer,
    Supplier,
)


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    search_fields = [
        "name",
        "code",
        "slug",
        "email",
        "phone_number",
        "address",
        "city",
        "state_or_region",
        "country",
    ]

    list_filter = [
        "is_active",
        "country",
        "state_or_region",
    ]

    list_display = [
        "name",
        "code",
        "slug",
        "email",
        "phone_number",
        "country",
        "is_active",
    ]

    prepopulated_fields = {"slug": ("name",)}

    ordering = ["name"]


@admin.register(Insurer)
class InsurerAdmin(admin.ModelAdmin):
    search_fields = [
        "name",
        "code",
        "email",
        "phone_number",
    ]

    list_filter = [
        "is_active",
    ]

    list_display = [
        "name",
        "code",
        # "organization",
        "email",
        "phone_number",
        "is_active",
    ]

    autocomplete_fields = ["organization"]

    ordering = ["name"]


@admin.register(InsurancePolicy)
class InsurancePolicyAdmin(admin.ModelAdmin):
    search_fields = [
        "name",
        "code",
        "insurer__name",
        "organization__name",
    ]

    list_filter = [
        "is_active",
        "insurer",
    ]

    list_display = [
        "name",
        "code",
        "insurer",
        "coverage_percent",
        "max_coverage_amount",
        "annual_coverage_limit",
        "is_active",
    ]

    autocomplete_fields = [
        "insurer",
    ]

    ordering = ["name"]


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    search_fields = [
        "first_name",
        "last_name",
        "email",
        "phone_number",
        "insurance_id",
        "organization__name",
    ]

    list_filter = [
        "gender",
        "has_insurance",
        "country",
    ]

    list_display = [
        "full_name",
        "email",
        "phone_number",
        "gender",
        "has_insurance",
        "insurance_policy",
    ]

    autocomplete_fields = [
        "insurance_policy",
    ]

    ordering = ["first_name", "last_name"]


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    search_fields = [
        "name",
        "email",
        "phone_number",
        "city",
        "state_or_region",
        "country",
        "organization__name",
    ]

    list_filter = [
        "is_active",
        "country",
        "state_or_region",
    ]

    list_display = [
        "name",
        "email",
        "phone_number",
        "city",
        "country",
        "is_active",
    ]

    autocomplete_fields = ["organization"]

    ordering = ["name"]