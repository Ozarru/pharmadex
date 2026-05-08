from django.db import models
from pharmadex.context import (
    get_current_organization,
    get_current_pharmacy,
    get_current_user,
    is_admin_request,
    is_tenancy_disabled,
    is_pharmacy_scope_disabled,
    get_allowed_pharmacy_ids,
)


class TenantQuerySet(models.QuerySet):
    def for_current_context(self):
        if is_tenancy_disabled() or is_admin_request():
            return self

        org = get_current_organization()
        user = get_current_user()

        if not org or not user:
            return self.none()

        qs = self

        # ----------------------------------
        # Organization filter (ALWAYS)
        # ----------------------------------
        if hasattr(self.model, "organization"):
            qs = qs.filter(organization=org)
        elif hasattr(self.model, "TENANT_FILTER"):
            qs = qs.filter(**{self.model.TENANT_FILTER: org})

        # ----------------------------------
        # Pharmacy filter + access control
        # ----------------------------------
        if hasattr(self.model, "pharmacy"):

            # restrict to allowed pharmacies
            allowed_ids = get_allowed_pharmacy_ids()
            if not allowed_ids:
                return qs.none()
            qs = qs.filter(pharmacy_id__in=allowed_ids)

            # apply current pharmacy (UI context)
            if not is_pharmacy_scope_disabled():
                pharmacy = get_current_pharmacy()
                if pharmacy:
                    qs = qs.filter(pharmacy=pharmacy)
        elif hasattr(self.model, "TENANT_FILTER"):
            prefix = self.model.TENANT_FILTER.rsplit("__organization", 1)[0]

            allowed_ids = get_allowed_pharmacy_ids()
            if not allowed_ids:
                return qs.none()
            qs = qs.filter(**{f"{prefix}_id__in": allowed_ids})

            if not is_pharmacy_scope_disabled():
                pharmacy = get_current_pharmacy()
                if pharmacy:
                    qs = qs.filter(**{prefix: pharmacy})

        return qs


class TenantManager(models.Manager):
    def get_queryset(self):
        qs = TenantQuerySet(self.model, using=self._db)
        return qs.for_current_context()

