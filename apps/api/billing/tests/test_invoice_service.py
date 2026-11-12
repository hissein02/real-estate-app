import pytest
from datetime import date, timedelta
from decimal import Decimal

from billing.models import Invoice, InvoiceStatus, InvoiceLineType
from billing.services.invoice_service import (
    INVOICE_NUMBER_PREFIX_FMT,
    generate_invoice,
    generate_invoice_with_extras,
    generate_stub_invoice,
    generate_deposit_invoice,
    void_invoice,
)
from tenants.models import LeaseStatus, BillingCycleAnchor
from tenants.tests.factories import LeaseFactory, UserFactory


@pytest.mark.django_db
class TestGenerateInvoice:
    def test_generates_invoice_for_active_lease(self):
        actor = UserFactory()
        lease = LeaseFactory(
            status=LeaseStatus.ACTIVE,
            start_date=date.today(),
            rent_unit_price=Decimal("100000"),
            currency="XAF",
        )
        invoice = generate_invoice(lease, date.today(), actor)
        assert invoice is not None
        assert invoice.total_amount == Decimal("100000")
        assert invoice.status == InvoiceStatus.ISSUED

    def test_idempotent_generation(self):
        actor = UserFactory()
        lease = LeaseFactory(
            status=LeaseStatus.ACTIVE,
            start_date=date.today(),
            rent_unit_price=Decimal("100000"),
        )
        inv1 = generate_invoice(lease, date.today(), actor)
        inv2 = generate_invoice(lease, date.today(), actor)
        assert inv1.pk == inv2.pk

    def test_returns_none_for_inactive_lease(self):
        actor = UserFactory()
        lease = LeaseFactory(status=LeaseStatus.DRAFT, start_date=date.today())
        result = generate_invoice(lease, date.today(), actor)
        assert result is None

    def test_creates_rent_line(self):
        actor = UserFactory()
        lease = LeaseFactory(
            status=LeaseStatus.ACTIVE,
            start_date=date.today(),
            rent_unit_price=Decimal("50000"),
        )
        invoice = generate_invoice(lease, date.today(), actor)
        assert invoice.lines.filter(line_type=InvoiceLineType.RENT).count() == 1


@pytest.mark.django_db
class TestGenerateStubInvoice:
    def test_generates_stub_when_starts_midmonth(self):
        actor = UserFactory()
        # Start on the 15th
        start = date.today().replace(day=15)
        lease = LeaseFactory(
            status=LeaseStatus.ACTIVE,
            start_date=start,
            rent_unit_price=Decimal("100000"),
            billing_cycle_anchor=BillingCycleAnchor.MONTH_START,
            prorate_first_period=True,
        )
        stub = generate_stub_invoice(lease, actor)
        assert stub is not None
        assert stub.is_prorated is True
        assert stub.total_amount < Decimal("100000")

    def test_no_stub_when_starts_on_first(self):
        actor = UserFactory()
        today = date.today()
        first = today.replace(day=1)
        lease = LeaseFactory(
            status=LeaseStatus.ACTIVE,
            start_date=first,
            billing_cycle_anchor=BillingCycleAnchor.MONTH_START,
            prorate_first_period=True,
        )
        stub = generate_stub_invoice(lease, actor)
        assert stub is None

    def test_no_stub_when_prorate_false(self):
        actor = UserFactory()
        start = date.today().replace(day=15)
        lease = LeaseFactory(
            status=LeaseStatus.ACTIVE,
            start_date=start,
            billing_cycle_anchor=BillingCycleAnchor.MONTH_START,
            prorate_first_period=False,
        )
        stub = generate_stub_invoice(lease, actor)
        assert stub is None


@pytest.mark.django_db
class TestVoidInvoice:
    def test_voids_unpaid_invoice(self):
        actor = UserFactory()
        lease = LeaseFactory(status=LeaseStatus.ACTIVE, start_date=date.today())
        invoice = generate_invoice(lease, date.today(), actor)
        void_invoice(invoice, reason="Test void", actor=actor)
        invoice.refresh_from_db()
        assert invoice.status == InvoiceStatus.VOID
        assert invoice.void_reason == "Test void"

    def test_cannot_void_already_void(self):
        actor = UserFactory()
        lease = LeaseFactory(status=LeaseStatus.ACTIVE, start_date=date.today())
        invoice = generate_invoice(lease, date.today(), actor)
        void_invoice(invoice, reason="first void", actor=actor)
        with pytest.raises(ValueError, match="already void"):
            void_invoice(invoice, reason="second void", actor=actor)


@pytest.mark.django_db
class TestGenerateDepositInvoice:
    def test_generates_deposit_invoice(self):
        actor = UserFactory()
        lease = LeaseFactory(
            status=LeaseStatus.ACTIVE,
            start_date=date.today(),
            deposit_amount=Decimal("200000"),
        )
        dep_invoice = generate_deposit_invoice(lease, actor)
        assert dep_invoice is not None
        assert dep_invoice.total_amount == Decimal("200000")
        assert dep_invoice.lines.filter(line_type=InvoiceLineType.DEPOSIT).count() == 1

    def test_no_deposit_if_zero(self):
        actor = UserFactory()
        lease = LeaseFactory(
            status=LeaseStatus.ACTIVE,
            start_date=date.today(),
            deposit_amount=Decimal("0"),
        )
        result = generate_deposit_invoice(lease, actor)
        assert result is None


