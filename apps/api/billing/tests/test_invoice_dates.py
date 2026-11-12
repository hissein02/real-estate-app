"""Editing invoice dates — and the consequences the caller is warned about."""

import pytest
from datetime import date, timedelta
from decimal import Decimal

from audit.models import AuditAction, AuditLog
from billing.models import Invoice, InvoiceStatus
from billing.services.invoice_service import (
    generate_invoice,
    generate_late_fee_for_invoice,
    void_invoice,
)
from tenants.models import LateFeeType, LeaseStatus
from tenants.tests.factories import LeaseFactory


@pytest.fixture
def issued_invoice(admin_user):
    lease = LeaseFactory(
        status=LeaseStatus.ACTIVE, rent_unit_price=Decimal("100000"),
        billing_interval_months=1, start_date=date(2026, 3, 1),
    )
    # Issued on the day the period opens, which is the normal case.
    return generate_invoice(
        lease, date(2026, 3, 1), admin_user, invoice_date=date(2026, 3, 1)
    )


@pytest.mark.django_db
class TestEditDates:
    def test_changes_both_dates(self, admin_client, issued_invoice):
        res = admin_client.patch(
            f"/api/v1/invoices/{issued_invoice.pk}/dates/",
            {"invoice_date": "2026-03-05", "due_date": "2026-03-20"},
            format="json",
        )
        assert res.status_code == 200
        issued_invoice.refresh_from_db()
        assert issued_invoice.invoice_date == date(2026, 3, 5)
        assert issued_invoice.due_date == date(2026, 3, 20)

    def test_can_change_only_the_due_date(self, admin_client, issued_invoice):
        original_issue = issued_invoice.invoice_date
        res = admin_client.patch(
            f"/api/v1/invoices/{issued_invoice.pk}/dates/",
            {"due_date": "2026-04-15"}, format="json",
        )
        assert res.status_code == 200
        issued_invoice.refresh_from_db()
        assert issued_invoice.due_date == date(2026, 4, 15)
        assert issued_invoice.invoice_date == original_issue

    def test_requires_at_least_one_date(self, admin_client, issued_invoice):
        res = admin_client.patch(
            f"/api/v1/invoices/{issued_invoice.pk}/dates/", {}, format="json"
        )
        assert res.status_code == 400

    def test_due_before_issue_is_allowed_but_flagged(self, admin_client, issued_invoice):
        """Billing a past period legitimately produces this, so it warns rather
        than blocks."""
        res = admin_client.patch(
            f"/api/v1/invoices/{issued_invoice.pk}/dates/",
            {"invoice_date": "2026-03-10", "due_date": "2026-03-01"},
            format="json",
        )
        assert res.status_code == 200
        assert any("before the invoice date" in w for w in res.data["warnings"])

    def test_a_void_invoice_cannot_be_edited(self, admin_client, issued_invoice, admin_user):
        void_invoice(issued_invoice, reason="mistake", actor=admin_user)
        res = admin_client.patch(
            f"/api/v1/invoices/{issued_invoice.pk}/dates/",
            {"due_date": "2026-04-01"}, format="json",
        )
        assert res.status_code == 400
        issued_invoice.refresh_from_db()
        assert issued_invoice.due_date == date(2026, 3, 1)

    def test_the_change_is_audited_with_before_and_after(self, admin_client, issued_invoice):
        admin_client.patch(
            f"/api/v1/invoices/{issued_invoice.pk}/dates/",
            {"due_date": "2026-04-15", "reason": "Accord avec le locataire"},
            format="json",
        )
        entry = AuditLog.objects.filter(
            object_type="Invoice", object_id=str(issued_invoice.pk), action=AuditAction.UPDATE
        ).latest("id")
        assert entry.reason == "Accord avec le locataire"
        assert entry.snapshot_json["before"]["due_date"] == "2026-03-01"
        assert entry.snapshot_json["after"]["due_date"] == "2026-04-15"


