# accounts/templatetags/custom_permissions.py
from django import template

register = template.Library()

@register.simple_tag
def has_organization_permission(user, codename, organization):
    return user.has_organization_permission(codename, organization)
