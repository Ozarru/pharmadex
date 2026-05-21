from decimal import Decimal
from django.db import transaction
from django.db.models import Sum
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver

from .models import (
    InventoryMovement,
    InventoryMovementItem,
    Sale,
    SaleItem,
    Product,
    ProductStock,
)


# ═══════════════════════════════════════════════════════════════
# STATUS TRACKING — Detect actual status changes
# ═══════════════════════════════════════════════════════════════

_status_cache = {}


@receiver(pre_save, sender=Sale)
def cache_sale_status_before_save(sender, instance, **kwargs):
    """
    Cache the old status before save so post_save can detect changes.
    """
    if instance.pk:
        try:
            old = Sale.objects.get(pk=instance.pk)
            _status_cache[instance.pk] = old.status
        except Sale.DoesNotExist:
            _status_cache[instance.pk] = None
    else:
        _status_cache['new_' + str(id(instance))] = None


# ═══════════════════════════════════════════════════════════════
# SALE SIGNAL — Handles status changes and new completed sales
# ═══════════════════════════════════════════════════════════════

@receiver(post_save, sender=Sale)
def handle_sale_status_change(sender, instance, created, **kwargs):
    """
    Central handler for Sale status changes.
    - Sale created as completed → create movements for all items
    - Status changed TO completed → create movements for all items
    - Status changed FROM completed → delete movements
    """
    old_status = _status_cache.pop(instance.pk, None) or _status_cache.pop('new_' + str(id(instance)), None)

    new_status = instance.status
    completed_statuses = {"completed", "delivered", "paid"}
    was_completed = old_status in completed_statuses
    is_completed = new_status in completed_statuses

    # ── Case 1: Just became completed (create movements) ─────────
    if not was_completed and is_completed:
        _create_movements_for_sale(instance)
        return

    # ── Case 2: No longer completed (delete movements) ──────────
    if was_completed and not is_completed:
        _delete_movements_for_sale(instance)
        return


# ═══════════════════════════════════════════════════════════════
# SALE ITEM SIGNAL — Handles individual item changes
# ═══════════════════════════════════════════════════════════════

@receiver(post_save, sender=SaleItem)
def handle_sale_item_change(sender, instance, created, **kwargs):
    """
    Handles individual SaleItem create/update.
    Only acts if parent Sale is in a completed state.
    """
    sale = instance.sale
    if sale.status not in {"completed", "delivered", "paid"}:
        return

    _sync_single_item(sale, instance)


@receiver(post_delete, sender=SaleItem)
def handle_sale_item_delete(sender, instance, **kwargs):
    """
    Remove the corresponding movement item when a SaleItem is deleted.
    If no items remain, delete the entire movement.
    """
    sale = instance.sale
    sale_id_short = str(sale.id)[:8]

    movement = InventoryMovement.objects.filter(
        reference=f"Sale #{sale_id_short}",
        organization=sale.organization,
        pharmacy=sale.pharmacy,
    ).first()

    if not movement:
        return

    # Delete the specific movement item
    InventoryMovementItem.objects.filter(
        inventory_movement=movement,
        product_stock=instance.product_stock,
    ).delete()

    # Clean up empty movement
    if not movement.items.exists():
        movement.delete()
        return


# ═══════════════════════════════════════════════════════════════
# PRODUCT STOCK SIGNAL — Auto-create stock for new products
# ═══════════════════════════════════════════════════════════════

@receiver(post_save, sender=Product)
def ensure_product_stock_exists(sender, instance, created, **kwargs):
    """
    Ensure a ProductStock exists for every Product in each pharmacy.
    """
    from pharmacies.models import Pharmacy

    pharmacies = Pharmacy.objects.filter(organization=instance.organization)

    for pharmacy in pharmacies:
        stock, stock_created = ProductStock.objects.get_or_create(
            product=instance,
            organization=instance.organization,
            pharmacy=pharmacy,
            defaults={
                "price": instance.price or Decimal("0.00"),
                "cost": instance.cost or Decimal("0.00"),
            },
        )

        if not stock_created:
            updates = {}
            if stock.price != instance.price:
                updates["price"] = instance.price
            if stock.cost != instance.cost:
                updates["cost"] = instance.cost

            if updates:
                for field, value in updates.items():
                    setattr(stock, field, value)
                stock.save(update_fields=list(updates.keys()))


