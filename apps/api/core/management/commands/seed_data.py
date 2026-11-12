"""
Seed command: python manage.py seed_data
Creates demo data for development: 2 owners, 3 properties, 10 units, 5 tenants, 5 active leases.
"""
import random
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

User = get_user_model()


class Command(BaseCommand):
    help = "Seed the database with demo data"

    def add_arguments(self, parser):
        parser.add_argument("--flush", action="store_true", help="Flush all data before seeding")

    def handle(self, *args, **options):
        if options["flush"]:
            self.stdout.write("Flushing data...")
            from billing.models import Allocation, Payment, Invoice
            from deposits.models import DepositTransaction
            from tenants.models import Lease, Tenant
            from portfolio.models import Unit, Property, Owner
            from audit.models import AuditLog
            from notifications.models import Notification

            Allocation.objects.all().delete()
            DepositTransaction.objects.all().delete()
            Payment.objects.all().delete()
            Invoice.objects.all().delete()
            Notification.objects.all().delete()
            AuditLog.objects.all().delete()
            Lease.objects.all().delete()
            Tenant.objects.all().delete()
            Unit.objects.all().delete()
            Property.objects.all().delete()
            Owner.objects.all().delete()

        with transaction.atomic():
            self._seed()

        self.stdout.write(self.style.SUCCESS("Seed data created successfully."))

    def _seed(self):
        from portfolio.models import Owner, Property, Unit
        from tenants.models import Tenant, Lease, LeaseStatus, Currency, BillingCycleAnchor
        from billing.services.invoice_service import generate_invoice, generate_deposit_invoice
        from dateutil.relativedelta import relativedelta

        # ------------------------------------------------------------------ #
        # Users                                                                 #
        # ------------------------------------------------------------------ #
        admin, created = User.objects.get_or_create(
            username="admin",
            defaults={
                "email": "admin@demo.local",
                "role": "admin",
                "first_name": "Admin",
                "last_name": "Demo",
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if created:
            admin.set_password("Admin1234!")
            admin.save()
            self.stdout.write(f"Created admin user: admin / Admin1234!")

        manager, created = User.objects.get_or_create(
            username="manager",
            defaults={
                "email": "manager@demo.local",
                "role": "manager",
                "first_name": "Marie",
                "last_name": "Gestionnaire",
            },
        )
        if created:
            manager.set_password("Manager1234!")
            manager.save()
            self.stdout.write("Created manager user: manager / Manager1234!")

        accountant, created = User.objects.get_or_create(
            username="accountant",
            defaults={
                "email": "accountant@demo.local",
                "role": "accountant",
                "first_name": "Paul",
                "last_name": "Comptable",
            },
        )
        if created:
            accountant.set_password("Account1234!")
            accountant.save()
            self.stdout.write("Created accountant user: accountant / Account1234!")

        actor = admin

        # ------------------------------------------------------------------ #
        # Owners                                                                #
        # ------------------------------------------------------------------ #
        owner1, _ = Owner.objects.get_or_create(
            last_name="Kamga",
            first_name="Jean-Pierre",
            defaults={
                "email": "jkamga@demo.local",
                "phone": "+235 00 00 00 00",
                "is_company": False,
            },
        )
        owner2, _ = Owner.objects.get_or_create(
            company_name="SCI Akwa Immobilier",
            defaults={
                "email": "contact@akwa-immo.cm",
                "is_company": True,
            },
        )

        # ------------------------------------------------------------------ #
        # Properties                                                            #
        # ------------------------------------------------------------------ #
        prop1, _ = Property.objects.get_or_create(
            name="Résidence Les Bougainvilliers",
            defaults={
                "property_type": "residential",
                "owner": owner1,
                "address_line1": "12 Rue de la Paix",
                "city": "Ndjamena",
                "country": "Tchad",
            },
        )
        prop2, _ = Property.objects.get_or_create(
            name="Immeuble Centre Commercial Akwa",
            defaults={
                "property_type": "commercial",
                "owner": owner2,
                "address_line1": "Avenue de Gaulle",
                "city": "Ndjamena",
                "country": "Tchad",
            },
        )
        prop3, _ = Property.objects.get_or_create(
            name="Villa Bastos",
            defaults={
                "property_type": "residential",
                "owner": owner1,
                "address_line1": "Rue Bastos 45",
                "city": "Moundou",
                "country": "Tchad",
            },
        )

        # ------------------------------------------------------------------ #
        # Units                                                                 #
        # ------------------------------------------------------------------ #
        units_data = [
            (prop1, "Apt 1A", "apartment"),
            (prop1, "Apt 1B", "apartment"),
            (prop1, "Apt 2A", "apartment"),
            (prop1, "Apt 2B", "apartment"),
            (prop2, "Bureau 101", "office"),
            (prop2, "Bureau 102", "office"),
            (prop2, "Boutique 001", "shop"),
            (prop3, "Villa principale", "apartment"),
            (prop3, "Studio annexe", "studio"),
            (prop3, "Parking", "parking"),
        ]

        units = []
        for prop, name, utype in units_data:
            unit, _ = Unit.objects.get_or_create(
                building=prop,
                name=name,
                defaults={"unit_type": utype},
            )
            units.append(unit)
        self.stdout.write(f"Ensured {len(units)} units exist.")

        # ------------------------------------------------------------------ #
        # Tenants                                                               #
        # ------------------------------------------------------------------ #
        tenants_data = [
            ("Alice", "Mbarga", "alice.mbarga@email.com"),
            ("Robert", "Tchakounte", "robert.t@email.com"),
            ("Fatima", "Bello", "fatimab@email.com"),
            ("Patrick", "Nkemdirim", "pnkem@email.com"),
            ("Serge", "Fotso", "sfotso@email.com"),
        ]

        tenants = []
        for fn, ln, email in tenants_data:
            tenant, _ = Tenant.objects.get_or_create(
                email=email,
                defaults={
                    "first_name": fn,
                    "last_name": ln,
                    "phone": (
                        f"+237 6{random.randint(70, 99)} "
                        f"{random.randint(10, 99)} "
                        f"{random.randint(10, 99)} "
                        f"{random.randint(10, 99)}"
                    ),
                },
            )
            tenants.append(tenant)
        self.stdout.write(f"Ensured {len(tenants)} tenants exist.")

        # ------------------------------------------------------------------ #
        # Leases + Invoices                                                     #
        # ------------------------------------------------------------------ #
        rent_amounts = [85000, 75000, 90000, 80000, 250000]
        today = date.today()
        # Leases started ~3 months ago, always on the 1st of the month
        start = (today.replace(day=1) - relativedelta(months=3))

        for i, (tenant, unit, rent) in enumerate(zip(tenants, units[:5], rent_amounts)):
            if Lease.objects.filter(unit=unit, status=LeaseStatus.ACTIVE).exists():
                self.stdout.write(f"Lease for {unit} already exists – skipping.")
                continue

            lease = Lease.objects.create(
                unit=unit,
                tenant=tenant,
                status=LeaseStatus.ACTIVE,
                start_date=start,
                rent_unit_price=Decimal(str(rent)),
                currency=Currency.XAF,
                billing_interval_months=1,
                billing_cycle_anchor=BillingCycleAnchor.MONTH_START,
                prorate_first_period=False,
                deposit_amount=Decimal(str(rent)),
                created_by=actor,
            )
            self.stdout.write(f"Created lease for {tenant.display_name} in {unit}")

            # Deposit invoice
            generate_deposit_invoice(lease, actor)

            # 3 months of rent invoices
            for m in range(3):
                period_start = start + relativedelta(months=m)
                generate_invoice(lease, period_start, actor)

        self.stdout.write("Seed complete.")
