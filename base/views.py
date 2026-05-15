# -----------------------------------
# Python Standard Library
# -----------------------------------
import math
from django.db.models import Q, ForeignKey, F, Count, Sum,Max, ExpressionWrapper, DecimalField
from django.template.loader import select_template
from django.http import FileResponse
from base import resources
from base.services.data_export_cron import export_all_to_zip, export_and_email_data
from datetime import datetime, timedelta
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.dateparse import parse_datetime, parse_time
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.core.exceptions import FieldDoesNotExist
import uuid
from datetime import timedelta
from urllib.parse import urlencode, unquote

# -----------------------------------
# Third-Party Libraries
# -----------------------------------
import chardet
import tablib
from import_export.formats.base_formats import CSV, XLSX

# -----------------------------------
# Django Core
# -----------------------------------
from django import forms
from django.apps import apps
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db import transaction
from django.db.models import Q
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseRedirect,
)
from django.shortcuts import (
    render,
    redirect,
    get_object_or_404,
)
from django.urls import reverse_lazy
from django.utils import translation
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.decorators.http import require_POST, require_http_methods
from django.views.generic import ListView, DetailView
from django.views.generic.edit import (
    ModelFormMixin,
    ProcessFormView,
    FormView,
)
from datetime import time

# -----------------------------------
# Local Apps
# -----------------------------------
from accounts.utils import user_has_permission
from pharmacies.models import Product, ProductBatch, ProductStock, Sale, SaleItem
from organizations.models import *
from base.models import *
from .utils import admin_list_display, admin_list_filter, admin_search_fields, model_admin, model_field_names, model_fields


def is_valid_uuid(val):
    try:
        uuid.UUID(str(val))
        return True
    except:
        return False


#  ------------------------------------
# User model import
#  ------------------------------------
User = get_user_model()


# -------------------------------------------------------------------------
# Custom Generic Views
# -------------------------------------------------------------------------
@require_POST
def set_language(request):
    lang_code = request.POST.get("language")
    next_url = request.META.get("HTTP_REFERER", "base:home")

    if lang_code and lang_code in dict(settings.LANGUAGES):
        translation.activate(lang_code)

        response = redirect(next_url)

        response.set_cookie(
            settings.LANGUAGE_COOKIE_NAME,  # usually "django_language"
            lang_code,
            max_age=365 * 24 * 60 * 60,
        )

        return response

    return redirect(next_url)


@require_http_methods(["GET", "POST"])
def generic_file_upload(request):

    if request.method == "GET":
        return render(request, "components/_drag_and_drop.html", {
            "app_name": request.GET.get("app_name"),
            "model_name": request.GET.get("model_name"),
            "object_id": request.GET.get("object_id"),
            "file_field": request.GET.get("file_field"),
        })

    # ---- POST
    file = request.FILES.get("file")
    app_name = request.POST.get("app_name")
    model_name = request.POST.get("model_name")
    object_id = request.POST.get("object_id")
    file_field = request.POST.get("file_field")

    if not all([file, app_name, model_name, object_id, file_field]):
        return HttpResponse(
            "",
            status=400,
            headers={
                "htmx_response_status": "400",
                "message_type": "warning",
            },
        )

    model = apps.get_model(app_name, model_name)
    obj = get_object_or_404(model, pk=object_id)

    if not hasattr(obj, file_field):
        return HttpResponse(
            "",
            status=400,
            headers={
                "htmx_response_status": "400",
                "message_type": "warning",
            },
        )

    setattr(obj, file_field, file)
    obj.save()

    # ✅ EXACT same contract as BaseModelView
    if request.headers.get("HX-Request") == "true":
        return HttpResponse(
            "",
            status=204,
            headers={
                "HX-Trigger": "db_changed",
                "htmx_response_status": "204",
                "message_type": "success",
            },
        )

    return HttpResponse("File uploaded successfully")


class BaseDeleteView(LoginRequiredMixin, View):
    template_name = "delete_confirmation.html"

    def dispatch(self, request, *args, **kwargs):
        self.model_name = kwargs.get("model_name", "").lower()

        try:
            content_type = ContentType.objects.get(model=self.model_name)
            self.model_class = content_type.model_class()
        except ContentType.DoesNotExist:
            raise Http404(_("Model not found."))

        # Determine success_url
        next_url = request.GET.get("next")
        if next_url and url_has_allowed_host_and_scheme(
            next_url, allowed_hosts={request.get_host()}
        ):
            self.success_url = unquote(next_url)
        else:
            try:
                self.success_url = self.model_class.get_default_url()
            except Exception:
                self.success_url = "/"

        return super().dispatch(request, *args, **kwargs)

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------

    def _is_hard_delete(self, request, **kwargs):
        """
        True when the request wants a permanent hard delete + history wipe.
        Accepts ?hard_delete=1  OR  ?hard_delete=1  (backwards-compatible).
        """
        truthy = {"1", "true", "True"}
        return (
            request.GET.get("hard_delete") in truthy
            or request.GET.get("hard_delete") in truthy
            or kwargs.get("hard_delete") is True
        )

    def has_delete_permission(self, user, obj):
        return user_has_permission("delete", user, obj.__class__)

    def get_objects(self):
        ids = self.request.GET.get("ids")
        pk = self.kwargs.get("pk")

        if ids:
            pk_list = [x for x in ids.split(",") if x]
            qs = self.model_class.objects.filter(pk__in=pk_list)
        elif pk:
            qs = self.model_class.objects.filter(pk=pk)
        else:
            qs = self.model_class.objects.none()

        return [
            obj for obj in qs
            if self.has_delete_permission(self.request.user, obj)
        ]

    def _hard_delete(self, obj):
        """
        Wipe the object's django-simple-history records then hard-delete the
        object itself (which lets Django cascade to related rows normally).
        """
        # wipe history if needed
        if hasattr(obj, "history"):
            obj.history.all().delete()

        # call the proper hard delete
        if hasattr(obj, "hard_delete"):
            obj.hard_delete()  # now triggers signals correctly
        else:
            obj.delete()

    # ------------------------------------------------------------------
    # GET — confirmation page
    # ------------------------------------------------------------------

    def get(self, request, *args, **kwargs):
        objects = self.get_objects()
        hard_delete = self._is_hard_delete(request, **kwargs)

        context = {
            "title": (
                _("Permanently Delete") if hard_delete
                else _("Delete Confirmation")
            ),
            "subtitle": (
                _("This will permanently erase these records and all their history. This cannot be undone.")
                if hard_delete
                else _("Are you sure you want to delete these items?")
            ),
            "objects":        objects,
            "objects_length": len(objects),
            "next":           request.GET.get("next", ""),
            "is_hard_delete":    hard_delete,
        }

        return render(request, self.template_name, context)

    # ------------------------------------------------------------------
    # POST — execute delete
    # ------------------------------------------------------------------

    def post(self, request, *args, **kwargs):
        objects = self.get_objects()
        hard_delete = self._is_hard_delete(request, **kwargs)

        if not objects:
            messages.error(
                request,
                _("You do not have permission to delete any of the selected items.")
            )
            return redirect(request.META.get("HTTP_REFERER", self.success_url))

        deleted_count = 0
        for obj in objects:
            try:
                if hard_delete:
                    self._hard_delete(obj)
                else:
                    obj.delete()     # soft delete via SoftDeletableModel
                deleted_count += 1
            except Exception as e:
                messages.error(request, str(e))

        if deleted_count:
            messages.success(
                request,
                _("{} object(s) deleted successfully.").format(deleted_count)
            )

        return redirect(self.success_url)

    # ------------------------------------------------------------------
    # UTILITY
    # ------------------------------------------------------------------

    def discard_ids_url(self, exclude_pk=None):
        current_ids = self.request.GET.get("ids", "").split(",")
        if exclude_pk:
            current_ids = [pk for pk in current_ids if pk != str(exclude_pk)]
        return f"{self.request.path}?{urlencode({'ids': ','.join(current_ids)})}"


class HTMXDeleteView(LoginRequiredMixin, View):
    """
    HTMX-only delete endpoint.
    Deletes one object (pk) or many (?ids=1,2,3)
    """

    def post(self, request, *args, **kwargs):
        if request.headers.get("HX-Request") != "true":
            return HttpResponseForbidden("HTMX requests only")

        model_name = kwargs.get("model_name", "").lower()

        try:
            content_type = ContentType.objects.get(model=model_name)
            model_class = content_type.model_class()
        except ContentType.DoesNotExist:
            raise Http404(_("Model not found."))

        # Get objects
        ids = request.POST.get("ids")
        pk = kwargs.get("pk")

        qs = model_class.objects.none()

        if ids:
            pk_list = [x for x in ids.split(",") if x]
            qs = model_class.objects.filter(pk__in=pk_list)
        elif pk:
            qs = model_class.objects.filter(pk=pk)

        # Permission check + delete
        deleted_count = 0
        for obj in qs:
            # Trigger a 403 Forbidden response if user does not have permission
            if not user_has_permission("delete", request.user, obj.__class__):
                if request.headers.get("HX-Request") == "true":
                    return HttpResponse(
                        "",  # Empty body, just the headers
                        status=403,
                        headers={
                            'HX-Trigger': 'server_response',
                            'htmx_response_status': '403',
                            'message_type': 'error',
                        }
                    )

            obj.delete()
            deleted_count += 1

        if not deleted_count:
            return HttpResponseForbidden(_("No objects deleted."))

        # HTMX response
        return HttpResponse(
            "",
            status=204,
            headers={
                "HX-Trigger": "server_response",
                "htmx_response_status": "204",
                "message_type": "success",
            },
        )


