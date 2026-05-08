from django.core.exceptions import ValidationError
import os
import uuid
from django.db import models
from django.urls import reverse
from django.utils import timezone
from model_utils.models import SoftDeletableModel
from simple_history.models import HistoricalRecords
from pharmadex.tenant import TenantManager
from utils import optimize_image
from pharmadex.managers import OrganizationManager
from django.utils.translation import gettext_lazy as _
from django.core.files.base import ContentFile
from django.utils.text import slugify
import re
from django.conf import settings


def camel_to_kebab(name: str) -> str:
    """
    Convert CamelCase to kebab-case:
    ProjectRealisation -> project-realisation
    GeotechnicalStudy -> geotechnical-study
    """
    # Insert a dash before uppercase letters that are not at the start
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1-\2', name)
    # Handle consecutive uppercase letters (like XMLParser -> xml-parser)
    kebab = re.sub('([a-z0-9])([A-Z])', r'\1-\2', s1).lower()
    return kebab


class BaseModel(models.Model):
    """
    Base model with:
    - UUID primary key
    - Active/verified flags
    - Timestamps
    - Dynamic URLs and permissions
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(
        default=timezone.now, editable=True, verbose_name=_("Created at"))
    updated_at = models.DateTimeField(
        auto_now=True, editable=True, verbose_name=_("Updated at"))
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                   related_name="%(app_label)s_%(class)s_created", editable=True, blank=True, null=True, verbose_name=_('Created by'))
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                   related_name="%(app_label)s_%(class)s_updated", editable=True, blank=True, null=True, verbose_name=_('Updated by'))

    class Meta:
        managed = True
        abstract = True
        ordering = ('-created_at',)

    # -----------------------
    # Meta helpers
    # -----------------------
    @property
    def model_name(self):
        return self.__class__.__name__

    @property
    def resource_name(self):
        """
        ProjectRealisation -> project-realisation
        """
        return camel_to_kebab(self.__class__.__name__)

    @classmethod
    def app_namespace(cls):
        """
        Dynamically resolve app namespace
        """
        return cls._meta.app_label

    # -----------------------
    # Dynamic URLs (APP-AGNOSTIC)
    # -----------------------

    # -----------------------
    # Optional overrides
    # -----------------------
    default_url = None
    detail_url = None
    update_url = None
    create_url = None
    stats_url = None

    # -----------------------
    # Naming helpers
    # -----------------------
    @classmethod
    def base_name(cls):
        return camel_to_kebab(cls.__name__)

    @classmethod
    def app_label(cls):
        return cls._meta.app_label

    # -----------------------
    # URL name resolvers
    # -----------------------

    @classmethod
    def get_default_url(cls):
        return cls.default_url or f"{cls.app_label()}:{cls.base_name()}-list"

    @classmethod
    def get_detail_url(cls):
        return cls.detail_url or f"{cls.app_label()}:{cls.base_name()}-detail"

    @classmethod
    def get_update_url(cls):
        return cls.update_url or f"{cls.app_label()}:{cls.base_name()}-update"

    @classmethod
    def get_create_url(cls):
        return cls.create_url or f"{cls.app_label()}:{cls.base_name()}-create"

    @classmethod
    def get_stats_url(cls):
        return cls.stats_url or f"{cls.app_label()}:{cls.base_name()}-stats"

    @classmethod
    def get_permissions(cls):
        """
        Dynamic permissions based on model name and verbose names
        """
        base_name = slugify(cls.__name__)
        return [
            (f"import_{base_name}",
             f"Can import {cls._meta.verbose_name.lower()}"),
            (f"export_{base_name}",
             f"Can export {cls._meta.verbose_name.lower()}"),
            (f"manage_{base_name}",
             f"Can manage all {cls._meta.verbose_name_plural.lower()}"),
        ]


class ActivatableModel(BaseModel):
    """
    Abstract model for objects that can be enabled or disabled without deletion.

    Combines:
    - BaseModel: UUID, timestamps, shared metadata, dynamic URLs/permissions
    - SoftDeletableModel: logical deletion and history preservation

    Provides:
    - is_active: explicit activation state, independent from soft deletion
    """
    is_active = models.BooleanField(
        default=False, editable=False, verbose_name=_("Is Active"))

    class Meta:
        abstract = True


class SoftDeleteQuerySet(models.QuerySet):
    def delete(self):
        # Soft-delete all objects in this queryset
        return super().update(is_removed=True)

    def hard_delete(self):
        # Actually delete from DB
        return super().delete()

    def alive(self):
        # Only non-deleted objects
        qs = self
        if hasattr(self.model, "is_removed"):
            qs = qs.exclude(is_removed=True)
        if hasattr(self.model, "is_deleted"):
            qs = qs.exclude(is_deleted=True)
        if hasattr(self.model, "is_archived"):
            qs = qs.exclude(is_archived=True)
        return qs

    def dead(self):
        # Only deleted objects
        qs = self
        if hasattr(self.model, "is_removed"):
            qs = qs.filter(is_removed=True)
        if hasattr(self.model, "is_deleted"):
            qs = qs.filter(is_deleted=True)
        if hasattr(self.model, "is_archived"):
            qs = qs.filter(is_archived=True)
        return qs


class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).alive()

    def all_with_deleted(self):
        return SoftDeleteQuerySet(self.model, using=self._db)

    def deleted_only(self):
        return SoftDeleteQuerySet(self.model, using=self._db).dead()


class ArchivableModel(BaseModel, SoftDeletableModel):
    """
    Base model combining:
    - BaseModel (UUID, timestamps, dynamic URLs/permissions)
    - Soft delete / history tracking
    """
    history = HistoricalRecords(inherit=True)

    objects = SoftDeleteManager()  # default manager hides deleted
    # optional, includes deleted if you call all_with_deleted()
    all_objects = SoftDeleteManager()

    class Meta:
        abstract = True

    def hard_delete(self, *args, **kwargs):
        """
        True hard delete: bypass soft-delete and trigger signals
        """
        # Optional: wipe history here or in view
        if hasattr(self, "history"):
            self.history.all().delete()

        # Call Django ORM delete directly
        # bypass SoftDeletableModel.delete() override
        super(SoftDeletableModel, self).delete(*args, **kwargs)


class OptimizedImageMixin(models.Model):
    """
    Mixin to optimize image fields before saving the model instance.
    Only re-processes images when they are changed.
    """
    image_fields = []  # override in child class

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        old_instance = None

        if not is_new:
            old_instance = self.__class__.objects.filter(pk=self.pk).first()

        for field_name in self.image_fields:
            image = getattr(self, field_name)

            if not image:
                continue

            # If new object → optimize
            if is_new:
                self._optimize_image(field_name, image)
                continue

            # Existing object → check if image changed
            old_image = getattr(old_instance, field_name, None)

            if not old_image or old_image.name != image.name:
                self._optimize_image(field_name, image)

        super().save(*args, **kwargs)

    def _optimize_image(self, field_name, image):
        optimized = optimize_image(image)
        filename = os.path.basename(image.name)
        getattr(self, field_name).save(
            filename,
            ContentFile(optimized.read()),
            save=False
        )

    class Meta:
        abstract = True


class OrganizationModel(BaseModel):
    
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="%(class)s_set",
        verbose_name=_("Related Organization"),
        to_field="id",  # explicitly reference PK
    )

    objects = TenantManager()

    class Meta:
        abstract = True


class PharmacyModel(OrganizationModel):
    
    pharmacy = models.ForeignKey(
        "pharmacies.Pharmacy",
        on_delete=models.PROTECT,
        related_name="%(class)s_set",
        verbose_name=_("Related Pharmacy"),
        to_field="id",  # explicitly reference PK
    )

    objects = TenantManager()

    class Meta:
        abstract = True

    def clean(self):
        super().clean()
        if self.pharmacy_id and self.organization_id:
            if self.organization_id != self.organization_id:
                raise ValidationError(
                    {"pharmacy": _(
                        "Pharmacy must belong to the same organization.")}
                )
