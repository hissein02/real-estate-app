"""Every variable offered in Settings must actually be supplied at render time.

If a template uses a variable the context lacks, .format() raises KeyError and
the code silently falls back to the built-in default — the operator's edit
looks ignored with no error anywhere.
"""

import pytest
from datetime import date, timedelta
from decimal import Decimal

from billing.services.email_service import build_invoice_email_draft
from billing.services.invoice_service import generate_invoice
from notifications.models import Notification
from settings_app.models import NotificationTemplate
from settings_app.services import TEMPLATE_DEFAULTS
from tenants.models import LeaseStatus
from tenants.tests.factories import LeaseFactory

LOCATION_VARS = ["property_name", "unit_name", "property_address"]


@pytest.fixture
def lease(db):
    lease = LeaseFactory(
        status=LeaseStatus.ACTIVE, rent_unit_price=Decimal("100000"),
        billing_interval_months=1, start_date=date.today(),
    )
    lease.unit.name = "Appartement 3B"
    lease.unit.save(update_fields=["name"])
    lease.unit.building.name = "Résidence Les Manguiers"
    lease.unit.building.address_line1 = "Avenue Charles de Gaulle"
    lease.unit.building.city = "N'Djaména"
    lease.unit.building.save()
    lease.tenant.email = "locataire@example.td"
    lease.tenant.save(update_fields=["email"])
    return lease


@pytest.mark.parametrize("template_type", sorted(TEMPLATE_DEFAULTS))
def test_settings_offers_the_location_variables(template_type):
    declared = TEMPLATE_DEFAULTS[template_type]["variables"]
    for var in LOCATION_VARS:
        assert var in declared, f"{template_type} does not offer {var}"


@pytest.mark.parametrize("template_type", sorted(TEMPLATE_DEFAULTS))
def test_every_declared_variable_has_sample_data(template_type):
    """The Settings preview renders with sample_data; a missing key breaks it."""
    spec = TEMPLATE_DEFAULTS[template_type]
    assert set(spec["variables"]) == set(spec["sample_data"])


@pytest.mark.parametrize("template_type", sorted(TEMPLATE_DEFAULTS))
def test_default_body_and_subject_render_with_sample_data(template_type):
    spec = TEMPLATE_DEFAULTS[template_type]
    spec["body"].format(**spec["sample_data"])
    spec["subject"].format(**spec["sample_data"])


@pytest.mark.django_db
class TestInvoiceEmailUsesRealLocation:
    def test_a_template_using_the_new_variables_renders(self, lease, admin_user):
        NotificationTemplate.objects.update_or_create(
            notification_type="invoice_generated",
            defaults={
                "subject_template": "Facture {invoice_number} — {property_name}",
                "body_template": (
                    "<p>{tenant_name}, logement {unit_name} "
                    "à {property_address} ({property_name}).</p>"
                ),
            },
        )
        invoice = generate_invoice(lease, date.today(), admin_user)

        draft = build_invoice_email_draft(invoice)

        assert "Résidence Les Manguiers" in draft["subject"]
        assert "Appartement 3B" in draft["body"]
        assert "Avenue Charles de Gaulle" in draft["body"]
        # If the context were missing a key we would silently get the default text.
        assert "Veuillez trouver ci-joint" not in draft["body"]

    def test_falls_back_cleanly_on_a_genuinely_unknown_variable(self, lease, admin_user):
        NotificationTemplate.objects.update_or_create(
            notification_type="invoice_generated",
            defaults={
                "subject_template": "Facture {invoice_number}",
                "body_template": "<p>{variable_qui_nexiste_pas}</p>",
            },
        )
        invoice = generate_invoice(lease, date.today(), admin_user)

        draft = build_invoice_email_draft(invoice)

        assert "variable_qui_nexiste_pas" not in draft["body"]
        assert draft["body"].strip() != ""


@pytest.mark.django_db
class TestNotificationsUseRealLocation:
    def test_rent_reminder_resolves_the_location(self, lease, admin_user):
        from notifications.services import send_rent_reminders

        due = date.today() + timedelta(days=7)
        invoice = generate_invoice(lease, date.today(), admin_user)
        invoice.due_date = due
        invoice.save(update_fields=["due_date"])

        NotificationTemplate.objects.update_or_create(
            notification_type="rent_reminder",
            defaults={
                "subject_template": "Loyer {property_name}",
                "body_template": "<p>{unit_name} — {property_address}</p>",
            },
        )
        send_rent_reminders(days_before=7)

        notif = Notification.objects.filter(lease=lease).latest("id")
        assert "Résidence Les Manguiers" in notif.subject
        assert "Appartement 3B" in notif.body

    def test_lease_expiry_warning_resolves_the_location(self, lease):
        from notifications.services import send_lease_expiry_warnings

        lease.end_date = date.today() + timedelta(days=30)
        lease.save(update_fields=["end_date"])
        NotificationTemplate.objects.update_or_create(
            notification_type="lease_expiry_warning",
            defaults={
                "subject_template": "Bail {property_name}",
                "body_template": "<p>{unit_name} — {property_address}</p>",
            },
        )
        send_lease_expiry_warnings(days_before=30)

        notif = Notification.objects.filter(lease=lease).latest("id")
        assert "Résidence Les Manguiers" in notif.subject
        assert "Avenue Charles de Gaulle" in notif.body
