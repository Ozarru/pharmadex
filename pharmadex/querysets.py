
from django.db.models import QuerySet, ForeignKey, OneToOneField, ManyToManyField
from django.db.models.fields.reverse_related import ManyToManyRel
from django.core.exceptions import FieldDoesNotExist
from .context import get_current_organization, is_admin_request

class OrganizationQuerySet(QuerySet):
    def _apply_organization_filter(self):
        qs = self._clone()

        if is_admin_request():
            return qs

        org = get_current_organization()
        if not org:
            return qs

        try:
            field = self.model._meta.get_field("organization")
            if isinstance(field, (ForeignKey, OneToOneField)):
                return qs.filter(organization=org)
        except FieldDoesNotExist:
            return qs

        return qs.filter(organization=org)
