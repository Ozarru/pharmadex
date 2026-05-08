from django.utils.translation import gettext_lazy as _
from django.contrib import admin
from .models import *

# Register your models here.
from django.contrib.auth.models import Permission


class PermissionCodenamePrefixFilter(admin.SimpleListFilter):
    title = "Permission Type"
    parameter_name = "codename_prefix"

    PREFIXES = [
        ("add", "Add"),
        ("change", "Change"),
        ("delete", "Delete"),
        ("import", "Import"),
        ("export", "Export"),
        ("manage", "Manage"),
    ]

    def lookups(self, request, model_admin):
        return self.PREFIXES

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(codename__startswith=self.value())
        return queryset


@admin.register(PermissionProxy)
class PermissionProxyAdmin(admin.ModelAdmin):
    search_fields = (
        "name",
        "codename",
        "content_type__app_label",
        "content_type__model",
    )

    list_display = (
        # "app__name",
        "content_type",
        "name",
        "codename",
    )

    list_filter = (
        PermissionCodenamePrefixFilter,
        "content_type__app_label",
        "content_type__model",
    )

    ordering = ("name",)

    # ====== Custom display fields ======

    @admin.display(description="App")
    def app(self, obj):
        return obj.content_type.app_label

    @admin.display(description="Model")
    def model(self, obj):
        return obj.content_type.model


@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    # Fields to search in the admin interface
    search_fields = (
        "username",
        "first_name",
        "last_name",
        "email",
        "phone_number",
        # "unique_identifier",
    )

    # Fields to display in the list view
    list_display = (
        "full_name",
        "email",
        "phone_number",
        # "unique_identifier",
        "is_online",
        "last_login",
        "is_staff",
        # "groups",
    )

    # Fields to filter by in the admin interface
    list_filter = (
        "is_staff",
        "is_active",
        "is_online",
        # "has_changed_password",
        # "groups",
    )

    # Default ordering of records
    ordering = ("last_name",)

    # Fields to be read-only in the admin interface
    readonly_fields = (
        "last_login",
        "last_logout",
    )

    # Grouping fields in sections (fieldsets)
    fieldsets = (
        (_("Identity"), {
            "fields": (
                "username",
                "first_name",
                "last_name",
            )
        }),
        (_("Contact"), {
            "fields": (
                "email",
                "phone_number",
            )
        }),
        (_("Access & Status"), {
            "fields": (
                "is_active",
                "is_online",
                "groups",
            )
        }),
        (_("Activity"), {
            "fields": (
                "last_login",
                "last_logout",
            )
        }),
    )

    # Allows filtering of many-to-many fields
    filter_horizontal = (
        "groups",
        "user_permissions",
    )

    # Computed field for displaying full name
    def full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"

    full_name.short_description = _("Full name")

    # You can add custom methods to display the user's role, if needed, based on the UserOrganizationRole model.
    # def role(self, obj):
    #     # Assuming the role is tied to the user-organization relationship
    #     user_role = UserOrganizationRole.objects.filter(user=obj).first()
    #     if user_role:
    #         return user_role.get_role_display()  # Assuming `get_role_display()` works based on the `Role` choices
    #     return _("No role assigned")

    # role.short_description = _("Role")


admin.site.register(Role)
admin.site.register(Profile)
admin.site.register(UserRole)

@admin.register(UserInvitation)
class UserInvitationAdmin(admin.ModelAdmin):

    search_fields = (
        "receiver_email",
        "sender__username",
        "sender__first_name",
        "sender__last_name",
        "receiver__username",
        "receiver__first_name",
        "receiver__last_name",
        "organization__name",
        "token",
    )

    list_display = (
        "receiver_email",
        "organization",
        "user_type",
        "sender",
        "receiver",
        "invitation_status",
        "expiration_date",
        "created_at",
    )

    list_filter = (
        "user_type",
        "organization",
        "created_at",
    )

    ordering = ("-created_at",)

    readonly_fields = (
        "token",
        "created_at",
        "invitation_status",
    )

    autocomplete_fields = (
        "organization",
        "sender",
        "receiver",
    )

    def invitation_status(self, obj):

        if obj.is_used():
            return _("Used")

        if obj.is_expired():
            return _("Expired")

        return _("Pending")

    invitation_status.short_description = _("Status")