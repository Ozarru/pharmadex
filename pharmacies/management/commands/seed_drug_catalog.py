import random
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from pharmadex.context import set_tenancy_disabled
from organizations.models import Organization
from pharmacies.models import Pharmacy, Product, ProductBatch, ProductCategory, ProductStock, ProductSubcategory


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--organization", type=str, default=None)
        parser.add_argument("--with-stock", action="store_true", default=False)
        parser.add_argument("--batches-per-product", type=int, default=2)
        parser.add_argument("--seed", type=int, default=42)

    @transaction.atomic
    def handle(self, *args, **options):
        set_tenancy_disabled(True)
        random.seed(options["seed"])

        org = self._resolve_organization(options["organization"])
        pharmacies = list(Pharmacy.objects.filter(organization=org))
        if not pharmacies:
            pharmacies = [self._ensure_demo_pharmacy(org)]

        categories = self._seed_categories()
        subcategories_by_key = self._seed_subcategories(categories)
        products = self._seed_products(org, subcategories_by_key)

        if options["with_stock"]:
            self._seed_stock(
                org=org,
                pharmacies=pharmacies,
                products=products,
                batches_per_product=max(1, int(options["batches_per_product"])),
            )

        self.stdout.write(self.style.SUCCESS("Seed complete."))

    def _resolve_organization(self, organization_id: str | None) -> Organization:
        if organization_id:
            return Organization.objects.get(id=organization_id)

        org = Organization.objects.order_by("created_at").first()
        if org:
            return org

        code = "DEMO"
        if Organization.objects.filter(code=code).exists():
            code = f"D{random.randint(100, 999)}"

        org = Organization.objects.create(
            name="Demo Pharmacy Organization",
            code=code,
            email="demo@example.com",
            phone_number="+0000000000",
            address="Demo Address",
            is_active=True,
        )
        return org

    def _ensure_demo_pharmacy(self, org: Organization) -> Pharmacy:
        pharmacy, _ = Pharmacy.objects.get_or_create(
            organization=org,
            code="MAIN",
            defaults={
                "name": "Main Pharmacy",
                "address": "Demo Address",
                "phone_number": "+0000000000",
                "is_active": True,
            },
        )
        return pharmacy

    def _seed_categories(self) -> dict[str, ProductCategory]:
        data = [
            ("Analgesics & Antipyretics", "Pain relief and fever management."),
            ("Antibiotics", "Bacterial infection treatment."),
            ("Antimalarials", "Malaria prevention and treatment."),
            ("Antihypertensives", "Blood pressure management."),
            ("Antidiabetics", "Blood glucose management."),
            ("Gastrointestinal", "Acid control, antiemetics, and gut health."),
            ("Respiratory & Allergy", "Cough, cold, asthma, and allergy medicines."),
            ("Dermatology", "Skin treatments."),
            ("Vitamins & Supplements", "Nutritional supplements."),
            ("Antiseptics & Disinfectants", "Wound care and disinfection."),
        ]

        out: dict[str, ProductCategory] = {}
        for name, description in data:
            obj, _ = ProductCategory.objects.update_or_create(
                name=name,
                defaults={"description": description, "is_active": True},
            )
            out[name] = obj
        return out

    def _seed_subcategories(
        self, categories: dict[str, ProductCategory]
    ) -> dict[str, ProductSubcategory]:
        data = {
            "Analgesics & Antipyretics": [
                "Paracetamol/Acetaminophen",
                "NSAIDs",
                "Opioid Analgesics",
                "Topical Analgesics",
            ],
            "Antibiotics": [
                "Penicillins",
                "Cephalosporins",
                "Macrolides",
                "Fluoroquinolones",
                "Tetracyclines",
                "Nitroimidazoles",
            ],
            "Antimalarials": [
                "Artemisinin Combinations",
                "Other Antimalarials",
            ],
            "Antihypertensives": [
                "ACE Inhibitors",
                "ARBs",
                "Calcium Channel Blockers",
                "Thiazide Diuretics",
                "Beta Blockers",
            ],
            "Antidiabetics": [
                "Biguanides",
                "Sulfonylureas",
                "Insulins",
            ],
            "Gastrointestinal": [
                "PPIs",
                "H2 Blockers",
                "Antacids",
                "Antiemetics",
                "Antidiarrheals",
                "Laxatives",
                "Rehydration",
            ],
            "Respiratory & Allergy": [
                "Antihistamines",
                "Cough Suppressants",
                "Expectorants",
                "Bronchodilators",
                "Inhaled Corticosteroids",
                "Nasal Sprays",
            ],
            "Dermatology": [
                "Antifungals",
                "Antibacterials",
                "Corticosteroids",
                "Emollients",
            ],
            "Vitamins & Supplements": [
                "Multivitamins",
                "Iron",
                "Folic Acid",
                "Vitamin C",
                "Calcium & Vitamin D",
            ],
            "Antiseptics & Disinfectants": [
                "Skin Antiseptics",
                "Wound Care",
            ],
        }

        out: dict[str, ProductSubcategory] = {}
        for cat_name, subs in data.items():
            cat = categories[cat_name]
            for sub in subs:
                obj, _ = ProductSubcategory.objects.update_or_create(
                    category=cat,
                    name=sub,
                    defaults={"is_active": True},
                )
                out[f"{cat_name}|{sub}"] = obj
        return out

    def _seed_products(
        self, org: Organization, subcategories_by_key: dict[str, ProductSubcategory]
    ) -> list[Product]:
        P = Product

        def sub(cat: str, name: str) -> ProductSubcategory:
            return subcategories_by_key[f"{cat}|{name}"]

        products = [
            dict(
                subcategory=sub("Analgesics & Antipyretics", "Paracetamol/Acetaminophen"),
                name="Paracetamol 500mg Tablets",
                generic_name="Paracetamol",
                strength="500 mg",
                dosage_form=P.DosageForm.TABLET,
                route_of_administration=P.AdministrationRoute.ORAL,
                prescription_type=P.PrescriptionType.OTC,
                is_prescription_required=False,
                is_controlled_substance=False,
                is_expirable=True,
                pack_size="Blister 10",
                price=Decimal("2.00"),
                cost=Decimal("1.20"),
            ),
            dict(
                subcategory=sub("Analgesics & Antipyretics", "NSAIDs"),
                name="Ibuprofen 400mg Tablets",
                generic_name="Ibuprofen",
                strength="400 mg",
                dosage_form=P.DosageForm.TABLET,
                route_of_administration=P.AdministrationRoute.ORAL,
                prescription_type=P.PrescriptionType.OTC,
                is_prescription_required=False,
                is_controlled_substance=False,
                is_expirable=True,
                pack_size="Blister 10",
                price=Decimal("3.00"),
                cost=Decimal("1.80"),
            ),
            dict(
                subcategory=sub("Analgesics & Antipyretics", "NSAIDs"),
                name="Diclofenac 50mg Tablets",
                generic_name="Diclofenac",
                strength="50 mg",
                dosage_form=P.DosageForm.TABLET,
                route_of_administration=P.AdministrationRoute.ORAL,
                prescription_type=P.PrescriptionType.RX,
                is_prescription_required=True,
                is_controlled_substance=False,
                is_expirable=True,
                pack_size="Blister 10",
                price=Decimal("4.00"),
                cost=Decimal("2.40"),
            ),
            dict(
                subcategory=sub("Analgesics & Antipyretics", "Opioid Analgesics"),
                name="Tramadol 50mg Capsules",
                generic_name="Tramadol",
                strength="50 mg",
                dosage_form=P.DosageForm.CAPSULE,
                route_of_administration=P.AdministrationRoute.ORAL,
                prescription_type=P.PrescriptionType.CONTROLLED,
                is_prescription_required=True,
                is_controlled_substance=True,
                is_expirable=True,
                pack_size="Blister 10",
                price=Decimal("8.00"),
                cost=Decimal("5.00"),
            ),
            dict(
                subcategory=sub("Analgesics & Antipyretics", "Topical Analgesics"),
                name="Diclofenac Gel 1% 30g",
                generic_name="Diclofenac",
                strength="1%",
                dosage_form=P.DosageForm.GEL if hasattr(P.DosageForm, "GEL") else P.DosageForm.CREAM,
                route_of_administration=P.AdministrationRoute.TOPICAL,
                prescription_type=P.PrescriptionType.OTC,
                is_prescription_required=False,
                is_controlled_substance=False,
                is_expirable=True,
                pack_size="Tube 30g",
                price=Decimal("6.00"),
                cost=Decimal("3.80"),
            ),
            dict(
                subcategory=sub("Antibiotics", "Penicillins"),
                name="Amoxicillin 500mg Capsules",
                generic_name="Amoxicillin",
                strength="500 mg",
                dosage_form=P.DosageForm.CAPSULE,
                route_of_administration=P.AdministrationRoute.ORAL,
                prescription_type=P.PrescriptionType.RX,
                is_prescription_required=True,
                is_controlled_substance=False,
                is_expirable=True,
                pack_size="Blister 10",
                price=Decimal("7.50"),
                cost=Decimal("4.80"),
            ),
            dict(
                subcategory=sub("Antibiotics", "Penicillins"),
                name="Amoxicillin/Clavulanate 625mg Tablets",
                generic_name="Amoxicillin + Clavulanic Acid",
                strength="500/125 mg",
                dosage_form=P.DosageForm.TABLET,
                route_of_administration=P.AdministrationRoute.ORAL,
                prescription_type=P.PrescriptionType.RX,
                is_prescription_required=True,
                is_controlled_substance=False,
                is_expirable=True,
                pack_size="Blister 10",
                price=Decimal("12.00"),
                cost=Decimal("7.50"),
            ),
            dict(
                subcategory=sub("Antibiotics", "Cephalosporins"),
                name="Cefixime 200mg Tablets",
                generic_name="Cefixime",
                strength="200 mg",
                dosage_form=P.DosageForm.TABLET,
                route_of_administration=P.AdministrationRoute.ORAL,
                prescription_type=P.PrescriptionType.RX,
                is_prescription_required=True,
                is_controlled_substance=False,
                is_expirable=True,
                pack_size="Blister 10",
                price=Decimal("15.00"),
                cost=Decimal("9.50"),
            ),
            dict(
                subcategory=sub("Antibiotics", "Macrolides"),
                name="Azithromycin 500mg Tablets",
                generic_name="Azithromycin",
                strength="500 mg",
                dosage_form=P.DosageForm.TABLET,
                route_of_administration=P.AdministrationRoute.ORAL,
                prescription_type=P.PrescriptionType.RX,
                is_prescription_required=True,
                is_controlled_substance=False,
                is_expirable=True,
                pack_size="Blister 3",
                price=Decimal("10.00"),
                cost=Decimal("6.50"),
            ),
            dict(
                subcategory=sub("Antibiotics", "Fluoroquinolones"),
                name="Ciprofloxacin 500mg Tablets",
                generic_name="Ciprofloxacin",
                strength="500 mg",
                dosage_form=P.DosageForm.TABLET,
                route_of_administration=P.AdministrationRoute.ORAL,
                prescription_type=P.PrescriptionType.RX,
                is_prescription_required=True,
                is_controlled_substance=False,
                is_expirable=True,
                pack_size="Blister 10",
                price=Decimal("9.00"),
                cost=Decimal("5.80"),
            ),
            dict(
                subcategory=sub("Antibiotics", "Tetracyclines"),
                name="Doxycycline 100mg Capsules",
                generic_name="Doxycycline",
                strength="100 mg",
                dosage_form=P.DosageForm.CAPSULE,
                route_of_administration=P.AdministrationRoute.ORAL,
                prescription_type=P.PrescriptionType.RX,
                is_prescription_required=True,
                is_controlled_substance=False,
                is_expirable=True,
                pack_size="Blister 10",
                price=Decimal("6.00"),
                cost=Decimal("3.70"),
            ),
            dict(
                subcategory=sub("Antibiotics", "Nitroimidazoles"),
                name="Metronidazole 400mg Tablets",
                generic_name="Metronidazole",
                strength="400 mg",
                dosage_form=P.DosageForm.TABLET,
                route_of_administration=P.AdministrationRoute.ORAL,
                prescription_type=P.PrescriptionType.RX,
                is_prescription_required=True,
                is_controlled_substance=False,
                is_expirable=True,
                pack_size="Blister 10",
                price=Decimal("4.50"),
                cost=Decimal("2.80"),
            ),
            dict(
                subcategory=sub("Antimalarials", "Artemisinin Combinations"),
                name="Artemether/Lumefantrine 20/120mg Tablets",
                generic_name="Artemether + Lumefantrine",
                strength="20/120 mg",
                dosage_form=P.DosageForm.TABLET,
                route_of_administration=P.AdministrationRoute.ORAL,
                prescription_type=P.PrescriptionType.RX,
                is_prescription_required=True,
                is_controlled_substance=False,
                is_expirable=True,
                pack_size="Blister 24",
                price=Decimal("18.00"),
                cost=Decimal("12.00"),
            ),
            dict(
                subcategory=sub("Antimalarials", "Other Antimalarials"),
                name="Quinine 300mg Tablets",
                generic_name="Quinine",
                strength="300 mg",
                dosage_form=P.DosageForm.TABLET,
                route_of_administration=P.AdministrationRoute.ORAL,
                prescription_type=P.PrescriptionType.RX,
                is_prescription_required=True,
                is_controlled_substance=False,
                is_expirable=True,
                pack_size="Blister 10",
                price=Decimal("9.50"),
                cost=Decimal("6.20"),
            ),
            dict(
                subcategory=sub("Antihypertensives", "Calcium Channel Blockers"),
                name="Amlodipine 5mg Tablets",
                generic_name="Amlodipine",
                strength="5 mg",
                dosage_form=P.DosageForm.TABLET,
                route_of_administration=P.AdministrationRoute.ORAL,
                prescription_type=P.PrescriptionType.RX,
                is_prescription_required=True,
                is_controlled_substance=False,
                is_expirable=True,
                pack_size="Blister 10",
                price=Decimal("5.00"),
                cost=Decimal("3.20"),
            ),
            dict(
                subcategory=sub("Antihypertensives", "ACE Inhibitors"),
                name="Lisinopril 10mg Tablets",
                generic_name="Lisinopril",
                strength="10 mg",
                dosage_form=P.DosageForm.TABLET,
                route_of_administration=P.AdministrationRoute.ORAL,
                prescription_type=P.PrescriptionType.RX,
                is_prescription_required=True,
                is_controlled_substance=False,
                is_expirable=True,
                pack_size="Blister 10",
                price=Decimal("6.00"),
                cost=Decimal("3.90"),
            ),
            dict(
                subcategory=sub("Antihypertensives", "ARBs"),
                name="Losartan 50mg Tablets",
                generic_name="Losartan",
                strength="50 mg",
                dosage_form=P.DosageForm.TABLET,
                route_of_administration=P.AdministrationRoute.ORAL,
                prescription_type=P.PrescriptionType.RX,
                is_prescription_required=True,
                is_controlled_substance=False,
                is_expirable=True,
                pack_size="Blister 10",
                price=Decimal("7.00"),
                cost=Decimal("4.50"),
            ),
            dict(
                subcategory=sub("Antihypertensives", "Thiazide Diuretics"),
                name="Hydrochlorothiazide 25mg Tablets",
                generic_name="Hydrochlorothiazide",
                strength="25 mg",
                dosage_form=P.DosageForm.TABLET,
                route_of_administration=P.AdministrationRoute.ORAL,
                prescription_type=P.PrescriptionType.RX,
                is_prescription_required=True,
                is_controlled_substance=False,
                is_expirable=True,
                pack_size="Blister 10",
                price=Decimal("4.00"),
                cost=Decimal("2.60"),
            ),
            dict(
                subcategory=sub("Antihypertensives", "Beta Blockers"),
                name="Atenolol 50mg Tablets",
                generic_name="Atenolol",
                strength="50 mg",
                dosage_form=P.DosageForm.TABLET,
                route_of_administration=P.AdministrationRoute.ORAL,
                prescription_type=P.PrescriptionType.RX,
                is_prescription_required=True,
                is_controlled_substance=False,
                is_expirable=True,
                pack_size="Blister 10",
                price=Decimal("5.50"),
                cost=Decimal("3.50"),
            ),
            dict(
                subcategory=sub("Antidiabetics", "Biguanides"),
                name="Metformin 500mg Tablets",
                generic_name="Metformin",
                strength="500 mg",
                dosage_form=P.DosageForm.TABLET,
                route_of_administration=P.AdministrationRoute.ORAL,
                prescription_type=P.PrescriptionType.RX,
                is_prescription_required=True,
                is_controlled_substance=False,
                is_expirable=True,
                pack_size="Blister 10",
                price=Decimal("6.50"),
                cost=Decimal("4.10"),
            ),
            dict(
                subcategory=sub("Antidiabetics", "Sulfonylureas"),
                name="Glibenclamide 5mg Tablets",
                generic_name="Glibenclamide",
                strength="5 mg",
                dosage_form=P.DosageForm.TABLET,
                route_of_administration=P.AdministrationRoute.ORAL,
                prescription_type=P.PrescriptionType.RX,
                is_prescription_required=True,
                is_controlled_substance=False,
                is_expirable=True,
                pack_size="Blister 10",
                price=Decimal("4.50"),
                cost=Decimal("2.90"),
            ),
            dict(
                subcategory=sub("Gastrointestinal", "PPIs"),
                name="Omeprazole 20mg Capsules",
                generic_name="Omeprazole",
                strength="20 mg",
                dosage_form=P.DosageForm.CAPSULE,
                route_of_administration=P.AdministrationRoute.ORAL,
                prescription_type=P.PrescriptionType.OTC,
                is_prescription_required=False,
                is_controlled_substance=False,
                is_expirable=True,
                pack_size="Blister 14",
                price=Decimal("6.00"),
                cost=Decimal("3.70"),
            ),
            dict(
                subcategory=sub("Gastrointestinal", "Antiemetics"),
                name="Ondansetron 4mg Tablets",
                generic_name="Ondansetron",
                strength="4 mg",
                dosage_form=P.DosageForm.TABLET,
                route_of_administration=P.AdministrationRoute.ORAL,
                prescription_type=P.PrescriptionType.RX,
                is_prescription_required=True,
                is_controlled_substance=False,
                is_expirable=True,
                pack_size="Blister 10",
                price=Decimal("9.00"),
                cost=Decimal("5.80"),
            ),
            dict(
                subcategory=sub("Gastrointestinal", "Antidiarrheals"),
                name="Loperamide 2mg Capsules",
                generic_name="Loperamide",
                strength="2 mg",
                dosage_form=P.DosageForm.CAPSULE,
                route_of_administration=P.AdministrationRoute.ORAL,
                prescription_type=P.PrescriptionType.OTC,
                is_prescription_required=False,
                is_controlled_substance=False,
                is_expirable=True,
                pack_size="Blister 10",
                price=Decimal("4.00"),
                cost=Decimal("2.50"),
            ),
            dict(
                subcategory=sub("Gastrointestinal", "Rehydration"),
                name="ORS Sachets",
                generic_name="Oral Rehydration Salts",
                strength=None,
                dosage_form=P.DosageForm.POWDER,
                route_of_administration=P.AdministrationRoute.ORAL,
                prescription_type=P.PrescriptionType.OTC,
                is_prescription_required=False,
                is_controlled_substance=False,
                is_expirable=True,
                pack_size="Sachet",
                price=Decimal("1.50"),
                cost=Decimal("0.80"),
            ),
            dict(
                subcategory=sub("Respiratory & Allergy", "Antihistamines"),
                name="Cetirizine 10mg Tablets",
                generic_name="Cetirizine",
                strength="10 mg",
                dosage_form=P.DosageForm.TABLET,
                route_of_administration=P.AdministrationRoute.ORAL,
                prescription_type=P.PrescriptionType.OTC,
                is_prescription_required=False,
                is_controlled_substance=False,
                is_expirable=True,
                pack_size="Blister 10",
                price=Decimal("3.00"),
                cost=Decimal("1.80"),
            ),
            dict(
                subcategory=sub("Respiratory & Allergy", "Bronchodilators"),
                name="Salbutamol Inhaler 100mcg",
                generic_name="Salbutamol",
                strength="100 mcg",
                dosage_form=P.DosageForm.INHALER,
                route_of_administration=P.AdministrationRoute.INHALATION,
                prescription_type=P.PrescriptionType.RX,
                is_prescription_required=True,
                is_controlled_substance=False,
                is_expirable=True,
                pack_size="200 doses",
                price=Decimal("9.00"),
                cost=Decimal("6.00"),
            ),
            dict(
                subcategory=sub("Dermatology", "Antifungals"),
                name="Clotrimazole Cream 1% 20g",
                generic_name="Clotrimazole",
                strength="1%",
                dosage_form=P.DosageForm.CREAM,
                route_of_administration=P.AdministrationRoute.TOPICAL,
                prescription_type=P.PrescriptionType.OTC,
                is_prescription_required=False,
                is_controlled_substance=False,
                is_expirable=True,
                pack_size="Tube 20g",
                price=Decimal("4.50"),
                cost=Decimal("2.80"),
            ),
            dict(
                subcategory=sub("Vitamins & Supplements", "Iron"),
                name="Ferrous Sulfate 200mg Tablets",
                generic_name="Ferrous Sulfate",
                strength="200 mg",
                dosage_form=P.DosageForm.TABLET,
                route_of_administration=P.AdministrationRoute.ORAL,
                prescription_type=P.PrescriptionType.OTC,
                is_prescription_required=False,
                is_controlled_substance=False,
                is_expirable=True,
                pack_size="Blister 10",
                price=Decimal("3.50"),
                cost=Decimal("2.10"),
            ),
        ]

        out: list[Product] = []
        for data in products:
            subcategory = data.pop("subcategory")
            name = data.pop("name")
            obj, _ = Product.objects.update_or_create(
                organization=org,
                subcategory=subcategory,
                name=name,
                defaults=data,
            )
            out.append(obj)

        self.stdout.write(self.style.SUCCESS(f"Products: {len(out)}"))
        return out

    def _seed_stock(
        self,
        *,
        org: Organization,
        pharmacies: list[Pharmacy],
        products: list[Product],
        batches_per_product: int,
    ):
        today = timezone.now().date()
        created_stocks = 0
        created_batches = 0

        for pharmacy in pharmacies:
            for product in products:
                stock, created = ProductStock.objects.get_or_create(
                    organization=org,
                    pharmacy=pharmacy,
                    product=product,
                    defaults={
                        "price": product.price,
                        "cost": product.cost,
                    },
                )
                if created:
                    created_stocks += 1

                existing_batches = ProductBatch.objects.filter(product_stock=stock).count()
                to_create = batches_per_product - existing_batches
                if to_create <= 0:
                    continue

                attempts = 0
                created_for_stock = 0
                while created_for_stock < to_create and attempts < to_create * 10:
                    attempts += 1
                    if product.is_expirable:
                        expiry = today + timezone.timedelta(days=random.randint(60, 720))
                    else:
                        expiry = today + timezone.timedelta(days=3650)

                    batch_number = f"B{today.year}{random.randint(10000, 99999)}"
                    if ProductBatch.objects.filter(product_stock=stock, batch_number=batch_number).exists():
                        continue

                    ProductBatch.objects.create(
                        organization=org,
                        pharmacy=pharmacy,
                        product_stock=stock,
                        batch_number=batch_number,
                        expiry_date=expiry,
                        manufacturing_date=today - timezone.timedelta(days=random.randint(30, 365)),
                        quantity=random.randint(10, 200),
                        is_active=True,
                    )
                    created_batches += 1
                    created_for_stock += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Stock created: {created_stocks}, batches created: {created_batches}"
            )
        )