@pytest.mark.django_db
class TestGenerateInvoiceWithExtras:
    """Manual generation must never fold into an existing invoice for the period."""

    def _active_lease(self, **kwargs):
        return LeaseFactory(
            status=LeaseStatus.ACTIVE,
            start_date=date.today(),
            rent_unit_price=Decimal("100000"),
            currency="XAF",
            **kwargs,
        )

    def test_rejects_a_period_that_is_already_invoiced(self):
        actor = UserFactory()
        lease = self._active_lease()
        existing = generate_invoice(lease, date.today(), actor)

        with pytest.raises(ValueError) as exc:
            generate_invoice_with_extras(
                lease=lease,
                period_start=date.today(),
                extra_lines=[],
                notes="",
                actor=actor,
                invoice_number="INV-MANUAL-1",
            )
        assert existing.invoice_number in str(exc.value)

    def test_does_not_mutate_the_existing_invoice(self):
        actor = UserFactory()
        lease = self._active_lease()
        existing = generate_invoice(lease, date.today(), actor)

        with pytest.raises(ValueError):
            generate_invoice_with_extras(
                lease=lease,
                period_start=date.today(),
                extra_lines=[{
                    "line_type": "adjustment",
                    "description": "Cleaning",
                    "quantity": Decimal("1"),
                    "unit_price": Decimal("5000"),
                }],
                notes="should not be applied",
                actor=actor,
                invoice_number="INV-MANUAL-2",
            )

        existing.refresh_from_db()
        assert existing.lines.count() == 1
        assert existing.total_amount == Decimal("100000")
        assert existing.notes == ""
        assert Invoice.objects.filter(invoice_number="INV-MANUAL-2").count() == 0

    def test_allows_reissue_after_the_original_is_voided(self):
        actor = UserFactory()
        lease = self._active_lease()
        original = generate_invoice(lease, date.today(), actor)
        void_invoice(original, reason="wrong amount", actor=actor)

        reissued = generate_invoice_with_extras(
            lease=lease,
            period_start=date.today(),
            extra_lines=[],
            notes="",
            actor=actor,
            invoice_number="INV-MANUAL-3",
        )
        assert reissued.pk != original.pk
        assert reissued.invoice_number == "INV-MANUAL-3"

    def test_extra_lines_are_included_in_the_total_and_status_stays_consistent(self):
        actor = UserFactory()
        lease = self._active_lease()

        invoice = generate_invoice_with_extras(
            lease=lease,
            period_start=date.today(),
            extra_lines=[{
                "line_type": "adjustment",
                "description": "Cleaning",
                "quantity": Decimal("2"),
                "unit_price": Decimal("5000"),
            }],
            notes="with extras",
            actor=actor,
            invoice_number="INV-MANUAL-4",
        )
        assert invoice.total_amount == Decimal("110000")
        assert invoice.status == InvoiceStatus.ISSUED
        assert invoice.balance == Decimal("110000")


@pytest.mark.django_db
class TestInvoiceNumbering:
    def _active_lease(self):
        return LeaseFactory(
            status=LeaseStatus.ACTIVE,
            start_date=date.today(),
            rent_unit_price=Decimal("100000"),
        )

    def test_auto_numbers_are_sequential_within_the_month(self):
        actor = UserFactory()
        prefix = date.today().strftime("INV-%Y%m-")

        numbers = [
            generate_invoice(self._active_lease(), date.today(), actor).invoice_number
            for _ in range(3)
        ]
        assert numbers == [f"{prefix}000001", f"{prefix}000002", f"{prefix}000003"]

    def test_auto_numbers_are_unique_across_many_invoices(self):
        actor = UserFactory()
        numbers = {
            generate_invoice(self._active_lease(), date.today(), actor).invoice_number
            for _ in range(25)
        }
        assert len(numbers) == 25

    def test_explicit_number_is_preserved(self):
        actor = UserFactory()
        invoice = generate_invoice(
            self._active_lease(), date.today(), actor, invoice_number="FACTURE-2026-007"
        )
        assert invoice.invoice_number == "FACTURE-2026-007"

    def test_sequence_survives_a_non_numeric_number_in_the_same_prefix(self):
        actor = UserFactory()
        prefix = date.today().strftime("INV-%Y%m-")
        # A hand-entered number sharing the month prefix must not break numbering.
        generate_invoice(
            self._active_lease(), date.today(), actor, invoice_number=f"{prefix}ZZZZZZ"
        )
        invoice = generate_invoice(self._active_lease(), date.today(), actor)
        assert invoice.invoice_number.startswith(prefix)
        assert Invoice.objects.filter(invoice_number=invoice.invoice_number).count() == 1

    def test_prefix_format_tracks_the_current_month(self):
        assert date.today().strftime(INVOICE_NUMBER_PREFIX_FMT) == date.today().strftime("INV-%Y%m-")
