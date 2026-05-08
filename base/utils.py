import time
from django.db import connection, OperationalError, InterfaceError
from django.core.cache import cache
from django.contrib import admin
from functools import lru_cache
from django.utils import timezone
from django.apps import apps
from importlib import import_module
from django.utils.translation import gettext_lazy as _


def _lazy_call(func_path: str):
    module_path, func_name = func_path.rsplit(".", 1)

    def _wrapper(*args, **kwargs):
        mod = import_module(module_path)
        return getattr(mod, func_name)(*args, **kwargs)

    return _wrapper


def _get_model(label: str):
    try:
        return apps.get_model(label)
    except Exception:
        return None


MONTH_CHOICES = [
    (1, _("January")),
    (2, _("February")),
    (3, _("March")),
    (4, _("April")),
    (5, _("May")),
    (6, _("June")),
    (7, _("July")),
    (8, _("August")),
    (9, _("September")),
    (10, _("October")),
    (11, _("November")),
    (12, _("December")),
]

CURRENT_YEAR = timezone.now().year

YEAR_CHOICES = [
    (str(y), str(y))
    for y in range(2000, CURRENT_YEAR + 6)
]

GENDER_CHOICES = (
    ('male', _('M')),
    ('female', _('F')),
)

now = timezone.now()
current_date = now.date()
current_week = now.isocalendar()[1]
current_year = now.year
current_month = now.replace(
    day=1, hour=0, minute=0, second=0, microsecond=0
)
start_of_week = now - timezone.timedelta(days=now.weekday())
start_of_week = start_of_week.replace(
    hour=0, minute=0, second=0, microsecond=0
)


# ------------------ DB RETRIES DECORATOR ------------------
def db_retry(max_retries=3, delay=1):
    def decorator(func):
        def wrapper(*args, **kwargs):
            for i in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (OperationalError, InterfaceError):
                    connection.close()
                    if i == max_retries - 1:
                        raise
                    time.sleep(delay)
        return wrapper
    return decorator


# ------------------ CACHING UTILS ------------------
def model_fields(model):
    key = f"model_fields:{model._meta.label_lower}"
    data = cache.get(key)

    if data is not None:
        return data

    data = {
        f.name: {
            "name": f.name,
            "type": f.get_internal_type(),
            "many_to_one": f.many_to_one,
            "many_to_many": f.many_to_many,
            "auto_created": f.auto_created,
            "related_model": f.related_model.__name__ if getattr(f, "related_model", None) else None,
        }
        for f in model._meta.get_fields()
    }

    cache.set(key, data, 3600)
    return data


def model_field_names(model):
    key = f"model_field_names:{model._meta.label_lower}"
    data = cache.get(key)

    if data is not None:
        return data

    data = set(model_fields(model).keys())
    cache.set(key, data, 3600)
    return data


# ------------------ ADMIN ------------------
def model_admin(model):
    key = f"model_admin:{model._meta.label_lower}"
    data = cache.get(key)

    if data is not None:
        return data

    from django.contrib import admin
    data = admin.site._registry.get(model)

    cache.set(key, data, 3600)
    return data


def admin_search_fields(model):
    key = f"admin_search_fields:{model._meta.label_lower}"
    data = cache.get(key)

    if data is not None:
        return data

    data = getattr(model_admin(model), "search_fields", [])
    cache.set(key, data, 3600)
    return data


def admin_list_filter(model):
    key = f"admin_list_filter:{model._meta.label_lower}"
    data = cache.get(key)

    if data is not None:
        return data

    data = getattr(model_admin(model), "list_filter", [])
    cache.set(key, data, 3600)
    return data


def admin_list_display(model):
    key = f"admin_list_display:{model._meta.label_lower}"
    data = cache.get(key)

    if data is not None:
        return data

    admin_obj = model_admin(model)

    data = (
        getattr(admin_obj, "list_display", []),
        set(getattr(admin_obj, "list_display_image_fields", [])),
    )

    cache.set(key, data, 3600)
    return data


# ------------------ ORM OPTIMIZATION ------------------
@lru_cache(maxsize=None)
def select_related_fields(model):
    return [
        f.name for f in model._meta.get_fields()
        if f.many_to_one and not f.auto_created
    ]


@lru_cache(maxsize=None)
def prefetch_related_fields(model):
    return [
        f.name for f in model._meta.get_fields()
        if f.many_to_many
    ]


# ------------------ FK CHOICES ------------------
def fk_choices(model, field_name, ttl=3600):
    key = f"fk_choices:{model.__name__}:{field_name}"
    data = cache.get(key)

    if data is None:
        field = model_fields(model)[field_name]
        qs = field.related_model.objects.all()
        data = [(obj.pk, str(obj)) for obj in qs]
        cache.set(key, data, ttl)

    return data


# ------------------ Growth calculator ------------------
def get_growth(model, date_field, qs, current_range, previous_range):
    # current_range and previous_range are tuples like (start,) or (start, end)
    current_start = current_range[0]
    previous_start, previous_end = previous_range

    current = qs.filter(
        **{f"{date_field}__gte": current_start}).distinct().count()
    previous = qs.filter(**{
        f"{date_field}__gte": previous_start,
        f"{date_field}__lt": previous_end
    }).distinct().count()

    growth = ((current - previous) / previous * 100) if previous else 0
    return current, previous, growth
