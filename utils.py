from datetime import timedelta
from django.utils import timezone
from django.core.files.base import ContentFile
from PIL import Image
from io import BytesIO
from django.http import JsonResponse
from django.shortcuts import redirect
from django.http import HttpResponseForbidden
from django.db import IntegrityError
import pandas as pd
from django.core.paginator import Paginator
from hashids import Hashids
from django.conf import settings
from django.core.exceptions import ValidationError
from decimal import Decimal, InvalidOperation
import locale

def to_bool(value):
    return str(value).lower() in ["true", "1", "yes", "on"]

def days_before_expirartion(days=3):
    return timezone.now() + timedelta(days)


import csv
from io import TextIOWrapper


def get_clean_csv_reader(file):
    """
    Returns a DictReader with:
    - UTF-8 BOM support
    - Normalized headers (strip + lowercase)
    - Cleaned row values (strip + no None)
    """
    wrapper = TextIOWrapper(file, encoding="utf-8-sig")
    reader = csv.DictReader(wrapper)

    # Normalize headers
    reader.fieldnames = [
        header.strip().lower()
        for header in reader.fieldnames
    ]

    for row in reader:
        yield {
            key.strip().lower(): (value or "").strip()
            for key, value in row.items()
        }

# ---------------------------------------------- Coma to Dot decimal ----------------------------------------------
def format_currency(value, symbol='$', language='en', symbol_position='prefix'):
    """
    Format a numeric value as a currency string.

    Args:
        value (float | int): The numeric value to format.
        symbol (str): The currency symbol (e.g. '$', '€', '₹').
        language (str): Language or locale hint (e.g. 'en', 'fr', 'de').
        symbol_position (str): Either 'prefix' or 'suffix'.

    Returns:
        str: Formatted currency string (e.g. '$1,234.56' or '1.234,56 €').
    """

    # Fallback for invalid input
    try:
        value = float(value)
    except (TypeError, ValueError):
        return f"{symbol} 0.00"

    # Try setting locale if available (optional safety)
    try:
        locale.setlocale(locale.LC_ALL, f"{language}_{language.upper()}.UTF-8")
    except locale.Error:
        locale.setlocale(locale.LC_ALL, '')  # System default

    formatted_value = f"{value:,.2f}"

    # Use typical conventions for certain languages automatically
    if language.lower() in ('fr', 'de', 'es', 'it'):
        formatted_value = formatted_value.replace(
            ',', 'X').replace('.', ',').replace('X', '.')

    if symbol_position == 'suffix' or language.lower() not in ('en', 'en_us'):
        return f"{formatted_value} {symbol}"
    else:
        return f"{symbol}{formatted_value}"


def cfa_format(amount):
    """
    Formats a number as CFA currency with thousands separators and 'F CFA' suffix.

    Example:
        cfa_format(1500000) -> "1.500.000 F CFA"
    """
    try:
        # Ensure it's an integer/float
        amount = int(round(amount))
        # Add thousands separator using dot
        formatted = f"{amount:,}".replace(",", ".")
        return f"{formatted} F CFA"
    except (TypeError, ValueError):
        return f"0 F CFA"
    
# ---------------------------------------------- Coma to Dot decimal ----------------------------------------------
def safe_decimal(value):
    if value is None:
        return Decimal("0.00")

    # Replace comma with dot before converting
    value = value.replace(',', '.')

    try:
        return Decimal(value)
    except (InvalidOperation, ValueError):
        return Decimal("0.00")


# ---------------------------------------------- Custom object ID hasher/unhasher ----------------------------------------------
hashids = Hashids(settings.HASHIDS_SALT, min_length=8)


def h_encode(id):
    return hashids.encode(id)


def h_decode(h):
    z = hashids.decode(h)
    if z:
        return z[0]


class HashIdConverter:
    regex = '[a-zA-Z0-9]{8,}'

    def to_python(self, value):
        return h_decode(value)

    def to_url(self, value):
        return h_encode(value)


