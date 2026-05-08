from pharmadex.context import (
    clear_context,
    set_current_organization,
    set_current_pharmacy,
    set_current_profile,
    set_current_request,
    set_current_user,
    set_tenancy_disabled,
    set_pharmacy_scope_disabled,
)


class TenantContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            set_current_request(request)

            user = request.user if getattr(request, "user", None) and request.user.is_authenticated else None
            set_current_user(user)
            set_tenancy_disabled(False)
            request.pharmacy_scope_disabled = bool(request.session.get("pharmacy_scope_disabled", False))
            set_pharmacy_scope_disabled(bool(request.pharmacy_scope_disabled))

            if not user:
                return self.get_response(request)

            profile = getattr(user, "profile", None)
            set_current_profile(profile)

            org = self._resolve_current_organization(request, user, profile)
            request.current_organization = org
            request.available_organizations = self._get_available_organizations(user, profile)
            set_current_organization(org)

            pharmacy = self._resolve_current_pharmacy(request, user, profile, org)
            request.current_pharmacy = pharmacy
            if pharmacy and org:
                set_current_pharmacy(pharmacy)
            request.available_pharmacies = self._get_available_pharmacies(user, profile, org)

            return self.get_response(request)
        finally:
            clear_context()

    def _allowed_organization_ids(self, user, profile):
        if user.is_superuser or getattr(user, "is_staff", False):
            return None

        ids = set()

        if profile:
            ids.update(profile.allowed_organizations.values_list("id", flat=True))
            if profile.current_organization_id:
                ids.add(profile.current_organization_id)

        ids.update(
            user.user_roles.exclude(organization__isnull=True).values_list(
                "organization_id", flat=True
            )
        )

        return ids

    def _get_available_organizations(self, user, profile):
        from organizations.models import Organization

        allowed_ids = self._allowed_organization_ids(user, profile)
        if allowed_ids is None:
            return Organization.objects.order_by("name")

        return Organization.objects.filter(id__in=allowed_ids).order_by("name")

    def _get_available_pharmacies(self, user, profile, org):
        if not org:
            return []

        from pharmacies.models import Pharmacy

        qs = Pharmacy.objects.filter(organization=org).order_by("name")
        if user.is_superuser or getattr(user, "is_staff", False):
            return qs

        if not profile:
            return qs.none()

        allowed = profile.allowed_pharmacies.filter(organization=org)
        if allowed.exists():
            return qs.filter(id__in=allowed.values_list("id", flat=True))

        return qs

    def _resolve_current_organization(self, request, user, profile):
        from organizations.models import Organization

        allowed_ids = self._allowed_organization_ids(user, profile)

        requested_id = request.session.get("current_organization_id") or getattr(
            profile, "current_organization_id", None
        )

        org = None
        if requested_id:
            try:
                org = Organization.objects.get(id=requested_id)
            except Organization.DoesNotExist:
                org = None

        if org and allowed_ids is not None and org.id not in allowed_ids:
            org = None

        if not org:
            if allowed_ids is None:
                org = Organization.objects.order_by("name").first()
            else:
                org = (
                    Organization.objects.filter(id__in=allowed_ids)
                    .order_by("name")
                    .first()
                )

        if profile and org and profile.current_organization_id != org.id:
            profile.current_organization = org
            profile.save(update_fields=["current_organization"])
            request.session["current_organization_id"] = str(org.id)

        return org

    def _resolve_current_pharmacy(self, request, user, profile, org):
        if not org:
            return None

        from pharmacies.models import Pharmacy

        allowed_org_ids = self._allowed_organization_ids(user, profile)
        if allowed_org_ids is not None and org.id not in allowed_org_ids:
            return None

        requested_id = request.session.get("current_pharmacy_id") or getattr(
            profile, "current_pharmacy_id", None
        )

        base_qs = Pharmacy.objects.filter(organization=org)
        if not (user.is_superuser or getattr(user, "is_staff", False)):
            if profile:
                allowed_pharmacies = profile.allowed_pharmacies.filter(organization=org)
                if allowed_pharmacies.exists():
                    base_qs = base_qs.filter(id__in=allowed_pharmacies.values_list("id", flat=True))

        pharmacy = None
        if requested_id:
            pharmacy = base_qs.filter(id=requested_id).first()

        if not pharmacy:
            if profile:
                allowed_pharmacies = profile.allowed_pharmacies.filter(organization=org)
                if allowed_pharmacies.count() == 1:
                    pharmacy = allowed_pharmacies.first()

        if profile and pharmacy and profile.current_pharmacy_id != pharmacy.id:
            profile.current_pharmacy = pharmacy
            profile.save(update_fields=["current_pharmacy"])
            request.session["current_pharmacy_id"] = str(pharmacy.id)

        if profile and not pharmacy and profile.current_pharmacy_id:
            profile.current_pharmacy = None
            profile.save(update_fields=["current_pharmacy"])
            request.session.pop("current_pharmacy_id", None)

        return pharmacy

