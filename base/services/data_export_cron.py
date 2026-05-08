from pathlib import Path
from django.conf import settings


def export_all_to_zip(output_dir=None):
    output_base = Path(output_dir) if output_dir else Path(settings.BASE_DIR) / "exports"
    output_base.mkdir(parents=True, exist_ok=True)
    return str(output_base)


def export_finances_as_zip(*args, **kwargs):
    return export_all_to_zip()


def export_and_email_data():
    return export_all_to_zip()

