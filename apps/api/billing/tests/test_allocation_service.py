import pytest
from datetime import date
from decimal import Decimal

from billing.models import InvoiceStatus
from billing.services.allocation_service import allocate, remove_allocation
from billing.services.invoice_service import generate_invoice
from billing.services.payment_service import post_payment
from tenants.models import LeaseStatus
from tenants.tests.factories import LeaseFactory, UserFactory


@pytest.mark.django_db
class TestAllocate:
    def _setup(self):
        actor = UserFactory()
        lease = LeaseFactory(
            status=LeaseStatus.ACTIVE,
            start_date=date.today(),
            rent_unit_price=Decimal("100000"),
        )
        invoice = generate_invoice(lease, date.today(), actor)
        payment = post_payment(
            lease=lease,
            amount=Decimal("150000"),
            currency="XAF",
            payment_date=date.today(),
            payment_method="cash",
            reference="",
            notes="",
            actor=actor,
        )
        return actor, lease, invoice, payment

    def test_full_allocation_marks_invoice_paid(self):
        actor, lease, invoice, payment = self._setup()
        allocate(payment, invoice, Decimal("100000"), actor)
        invoice.refresh_from_db()
        assert invoice.status == InvoiceStatus.PAID
        assert invoice.paid_amount == Decimal("100000")

    def test_partial_allocation(self):
        actor, lease, invoice, payment = self._setup()
        allocate(payment, invoice, Decimal("50000"), actor)
        invoice.refresh_from_db()
        assert invoice.status == InvoiceStatus.PARTIALLY_PAID
        assert invoice.paid_amount == Decimal("50000")

    def test_cannot_over_allocate_payment(self):
        actor, lease, invoice, payment = self._setup()
        with pytest.raises(ValueError, match="exceeds payment unallocated"):
            allocate(payment, invoice, Decimal("200000"), actor)

    def test_cannot_over_allocate_invoice(self):
        actor, lease, invoice, payment = self._setup()
        with pytest.raises(ValueError, match="exceeds invoice balance"):
            allocate(payment, invoice, Decimal("120000"), actor)

    def test_unallocated_amount_decreases(self):
        actor, lease, invoice, payment = self._setup()
        allocate(payment, invoice, Decimal("60000"), actor)
        payment.refresh_from_db()
        assert payment.unallocated_amount == Decimal("90000")

    def test_remove_allocation_reverts_invoice(self):
        actor, lease, invoice, payment = self._setup()
        allocation = allocate(payment, invoice, Decimal("100000"), actor)
        invoice.refresh_from_db()
        assert invoice.status == InvoiceStatus.PAID
        remove_allocation(allocation, reason="Correction", actor=actor)
        invoice.refresh_from_db()
        assert invoice.status == InvoiceStatus.ISSUED
        assert invoice.paid_amount == Decimal("0")
