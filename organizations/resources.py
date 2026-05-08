from import_export import resources

from base.resources import BaseResource
from .models import Customer, Organization, Staff


class OrganizationResource(resources.ModelResource):
    def before_import(self, dataset, using_transactions, dry_run, **kwargs):
        request = kwargs.get("request", None)
        if not request or not getattr(request.user, "is_platform_admin", False):
            raise PermissionError("Only platform admins can import organizations.")

    class Meta:
        model = Organization
        import_id_fields = ("slug",)
        fields = (
            "name",
            "code",
            "slug",
            "email",
            "phone_number",
            "address",
            "is_active",
        )
        export_order = fields


class StaffResource(BaseResource):
    class Meta(BaseResource.Meta):
        model = Staff
        import_id_fields = ("organization", "email")
        fields = (
            "id",
            "organization",
            "staff_id",
            "last_name",
            "first_name",
            "gender",
            "email",
            "phone_number",
            "is_active",
        )
        export_order = fields


class CustomerResource(BaseResource):
    class Meta(BaseResource.Meta):
        model = Customer
        import_id_fields = ("organization", "email")
        fields = (
            "id",
            "organization",
            "last_name",
            "first_name",
            "gender",
            "date_of_birth",
            "email",
            "phone_number",
            "has_insurance",
            "insurrance_id",
            "is_active",
        )
        export_order = fields


