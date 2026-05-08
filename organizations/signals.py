from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import *
from pharmacies.models import Pharmacy

from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=Organization)
def ensure_pharmacy_and_pharmacy_exists(sender, instance, created, **kwargs):
    """
    Ensure at least one Pharmacy and Pharmacy exist per Organization.
    """

    # 1. Ensure Pharmacy exists
    Pharmacy.objects.get_or_create(
        organization=instance,
        defaults={
            "name": f"{instance.name} Pharmacy",
            "code": "HQ",  # must be unique per org
            "address": instance.address or "",
        }
    )