# ═══════════════════════════════════════════════════════════════
# INTERNAL HELPERS
# ═══════════════════════════════════════════════════════════════

def _create_movements_for_sale(sale):
    """
    Create or rebuild all movement items for a completed sale.
    Uses atomic transaction to ensure all-or-nothing.
    """
    sale_id_short = str(sale.id)[:8]

    with transaction.atomic():
        # Get or create the parent movement
        movement, _ = InventoryMovement.objects.get_or_create(
            reference=f"Sale #{sale_id_short}",
            organization=sale.organization,
            pharmacy=sale.pharmacy,
            defaults={
                "movement_type": "exit",
                "reason": f"Stock Exit — Sale #{sale_id_short}",
                "created_by": sale.vendor,
            },
        )

        # Clear existing items (rebuild from scratch to avoid stale data)
        # Use raw delete to skip the model's save() / apply_movement()
        movement.items.all().delete()

        # Create fresh items for all sale lines
        # Use bulk_create and skip apply_movement since we'll call it manually
        movement_items = []
        for item in sale.items.select_related("product_stock").all():
            movement_items.append(InventoryMovementItem(
                inventory_movement=movement,
                product_stock=item.product_stock,
                quantity=item.quantity,
                comment=f"Auto-synced from SaleItem #{item.id}",
            ))

        if movement_items:
            # bulk_create skips the custom save() — no double stock movement
            InventoryMovementItem.objects.bulk_create(movement_items)

            # Now manually apply each movement to stock batches
            for mi in movement_items:
                mi.apply_movement()

        print(f"[SIGNAL] Created movement #{movement.id} with {len(movement_items)} items for Sale #{sale_id_short}")


def _sync_single_item(sale, sale_item):
    """
    Sync a single SaleItem to its movement.
    Used when items are added/edited on an already-completed sale.
    """
    sale_id_short = str(sale.id)[:8]

    movement, _ = InventoryMovement.objects.get_or_create(
        reference=f"Sale #{sale_id_short}",
        organization=sale.organization,
        pharmacy=sale.pharmacy,
        defaults={
            "movement_type": "exit",
            "reason": f"Stock Exit — Sale #{sale_id_short}",
            "created_by": sale.vendor,
        },
    )

    # Update or create the specific item
    item, created = InventoryMovementItem.objects.update_or_create(
        inventory_movement=movement,
        product_stock=sale_item.product_stock,
        defaults={
            "quantity": sale_item.quantity,
            "comment": f"Auto-synced from SaleItem #{sale_item.id}",
        },
    )

    # Apply stock movement only if newly created
    if created:
        item.apply_movement()
    else:
        # For updates, you'd need to reverse the old movement and re-apply
        # This is complex — for now, log a warning
        print(f"[SIGNAL] WARNING: Updated existing movement item for {sale_item.product_stock.product.name} — stock may be out of sync")

    print(f"[SIGNAL] {'Created' if created else 'Updated'} movement item for {sale_item.product_stock.product.name} (qty: {sale_item.quantity})")


def _delete_movements_for_sale(sale):
    """
    Delete all movements when a sale is no longer completed.
    """
    sale_id_short = str(sale.id)[:8]

    deleted, _ = InventoryMovement.objects.filter(
        reference=f"Sale #{sale_id_short}",
        organization=sale.organization,
        pharmacy=sale.pharmacy,
    ).delete()

    print(f"[SIGNAL] Deleted {deleted} movement(s) for Sale #{sale_id_short} (status: {sale.status})")