# ---------------------------------------------- Custom paginator ------------------------------
def paginate_objects(req, obj_view, obj_count=24):
    p = Paginator(obj_view, obj_count)
    page = req.GET.get('page')
    objects = p.gets_page(page)
    return objects


# ---------------------------------------------- Custom files format and size validators ----------------------------------------------
def validate_single_image(image, max_size_mb=2):
    """Vérifie et valide le type et la taille de l'image."""
    if image and not image.name.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
        raise ValidationError(
            "Le fichier doit être une image au format PNG, JPG, JPEG ou GIF.")

    """Vérifie et valide la taille de l'image (exemple : max 2MB)"""
    max_size_bytes = max_size_mb * 1024 * 1024  # Convertir Mo en octets
    if image.size > max_size_bytes:
        raise ValidationError(
            f"La taille de l'image ne doit pas dépasser {max_size_mb} Mo.")


def validate_multiple_images(images, max_size_mb=2, max_images=10):
    """Valide une liste d'images"""
    if len(images) > max_images:
        raise ValidationError(
            f"Vous ne pouvez pas télécharger plus de {max_images} images.")

    for image in images:
        if not image.name.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
            raise ValidationError(
                "Chaque fichier doit être une image au format PNG, JPG, JPEG ou GIF.")

    max_size_bytes = max_size_mb * 1024 * 1024
    if image.size > max_size_bytes:
        raise ValidationError(
            f"Chaque image ne doit pas dépasser {max_size_mb} Mo.")


def validate_multiple_videos(videos, max_size_mb=10, max_videos=5):
    """Valide une liste de vidéos"""
    if len(videos) > max_videos:
        raise ValidationError(
            f"Vous ne pouvez pas télécharger plus de {max_videos} vidéos.")

    for video in videos:
        # Vérifie le type de fichier de la vidéo
        if not video.name.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')):
            raise ValidationError(
                "Chaque fichier doit être une vidéo au format MP4, AVI, MOV ou MKV.")

        # Vérifie la taille de la vidéo
        max_size_bytes = max_size_mb * 1024 * 1024  # Convertir Mo en octets
        if video.size > max_size_bytes:
            raise ValidationError(
                f"Chaque vidéo ne doit pas dépasser {max_size_mb} Mo.")


# Liste des formats de fichiers acceptés
allowed_extensions = [
    '.png', '.jpg', '.jpeg',
    '.pdf', '.doc', '.docx', '.xls',
    '.xlsx', '.csv', '.odt', '.ods',
]


def validate_single_document(file, max_size_mb=50, formats=allowed_extensions):
    """Valide un document pour s'assurer qu'il est dans un format accepté et ne dépasse pas la taille maximale."""

    # Vérifie l'extension du fichier
    if not file.name.lower().endswith(tuple(formats)):
        raise ValidationError(
            f"Le fichier doit être dans un des formats suivant : {formats}"
        )

    # Vérifie la taille du fichier
    max_size_bytes = max_size_mb * 1024 * 1024  # Conversion en octets
    if file.size > max_size_bytes:
        raise ValidationError(
            f"La taille du fichier ne doit pas dépasser {max_size_mb} Mo."
        )


def validate_multiple_documents(documents, max_size_mb=50, max_documents=10, formats=allowed_extensions):
    """Valide une liste de documents"""

    if len(documents) > max_documents:
        raise ValidationError(
            f"Vous ne pouvez pas télécharger plus de {max_documents} documents.")

    for document in documents:
        # Vérifie le type de fichier du document
        if not document.name.lower().endswith(formats):
            raise ValidationError(
                f"Chaque fichier doit être un dans un des formats suivant : {formats}"
            )

        # Vérifie la taille du document
        max_size_bytes = max_size_mb * 1024 * 1024  # Convertir Mo en octets
        if document.size > max_size_bytes:
            raise ValidationError(
                f"Chaque document ne doit pas dépasser {max_size_mb} Mo.")


