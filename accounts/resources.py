from base.resources import BaseResource
from .models import Profile, CustomUser, CustomUser, Role #,UserInvitation, UserRole
from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget, ManyToManyWidget
from django.contrib.auth.models import Permission
from organizations.models import Organization
from pharmacies.models import Pharmacy


class RoleResource(resources.ModelResource):
    permissions = fields.Field(
        column_name='permissions',
        attribute='permissions',
        widget=ManyToManyWidget(Permission, separator=';', field='codename')
    )

    class Meta:
        model = Role
        import_id_fields = ('id',)
        fields = ('id', 'name', 'user_type', 'permissions')
        export_order = fields


class CustomUserResource(resources.ModelResource):
    class Meta:
        model = CustomUser
        import_id_fields = ('id',)
        fields = (
            'id', 'email', 'phone_number', 'username',
            'first_name', 'last_name', 'is_active', 'is_staff',
            'last_login', 'last_logout', 'is_online'
        )
        export_order = fields


class ProfileResource(resources.ModelResource):

    user = fields.Field(
        column_name='user',
        attribute='user',
        widget=ForeignKeyWidget(CustomUser, 'email')
    )
    current_organization = fields.Field(
        column_name='current_organization',
        attribute='current_organization',
        widget=ForeignKeyWidget(Organization, 'name')
    )
    current_pharmacy = fields.Field(
        column_name='current_pharmacy',
        attribute='current_pharmacy',
        widget=ForeignKeyWidget(Pharmacy, 'name')
    )
    # current_role = fields.Field(
    #     column_name='current_role',
    #     attribute='current_role',
    #     widget=ForeignKeyWidget(UserRole, 'id')
    # )
    allowed_organizations = fields.Field(
        column_name='allowed_organizations',
        attribute='allowed_organizations',
        widget=ManyToManyWidget(Organization, separator=';', field='name')
    )
    allowed_pharmacies = fields.Field(
        column_name='allowed_pharmacies',
        attribute='allowed_pharmacies',
        widget=ManyToManyWidget(Pharmacy, separator=';', field='name')
    )

    class Meta:
        model = Profile
        import_id_fields = ('id',)
        fields = (
            'id',
            'user',
            'gender',
            'image',
            'bio',
            'current_role',
            'current_organization',
            'allowed_organizations',
            'current_pharmacy',
            'allowed_pharmacies',
        )
        export_order = fields
        

# class UserInvitationResource(BaseResource):
#     # organization = fields.Field(
#     #     column_name='organization',
#     #     attribute='organization',
#     #     widget=ForeignKeyWidget(Organization, 'name')
#     # )
#     sender = fields.Field(
#         column_name='sender',
#         attribute='sender',
#         widget=ForeignKeyWidget(CustomUser, 'email')
#     )
#     receiver = fields.Field(
#         column_name='receiver',
#         attribute='receiver',
#         widget=ForeignKeyWidget(CustomUser, 'email')
#     )

#     class Meta:
#         model = UserInvitation
#         import_id_fields = ('id',)
#         fields = ('id', 'organization', 'sender', 'receiver',
#                   'receiver_email', 'user_type', 'role_type', 'token')
#         export_order = fields




