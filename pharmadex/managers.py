from django.db import models
from .querysets import OrganizationQuerySet

class OrganizationManager(models.Manager):
    def get_queryset(self):
        return OrganizationQuerySet(self.model, using=self._db)._apply_organization_filter()
