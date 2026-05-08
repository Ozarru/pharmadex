# from finances.models import Currency
from collections.abc import Iterable
import json
from django import template

register = template.Library()


@register.filter
def jsonify(value):
    return json.dumps(value)


@register.filter
def get_attr(obj, attr_name):
    try:
        for attr in attr_name.split("."):
            obj = getattr(obj, attr)
            if callable(obj):
                obj = obj()
        return obj
    except Exception:
        return ""

# custom_tags.py

@register.filter
def get_date_param(get_dict, key):
    """Usage: request.GET|get_date_param:'created_at_start_date'"""
    return get_dict.get(key, "")

@register.simple_tag
def get_param(get_dict, field_name, suffix):
    """Usage: {% get_param request.GET field.name '_start_date' %}"""
    return get_dict.get(f"{field_name}{suffix}", "")

@register.filter
def has_attr(obj, attr_name):
    return hasattr(obj, attr_name)


@register.filter
def call_method(obj, method_name):
    method = getattr(obj, method_name)
    return method() if callable(method) else method


@register.filter
def get_item(dictionary, key):
    if dictionary and key in dictionary:
        return dictionary.get(key)
    return None


@register.filter
def is_iterable(value):
    """
    Returns True if the value is an iterable (list, tuple, queryset) but NOT a string.
    """
    return isinstance(value, Iterable) and not isinstance(value, str)


@register.filter
def getlist(querydict, key):
    """Return the list of values for a GET parameter."""
    return querydict.getlist(key)


class SetNode(template.Node):
    def __init__(self, var_name, var_value):
        self.var_name = var_name
        self.var_value = var_value

    def render(self, context):
        try:
            value = self.var_value.resolve(context)
        except:
            value = self.var_value
        context[self.var_name] = value
        return ''


@register.tag
def set(parser, token):
    """
    Usage: {% set variable = value %}
    Example: {% set container_id = tab.model_container %}
    """
    parts = token.contents.split()
    if len(parts) < 4 or parts[2] != '=':
        raise template.TemplateSyntaxError(
            "'set' tag must be in the format: {% set variable = value %}"
        )
    var_name = parts[1]
    var_value = parser.compile_filter(' '.join(parts[3:]))
    return SetNode(var_name, var_value)



@register.filter
def get_related_field_value(obj, field_name):
    try:
        # Attempt to get the attribute, handle double underscore relations
        field_parts = field_name.split('__')
        value = obj
        for part in field_parts:
            value = getattr(value, part)
        return value
    except AttributeError:
        return None

