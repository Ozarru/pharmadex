from django.db import models
from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget, ManyToManyWidget, DateWidget, TimeWidget
from django.utils.translation import gettext_lazy as _


# =========================================================
# Tenant-Safe FK Widget
# =========================================================
class TenantForeignKeyWidget(ForeignKeyWidget):
    """
    Ensures FK lookups are restricted to the
    current user's organization.
    """

    def get_queryset(self, value, row, *args, **kwargs):
        request = getattr(self.resource, "request", None)
        if not request:
            return self.model.objects.none()

        org = getattr(request.user.profile, "current_organization", None)

        if hasattr(self.model, "organization"):
            return self.model.objects.filter(organization=org)

        return self.model.objects.none()


# =========================================================
# Base Resource (Tenant Aware)
# =========================================================
from import_export import resources, fields
from import_export.widgets import DateWidget, TimeWidget
from django.utils.translation import gettext_lazy as _

class BaseResource(resources.ModelResource):
    """
    Base resource for OrganizationModel:

    - Infers organization from request.user.profile.current_organization
    - Automatically assigns created_by / updated_by
    - Cleans BOM/unicode junk
    - Adds created_at_date / created_at_time fields
    - Safe with UUID PKs and tenant-aware models
    - Adds ID field first and ensures export order
    """

    # ---------------------------
    # ID field
    # ---------------------------
    id = fields.Field(
        column_name=_("ID"),
        attribute="id",
    )

    # ---------------------------
    # Created date / time
    # ---------------------------
    # created_at_date = fields.Field(
    #     column_name=_("Created Date"),
    #     attribute="created_at",
    #     widget=DateWidget(format="%Y-%m-%d"),
    # )

    # created_at_time = fields.Field(
    #     column_name=_("Created Time"),
    #     attribute="created_at",
    #     widget=TimeWidget(format="%H:%M:%S"),
    # )

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

    # ---------------------------
    # Import hooks (unchanged)
    # ---------------------------
    def before_import(self, dataset, using_transactions, dry_run, **kwargs):
        self.request = kwargs.get("request", self.request)

    def before_import_row(self, row, **kwargs):
        for key, value in row.items():
            if isinstance(value, str):
                row[key] = value.replace("\ufeff", "").strip()

        for field in ("gender", "sex"):
            if field in row and isinstance(row[field], str):
                row[field] = row[field].lower()

    # ---------------------------
    # Save hooks (unchanged)
    # ---------------------------
    def before_save_instance(
        self, instance, row, using_transactions=False, dry_run=False
    ):
        if dry_run:
            return

        if not self.request:
            raise ValueError(
                "Request not provided. Pass request=self.request to resource."
            )

        user = self.request.user
        profile = getattr(user, "profile", None)
        current_org = getattr(profile, "current_organization", None)

        if hasattr(instance, "organization"):
            if not current_org:
                raise ValueError("User has no current organization set.")
            instance.organization = current_org

        if hasattr(instance, "created_by") and not instance.pk:
            instance.created_by = user

        if hasattr(instance, "updated_by"):
            instance.updated_by = user

    class Meta:
        use_transactions = True
        skip_unchanged = True
        report_skipped = True
        # ---------------------------
        # Export order defaults
        # ---------------------------
        # ID first, then created date, then created time
        # export_order = ("id", "created_at_date", "created_at_time")
        
        
# --------------------- OPTIONAL USER EMAIL ---------------------
class UserEmailOptionalWidget(ForeignKeyWidget):
    def clean(self, value, row=None, *args, **kwargs):
        if not value:
            return None
        try:
            return self.model.objects.get(email=value)
        except self.model.DoesNotExist:
            return None


# --------------------- AUTO-CREATE FK BY NAME ---------------------
class AutoCreateFKWidget(ForeignKeyWidget):
    def clean(self, value, row=None, *args, **kwargs):
        if not value:
            return None
        obj, _boolean = self.model.objects.get_or_create(**{self.field: value})
        return obj


# --------------------- AUTO-CREATE MANY-TO-MANY ---------------------
class AutoCreateManyToManyWidget(ManyToManyWidget):

    def __init__(self, model, field='pk', separator=','):
        """
        Universal flexible widget:
        - model: related model
        - field: lookup or creation field (e.g., 'name', 'email', 'matric_number')
        - separator: ',', ';', '|', '/', custom characters
        """
        super().__init__(model=model, field=field, separator=separator)
        self.model = model
        self.field = field
        self.separator = separator

    def clean(self, value, row=None, *args, **kwargs):
        """
        Splits using provided separator, strips whitespace,
        auto-creates missing objects.
        """
        if not value:
            return []

        # clean and split safely
        values = [v.strip() for v in value.split(self.separator) if v.strip()]

        objects = []
        for val in values:
            obj, _boolean = self.model.objects.get_or_create(
                **{self.field: val})
            objects.append(obj)

        return objects
