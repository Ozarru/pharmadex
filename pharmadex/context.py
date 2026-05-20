import threading

from pharmadex.config.constants import CountryPreset, CurrencyPreset, MobileOperatorPreset

_thread_locals = threading.local()

# -------------------------------------------------
# Tenancy toggle (debug / platform admin)
# -------------------------------------------------
def set_tenancy_disabled(disabled: bool):
    _thread_locals.tenancy_disabled = bool(disabled)

def is_tenancy_disabled() -> bool:
    return bool(getattr(_thread_locals, "tenancy_disabled", False))

def set_pharmacy_scope_disabled(disabled: bool):
    _thread_locals.pharmacy_scope_disabled = bool(disabled)

def is_pharmacy_scope_disabled() -> bool:
    return bool(getattr(_thread_locals, "pharmacy_scope_disabled", False))


# -------------------------------------------------
# Current request
# -------------------------------------------------
def set_current_request(request):
    _thread_locals.request = request

def get_current_request():
    return getattr(_thread_locals, "request", None)


# -------------------------------------------------
# Current user
# -------------------------------------------------
def set_current_user(user):
    _thread_locals.user = user

def get_current_user():
    return getattr(_thread_locals, "user", None)


# -------------------------------------------------
# Current organization
# -------------------------------------------------
def set_current_organization(organization):
    _thread_locals.organization = organization

def get_current_organization():
    return getattr(_thread_locals, "organization", None)


# -------------------------------------------------
# Current pharmacy (NEW - IMPORTANT)
# -------------------------------------------------
def get_allowed_pharmacy_ids():
    user = get_current_user()
    if not user:
        return []

    if not hasattr(_thread_locals, "allowed_pharmacy_ids"):
        profile = getattr(user, "profile", None)
        org = get_current_organization()

        if is_privileged_user(user):
            from pharmacies.models import Pharmacy

            qs = Pharmacy.objects.all()
            if org:
                qs = qs.filter(organization=org)
            _thread_locals.allowed_pharmacy_ids = list(
                qs.values_list("id", flat=True)
            )
        elif profile:
            qs = profile.allowed_pharmacies.all()
            if org:
                qs = qs.filter(organization=org)

            allowed_ids = list(qs.values_list("id", flat=True))
            if not allowed_ids and org:
                from pharmacies.models import Pharmacy

                if (
                    profile.current_organization_id == org.id
                    or profile.allowed_organizations.filter(id=org.id).exists()
                ):
                    allowed_ids = list(
                        Pharmacy.objects.filter(organization=org).values_list("id", flat=True)
                    )

            _thread_locals.allowed_pharmacy_ids = allowed_ids
        else:
            _thread_locals.allowed_pharmacy_ids = []

    return _thread_locals.allowed_pharmacy_ids


def set_current_pharmacy(pharmacy):
    """
    Set current pharmacy with safety checks:
    - Must belong to current organization
    - Must be allowed for current user
    """
    if pharmacy is None:
        _thread_locals.pharmacy = None
        return

    org = get_current_organization()
    user = get_current_user()

    # Ensure organization is set first
    if org is None:
        raise ValueError("Cannot set pharmacy without organization")

    # Enforce same organization
    if pharmacy.organization_id != org.id:
        raise ValueError("Pharmacy does not belong to current organization")

    # Optional: enforce user access
    if user and not is_privileged_user(user):
        allowed_ids = set(get_allowed_pharmacy_ids())
        if allowed_ids and pharmacy.id not in allowed_ids:
            raise PermissionError("User not allowed to access this pharmacy")

    _thread_locals.pharmacy = pharmacy


def get_current_pharmacy():
    return getattr(_thread_locals, "pharmacy", None)


# -------------------------------------------------
# Optional: profile
# -------------------------------------------------
def set_current_profile(profile):
    _thread_locals.profile = profile

def get_current_profile():
    return getattr(_thread_locals, "profile", None)


# -------------------------------------------------
# Admin / privilege checks
# -------------------------------------------------
def is_admin_request():
    request = get_current_request()
    user = get_current_user()

    if not request or not hasattr(request, "path"):
        return False

    if not request.path.startswith("/admin/"):
        return False

    return is_privileged_user(user)


def is_privileged_user(user):
    if not user:
        return False
    is_platform_admin = False
    if hasattr(user, "is_platform_admin") and callable(user.is_platform_admin):
        is_platform_admin = bool(user.is_platform_admin())
    else:
        is_platform_admin = bool(getattr(user, "is_platform_admin", False))
    return bool(
        getattr(user, "is_superuser", False)
        or is_platform_admin
    )


# -------------------------------------------------
# Cleanup (VERY IMPORTANT)
# -------------------------------------------------
def clear_context():
    """
    Prevent data leaking between requests (thread reuse).
    MUST be called at end of request.
    """
    for key in [
        "request",
        "user",
        "organization",
        "pharmacy",
        "profile",
        "tenancy_disabled",
        "pharmacy_scope_disabled",
        "allowed_pharmacy_ids",
    ]:
        if hasattr(_thread_locals, key):
            delattr(_thread_locals, key)


# -------------------------------------------------
# Cleanup (VERY IMPORTANT)
# -------------------------------------------------
def market_context(request):
    """
    Add to TEMPLATES['OPTIONS']['context_processors']
    Makes constants available in all templates.
    """
    return {
        "COUNTRY_CHOICES": CountryPreset.choices(),
        "CURRENCY_CHOICES": CurrencyPreset.choices(),
        "MOBILE_OPERATORS": MobileOperatorPreset.choices(),
    }