class BaseModelView(LoginRequiredMixin, ModelFormMixin, ProcessFormView):
    model = None
    fields = []
    success_url = reverse_lazy('list')

    title = ''
    subtitle = ''

    template_name = 'generic/form.html'
    htmx_template_name = 'generic/htmx_form.html'
    extra_context = {}

    def get_template_names(self):
        is_htmx = bool(self.request.headers.get("HX-Request"))
        if is_htmx and self.htmx_template_name:
            return [self.htmx_template_name]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': self.title,
            'form_subtitle': self.subtitle,
            'title': self.title,
            'subtitle': self.subtitle,
            'model_icon': self.model.model_icon,
            'header_paragraph': _("""Use this form to add a new record or update an existing one. 
                                         Fill in all required fields accurately and review optional information to ensure data completeness."""),
        })
        context.update(self.extra_context)
        return context

    def dispatch(self, request, *args, **kwargs):
        # print('dispatch check')
        self.is_add = kwargs.get('pk') is None

        if not self.is_add:
            try:
                self.instance = self.model.objects.get(pk=kwargs['pk'])
            except self.model.DoesNotExist:
                raise Http404(_("Object not found"))
        else:
            self.instance = None

        # Check permission before proceeding
        if not self.has_permission(request.user):
            error_message = _(
                "You do not have permission to perform this action.")

            # If HTMX request, trigger a 403 Forbidden response and close the modal
            if request.headers.get("HX-Request") == "true":
                return HttpResponse(
                    "",  # Empty body, just the headers
                    status=403,
                    headers={
                        'HX-Trigger': 'server_response',
                        'htmx_response_status': '403',
                        'message_type': 'error',
                    }
                )

            # For normal request, redirect with an error message
            messages.error(request, error_message)
            return redirect(request.META.get("HTTP_REFERER", self.success_url))

        return super().dispatch(request, *args, **kwargs)

    def has_permission(self, user):
        # print('permission check')
        """Check if the user has the permission to add or change the model."""
        if not user or not user.is_authenticated:
            return False

        # Superuser always has permission
        if user.is_superuser or user.is_platform_admin():
            return True

        # Generate the permission string based on the model and action
        action = "add" if self.is_add else "change"
        return user_has_permission(action, user, self.model)

    # -----------------------------
    # FORM VAIDATION
    # -----------------------------
    def form_valid(self, form):
        current_organization = getattr(
            self.request.user.profile, "current_organization", None
        )

        # -----------------------------
        # Organization validation
        # -----------------------------
        if hasattr(self.model, "organization"):
            if not current_organization:
                form.add_error(
                    None,
                    _("No organization is set for your account. Please set your current organization first."),
                )
                return self.form_invalid(form)

            form.instance.organization = current_organization

        is_new = form.instance.pk is None

        # -----------------------------
        # Audit fields
        # -----------------------------
        if is_new:
            if hasattr(form.instance, "created_by"):
                form.instance.created_by = self.request.user

        if hasattr(form.instance, "updated_by"):
            form.instance.updated_by = self.request.user

        self.object = form.save()

        # -----------------------------
        # M2M handling
        # -----------------------------
        if hasattr(self.object, "organizations") and current_organization:
            self.object.organizations.add(current_organization)

        # =============================
        # HTMX RESPONSE (SUCCESS)
        # =============================
        if self.request.headers.get("HX-Request") == "true":

            message = _("Save Successsful.")

            return HttpResponse(
                "",
                status=204,
                headers={
                    'HX-Trigger': 'server_response',
                    'htmx_response_status': '204',
                    'message_type': 'success',
                    'message': message,
                }
            )

        # =============================
        # NORMAL RESPONSE
        # =============================
        action = _("created") if is_new else _("updated")

        messages.success(
            self.request,
            _(f"{self.title} {action} successfully.")
        )

        return HttpResponseRedirect(self.get_success_url())

    def form_invalid(self, form):
        # print('invalid check')
        context = self.get_context_data(form=form)

        message = _("Please correct the errors in the form.")

        # If HTMX request, send status and message type in response headers
        if self.request.headers.get("HX-Request") == "true":
            return HttpResponse(
                "",  # Empty body
                status=400,  # Bad Request status for invalid form
                headers={
                    'HX-Trigger': 'server_response',
                    'htmx_response_status': '400',
                    'message_type': 'warning',
                    'message': message,
                }
            )

        # Normal form invalid handling for non-HTMX requests
        messages.error(self.request, message)
        return render(self.request, self.get_template_names()[0], context)


# --------------------------------------------------------------
# FIELD-TYPE → FILTER-TYPE MAPPING
# (used by get_admin_filter_fields to avoid a long if/elif chain)
# --------------------------------------------------------------
_FIELD_TYPE_MAP = {
    models.DateTimeField: "datetime",
    models.DateField:     "date",
    models.TimeField:     "time",
    models.BooleanField:  "boolean",
    models.ManyToManyField: "m2m",
    models.ForeignKey:    "select",
    models.OneToOneField: "select",
}

# Param name → model field name for standard related-object GET filters.
# Each entry is (get_param, model_field).  A None field means "no field guard"
# (the filter is applied unconditionally when the param is present).
_RELATED_GET_FILTERS = [
    ("staff_profile_id",       "staff_profile"),
    ("sale_id",                "sale"),
    ("inventory_operation_id", "inventory_operation"),
    ("inventory_audit_id",     "inventory_audit"),
    ("object_id",              "object_id"),
]


