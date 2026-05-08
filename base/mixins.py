
from accounts.utils import user_has_permission
from django.db import models
from django.contrib import admin


class AdminFilteringMixin:
    """
    Provides search_fields and filter_fields extraction
    exactly the same way as your ListView.
    """

    def get_model_admin(self, model):
        return admin.site._registry.get(model)

    def get_admin_search_fields(self, model):
        model_admin = self.get_model_admin(model)
        if not model_admin:
            return []
        return getattr(model_admin, "search_fields", [])

    def get_admin_filters(self, model):
        model_admin = self.get_model_admin(model)
        if not model_admin:
            return [], {}

        list_filter = getattr(model_admin, "list_filter", [])

        filters_fields = []
        filters_choices = {}

        for f in list_filter:
            # f is a field name
            if isinstance(f, str):
                filters_fields.append(f)

                # Try to get choices from model
                try:
                    field = model._meta.get_field(f)
                    if field.choices:
                        filters_choices[f] = [
                            {"value": v, "label": l} for v, l in field.choices
                        ]
                except Exception:
                    pass

        return filters_fields, filters_choices


class TabBuilderMixin:
    def build_tab(self, model, **kwargs):
        user = getattr(self.request, "user", None)

        # --- Permission capability ---
        can_add = user_has_permission("add", user, model)
        can_view = user_has_permission("view", user, model)
        can_change = user_has_permission("change", user, model)
        can_delete = user_has_permission("delete", user, model)

        # --- Explicit UI override ---
        # Explicit override
        if "show_add" in kwargs:
            requested_show_add = kwargs.pop("show_add")
        else:
            requested_show_add = True  # default intent

        # FINAL UI DECISION (safe)
        show_add = requested_show_add and can_add

        # ---- Admin metadata ----
        model_admin = getattr(
            self,
            "get_model_admin",
            lambda m: type("EmptyAdmin", (), {})()
        )(model)

        search_fields = getattr(model_admin, "search_fields", [])
        list_filter_fields = getattr(model_admin, "list_filter", [])

        filters_fields = []
        filters_choices = {}
        filters_metadata = {}

        for field_name in list_filter_fields:
            try:
                field = model._meta.get_field(field_name)
            except Exception:
                continue

            if isinstance(field, (models.DateField, models.DateTimeField)):
                field_type = "date"
            elif isinstance(field, models.BooleanField):
                field_type = "boolean"
            elif isinstance(field, models.ManyToManyField):
                field_type = "m2m"
            elif isinstance(field, models.ForeignKey):
                field_type = "select"
            else:
                field_type = "select"

            filters_fields.append({
                "name": field_name,
                "type": field_type,
                "verbose_name": field.verbose_name,
            })

            filters_metadata[field_name] = {
                "type": field_type,
                "verbose": field.verbose_name.title(),
            }

            if field_type in ("select", "m2m"):
                if getattr(field, "choices", None):
                    filters_choices[field_name] = list(field.choices)
                elif getattr(field, "related_model", None):
                    filters_choices[field_name] = [
                        (obj.pk, str(obj)) for obj in field.related_model.objects.all()
                    ]
                else:
                    # fallback for fields without related_model
                    filters_choices[field_name] = []


        tab_context = {
            "model": model,
            "search_fields": search_fields,
            "filters_fields": filters_fields,
            "filters_choices": filters_choices,
            "filters_metadata": filters_metadata,

            # permissions
            "can_view": can_view,
            "can_add": can_add,
            "can_change": can_change,
            "can_delete": can_delete,

            # UI
            "show_add": show_add,
        }
        
        # print(f"show_add {model} : ", show_add)
        # print(f"can_add {model} : ", can_add)

        tab_context.update(kwargs)
        return tab_context
