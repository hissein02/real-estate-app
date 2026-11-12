import pytest
from datetime import date
from decimal import Decimal

from billing.models import PaymentStatus
from billing.services.payment_service import post_payment, void_payment
from billing.services.allocation_service import allocate
from billing.services.invoice_service import generate_invoice
from tenants.models import LeaseStatus
from tenants.tests.factories import LeaseFactory, UserFactory


@pytest.mark.django_db
class TestPostPayment:
    def test_creates_payment(self):
        actor = UserFactory()
        lease = LeaseFactory(status=LeaseStatus.ACTIVE, start_date=date.today())
        payment = post_payment(
            lease=lease,
            amount=Decimal("100000"),
            currency="XAF",
            payment_date=date.today(),
            payment_method="cash",
            reference="REF001",
            notes="",
            actor=actor,
        )
        assert payment.pk is not None
        assert payment.status == PaymentStatus.POSTED
        assert payment.amount == Decimal("100000")

    def test_rejects_zero_amount(self):
        actor = UserFactory()
        lease = LeaseFactory(status=LeaseStatus.ACTIVE, start_date=date.today())
        with pytest.raises(ValueError):
            post_payment(
                lease=lease,
                amount=Decimal("0"),
                currency="XAF",
                payment_date=date.today(),
                payment_method="cash",
                reference="",
                notes="",
                actor=actor,
            )


@pytest.mark.django_db
class TestVoidPayment:
    def test_voids_payment_and_reverses_allocations(self):
        actor = UserFactory()
        lease = LeaseFactory(
            status=LeaseStatus.ACTIVE,
            start_date=date.today(),
            rent_unit_price=Decimal("100000"),
        )
        invoice = generate_invoice(lease, date.today(), actor)
        payment = post_payment(
            lease=lease,
            amount=Decimal("100000"),
            currency="XAF",
            payment_date=date.today(),
            payment_method="cash",
            reference="",
            notes="",
            actor=actor,
        )
        allocate(payment, invoice, Decimal("100000"), actor)
        invoice.refresh_from_db()
        assert invoice.paid_amount == Decimal("100000")

        void_payment(payment, reason="Reversal", actor=actor)
        payment.refresh_from_db()
        invoice.refresh_from_db()
        assert payment.status == PaymentStatus.VOID
        assert invoice.paid_amount == Decimal("0")
