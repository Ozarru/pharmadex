from django.utils import timezone
from django.utils.dateparse import parse_date
from datetime import datetime
from decimal import Decimal

from organizations.models import Customer
from .models import *
from utils import get_clean_csv_reader


def import_products_from_csv(
    file,
    organization=None,
    request=None,
    initial_stock_quantity=0,
    **kwargs
):
    created_count = 0

    for row in get_clean_csv_reader(file):

        category_name = (row.get("category_name") or "").strip()
        subcategory_name = (row.get("subcategory_name") or "").strip()
        product_name = (row.get("product_name") or "").strip()

        if not category_name or not subcategory_name or not product_name:
            continue

        # CATEGORY
        category, _ = ProductCategory.objects.get_or_create(
            name=category_name,
            defaults={"is_active": True}
        )

        # SUBCATEGORY
        subcategory, _ = ProductSubcategory.objects.get_or_create(
            category=category,
            name=subcategory_name,
            defaults={"is_active": True}
        )

        # ACTIVE FLAG
        is_active_raw = (row.get("is_active") or "O").strip().upper()
        is_active = is_active_raw in ["O", "YES", "TRUE", "1"]

        # PRICE
        try:
            price = Decimal((row.get("price") or "0").strip())
        except Exception:
            price = Decimal("0.00")

        # PRODUCT
        product, created = Product.objects.get_or_create(
            organization=organization,
            subcategory=subcategory,
            name=product_name,
            defaults={
                "price": price,
                "is_active": is_active
            }
        )

        if not created:
            product.price = price
            product.is_active = is_active
            product.save(update_fields=["price", "is_active", "updated_at"])

        # OPTIONAL STOCK
        # ProductStock.objects.update_or_create(
        #     organization=organization,
        #     product=product,
        #     defaults={
        #         "price": price,
        #         "quantity": initial_stock_quantity
        #     }
        # )

        if created:
            created_count += 1

    return created_count


def create_inventory_movements_from_csv(
    file,
    organization=None,
    pharmacy=None,
    movement_type="entry",
    reason="Inventory Movement",
    created_by=None,
    request=None,
    **kwargs
):
    created_count = 0
    inventory_movement = None

    # ✅ fallback to request.user
    if not created_by and request:
        created_by = request.user

    if not pharmacy and request:
        pharmacy = getattr(request, "current_pharmacy", None)

    if not organization and pharmacy:
        organization = pharmacy.organization

    for row in get_clean_csv_reader(file):

        product_name = (row.get("product_name") or "").strip()
        if not product_name:
            continue

        product = Product.objects.filter(
            name=product_name,
            organization=organization
        ).first()

        if not product:
            continue

        product_stock, _ = ProductStock.objects.get_or_create(
            product=product,
            organization=organization,
            pharmacy=pharmacy,
        )

        try:
            quantity = int(row.get("quantity") or 0)
        except Exception:
            continue

        if quantity <= 0:
            continue

        if movement_type == "entry":
            batch_number = (row.get("batch_number") or "").strip()
            expiry_date = row.get("expiry_date")
            if not batch_number or not expiry_date:
                continue

            expiry_date = parse_date(str(expiry_date))
            if not expiry_date:
                continue

            batch, _ = ProductBatch.objects.get_or_create(
                product_stock=product_stock,
                batch_number=batch_number,
                defaults={
                    "organization": organization,
                    "pharmacy": pharmacy,
                    "expiry_date": expiry_date,
                    "quantity": 0,
                },
            )
            batch.quantity += quantity
            batch.save(update_fields=["quantity"])
        else:
            if not inventory_movement:
                inventory_movement = InventoryMovement.objects.create(
                    organization=organization,
                    pharmacy=pharmacy,
                    movement_type=movement_type,
                    reason=reason,
                    created_by=created_by,
                )

            InventoryMovementItem.objects.create(
                inventory_movement=inventory_movement,
                product_stock=product_stock,
                quantity=quantity,
                comment=row.get("comment", ""),
            )

        created_count += 1

    return created_count


def import_sales_from_csv(
    file,
    organization=None,
    request=None,
    pharmacy=None,
    notes_default="",
    **kwargs
):
    created_count = 0

    if not request:
        raise ValueError("Request is required to assign vendor")

    for row in get_clean_csv_reader(file):

        customer = None
        customer_email = (row.get("customer_email") or row.get("customer") or "").strip()
        customer_phone = (row.get("customer_phone") or "").strip()
        if customer_email:
            customer = Customer.objects.filter(
                organization=organization,
                email__iexact=customer_email,
            ).first()
        elif customer_phone:
            customer = Customer.objects.filter(
                organization=organization,
                phone_number=customer_phone,
            ).first()

        # DATE
        try:
            created_at = datetime.strptime(row.get("created_at"), "%d/%m/%Y")
            created_at = timezone.make_aware(created_at)
        except Exception:
            continue

        # AMOUNT
        try:
            total_amount = Decimal(row.get("total_amount") or "0.00")
        except Exception:
            total_amount = Decimal("0.00")

        # SALE
        sale = Sale.objects.create(
            created_at=created_at,
            organization=organization,
            pharmacy=pharmacy.pharmacy,
            customer=customer,
            vendor=request.user,   # ✅ always correct now
            pharmacy=pharmacy,
            total_amount=total_amount,
            notes=row.get("notes") or notes_default
        )

        # PRODUCT
        product_name = row.get("items")
        if not product_name:
            sale.delete()
            continue

        product_stock = ProductStock.objects.filter(
            product__name=product_name,
            organization=organization,
            pharmacy=pharmacy.pharmacy,
        ).first()

        if not product_stock:
            sale.delete()
            continue

        # QUANTITY FIX ✅
        try:
            quantity = int(row.get("quantity") or 1)
        except Exception:
            quantity = 1

        SaleItem.objects.create(
            sale=sale,
            product_stock=product_stock,
            quantity=quantity,
            unit_price=product_stock.effective_price,
            total_price=product_stock.effective_price * quantity
        )

        sale.recalculate_total()
        created_count += 1

    return created_count