@pytest.mark.django_db
class TestConsequencesAreReported:
    def _overdue_invoice(self, actor, late_fee=LateFeeType.NONE):
        lease = LeaseFactory(
            status=LeaseStatus.ACTIVE, rent_unit_price=Decimal("100000"),
            billing_interval_months=1,
            start_date=date.today() - timedelta(days=60),
            late_fee_type=late_fee, late_fee_value=Decimal("5000"),
            late_fee_grace_period_days=0,
        )
        return generate_invoice(lease, date.today() - timedelta(days=40), actor)

    def test_warns_when_an_invoice_stops_being_overdue(self, admin_client, admin_user):
        invoice = self._overdue_invoice(admin_user)
        assert invoice.is_overdue

        res = admin_client.patch(
            f"/api/v1/invoices/{invoice.pk}/dates/",
            {"due_date": str(date.today() + timedelta(days=30))}, format="json",
        )
        assert res.status_code == 200
        assert any("no longer" in w for w in res.data["warnings"])

    def test_warns_when_an_invoice_becomes_overdue(self, admin_client, admin_user):
        lease = LeaseFactory(
            status=LeaseStatus.ACTIVE, rent_unit_price=Decimal("100000"),
            billing_interval_months=1, start_date=date.today() + timedelta(days=10),
        )
        invoice = generate_invoice(lease, date.today() + timedelta(days=10), admin_user)
        assert not invoice.is_overdue

        res = admin_client.patch(
            f"/api/v1/invoices/{invoice.pk}/dates/",
            {"due_date": str(date.today() - timedelta(days=1))}, format="json",
        )
        assert any("now overdue" in w for w in res.data["warnings"])

    def test_warns_that_an_existing_late_fee_is_not_retracted(self, admin_client, admin_user):
        invoice = self._overdue_invoice(admin_user, late_fee=LateFeeType.FIXED)
        fee = generate_late_fee_for_invoice(invoice, admin_user)
        assert fee is not None

        res = admin_client.patch(
            f"/api/v1/invoices/{invoice.pk}/dates/",
            {"due_date": str(date.today() + timedelta(days=30))}, format="json",
        )
        assert any(fee.invoice_number in w for w in res.data["warnings"])
        # The fee is still there — moving a date must not silently erase money.
        fee.refresh_from_db()
        assert fee.status != InvoiceStatus.VOID

    def test_warns_when_the_due_date_moves_to_another_month(self, admin_client, issued_invoice):
        res = admin_client.patch(
            f"/api/v1/invoices/{issued_invoice.pk}/dates/",
            {"due_date": "2026-05-10"}, format="json",
        )
        assert any("different month" in w for w in res.data["warnings"])

    def test_no_spurious_warning_for_a_same_month_shift(self, admin_client, issued_invoice):
        res = admin_client.patch(
            f"/api/v1/invoices/{issued_invoice.pk}/dates/",
            {"due_date": "2026-03-25"}, format="json",
        )
        assert res.data["warnings"] == []


@pytest.mark.django_db
class TestPermissions:
    @pytest.mark.parametrize("client_name", ["agent_client", "readonly_client"])
    def test_non_finance_roles_cannot_edit_dates(self, request, client_name, issued_invoice):
        client = request.getfixturevalue(client_name)
        res = client.patch(
            f"/api/v1/invoices/{issued_invoice.pk}/dates/",
            {"due_date": "2026-04-01"}, format="json",
        )
        assert res.status_code == 403
        issued_invoice.refresh_from_db()
        assert issued_invoice.due_date == date(2026, 3, 1)

    def test_accountant_can_edit_dates(self, accountant_client, issued_invoice):
        res = accountant_client.patch(
            f"/api/v1/invoices/{issued_invoice.pk}/dates/",
            {"due_date": "2026-03-20"}, format="json",
        )
        assert res.status_code == 200
