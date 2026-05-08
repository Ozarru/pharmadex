from django.contrib import admin
from .models import Organization #,Customer, 


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    search_fields = [
        "name",
        "code",
        "slug",
        "email",
        "phone_number",
        "address",
    ]

    list_filter = [
        "is_active",
    ]

    list_display = [
        "name",
        "code",
        "slug",
        "email",
        "phone_number",
        "is_active",
    ]

    prepopulated_fields = {"slug": ("name",)}


# @admin.register(Customer)
# class CustomerAdmin(admin.ModelAdmin):
#     search_fields = [
#         "last_name",
#         "first_name",
#         "email",
#         "phone_number",
#         "insurrance_id",
#     ]

#     list_filter = [
#         "organization",
#         "is_active",
#         "gender",
#         "has_insurance",
#     ]

#     list_display = [
#         "organization",
#         "last_name",
#         "first_name",
#         "phone_number",
#         "email",
#         "has_insurance",
#         "is_active",
#     ]

