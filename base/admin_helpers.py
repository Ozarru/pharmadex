from django.db import models

def get_model_list_display(model):
    fields = []

    for field in model._meta.get_fields():
        if getattr(field, "auto_created", False):
            continue
        if field.name in ("id", "Organization"):
            continue

        fields.append({
            "name": field.name,
            "verbose": field.verbose_name.title(),
            "is_boolean": field.get_internal_type() == "BooleanField",
            "is_date": field.get_internal_type() in ("DateField", "DateTimeField"),
            "is_fk": field.get_internal_type() in ("ForeignKey", "OneToOneField"),
            "is_image": field.get_internal_type() == "ImageField",
        })


    return fields
