"""Manually added adjustment lines must reach the rendered invoice."""

import pytest
from datetime import date
from decimal import Decimal

from billing.models import InvoiceLineType
from billing.services.invoice_service import generate_invoice_with_extras
from tenants.models import LeaseStatus
from tenants.tests.factories import LeaseFactory


@pytest.fixture
def invoice_with_adjustment(admin_user):
    lease = LeaseFactory(
        status=LeaseStatus.ACTIVE, rent_unit_price=Decimal("100000"),
        billing_interval_months=1, start_date=date(2026, 3, 1), currency="XAF",
    )
    return generate_invoice_with_extras(
        lease=lease,
        period_start=date(2026, 3, 1),
        extra_lines=[
            {"line_type": "adjustment", "description": "Nettoyage",
             "quantity": Decimal("2"), "unit_price": Decimal("5000")},
            {"line_type": "other", "description": "Badge d'accès",
             "quantity": Decimal("1"), "unit_price": Decimal("15000")},
        ],
        notes="",
        actor=admin_user,
        invoice_number="INV-DOC-1",
    )


@pytest.mark.django_db
class TestAdjustmentsOnTheInvoice:
    def test_adjustments_are_stored_as_lines(self, invoice_with_adjustment):
        inv = invoice_with_adjustment
        descriptions = {l.description for l in inv.lines.all()}
        assert "Nettoyage" in descriptions
        assert "Badge d'accès" in descriptions
        assert inv.lines.count() == 3   # rent + two extras

    def test_total_includes_the_adjustments(self, invoice_with_adjustment):
        # 100000 rent + (2 x 5000) + (1 x 15000)
        assert invoice_with_adjustment.total_amount == Decimal("125000")

    def test_each_line_reconciles_quantity_times_unit_price(self, invoice_with_adjustment):
        for line in invoice_with_adjustment.lines.all():
            assert line.quantity * line.unit_price == line.amount

    def test_adjustments_appear_in_the_rendered_pdf_html(self, admin_client, invoice_with_adjustment):
        """Render through the real PDF endpoint's template path."""
        res = admin_client.get(f"/api/v1/invoices/{invoice_with_adjustment.pk}/pdf/")
        assert res.status_code == 200
        assert res["Content-Type"] == "application/pdf"
        assert len(res.content) > 1000            # a real document, not an error stub
        assert res.content.startswith(b"%PDF")

    def test_money_is_not_truncated_for_decimal_currencies(self, admin_user):
        """int() on unit price used to drop the cents on EUR/USD invoices."""
        lease = LeaseFactory(
            status=LeaseStatus.ACTIVE, rent_unit_price=Decimal("1234.56"),
            billing_interval_months=1, start_date=date(2026, 4, 1), currency="EUR",
        )
        inv = generate_invoice_with_extras(
            lease=lease, period_start=date(2026, 4, 1), extra_lines=[], notes="",
            actor=admin_user, invoice_number="INV-DOC-EUR",
        )
        line = inv.lines.get(line_type=InvoiceLineType.RENT)
        assert line.unit_price == Decimal("1234.56")

        from settings_app.services import format_amount
        assert format_amount(line.unit_price) == "1 234.56"


@pytest.mark.django_db
class TestManualGenerationEndpoint:
    """The schedule page posts without an invoice_number; that must work."""

    def _lease(self):
        return LeaseFactory(
            status=LeaseStatus.ACTIVE, rent_unit_price=Decimal("100000"),
            billing_interval_months=1, start_date=date(2026, 5, 1), currency="XAF",
        )

    def test_generates_without_an_invoice_number(self, admin_client):
        lease = self._lease()
        res = admin_client.post(
            "/api/v1/invoices/generate/",
            {"lease_id": lease.pk, "period_start": "2026-05-01", "send_email": False},
            format="json",
        )
        assert res.status_code == 201, res.data
        assert res.data["invoice_number"].startswith("INV-")

    def test_an_explicit_number_is_still_honoured(self, admin_client):
        lease = self._lease()
        res = admin_client.post(
            "/api/v1/invoices/generate/",
            {"lease_id": lease.pk, "period_start": "2026-05-01",
             "invoice_number": "FACTURE-2026-042", "send_email": False},
            format="json",
        )
        assert res.status_code == 201
        assert res.data["invoice_number"] == "FACTURE-2026-042"

    def test_duplicate_explicit_number_is_rejected(self, admin_client):
        lease = self._lease()
        admin_client.post(
            "/api/v1/invoices/generate/",
            {"lease_id": lease.pk, "period_start": "2026-05-01",
             "invoice_number": "DUP-1", "send_email": False}, format="json",
        )
        other = self._lease()
        res = admin_client.post(
            "/api/v1/invoices/generate/",
            {"lease_id": other.pk, "period_start": "2026-05-01",
             "invoice_number": "DUP-1", "send_email": False}, format="json",
        )
        assert res.status_code == 400
        assert "invoice_number" in res.data

    def test_manual_numbers_continue_the_sequence(self, admin_client):
        first = admin_client.post(
            "/api/v1/invoices/generate/",
            {"lease_id": self._lease().pk, "period_start": "2026-05-01"}, format="json",
        ).data["invoice_number"]
        second = admin_client.post(
            "/api/v1/invoices/generate/",
            {"lease_id": self._lease().pk, "period_start": "2026-05-01"}, format="json",
        ).data["invoice_number"]
        assert int(second[-6:]) == int(first[-6:]) + 1
