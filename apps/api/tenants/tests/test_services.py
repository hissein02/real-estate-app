import pytest
from datetime import date, timedelta
from decimal import Decimal

from tenants.models import LeaseStatus, BillingCycleAnchor
from tenants.services import activate_lease, terminate_lease, renew_lease, get_next_invoice_period_start
from tenants.tests.factories import LeaseFactory, UserFactory


@pytest.mark.django_db
class TestActivateLease:
    def test_activates_draft_lease(self):
        actor = UserFactory()
        lease = LeaseFactory(status=LeaseStatus.DRAFT, start_date=date.today())
        activate_lease(lease, actor)
        lease.refresh_from_db()
        assert lease.status == LeaseStatus.ACTIVE

    def test_cannot_activate_already_active(self):
        actor = UserFactory()
        lease = LeaseFactory(status=LeaseStatus.ACTIVE, start_date=date.today())
        with pytest.raises(ValueError):
            activate_lease(lease, actor)


@pytest.mark.django_db
class TestTerminateLease:
    def test_terminates_active_lease(self):
        actor = UserFactory()
        lease = LeaseFactory(status=LeaseStatus.ACTIVE, start_date=date.today())
        terminate_lease(lease, reason="Tenant moved out", termination_date=date.today(), actor=actor)
        lease.refresh_from_db()
        assert lease.status == LeaseStatus.TERMINATED
        assert lease.end_date == date.today()

    def test_cannot_terminate_draft(self):
        actor = UserFactory()
        lease = LeaseFactory(status=LeaseStatus.DRAFT, start_date=date.today())
        with pytest.raises(ValueError):
            terminate_lease(lease, reason="test", termination_date=date.today(), actor=actor)


@pytest.mark.django_db
class TestRenewLease:
    def test_creates_new_lease(self):
        actor = UserFactory()
        today = date.today()
        lease = LeaseFactory(
            status=LeaseStatus.ACTIVE,
            start_date=today - timedelta(days=365),
            end_date=today,
            rent_unit_price=Decimal("100000"),
        )
        new_lease = renew_lease(lease, new_end_date=today + timedelta(days=365), new_rent_unit_price=None, actor=actor)
        lease.refresh_from_db()
        assert lease.status == LeaseStatus.EXPIRED
        assert new_lease.status == LeaseStatus.ACTIVE
        assert new_lease.rent_unit_price == Decimal("100000")
        assert new_lease.renewed_from == lease

    def test_new_rent_amount(self):
        actor = UserFactory()
        today = date.today()
        lease = LeaseFactory(
            status=LeaseStatus.ACTIVE,
            start_date=today - timedelta(days=365),
            end_date=today,
            rent_unit_price=Decimal("100000"),
        )
        new_lease = renew_lease(lease, new_end_date=None, new_rent_unit_price=Decimal("120000"), actor=actor)
        assert new_lease.rent_unit_price == Decimal("120000")


@pytest.mark.django_db
class TestGetNextInvoicePeriodStart:
    def test_returns_start_date_for_new_lease(self):
        actor = UserFactory()
        today = date.today()
        lease = LeaseFactory(
            status=LeaseStatus.ACTIVE,
            start_date=today,
            billing_cycle_anchor=BillingCycleAnchor.LEASE_START,
        )
        result = get_next_invoice_period_start(lease)
        assert result == today

    def test_returns_none_for_inactive_lease(self):
        lease = LeaseFactory(status=LeaseStatus.DRAFT, start_date=date.today())
        assert get_next_invoice_period_start(lease) is None

    def test_returns_none_for_future_period(self):
        actor = UserFactory()
        today = date.today()
        lease = LeaseFactory(
            status=LeaseStatus.ACTIVE,
            start_date=today + timedelta(days=5),
            billing_cycle_anchor=BillingCycleAnchor.LEASE_START,
        )
        result = get_next_invoice_period_start(lease)
        assert result is None
