import pytest
from datetime import date, timedelta
from decimal import Decimal

from billing.models import InvoiceStatus
from billing.services.arrears_service import get_lease_balance, get_portfolio_arrears_summary
from billing.services.invoice_service import generate_invoice
from billing.services.payment_service import post_payment
from billing.services.allocation_service import allocate
from tenants.models import LeaseStatus
from tenants.tests.factories import LeaseFactory, UserFactory


@pytest.mark.django_db
class TestGetLeaseBalance:
    def test_zero_balance_on_new_lease(self):
        actor = UserFactory()
        lease = LeaseFactory(status=LeaseStatus.ACTIVE, start_date=date.today())
        balance = get_lease_balance(lease)
        assert balance["total_invoiced"] == Decimal("0")
        assert balance["total_paid"] == Decimal("0")
        assert balance["balance"] == Decimal("0")

    def test_balance_after_invoice(self):
        actor = UserFactory()
        lease = LeaseFactory(
            status=LeaseStatus.ACTIVE,
            start_date=date.today(),
            rent_unit_price=Decimal("100000"),
        )
        generate_invoice(lease, date.today(), actor)
        balance = get_lease_balance(lease)
        assert balance["total_invoiced"] == Decimal("100000")
        assert balance["balance"] == Decimal("100000")

    def test_balance_after_payment_and_allocation(self):
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
        balance = get_lease_balance(lease)
        assert balance["balance"] == Decimal("0")
