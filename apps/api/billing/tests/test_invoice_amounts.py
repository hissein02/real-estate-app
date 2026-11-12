"""Rent is a unit price x quantity, and partial periods are billed pro rata."""

import pytest
from datetime import date
from decimal import Decimal

from dateutil.relativedelta import relativedelta

from billing.models import Invoice, InvoiceLineType
from billing.services.invoice_service import (
    generate_due_invoices_for_all_active_leases,
    generate_invoice,
    generate_stub_invoice,
)
from tenants.models import BillingCycleAnchor, LeaseStatus
from tenants.tests.factories import LeaseFactory, UserFactory


@pytest.mark.django_db
class TestUnitPriceAndQuantity:
    def test_period_total_is_unit_price_times_interval(self):
        lease = LeaseFactory(
            status=LeaseStatus.ACTIVE, rent_unit_price=Decimal("1600000"),
            billing_interval_months=6, start_date=date(2026, 1, 1),
        )
        assert lease.rent_period_total == Decimal("9600000")

    def test_invoice_line_carries_quantity_and_unit_price(self):
        actor = UserFactory()
        lease = LeaseFactory(
            status=LeaseStatus.ACTIVE, rent_unit_price=Decimal("1600000"),
            billing_interval_months=6, start_date=date(2026, 1, 1),
        )
        invoice = generate_invoice(lease, date(2026, 1, 1), actor)
        line = invoice.lines.get(line_type=InvoiceLineType.RENT)

        assert line.quantity == Decimal("6")
        assert line.unit_price == Decimal("1600000")
        assert line.amount == Decimal("9600000")
        assert invoice.total_amount == Decimal("9600000")
        # The line must reconcile: qty x unit price == amount.
        assert line.quantity * line.unit_price == line.amount

    def test_monthly_lease_is_quantity_one(self):
        actor = UserFactory()
        lease = LeaseFactory(
            status=LeaseStatus.ACTIVE, rent_unit_price=Decimal("100000"),
            billing_interval_months=1, start_date=date(2026, 3, 1),
        )
        line = generate_invoice(lease, date(2026, 3, 1), actor).lines.first()
        assert (line.quantity, line.unit_price) == (Decimal("1"), Decimal("100000"))


@pytest.mark.django_db
class TestProration:
    def test_stub_uses_the_monthly_rate_not_the_period_total(self):
        """Previously divided the whole period's rent by days in one month,
        overcharging by exactly billing_interval_months."""
        actor = UserFactory()
        lease = LeaseFactory(
            status=LeaseStatus.ACTIVE,
            billing_cycle_anchor=BillingCycleAnchor.MONTH_START,
            prorate_first_period=True,
            billing_interval_months=3,
            rent_unit_price=Decimal("100000"),   # per month
            start_date=date(2026, 1, 17),        # 15 days left in January
        )
        stub = generate_stub_invoice(lease, actor)

        expected = (Decimal("100000") / 31 * 15).quantize(Decimal("1"))
        assert stub.total_amount == expected
        assert stub.is_prorated is True

    def test_period_cut_short_by_lease_end_is_prorated(self):
        actor = UserFactory()
        lease = LeaseFactory(
            status=LeaseStatus.ACTIVE, rent_unit_price=Decimal("100000"),
            billing_interval_months=1,
            start_date=date(2026, 1, 1), end_date=date(2026, 1, 10),
        )
        invoice = generate_invoice(lease, date(2026, 1, 1), actor)

        assert invoice.period_end == date(2026, 1, 10)
        assert invoice.is_prorated is True
        # 10 of 31 days
        assert invoice.total_amount == (Decimal("100000") / 31 * 10).quantize(Decimal("1"))
        assert invoice.proration_details["billed_days"] == 10
        assert invoice.proration_details["full_period_days"] == 31
        line = invoice.lines.get()
        assert line.quantity == Decimal("10")   # days become the quantity

    def test_full_period_is_not_marked_prorated(self):
        actor = UserFactory()
        lease = LeaseFactory(
            status=LeaseStatus.ACTIVE, rent_unit_price=Decimal("100000"),
            billing_interval_months=1,
            start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
        )
        invoice = generate_invoice(lease, date(2026, 1, 1), actor)
        assert invoice.is_prorated is False
        assert invoice.total_amount == Decimal("100000")


@pytest.mark.django_db
class TestBacklogCatchUp:
    def test_one_run_clears_a_multi_period_backlog(self):
        """A lease months behind must be brought fully up to date in one run,
        not one period per night."""
        actor = UserFactory()
        start = date.today().replace(day=1) - relativedelta(months=8)
        lease = LeaseFactory(
            status=LeaseStatus.ACTIVE, rent_unit_price=Decimal("100000"),
            billing_interval_months=1, start_date=start,
        )

        generated = generate_due_invoices_for_all_active_leases(actor)

        assert len(generated) >= 8
        invoices = Invoice.objects.filter(lease=lease).order_by("period_start")
        # Periods are contiguous with no gaps or overlaps.
        for earlier, later in zip(invoices, invoices[1:]):
            assert later.period_start == earlier.period_end + relativedelta(days=1)

    def test_a_second_run_is_a_no_op(self):
        actor = UserFactory()
        lease = LeaseFactory(
            status=LeaseStatus.ACTIVE, rent_unit_price=Decimal("100000"),
            billing_interval_months=1,
            start_date=date.today().replace(day=1) - relativedelta(months=3),
        )
        generate_due_invoices_for_all_active_leases(actor)
        count_after_first = Invoice.objects.filter(lease=lease).count()

        second = generate_due_invoices_for_all_active_leases(actor)

        assert second == []
        assert Invoice.objects.filter(lease=lease).count() == count_after_first

    def test_does_not_bill_past_the_lease_end(self):
        actor = UserFactory()
        lease = LeaseFactory(
            status=LeaseStatus.ACTIVE, rent_unit_price=Decimal("100000"),
            billing_interval_months=1,
            start_date=date.today() - relativedelta(months=6),
            end_date=date.today() - relativedelta(months=3),
        )
        generate_due_invoices_for_all_active_leases(actor)

        for inv in Invoice.objects.filter(lease=lease):
            assert inv.period_end <= lease.end_date