class BaseListView(LoginRequiredMixin, ListView):
    model = None
    model_name = None
    model_stats_url = None
    display_fields = None
    search_fields = None
    filter_fields = None
    template_name = ''
    partial_parent_directory = None
    partial_nested_directory = None
    active_page = None
    context_object_name = ''
    title = ''
    subtitle = ''
    model_icon = ''
    header_paragraph = ''
    can_crud_object = False
    object_crud_link = ''
    object_crud_via_htmx = True
    object_is_actionable = False
    paginate_by = 24
    pagination_url = ''
    pagination_target = ''
    can_be_deleted = True

    # ------------------------------------------------------------------
    # SMALL HELPERS
    # ------------------------------------------------------------------

    def model_has_field(self, field_name: str) -> bool:
        return any(f.name == field_name for f in self.model._meta.get_fields())

    def _get_field_type_str(self, field) -> str:
        """Return a string type token for a model field instance."""
        for field_cls, type_str in _FIELD_TYPE_MAP.items():
            if isinstance(field, field_cls):
                return type_str
        return "select"

    def _is_empty_param(self, value) -> bool:
        """Return True when a GET param should be treated as absent."""
        return value is None or str(value).strip() in ("", "null", "undefined", "None")

    # ------------------------------------------------------------------
    # ADMIN UTILITIES
    # ------------------------------------------------------------------

    def get_model_admin(self):
        """Return the ModelAdmin instance for this model."""
        from django.contrib import admin
        return admin.site._registry.get(self.model)

    def get_search_fields(self):
        """Pull search_fields from the model's ModelAdmin."""
        return getattr(self.get_model_admin(), "search_fields", [])

    def get_admin_filters(self):
        """Pull list_filter fields from the model's ModelAdmin."""
        return getattr(self.get_model_admin(), "list_filter", [])

    def get_pseudo_filters(self):
        """
        Return pseudo-filter metadata defined on the model.

        Expected format on the model::

            @classmethod
            def pseudo_filters(cls):
                return {
                    "filter_name": {
                        "type": "boolean" | "select" | "text",
                        "verbose": "Label",
                        "choices": [(val, label), ...],   # optional
                        "queryset_fn": callable(qs, value) -> qs,
                    }
                }
        """
        if hasattr(self.model, "pseudo_filters"):
            return self.model.pseudo_filters()
        return {}

    def get_admin_filter_fields(self):
        """
        Build the combined filter-field metadata list consumed by templates.
        Pseudo filters are listed first, then real model fields from list_filter.
        """
        model_admin = self.get_model_admin()
        fields = []

        # 1. Pseudo filters
        for name, config in self.get_pseudo_filters().items():
            fields.append({
                "name":         name,
                "type":         config.get("type", "select"),
                "verbose_name": config.get("verbose", name),
                "choices":      config.get("choices", []),
                "pseudo":       True,
            })

        # 2. Real model fields from list_filter
        for field_name in getattr(model_admin, "list_filter", []):
            try:
                field = self.model._meta.get_field(field_name)
            except Exception:
                continue

            fields.append({
                "name":         field_name,
                "type":         self._get_field_type_str(field),
                "verbose_name": field.verbose_name,
            })

        return fields

    # ------------------------------------------------------------------
    # ADMIN list_display → DISPLAY FIELDS
    # ------------------------------------------------------------------
    def get_display_fields(self):
        model_admin = self.get_model_admin()
        list_display = getattr(model_admin, "list_display", [])
        image_fields = set(
            getattr(model_admin, "list_display_image_fields", []))
        fields = []

        for name in list_display:
            meta = {
                "name":    name,
                "verbose": name.replace("_", " ").title(),
                "type":    "text",
            }

            # 1. Real model field
            try:
                field = self.model._meta.get_field(name)
                meta["verbose"] = field.verbose_name.title()
                meta["type"] = self._get_field_type_str(field)
                # ImageField isn't in _FIELD_TYPE_MAP because it would collide;
                # handle it explicitly here.
                if isinstance(field, models.ImageField):
                    meta["type"] = "image"

            except Exception:
                # 2. Admin display method
                if model_admin and hasattr(model_admin, name):
                    admin_attr = getattr(model_admin, name)
                    if getattr(admin_attr, "boolean", False):
                        meta["type"] = "boolean"
                    if hasattr(admin_attr, "short_description"):
                        meta["verbose"] = admin_attr.short_description

                # 3. Model property / callable
                elif hasattr(self.model, name):
                    attr = getattr(self.model, name)
                    if getattr(attr, "boolean", False):
                        meta["type"] = "boolean"

            # Declared image override always wins
            if name in image_fields:
                meta["type"] = "image"

            fields.append(meta)

        return fields

    # ------------------------------------------------------------------
    # ORGANISATION-SCOPED + PERMISSION FILTERING
    # ------------------------------------------------------------------

    def get_filtered_queryset(self, current_organization):
        user = self.request.user

        if not user.is_authenticated:
            return self.model.objects.none()

        queryset = self.model.objects.all()

        # Organization model is never organisation-scoped
        from organizations.models import Organization
        if self.model == Organization:
            return queryset

        # Detect organisation field name
        model_field_names = {f.name for f in self.model._meta.get_fields()}
        org_field = None
        if "organization" in model_field_names:
            org_field = "organization"
        elif "organizations" in model_field_names:
            org_field = "organizations"

        try:
            user_role = user.organization_roles.filter(
                organization=current_organization
            ).first()
        except Exception:
            pass

        # No org field → no restriction
        if not org_field:
            return queryset

        # Apply org scope: non-privileged users must always be scoped;
        # privileged users are scoped only when an org is active.
        # is_privileged = user.is_privileged_in(
        #     user.profile.current_organization)

        if current_organization:
            queryset = queryset.filter(**{org_field: current_organization})
        # elif not is_privileged:
        #     return self.model.objects.none()

        return queryset

    # ------------------------------------------------------------------
    # UNIVERSAL FILTER HANDLER
    # ------------------------------------------------------------------

    def apply_admin_filters(self, queryset):
        request = self.request
        pseudo_filters = self.get_pseudo_filters()

        # 1. Pseudo filters
        for name, config in pseudo_filters.items():
            value = request.GET.get(name)
            if self._is_empty_param(value):
                continue
            fn = config.get("queryset_fn")
            if fn:
                queryset = fn(queryset, value)

        # 2. Real list_filter fields
        for f in self.get_admin_filters():

            # Determine param name
            param_name = getattr(f, "parameter_name",
                                 f.__name__) if callable(f) else f

            # Callable (Django-style) filter
            if callable(f):
                value = request.GET.get(param_name)
                if self._is_empty_param(value):
                    continue
                queryset = f(queryset, value)
                continue

            # Pseudo filters are already handled above
            if param_name in pseudo_filters:
                continue

            # Field-based filtering
            base_field_name = f.split("__")[0]
            try:
                field_obj = self.model._meta.get_field(base_field_name)
            except Exception:
                continue

            field_type = field_obj.get_internal_type()

            if field_type in ("DateField", "DateTimeField", "TimeField"):
                start = request.GET.get(f"{f}_start")
                end = request.GET.get(f"{f}_end")
                start_time_str = request.GET.get(f"{f}_start_time")
                end_time_str = request.GET.get(f"{f}_end_time")

                if self._is_empty_param(start) and self._is_empty_param(end) and self._is_empty_param(start_time_str) and self._is_empty_param(end_time_str):
                    continue

                if field_type == "DateField":
                    if start and not self._is_empty_param(start):
                        start_date = parse_date(start)
                        if start_date:
                            queryset = queryset.filter(
                                **{f"{f}__gte": start_date})
                    if end and not self._is_empty_param(end):
                        end_date = parse_date(end)
                        if end_date:
                            queryset = queryset.filter(
                                **{f"{f}__lte": end_date})

                elif field_type == "TimeField":
                    if start and not self._is_empty_param(start):
                        start_time = parse_time(start)
                        if start_time:
                            queryset = queryset.filter(
                                **{f"{f}__gte": start_time})
                    if end and not self._is_empty_param(end):
                        end_time = parse_time(end)
                        if end_time:
                            queryset = queryset.filter(
                                **{f"{f}__lte": end_time})

                else:
                    start_dt = parse_datetime(
                        start) if start and "T" in str(start) else None
                    end_dt = parse_datetime(
                        end) if end and "T" in str(end) else None

                    if not start_dt and start and not self._is_empty_param(start):
                        start_date = parse_date(start)
                        if start_date:
                            start_t = parse_time(start_time_str) if start_time_str and not self._is_empty_param(
                                start_time_str) else time.min
                            start_dt = datetime.combine(start_date, start_t)

                    if not end_dt and end and not self._is_empty_param(end):
                        end_date = parse_date(end)
                        if end_date:
                            end_t = parse_time(end_time_str) if end_time_str and not self._is_empty_param(
                                end_time_str) else time.max
                            end_dt = datetime.combine(end_date, end_t)

                    if start_dt and timezone.is_naive(start_dt) and settings.USE_TZ:
                        start_dt = timezone.make_aware(
                            start_dt, timezone.get_current_timezone())
                    if end_dt and timezone.is_naive(end_dt) and settings.USE_TZ:
                        end_dt = timezone.make_aware(
                            end_dt, timezone.get_current_timezone())

                    if start_dt:
                        queryset = queryset.filter(**{f"{f}__gte": start_dt})
                    if end_dt:
                        queryset = queryset.filter(**{f"{f}__lte": end_dt})

                continue

            value = request.GET.get(param_name)
            if self._is_empty_param(value):
                continue

            if field_type == "BooleanField":
                if value in {"1", "true", "True", "on"}:
                    queryset = queryset.filter(**{f: True})
                elif value in {"0", "false", "False", "off"}:
                    queryset = queryset.filter(**{f: False})

            elif field_type in ("ForeignKey", "OneToOneField"):
                queryset = queryset.filter(**{f: value})

            elif getattr(field_obj, "choices", None):
                queryset = queryset.filter(**{f: value})

            elif field_type in ("IntegerField", "FloatField", "DecimalField"):
                queryset = queryset.filter(**{f: value})

            else:
                queryset = queryset.filter(**{f"{f}__icontains": value})

        return queryset

    # ------------------------------------------------------------------
    # MAIN QUERYSET (SEARCH + FILTER)
    # ------------------------------------------------------------------

    def get_queryset(self):
        current_organization = self.request.user.profile.current_organization
        queryset = self.get_filtered_queryset(current_organization)

        if self.model_has_field("created_at"):
            queryset = queryset.order_by("-created_at")

        queryset = self.apply_admin_filters(queryset).distinct()

        # Standard related-object GET filters
        for param, field in _RELATED_GET_FILTERS:
            value = self.request.GET.get(param)
            if not value:
                continue
            if field is None or self.model_has_field(field):
                queryset = queryset.filter(**{f"{field or param}": value})

        # Category / subcategory / product
        if category_id := self.request.GET.get("category_id"):
            queryset = queryset.filter(subcategory__category_id=category_id)
        if subcategory_id := self.request.GET.get("subcategory_id"):
            queryset = queryset.filter(subcategory_id=subcategory_id)
        if product_id := self.request.GET.get("product_id"):
            queryset = queryset.filter(id=product_id)

        # Full-text search
        if search := self.request.GET.get("search"):
            q = Q()
            model = self.model  # or queryset.model

            for field in self.get_search_fields():
                try:
                    field_obj = model._meta.get_field(field)

                    # If it's a ForeignKey → search a text field inside it
                    if isinstance(field_obj, ForeignKey):
                        # default to 'id' OR better: a readable field like 'name' or 'code'
                        q |= Q(**{f"{field}__id__icontains": search})
                    else:
                        q |= Q(**{f"{field}__icontains": search})

                except Exception:
                    # fallback (for related lookups like user__username)
                    q |= Q(**{f"{field}__icontains": search})

            queryset = queryset.filter(q)

        # Strip soft-deleted objects — check all possible soft-delete field names
        for soft_field in ("is_deleted", "is_removed", "is_archived"):
            if self.model_has_field(soft_field):
                queryset = queryset.filter(**{soft_field: False})

        return queryset

    # ------------------------------------------------------------------
    # SOFT DELETE CHECK
    # ------------------------------------------------------------------

    def _supports_soft_delete(self):
        mro = [cls.__name__ for cls in self.model.__mro__]
        has_field = any(
            f.name in ("is_deleted", "deleted")
            for f in self.model._meta.get_fields()
        )
        return "SoftDeletableModel" in mro or has_field

    # ------------------------------------------------------------------
    # DISPATCH AND ACCESS RESTRICTION
    # ------------------------------------------------------------------

    def dispatch(self, request, *args, **kwargs):
        if not user_has_permission("view", request.user, self.model):
            messages.error(request, _(
                "You do not have permission to view this page."))
            referer = request.META.get(
                "HTTP_REFERER", str(reverse_lazy("base:home")))
            return redirect(referer)
        return super().dispatch(request, *args, **kwargs)

    # ------------------------------------------------------------------
    # CONTEXT
    # ------------------------------------------------------------------
    def _build_filters_metadata(self, context):
        """
        Populate context['filters_metadata'] and context['filters_choices']
        from admin list_filter fields and pseudo-filter definitions.
        """
        filters_metadata = {}
        filters_choices = {}

        for field_name in self.get_admin_filters():
            try:
                field = self.model._meta.get_field(field_name)
                field_type = field.get_internal_type()

                if field_type == "BooleanField":
                    filters_metadata[field_name] = {
                        "type":    "boolean",
                        "verbose": field.verbose_name.title(),
                    }

                elif field_type in ("ForeignKey", "OneToOneField"):
                    filters_metadata[field_name] = {
                        "type":    "select",
                        "verbose": field.verbose_name.title(),
                    }
                    filters_choices[field_name] = [
                        (obj.pk, str(obj))
                        for obj in field.related_model.objects.all()
                    ]

                elif field.choices:
                    filters_metadata[field_name] = {
                        "type":    "select",
                        "verbose": field.verbose_name.title(),
                    }
                    filters_choices[field_name] = field.choices

                else:
                    filters_metadata[field_name] = {
                        "type":    "text",
                        "verbose": field.verbose_name.title(),
                    }

            except Exception:
                continue

        # Pseudo filters
        for name, f in self.get_pseudo_filters().items():
            filters_metadata[name] = {
                "type":    f.get("type", "text"),
                "verbose": f.get("verbose", name.replace("_", " ").title()),
            }
            if "choices" in f:
                filters_choices[name] = f["choices"]

        context["filters_metadata"] = filters_metadata
        context["filters_choices"] = filters_choices

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        url_query_string = self.request.GET.copy().urlencode()
        default_url = self.model.get_default_url()
        detail_url = self.model.get_detail_url()
        update_url = self.model.get_update_url()
        create_url = self.model.get_create_url()

        model_name = self.model._meta.model_name
        model_container = default_url.split(
            ":", 1)[-1].lower() if ":" in default_url else ""

        current_org = getattr(user.profile, "current_organization", None)

        context.update({
            "model":                     self.model,
            "model_name":                self.model.__name__,
            "model_verbose_name":        self.model._meta.verbose_name,
            "model_verbose_name_plural": self.model._meta.verbose_name_plural,
            "model_app":                 self.model._meta.app_label,
            "display_fields":            self.get_display_fields(),
            "search_fields":             self.get_search_fields(),
            "admin_filters":             self.get_admin_filters(),
            "active_page":               self.active_page,
            "title":                     _(self.title or f"{self.model.__name__}s"),
            "subtitle":                  _(self.subtitle),
            "model_icon":                getattr(self.model, "model_icon", ""),
            "header_paragraph":          _(self.header_paragraph),
            "url_query_string":          url_query_string,
            "pagination_url":            default_url,
            "pagination_target":         model_container,
            "model_list_url":            default_url,
            "model_detail_url":          detail_url,
            "model_update_url":          update_url,
            "model_create_url":          create_url,
            "model_container":           model_container,
            "filters_metadata":          {},
            "filters_choices":           {},
        })

        # CRUD permissions
        if user.is_superuser or user.is_platform_admin():
            context.update({
                "can_crud_object":      True,
                "object_crud_link":     create_url,
                "object_crud_via_htmx": True,
                "object_is_actionable": True,
                "can_be_deleted": True,
            })
        elif hasattr(user, "get_permissions"):
            perms = user.get_permissions()
            if f"change_{model_name}" in perms:
                context.update({
                    "can_crud_object":      True,
                    "object_crud_link":     create_url,
                    "object_crud_via_htmx": True,
                    "object_is_actionable": True,
                })
            if f"delete_{model_name}" in perms:
                context.update({
                    "can_be_deleted": True,
                })
        else:
            context.update({
                "can_crud_object":      False,
                "object_crud_link":     None,
                "object_crud_via_htmx": False,
                "object_is_actionable": False,
            })

        # Bulk action flags
        context["can_activate"] = self.model_has_field("is_active")
        context["can_verify"] = self.model_has_field("is_verified")

        # Filter metadata (real + pseudo)
        self._build_filters_metadata(context)

        # filters_fields for template — consistent list of dicts (no string mixing)
        context["filters_fields"] = self.get_admin_filter_fields()

        return context

    # ------------------------------------------------------------------
    # RENDERING (HTML or HTMX PARTIALS)
    # ------------------------------------------------------------------

    def get(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        context = self.get_context_data()
        is_htmx = request.headers.get("HX-Request")
        origin = request.GET.get("origin")

        if is_htmx and origin == "partial":
            template = self._resolve_partial_template()
            return render(request, template, context)

        return render(request, self.template_name, context)

    def _resolve_partial_template(self):
        """Return the first existing partial template (generic fallback first)."""

        templates = []

        # Always try generic first
        templates.append("generic/_list.html")

        # Then try specific paths
        if self.partial_parent_directory:
            if self.partial_nested_directory:
                templates.append(
                    f"{self.partial_parent_directory}/{self.partial_nested_directory}/_list.html"
                )
            else:
                templates.append(
                    f"{self.partial_parent_directory}/{self.model.__name__.lower()}/_list.html"
                )
        else:
            templates.append(f"{self.model.__name__.lower()}/_list.html")

        # Return first existing template
        return select_template(templates).template.name


class BaseListViewCached(LoginRequiredMixin, ListView):
    model = None
    template_name = ""
    partial_parent_directory = None
    partial_nested_directory = None
    paginate_by = 24

    # ------------------------------------------------------------------
    # FAST FIELD CHECKS (USES CACHE HELPERS)
    # ------------------------------------------------------------------

    def model_has_field(self, name: str) -> bool:
        return name in model_field_names(self.model)

    # ------------------------------------------------------------------
    # ADMIN (CACHED)
    # ------------------------------------------------------------------

    def get_model_admin(self):
        return model_admin(self.model)

    def get_search_fields(self):
        return admin_search_fields(self.model)

    def get_admin_filters(self):
        return admin_list_filter(self.model)

    def get_display_fields(self):
        admin_obj = self.get_model_admin()
        list_display, image_fields = admin_list_display(self.model)

        fields = []
        field_map = model_fields(self.model)

        for name in list_display:
            meta = {
                "name": name,
                "verbose": name.replace("_", " ").title(),
                "type": "text",
            }

            field_info = field_map.get(name)

            if field_info:
                meta["verbose"] = name.replace("_", " ").title()
                meta["type"] = field_info["type"]

                if field_info["type"] == "ImageField":
                    meta["type"] = "image"

            if admin_obj and hasattr(admin_obj, name):
                attr = getattr(admin_obj, name)
                if getattr(attr, "boolean", False):
                    meta["type"] = "boolean"

            if name in image_fields:
                meta["type"] = "image"

            fields.append(meta)

        return fields

    # ------------------------------------------------------------------
    # FILTER HELPERS (OPTIMIZED)
    # ------------------------------------------------------------------

    def _is_empty_param(self, value):
        return value in (None, "", "null", "None", "undefined")

    def get_pseudo_filters(self):
        return getattr(self.model, "pseudo_filters", lambda: {})()

    def get_admin_filter_fields(self):
        field_map = model_fields(self.model)
        fields = []

        # pseudo filters first
        for name, cfg in self.get_pseudo_filters().items():
            fields.append({
                "name": name,
                "type": cfg.get("type", "select"),
                "verbose_name": cfg.get("verbose", name),
                "choices": cfg.get("choices", []),
                "pseudo": True,
            })

        for f in self.get_admin_filters():
            try:
                field = field_map.get(f)
                if not field:
                    continue

                fields.append({
                    "name": f,
                    "type": field["type"],
                    "verbose_name": f.replace("_", " ").title(),
                })
            except Exception:
                continue

        return fields

    # ------------------------------------------------------------------
    # QUERYSET OPTIMIZED (LESS DB INTROSPECTION)
    # ------------------------------------------------------------------

    def get_queryset(self):
        qs = self.model.objects.all()

        if self.model_has_field("created_at"):
            qs = qs.order_by("-created_at")

        qs = self.apply_admin_filters(qs).distinct()

        # soft delete (fast check)
        for f in ("is_deleted", "is_removed", "is_archived"):
            if self.model_has_field(f):
                qs = qs.filter(**{f: False})

        return qs

    # ------------------------------------------------------------------
    # FILTER ENGINE (SIMPLIFIED)
    # ------------------------------------------------------------------

    def apply_admin_filters(self, queryset):
        request = self.request
        pseudo = self.get_pseudo_filters()
        field_map = model_fields(self.model)

        # pseudo filters
        for name, cfg in pseudo.items():
            value = request.GET.get(name)
            if self._is_empty_param(value):
                continue
            fn = cfg.get("queryset_fn")
            if fn:
                queryset = fn(queryset, value)

        # normal filters
        for f in self.get_admin_filters():
            value = request.GET.get(f)
            if self._is_empty_param(value):
                continue

            field = field_map.get(f)
            if not field:
                continue

            ftype = field["type"]

            if ftype == "BooleanField":
                queryset = queryset.filter(
                    **{f: value in ("1", "true", "True")})

            elif ftype in ("DateField", "DateTimeField"):
                start = request.GET.get(f"{f}_start")
                end = request.GET.get(f"{f}_end")

                if start:
                    queryset = queryset.filter(**{f"{f}__gte": start})
                if end:
                    queryset = queryset.filter(**{f"{f}__lte": end})

            elif ftype in ("ForeignKey", "OneToOneField"):
                queryset = queryset.filter(**{f: value})

            elif field.get("choices"):
                queryset = queryset.filter(**{f: value})

            else:
                queryset = queryset.filter(**{f"{f}__icontains": value})

        return queryset


class BaseDetailView(LoginRequiredMixin, DetailView):
    """
    Reusable base view for displaying object details with:
    - organization-scoped access
    - CRUD permission context
    - HTMX partial rendering support
    """
    model = None
    template_name = ''
    context_object_name = None
    title = ''
    subtitle = ''
    model_icon = ''
    header_paragraph = ''
    can_crud_object = False
    object_pk = ''
    object_crud_link = ''
    object_crud_via_htmx = True
    partial_parent_directory = None
    partial_nested_directory = None
    active_page = None

    # --------------------------
    # Permission check
    # --------------------------
    def dispatch(self, request, *args, **kwargs):
        if not user_has_permission("view", request.user, self.model):
            messages.error(request, _(
                "You do not have permission to view this page."))
            referer = request.META.get(
                "HTTP_REFERER", str(reverse_lazy("base:home")))
            return redirect(referer)

        return super().dispatch(request, *args, **kwargs)

    # --------------------------
    # Queryset restricted by organization
    # --------------------------
    def get_queryset(self):
        queryset = self.model.objects.all()
        user = self.request.user
        if not user.is_authenticated:
            return self.model.objects.none()

        current_organization = getattr(
            user.profile, 'current_organization', None)

        # if not user.is_privileged_in(current_organization):
        #     if current_organization:
        #         if hasattr(self.model, 'organization'):
        #             queryset = queryset.filter(
        #                 organization=current_organization)
        #         elif hasattr(self.model, 'organizations'):
        #             queryset = queryset.filter(
        #                 organizations=current_organization)
        #     else:
        #         return self.model.objects.none()

        return queryset

    # --------------------------
    # Object retrieval
    # --------------------------
    def get_object(self, queryset=None):
        if queryset is None:
            queryset = self.get_queryset()
        return get_object_or_404(queryset, pk=self.kwargs.get('pk'))

    # --------------------------
    # Context data
    # --------------------------
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        obj = context.get(self.context_object_name or 'object')

        # -------------------------
        # Enable change permission if allowed
        # -------------------------
        if user_has_permission('change', user, self.model):
            context['can_crud_object'] = True
            context['object_pk'] = self.object.pk
            context['object_crud_link'] = getattr(
                self.model, 'get_update_url', '')

        # -------------------------
        # Basic UI info
        # -------------------------
        context.update({
            'model_app': self.model._meta.app_label,
            'model_name': self.model.__name__,
            'active_page': getattr(self, 'active_page', None),
            'title': _(getattr(self, 'title', f"{self.model._meta.verbose_name} Details")),
            'subtitle': _(getattr(self, 'subtitle', f"Detailed view of {obj}")),
            'model_icon': getattr(self, 'model_icon', '') or getattr(self.model, 'model_icon', ''),
            'header_paragraph': _(getattr(self, 'header_paragraph', "Detailed information and related records.")),
        })

        return context

    # --------------------------
    # GET request rendering
    # --------------------------
    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        context = self.get_context_data(object=self.object)

        # HTMX partial rendering
        is_htmx = request.headers.get('HX-Request')
        origin = request.GET.get('origin')
        if is_htmx and origin == 'partial':
            if self.partial_parent_directory:
                template = (
                    f"{self.partial_parent_directory}/{self.partial_nested_directory}/_detail.html"
                    if self.partial_nested_directory
                    else f"{self.partial_parent_directory}/{self.model.__name__.lower()}/_detail.html"
                )
            else:
                template = f"{self.model.__name__.lower()}/_detail.html"
            return render(request, template, context)

        return render(request, self.template_name, context)

    # --------------------------
    # Admin helpers (optional)
    # --------------------------
    def get_model_admin(self, model):
        return admin.site._registry.get(model)


class BaseParentChildFormView(View):
    model = None
    form_class = None
    formset_class = None

    template_name = None
    htmx_template_name = None

    title_create = ""
    title_update = ""
    subtitle_create = ""
    subtitle_update = ""
    active_page = None
    header_paragraph = ""

    success_url_name = None
    success_url_kwarg = "pk"
    can_add_item = True

    # -------------------------------------------------
    # FLEXIBLE TENANT CONFIG
    # -------------------------------------------------
    # e.g. {"organization": lambda r: ..., "pharmacy": lambda r: ...}
    lookup_kwargs = None

    # -------------------------------------------------
    # TENANT HELPERS
    # -------------------------------------------------
    def get_organization(self, request):
        if getattr(request, "current_organization", None):
            return request.current_organization
        profile = getattr(request.user, "profile", None)
        return getattr(profile, "current_organization", None)

    def get_pharmacy(self, request):
        if getattr(request, "current_pharmacy", None):
            return request.current_pharmacy
        profile = getattr(request.user, "profile", None)
        return getattr(profile, "current_pharmacy", None)

    # -------------------------------------------------
    # REQUEST HELPERS
    # -------------------------------------------------
    def is_htmx(self, request):
        return request.headers.get("HX-Request") == "true"

    def get_template(self, request):
        if self.is_htmx(request) and self.htmx_template_name:
            return self.htmx_template_name
        return self.template_name

    # -------------------------------------------------
    # OBJECT FETCHING (SAFE + FLEXIBLE)
    # -------------------------------------------------
    def get_object(self, request, pk):
        if not pk:
            return None

        filters = {}

        if self.lookup_kwargs:
            for key, func in self.lookup_kwargs.items():
                filters[key] = func(request)

        return get_object_or_404(
            self.model,
            pk=pk,
            **filters
        )

    # -------------------------------------------------
    # CHILD INITIAL DATA
    # -------------------------------------------------
    def get_child_initial(self, request, parent_obj):
        return []

    # -------------------------------------------------
    # FORMSET BUILDING (SAFE)
    # -------------------------------------------------
    def get_formset_kwargs(self, request, parent_obj, data=None):
        """
        Override this per view to inject:
        - organization
        - pharmacy
        - both
        - or nothing
        """
        return {}

    def build_formset(self, request, parent_obj, data=None):
        kwargs = {
            "instance": parent_obj,
            **self.get_formset_kwargs(request, parent_obj, data),
        }

        if parent_obj is None:
            kwargs["initial"] = self.get_child_initial(request, parent_obj)

        if data:
            kwargs["data"] = data

        return self.formset_class(**kwargs)

    # -------------------------------------------------
    # HOOKS
    # -------------------------------------------------
    def set_parent_fields(self, request, parent_obj, is_create):
        # SAFE DEFAULT: assign if exists
        if hasattr(parent_obj, "organization"):
            parent_obj.organization = self.get_organization(request)

        if hasattr(parent_obj, "pharmacy"):
            parent_obj.pharmacy = self.get_pharmacy(request)

        return parent_obj

    def set_child_fields(self, request, child_obj, parent_obj, is_create):
        return child_obj

    # -------------------------------------------------
    # REDIRECT
    # -------------------------------------------------
    def get_success_redirect(self, parent_obj):
        return redirect(self.success_url_name, **{
            self.success_url_kwarg: parent_obj.pk
        })

    # -------------------------------------------------
    # CONTEXT
    # -------------------------------------------------
    def get_page_copy(self, is_create):
        return {
            "title": self.title_create if is_create else self.title_update,
            "subtitle": self.subtitle_create if is_create else self.subtitle_update,
        }

    def build_context(self, request, form, formset, is_create):
        copy = self.get_page_copy(is_create)

        return {
            "form": form,
            "formset": formset,
            "title": copy["title"],
            "subtitle": copy["subtitle"],
            "active_page": self.active_page,
            "header_paragraph": self.header_paragraph,
            "model_icon": getattr(self.model, "model_icon", ""),
            "can_add_item": self.can_add_item,
        }

    # -------------------------------------------------
    # GET
    # -------------------------------------------------
    def get(self, request, pk=None):
        parent_obj = self.get_object(request, pk)
        is_create = parent_obj is None

        form = self.form_class(instance=parent_obj)
        formset = self.build_formset(request, parent_obj)

        context = self.build_context(request, form, formset, is_create)
        return render(request, self.get_template(request), context)

    # -------------------------------------------------
    # POST
    # -------------------------------------------------
    def post(self, request, pk=None):
        parent_obj = self.get_object(request, pk)
        is_create = parent_obj is None

        form = self.form_class(request.POST, instance=parent_obj)
        formset = self.build_formset(request, parent_obj, data=request.POST)

        if not (form.is_valid() and formset.is_valid()):
            messages.error(request, "Please correct the errors in the form.")
            context = self.build_context(request, form, formset, is_create)
            return render(request, self.get_template(request), context)

        try:
            with transaction.atomic():

                # Save parent
                parent_obj = form.save(commit=False)
                parent_obj = self.set_parent_fields(
                    request, parent_obj, is_create)
                parent_obj.save()

                # Save children
                formset.instance = parent_obj
                children = formset.save(commit=False)

                for child in children:
                    child = self.set_child_fields(
                        request, child, parent_obj, is_create
                    )
                    child.save()

                # deletions
                if getattr(formset, "deleted_objects", None):
                    for obj in formset.deleted_objects:
                        obj.delete()

        except Exception:
            messages.error(
                request,
                "An unexpected error occurred while saving. Please check the data."
            )
            context = self.build_context(request, form, formset, is_create)
            return render(request, self.get_template(request), context)

        messages.success(
            request,
            "Created successfully." if is_create else "Updated successfully."
        )

        return self.get_success_redirect(parent_obj)


@login_required(login_url="accounts:login")
@require_http_methods(["GET", "POST"])
def pharmacy_file_upload(request):
    """
    Pharmacy-only file upload endpoint (secure + scoped).
    """

    # -------------------- ALLOWED PHARMACY MODELS --------------------
    allowed = {
        ("pharmacy", "prescription"): {"attachment"},
        ("pharmacy", "dispense_record"): {"receipt_file"},
        ("pharmacy", "purchase_order"): {"document"},
        ("pharmacy", "goods_receipt"): {"document"},
        ("pharmacy", "supplier_invoice"): {"invoice_file"},
        ("patients", "patientrecord"): {"attachment"},
    }

    # ==================== GET ====================
    if request.method == "GET":
        app_name = (request.GET.get("app_name") or "").strip()
        model_name = (request.GET.get("model_name") or "").strip()
        file_field = (request.GET.get("file_field") or "").strip()
        object_id = (request.GET.get("object_id") or "").strip()

        key = (app_name.lower(), model_name.lower())

        if key not in allowed or file_field not in allowed[key] or not object_id:
            raise Http404()

        return render(request, "components/_drag_and_drop.html", {
            "app_name": app_name,
            "model_name": model_name,
            "object_id": object_id,
            "file_field": file_field,
        })

    # ==================== POST ====================
    file = request.FILES.get("file")
    app_name = (request.POST.get("app_name") or "").strip()
    model_name = (request.POST.get("model_name") or "").strip()
    object_id = (request.POST.get("object_id") or "").strip()
    file_field = (request.POST.get("file_field") or "").strip()

    if not all([file, app_name, model_name, object_id, file_field]):
        return HttpResponse("", status=400, headers={
            "htmx_response_status": "400",
            "message_type": "warning",
        })

    key = (app_name.lower(), model_name.lower())

    if key not in allowed or file_field not in allowed[key]:
        return HttpResponse("", status=400, headers={
            "htmx_response_status": "400",
            "message_type": "warning",
        })

    model = apps.get_model(app_name, model_name)

    # -------------------- PERMISSION CHECK --------------------
    if not CustomPermissionRequiredMixin().has_manage_permission(request.user, model):
        return HttpResponseForbidden()

    # -------------------- VALID FIELD --------------------
    try:
        field_obj = model._meta.get_field(file_field)
    except FieldDoesNotExist:
        return HttpResponse("", status=400)

    if not isinstance(field_obj, models.FileField):
        return HttpResponse("", status=400)

    # -------------------- FILE SIZE LIMIT --------------------
    max_bytes = getattr(
        settings, "PHARMACY_UPLOAD_MAX_BYTES", 10 * 1024 * 1024)

    if getattr(file, "size", 0) > max_bytes:
        return HttpResponse("", status=400, headers={
            "htmx_response_status": "400",
            "message_type": "warning",
        })

    # -------------------- ORGANIZATION SCOPING --------------------
    qs = model._default_manager.all()
    org = getattr(getattr(request.user, "profile", None),
                  "current_organization", None)

    try:
        model._meta.get_field("organization")
        qs = qs.filter(organization=org)
    except FieldDoesNotExist:
        pass

    obj = get_object_or_404(qs, pk=object_id)

    # -------------------- ATTACH FILE --------------------
    if not hasattr(obj, file_field):
        return HttpResponse("", status=400)

    setattr(obj, file_field, file)
    obj.save()

    # ==================== HX RESPONSE ====================
    if request.headers.get("HX-Request") == "true":
        return HttpResponse("", status=204, headers={
            "HX-Trigger": "server_response",
            "htmx_response_status": "204",
            "message_type": "success",
        })

    return HttpResponse("File uploaded successfully")


# --------------------------
# Custome Toggle Permission Checker
# --------------------------
class CustomPermissionRequiredMixin:
    """Mixin to enforce 'can_manage' permission on the model."""

    def has_manage_permission(self, user, model):
        if not user.is_authenticated:
            return False

        # Superuser bypass
        if user.is_superuser or user.is_platform_admin():
            return True

        model_app = model._meta.app_label
        model_name = model._meta.model_name
        return f"can_manage_{model_name}" in user.get_permissions()

    def enforce_permission(self, request, model):
        if not self.has_manage_permission(request.user, model):
            messages.error(request, _(
                "You do not have permission to perform this action."))
            return redirect(request.META.get("HTTP_REFERER", "base:home"))
        return None


# --------------------------
# Toggle active status
# --------------------------
class ToggleActivityView(CustomPermissionRequiredMixin, View):
    def post(self, request, model_name, pk):
        try:
            model = ContentType.objects.get(
                model=model_name.lower()
            ).model_class()
        except ContentType.DoesNotExist:
            return HttpResponseBadRequest("Model not found")

        perm_redirect = self.enforce_permission(request, model)
        if perm_redirect:
            return perm_redirect

        obj = get_object_or_404(model, pk=pk)
        if not hasattr(obj, 'is_active'):
            return HttpResponseBadRequest("Object has no 'is_active' field")

        obj.is_active = not obj.is_active

        if hasattr(obj, 'status'):
            if obj._meta.model_name == 'cardaccount':
                obj.status = 'active' if obj.is_active else 'deactivated'
            else:
                obj.status = 'active' if obj.is_active else 'inactive'

        obj.save()

        messages.success(request, _(f"{model_name} successfully modified."))

        if request.headers.get("HX-Request"):
            return HttpResponse(status=204, headers={'HX-Trigger': 'server_response'})
        else:
            return redirect(request.META.get("HTTP_REFERER", "base:home"))


class BulkToggleActivityView(CustomPermissionRequiredMixin, View):
    def post(self, request, model_name):
        ids = request.POST.getlist("ids[]")
        if not ids:
            return HttpResponseBadRequest("No IDs provided")

        try:
            model = ContentType.objects.get(
                model=model_name.lower()).model_class()
        except ContentType.DoesNotExist:
            return HttpResponseBadRequest("Model not found")

        perm_redirect = self.enforce_permission(request, model)
        if perm_redirect:
            return perm_redirect

        if not hasattr(model, "is_active"):
            return HttpResponseBadRequest("Model has no 'is_active' field")

        qs = model.objects.filter(pk__in=ids)
        for obj in qs:
            obj.is_active = not obj.is_active
            if hasattr(obj, 'status'):
                if obj._meta.model_name == 'cardaccount':
                    obj.status = 'active' if obj.is_active else 'deactivated'
                else:
                    obj.status = 'active' if obj.is_active else 'inactive'
            obj.save()

        messages.success(request, _(
            f"{qs.count()} {model_name}(s) successfully toggled."))
        return HttpResponse(status=204, headers={"HX-Trigger": "server_response"})


# --------------------------
# Toggle archived status
# --------------------------
class ToggleArchivalView(CustomPermissionRequiredMixin, View):
    def post(self, request, model_name, pk):
        try:
            model = ContentType.objects.get(
                model=model_name.lower()).model_class()
        except ContentType.DoesNotExist:
            return HttpResponseBadRequest("Model not found")

        perm_redirect = self.enforce_permission(request, model)
        if perm_redirect:
            return perm_redirect

        obj = get_object_or_404(model, pk=pk)
        if not hasattr(obj, 'is_archived'):
            return HttpResponseBadRequest("Object has no 'is_archived' field")

        obj.is_archived = not obj.is_archived
        if hasattr(obj, 'status'):
            obj.status = 'archived' if obj.is_archived else 'unarchived'
        obj.save()

        messages.success(request, _(f"{model_name} successfully modified."))
        return HttpResponse(status=204, headers={'HX-Trigger': 'server_response'})


class BulkToggleArchivalView(CustomPermissionRequiredMixin, View):
    def post(self, request, model_name):
        ids = request.POST.getlist("ids[]")
        if not ids:
            return HttpResponseBadRequest("No IDs provided")

        try:
            model = ContentType.objects.get(
                model=model_name.lower()).model_class()
        except ContentType.DoesNotExist:
            return HttpResponseBadRequest("Model not found")

        perm_redirect = self.enforce_permission(request, model)
        if perm_redirect:
            return perm_redirect

        if not hasattr(model, "is_active"):
            return HttpResponseBadRequest("Model has no 'is_active' field")

        qs = model.objects.filter(pk__in=ids)
        for obj in qs:
            obj.is_active = not obj.is_active
            if hasattr(obj, 'status'):
                if obj._meta.model_name == 'cardaccount':
                    obj.status = 'active' if obj.is_active else 'deactivated'
                else:
                    obj.status = 'active' if obj.is_active else 'inactive'
            obj.save()

        messages.success(request, _(
            f"{qs.count()} {model_name}(s) successfully toggled."))
        return HttpResponse(status=204, headers={"HX-Trigger": "server_response"})


# --------------------------
# Toggle verification
# --------------------------
class ToggleVerificationView(CustomPermissionRequiredMixin, View):
    def post(self, request, model_name, pk):
        try:
            model = ContentType.objects.get(
                model=model_name.lower()).model_class()
        except ContentType.DoesNotExist:
            return HttpResponseBadRequest("Model not found")

        perm_redirect = self.enforce_permission(request, model)
        if perm_redirect:
            return perm_redirect

        obj = get_object_or_404(model, pk=pk)
        if not hasattr(obj, 'is_verified'):
            return HttpResponseBadRequest("Object has no 'is_verified' field")

        obj.is_verified = not obj.is_verified
        if hasattr(obj, 'status'):
            obj.status = 'verified' if obj.is_verified else 'unverified'
        obj.save()

        messages.success(request, _(f"{model_name} successfully modified."))
        return HttpResponse(status=204, headers={'HX-Trigger': 'server_response'})


class BulkToggleVerificationView(CustomPermissionRequiredMixin, View):
    def post(self, request, model_name):
        ids = request.POST.getlist("ids[]")
        if not ids:
            return HttpResponseBadRequest("No IDs provided")

        try:
            model = ContentType.objects.get(
                model=model_name.lower()).model_class()
        except ContentType.DoesNotExist:
            return HttpResponseBadRequest("Model not found")

        perm_redirect = self.enforce_permission(request, model)
        if perm_redirect:
            return perm_redirect

        if not hasattr(model, "is_verified"):
            return HttpResponseBadRequest("Model has no 'is_verified' field")

        qs = model.objects.filter(pk__in=ids)
        for obj in qs:
            obj.is_verified = not obj.is_verified
            if hasattr(obj, 'status'):
                obj.status = 'verified' if obj.is_verified else 'unverified'
            obj.save()

        messages.success(request, _(
            f"{qs.count()} {model_name}(s) successfully toggled."))
        return HttpResponse(status=204, headers={"HX-Trigger": "server_response"})


# --------------------------
# Toggle arbitrary status
# --------------------------
class ToggleStatusView(CustomPermissionRequiredMixin, View):
    def post(self, request, model_name, pk):
        try:
            model = ContentType.objects.get(
                model=model_name.lower()).model_class()
        except ContentType.DoesNotExist:
            return HttpResponseBadRequest("Model not found")

        perm_redirect = self.enforce_permission(request, model)
        if perm_redirect:
            return perm_redirect

        obj = get_object_or_404(model, pk=pk)
        new_status = request.POST.get('status')
        if not hasattr(obj, 'status') or not new_status:
            return HttpResponseBadRequest("Invalid status field or value")

        obj.status = new_status
        obj.save()

        messages.success(request, _(
            f"{model_name.capitalize()} status updated successfully to '{new_status}'."))

        if request.headers.get('HX-Request') == 'true':
            return HttpResponse(status=204, headers={'HX-Trigger': 'server_response'})
        return redirect(request.META.get('HTTP_REFERER', '/'))


# Helper functions to check for ForeignKey and ManyToManyField
def has_foreign_key(model_class, field_name):
    """Check if the model has a ForeignKey field."""
    # Check if the field exists in the model
    for field in model_class._meta.get_fields():
        if field.name == field_name:
            return isinstance(field, models.ForeignKey)
    return False


def has_many_to_many(model_class, field_name):
    """Check if the model has a ManyToManyField."""
    # Check if the field exists in the model
    for field in model_class._meta.get_fields():
        if field.name == field_name:
            return isinstance(field, models.ManyToManyField)
    return False


def get_model_and_resource(self, app_name, model_name):
    # model_name will arrive lowercase from URLs → convert properly
    model = apps.get_model(app_name, model_name)

    if not model:
        raise Http404(f"Model {model_name} not found in app {app_name}")

    resource_name = f"{model.__name__}Resource"
    resource_class = getattr(resources, resource_name, None)
    return model, resource_class


class BaseExportView(LoginRequiredMixin, View):

    def get(self, request, app_name, model_name, format_type="csv"):
        model, resource_class = get_model_and_resource(
            self, app_name, model_name)

        if not resource_class:
            return HttpResponse(f"No Resource found for {model_name}", status=404)

        queryset = model.objects.all()

        # -------- DATE FILTERS --------
        date = request.GET.get("date")
        start_date = request.GET.get("start_date")
        end_date = request.GET.get("end_date")

        filename_suffix = "all"  # default suffix

        start_hour = request.GET.get("start_hour")
        end_hour = request.GET.get("end_hour")

        # Initialize start and end
        start = None
        end = None

        # Determine the base date range
        if date:
            d = parse_date(date)
            if d:
                start = timezone.make_aware(
                    datetime.combine(d, datetime.min.time()))
                end = start + timedelta(days=1)
                filename_suffix = d.strftime("%Y-%m-%d")

        elif start_date and end_date:
            sd = parse_date(start_date)
            ed = parse_date(end_date)
            if sd and ed:
                start = timezone.make_aware(
                    datetime.combine(sd, datetime.min.time()))
                end = timezone.make_aware(
                    datetime.combine(ed, datetime.max.time()))
                filename_suffix = f"{sd.strftime('%Y-%m-%d')}_to_{ed.strftime('%Y-%m-%d')}"

        # If hourly filter is applied, override start/end hours
        if start is not None and end is not None and start_hour is not None and end_hour is not None:
            try:
                start_hour = int(start_hour)
                end_hour = int(end_hour)
                start = start.replace(
                    hour=start_hour, minute=0, second=0, microsecond=0)
                end = end.replace(hour=end_hour, minute=59,
                                  second=59, microsecond=999999)
                filename_suffix += f"_{start_hour:02d}h-{end_hour:02d}h"
            except ValueError:
                pass

        # Apply filter to queryset
        if start is not None and end is not None:
            queryset = queryset.filter(
                created_at__gte=start, created_at__lte=end)

        # -------- EXPORT --------
        resource = resource_class()
        dataset = resource.export(queryset)

        if format_type == "xlsx":
            fmt = XLSX()
            ext = "xlsx"
        else:
            fmt = CSV()
            ext = "csv"

        data = fmt.export_data(dataset)
        filename = f"{model_name}_{filename_suffix}.{ext}"

        response = HttpResponse(data, content_type=fmt.get_content_type())
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class ImportForm(forms.Form):
    import_file = forms.FileField()


class BaseImportView(LoginRequiredMixin, FormView):
    form_class = ImportForm
    template_name = "components/_import.html"

    def get_model_and_resource(self, app_name, model_name):
        model = apps.get_model(app_name, model_name.capitalize())
        resource_class = getattr(resources, f"{model.__name__}Resource", None)
        return model, resource_class

    def get_success_url(self):
        return self.request.META.get("HTTP_REFERER", "base:home")

    def form_valid(self, form):
        import_file = form.cleaned_data["import_file"]
        ext = import_file.name.split(".")[-1].lower()

        app_name = self.kwargs["app_name"]
        model_name = self.kwargs["model_name"]

        model, resource_class = self.get_model_and_resource(
            app_name, model_name)
        if not resource_class:
            messages.error(
                self.request, f"No resource class found for {model_name}."
            )
            return redirect(self.get_success_url())

        # --- READ FILE ---
        raw = import_file.read()

        # -------------------------------
        # XLSX: DO NOT DECODE
        # -------------------------------
        if ext == "xlsx":
            file_format = XLSX()
            dataset = file_format.create_dataset(raw)
        else:
            # -------------------------------
            # CSV: AUTO-DETECT ENCODING SAFELY
            # -------------------------------
            detected = chardet.detect(raw)
            encoding = detected.get("encoding") or "latin-1"

            if detected.get("confidence", 0) < 0.5:
                encoding = "latin-1"

            try:
                decoded_text = raw.decode(encoding)
            except UnicodeDecodeError:
                decoded_text = raw.decode("latin-1")  # final fallback

            file_format = CSV()
            dataset = file_format.create_dataset(decoded_text)

        # -------------------------------
        # PASS REQUEST TO RESOURCE
        # -------------------------------
        resource = resource_class(request=self.request)

        # -------------------------------
        # FILTER COLUMNS
        # -------------------------------
        resource_fields = [f.column_name for f in resource.get_fields()]
        cleaned_rows = []

        for row in dataset.dict:
            # keep only valid fields
            cleaned = {k: v for k, v in row.items() if k in resource_fields}

            # guarantee all columns exist
            for h in resource_fields:
                cleaned.setdefault(h, "")

            cleaned_rows.append(cleaned)

        # -------------------------------
        # REBUILD TABLIB DATASET SAFELY
        # -------------------------------
        dataset = tablib.Dataset(
            *[[row[h] for h in resource_fields] for row in cleaned_rows],
            headers=resource_fields
        )

        # -------------------------------
        # IMPORT
        # -------------------------------
        # DO NOT PASS `request=` HERE, resource already has it
        result = resource.import_data(
            dataset,
            dry_run=False,
            raise_errors=False,
            collect_failed_rows=True,
            use_transactions=False,
            user=self.request.user,
        )

        if result.has_errors():
            messages.error(self.request, str(result.row_errors()))
        else:
            messages.success(
                self.request, f"Data import successful for {model_name}!"
            )

        return redirect(self.get_success_url())


@login_required(login_url='accounts:login')
def not_found(request, exception):
    context = {
        "active_page": "not_found_page",
        "title": _("Page not found"),
        "subtitle": _("Error 404"),
        "header_paragraph": _(
            "The page you are trying to access does not exist, may have been moved, "
            "or you may not have the correct access rights."
        ),
    }
    return render(request, "not_found.html", context)


@login_required(login_url='accounts:login')
def app_parameters(request):
    context = {
        "active_page": "app_parameters_page",
        "title": _("Platform Settings Page"),
        "subtitle": _("Manage the platform's  parameters"),
        "header_paragraph": _("""The platform parameters section allows system administrators to configure
                                    and manage the foundational settings of the SaaS environment — including user roles,
                                    feature toggles, access levels, billing preferences, support settings, and system-wide
                                    defaults. These configurations ensure that the platform operates efficiently, securely,
                                    and is tailored to meet the business needs of different client organizations."""),


    }
    return render(request, 'parameters/index.html', context)


# -------------------------------------------------------------------------
# index
# -------------------------------------------------------------------------


@login_required(login_url='accounts:login')
def home(request):
    user = request.user
    profile = getattr(user, "profile", None)

    current_org = getattr(request, "current_organization", None) or getattr(
        profile, "current_organization", None)
    current_pharmacy = getattr(request, "current_pharmacy", None) or getattr(
        profile, "current_pharmacy", None)

    from organizations.models import Customer, Supplier
    # from hr.models import Staff
    from pharmacies.models import Pharmacy, Product, ProductBatch, Sale, PurchaseOrder
    from django.utils.timezone import now
    from django.db.models import Sum, F

    if not current_org:
        return render(request, "base/home.html", {
            "active_page": "home_page",
            "title": _("Home"),
            "subtitle": _("Select or create an organization to start"),
            "header_paragraph": _("You can sign in even without an organization. Create one or ask an admin to invite you."),
            "model_icon": "fa-solid fa-house",
            "current_organization": None,
        })

    # -----------------------------
    # SCOPE
    # -----------------------------
    batches = ProductBatch.objects.all()

    if current_pharmacy:
        batches = batches.filter(product_stock__pharmacy=current_pharmacy)
        pharmacy_filter = {"pharmacy": current_pharmacy}
    else:
        batches = batches.filter(
            product_stock__pharmacy__organization=current_org)
        pharmacy_filter = {"pharmacy__organization": current_org}

    # -----------------------------
    # DATE FILTERS
    # -----------------------------
    today = now().date()

    # -----------------------------
    # CORE COUNTS
    # -----------------------------
    customers_count = Customer.objects.filter(organization=current_org).count()
    suppliers_count = Supplier.objects.filter(organization=current_org).count()
    # staff_count = Staff.objects.filter(organization=current_org).count()

    pharmacies_count = Pharmacy.objects.filter(
        organization=current_org).count()

    products_count = Product.objects.filter(
        is_active=True,
        organization=current_org
    ).count()

    sales_qs = Sale.objects.filter(**pharmacy_filter)

    sales_count = sales_qs.count()

    purchase_orders_count = PurchaseOrder.objects.filter(
        **pharmacy_filter).count()

    # -----------------------------
    # STOCK HEALTH (BATCH LOGIC)
    # -----------------------------
    expiring_count = batches.expiring().count()
    expired_count = batches.expired().count()
    damaged_count = batches.damaged().count()

    low_stock_count = batches.filter(quantity__lte=F(
        "product_stock__product__min_stock_threshold")).count()

    cutoff_date = now() - timedelta(days=180)

    dead_stock_count = ProductBatch.objects.annotate(
        last_sale_date=Max("product_stock__sale_items__sale__created_at")
    ).filter(
        quantity__gt=0,   # only if ProductBatch HAS quantity field
        last_sale_date__lt=cutoff_date
    ).count()
    
    cutoff_date = now() - timedelta(days=30)

    fast_moving_count = ProductBatch.objects.annotate(
        sales_count=Count(
            "product_stock__sale_items",
            filter=models.Q(product_stock__sale_items__sale__created_at__gte=cutoff_date)
        )
    ).filter(
        sales_count__gte=10,   # threshold = high frequency
        quantity__gt=0
    ).count()

    overstocked_count = batches.filter(quantity__gt=F(
        "product_stock__product__min_stock_threshold") * 3).count()

    # -----------------------------
    # FINANCE KPIs
    # -----------------------------
    today_sales = sales_qs.filter(created_at__date=today).aggregate(
        total=Sum("total_amount")
    )["total"] or 0

    today_profit = SaleItem.objects.filter(
        sale__pharmacy__organization=current_org,
        sale__created_at__date=today
    ).aggregate(
        total=Sum(
            ExpressionWrapper(
                (F("unit_price") - F("product_stock__cost")) * F("quantity"),
                output_field=DecimalField()
            )
        )
    )["total"] or 0

    today_profit = math.floor(today_profit)

    outstanding_credit = sales_qs.filter(status="on_credit").aggregate(
        total=Sum("total_amount")
    )["total"] or 0

    # -----------------------------
    # CONTEXT
    # -----------------------------
    context = {
        "active_page": "home_page",
        "title": _("Home"),
        "subtitle": _("Organization overview"),
        "header_paragraph": _("Overview of your organization and pharmacy operations."),
        "model_icon": "fa-solid fa-house",

        "current_organization": current_org,
        "current_pharmacy": current_pharmacy,

        # CORE
        "customers_count": customers_count,
        "suppliers_count": suppliers_count,
        # "staff_count": staff_count,
        "pharmacies_count": pharmacies_count,
        "products_count": products_count,
        "sales_count": sales_count,
        "purchase_orders_count": purchase_orders_count,

        # STOCK HEALTH
        "expiring_products_count": expiring_count,
        "expired_products_count": expired_count,
        "damaged_stock_count": damaged_count,
        "low_stock_count": low_stock_count,
        "dead_stock_count": dead_stock_count,
        "fast_moving_count": fast_moving_count,
        "overstocked_count": overstocked_count,

        # FINANCE
        "today_sales": today_sales,
        "today_profit": today_profit,
        "outstanding_credit": outstanding_credit,
    }

    return render(request, "base/home.html", context)


# -------------------------------------------------------------------------
# System Parameters
# -------------------------------------------------------------------------
@login_required(login_url='accounts:login')
def system_parameters(request):
    user = request.user
    header_paragraph = _(
        "The system parameters section allows administrators to configure core "
        "platform settings, including global preferences, integrations, feature "
        "controls, and operational defaults to ensure the SaaS environment runs "
        "efficiently and supports organizational needs."
    )

    context = {
        "active_page": "system_parameters_page",
        "title": _("Platform System Parameters Page"),
        "subtitle": _("Manage the platform's system parameters"),
        "header_paragraph": header_paragraph,
        "model_icon": 'fa-solid fa-server',

    }
    return render(request, 'parameters/system.html', context)


# -------------------------------------------------------------------------
# Security Parameters
# -------------------------------------------------------------------------
@login_required(login_url='accounts:login')
def security_parameters(request):
    user = request.user
    header_paragraph = _(
        "The security parameters section enables administrators to define and manage "
        "critical security controls — including authentication policies, multi-factor "
        "requirements, session governance, IP restrictions, and account protection rules. "
        "These settings safeguard the platform and help maintain compliance."
    )

    context = {
        "active_page": "security_parameters_page",
        "title": _("Platform Security Parameters Page"),
        "subtitle": _("Manage the platform's security parameters"),
        "header_paragraph": header_paragraph,
        "model_icon": 'fa-solid fa-shield',

    }
    return render(request, 'parameters/security.html', context)


# -------------------------------------------------------------------------
# User Parameters
# -------------------------------------------------------------------------
@login_required(login_url='accounts:login')
def user_parameters(request):
    user = request.user
    header_paragraph = _(
        "The user parameters section allows administrators to configure defaults and "
        "policies related to user accounts — including profile settings, user role behavior, "
        "permissions structure, and user experience configurations across the platform."
    )

    context = {
        "active_page": "user_parameters_page",
        "title": _("Platform User Parameters Page"),
        "subtitle": _("Manage the platform's user parameters"),
        "header_paragraph": header_paragraph,
        "model_icon": 'fa-solid fa-user-gear',

    }
    return render(request, 'parameters/users.html', context)


# -------------------------------------------------------------------------
# Export Trigger
# -------------------------------------------------------------------------
@login_required(login_url='accounts:login')
def trigger_export_email(request):
    if not (request.user.is_superuser or request.user.is_platform_admin()):
        return HttpResponseForbidden()
    is_htmx = request.headers.get("HX-Request") == "true"

    # ✅ Get optional date from query params
    date = request.GET.get("date")  # e.g. ?date=2026-03-26
    if date:
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            date = None  # fallback safely

    try:
        export_and_email_data(date=date)

        if is_htmx:
            response = HttpResponse(status=200)
            response["htmx_response_status"] = "200"
            response["message_type"] = "success"
            response["message"] = (
                f"Export completed successfully"
                + (f" for {date}" if date else "")
            )
            return response

        messages.success(
            request,
            f"Export traité (envoyé ou déjà effectué){f' pour {date}' if date else ''}."
        )

    except Exception as e:
        if is_htmx:
            response = HttpResponse(status=500)
            response["htmx_response_status"] = "500"
            response["message_type"] = "error"
            response["message"] = str(e)
            return response

        messages.error(request, f"Erreur lors de l'export : {e}")

    return redirect(request.META.get("HTTP_REFERER", "base:home"))


# =========================
# DJANGO VIEW: DOWNLOAD
# =========================
@login_required(login_url='accounts:login')
def download_exports(request):
    if not (request.user.is_superuser or request.user.is_platform_admin()):
        return HttpResponseForbidden()
    zip_paths, _ = export_all_to_zip()

    # return first zip (or customize)
    first_zip = zip_paths[0]

    return FileResponse(
        open(first_zip, "rb"),
        as_attachment=True,
        filename=first_zip.name,
    )


# =========================
# DJANGO VIEW: GENERATE + LINKS
# =========================
@login_required(login_url='accounts:login')
def generate_exports(request):
    if not (request.user.is_superuser or request.user.is_platform_admin()):
        return HttpResponseForbidden()
    zip_paths, _ = export_all_to_zip()

    files = [
        {
            "name": path.name,
            "url": f"{settings.MEDIA_URL}exports/{path.parent.name}/{path.name}",
        }
        for path in zip_paths
    ]

    return JsonResponse({"files": files})
