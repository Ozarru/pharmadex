from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import *
from pharmacies.models import Pharmacy
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=Organization)
def ensure_pharmacy_exists(sender, instance, created, **kwargs):
    """
    Ensure an organization has at least one pharmacy.
    """

    if not Pharmacy.objects.filter(organization=instance).exists():
        Pharmacy.objects.create(
            organization=instance,
            name=f"{instance.name} Pharmacy",
            code="HQ",
            address=instance.address or "",
        )