# ---------------------------------------------- Excel file processor ----------------------------------------------
def process_excel_file(file, model_class, fields_mapping, foreign_keys=None):
    """
    Process the uploaded Excel file and create model instances dynamically, handling foreign key relationships.

    :param file: Uploaded file object (from request.FILES)
    :param model_class: The model class to create objects for (e.g., Category, Product)
    :param fields_mapping: A dictionary to map the model fields to Excel columns
    :param foreign_keys: A dictionary to indicate which fields are foreign keys and their related model class
    :return: List of messages indicating the result of the operation
    """
    try:
        # Read the uploaded Excel file
        excel_data = pd.ExcelFile(file)
        messages = []

        # Loop through each sheet in the Excel file
        for sheet_name in excel_data.sheet_names:
            sheet = excel_data.parse(sheet_name)

            # Ensure column names are in lowercase
            sheet.columns = [col.lower() for col in sheet.columns]

            # Loop through rows and process data
            for index, row in sheet.iterrows():
                # Extract data based on the fields_mapping
                data = {}
                for model_field, excel_column in fields_mapping.items():
                    # Make the excel column name lowercase
                    excel_column_lower = excel_column.lower()

                    if excel_column_lower in sheet.columns:
                        value = row.get(excel_column_lower)

                        # If the field is a foreign key, handle it accordingly
                        if foreign_keys and model_field in foreign_keys:
                            related_model_class = foreign_keys[model_field]
                            related_object = None

                            if pd.notna(value):
                                # Try to find the related object by name or another unique field
                                related_object = related_model_class.objects.filter(
                                    name=value).first()
                                if not related_object:
                                    # If it doesn't exist, create a new related object
                                    related_object = related_model_class.objects.create(
                                        name=value)

                            if related_object:
                                data[model_field] = related_object
                        else:
                            # Regular field processing
                            if pd.notna(value):
                                data[model_field] = str(value).strip()

                if data:
                    try:
                        # Create the model instance
                        obj = model_class.objects.create(**data)

                        # Append success message
                        messages.append(
                            f"Created {model_class.__name__}: {data.get('name', 'No Name')}")
                    except IntegrityError:
                        messages.append(
                            f"Error with {model_class.__name__} data: {data}")
                    except Exception as e:
                        messages.append(
                            f"Unexpected error creating {model_class.__name__}: {str(e)}")

        return messages

    except Exception as e:
        return [f"Error processing file: {str(e)}"]


# ---------------------------------------------- Image optimizer ----------------------------------------------
def optimize_image(file, max_size=(1280, 720), format='JPEG', quality=70):
    """
    Resize, compress, and convert an image for optimal web performance.

    :param file: The original image file (InMemoryUploadedFile or File)
    :param max_size: (width, height) tuple to resize image to fit
    :param format: Output format ('JPEG', 'WEBP', etc.)
    :param quality: Compression quality (0–100)
    :return: Optimized Django ContentFile object
    """
    try:
        image = Image.open(file)
        image = image.convert('RGB')  # Strip alpha channels

        # Resize in-place (updated for Pillow 10+)
        image.thumbnail(max_size, Image.Resampling.LANCZOS)

        # Save to BytesIO
        buffer = BytesIO()
        image.save(buffer, format=format, quality=quality)
        buffer.seek(0)

        # Create Django File object
        optimized_file = ContentFile(buffer.read())
        return optimized_file
    except Exception as e:
        print("Image optimization failed:", e)
        return file  # fallback to original


# ---------------------------------------------- Growth Caculators ----------------------------------------------
def calculate_linear_growth(current_period: int, previous_period: int) -> int:
    """
    Calculates percentage growth between current_period and previous_period values.
    Avoids division by zero by returning:
    - 100% if current_period > 0 and previous_period == 0
    - 0% if both are 0
    """
    if previous_period == 0:
        return 100 if current_period > 0 else 0
    return round(((current_period - previous_period) / previous_period) * 100)


def calculate_multilateral_growth(current_period_count: int, previous_period_total: int, periods: int = 1) -> int:
    """
    Supports multi-period growth comparison.
    If periods > 1, assumes `previous_period_total` is already a combined count (not average).
    """
    previous_periods_avg = previous_period_total / \
        periods if periods > 1 else previous_period_total
    return calculate_linear_growth(current_period_count, previous_periods_avg)
