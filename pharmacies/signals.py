from decimal import Decimal
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import InventoryMovement, InventoryMovementItem, Sale, SaleItem, Product, ProductStock
from .models import *


@receiver(post_save, sender=SaleItem)
def sync_stock_movement_for_sale(sender, instance, created, **kwargs):

    sale_id_short = str(instance.sale.id)[:8]

    movement, _ = InventoryMovement.objects.get_or_create(
        reference=f"Sale #{sale_id_short}",
        organization=instance.sale.organization,
        pharmacy=instance.sale.pharmacy,
        defaults={
            "movement_type": "exit",
            "reason": f"Automatique Stock Exit — Sale #{sale_id_short}",
            "pharmacy": instance.sale.pharmacy,
            "created_by": instance.sale.vendor,
        }
    )

    movement_item, movement_created = InventoryMovementItem.objects.get_or_create(
        inventory_movement=movement,
        product_stock=instance.product_stock,
        defaults={
            "quantity": instance.quantity,
        }
    )

    # If item already exists → update it
    if not movement_created:
        movement_item.quantity = instance.quantity
        movement_item.product_stock = instance.product_stock
        movement_item.save()


@receiver(post_delete, sender=SaleItem)
def delete_stock_movement_for_sale(sender, instance, **kwargs):

    sale_id_short = str(instance.sale.id)[:8]

    movement = InventoryMovement.objects.filter(
        reference=f"Sale #{sale_id_short}"
    ).first()

    if movement:
        InventoryMovementItem.objects.filter(
            inventory_movement=movement,
            product_stock=instance.product_stock
        ).delete()


@receiver(post_save, sender=Product)
def create_or_update_product_stock(sender, instance, created, **kwargs):
    """
    Ensure a ProductStock exists for every Product.
    - On create: create a new ProductStock.
    - On update: update stock's price/cost if the product has changed.
    """
    from pharmacies.models import Pharmacy

    pharmacies = Pharmacy.objects.filter(organization=instance.organization)
    for pharmacy in pharmacies:
        stock, stock_created = ProductStock.objects.get_or_create(
            product=instance,
            organization=instance.organization,
            pharmacy=pharmacy,
            defaults={
                "price": instance.price,
                "cost": instance.cost,
            },
        )

        if not stock_created:
            updated_fields = {}
            if stock.price != instance.price:
                updated_fields["price"] = instance.price
            if stock.cost != instance.cost:
                updated_fields["cost"] = instance.cost

            if updated_fields:
                for field, value in updated_fields.items():
                    setattr(stock, field, value)
                stock.save(update_fields=list(updated_fields.keys()))
