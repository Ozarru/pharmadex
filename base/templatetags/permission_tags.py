from django import template

register = template.Library()


def user_has_role_permission(user, action, model_name):
    """
    Checks permission based on:
    1. Platform admin override
    2. Organization role
    3. Django native permissions (optional fallback)
    """

    if not user.is_authenticated:
        return False

    # Platform admin override
    if getattr(user, "is_platform_admin", None) and user.is_platform_admin():
        return True
    if getattr(user, "is_superuser", False):
        return True

    profile = getattr(user, "profile", None)
    if not profile:
        return False

    org = profile.current_organization
    assignment = profile.current_role

    if not org or not assignment or not assignment.role:
        return False

    role_name = assignment.role.user_type.lower()

    action = action.lower()

    # --------------------------
    # Define role-based logic
    # --------------------------

    # PLATFORM ADMIN → full access
    if role_name == "platform_admin":
        return True

    if role_name in ["pharmacy_manager", "inventory_manager"]:
        return action in ["view", "add", "change", "delete", "manage", "import", "export"]

    if role_name == "cashier":
        return action in ["view", "add", "change"]

    if role_name == "vendor":
        return action in ["view", "add", "change"]

    if role_name in ["pharmacist", "doctor"]:
        return action in ["view", "add", "change"]

    # --------------------------
    # Fallback to Django perms
    # --------------------------
    django_perm = f"{model_name.lower()}.{action}_{model_name.lower()}"
    return user.has_perm(django_perm)


# Generic permission filter
@register.filter
def has_perm_for(user, args):
    """
    Usage:
    {% if user|has_perm_for:"add,Product" %}
    """
    try:
        action, model_name = [x.strip() for x in args.split(",")]
    except ValueError:
        return False

    return user_has_role_permission(user, action, model_name)


# Convenience filters
@register.filter
def can_view(user, model_name):
    return user_has_role_permission(user, "view", model_name)


@register.filter
def can_add(user, model_name):
    return user_has_role_permission(user, "add", model_name)


@register.filter
def can_change(user, model_name):
    return user_has_role_permission(user, "change", model_name)


@register.filter
def can_delete(user, model_name):
    return user_has_role_permission(user, "delete", model_name)


@register.filter
def can_manage(user, model_name):
    return user_has_role_permission(user, "manage", model_name)


@register.filter
def can_import(user, model_name):
    return user_has_role_permission(user, "import", model_name)


@register.filter
def can_export(user, model_name):
    return user_has_role_permission(user, "export", model_name)
