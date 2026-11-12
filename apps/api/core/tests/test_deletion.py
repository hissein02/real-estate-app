"""Deletion policy: admin-only, audited, and blocked deletes explain themselves."""

import pytest
from datetime import date
from decimal import Decimal

from audit.models import AuditAction, AuditLog
from billing.tests.factories import InvoiceFactory
from portfolio.models import Owner
from portfolio.tests.factories import OwnerFactory, PropertyFactory
from tenants.models import Lease, LeaseStatus
from tenants.tests.factories import LeaseFactory, TenantFactory


@pytest.mark.django_db
class TestDeletePermissions:
    def test_admin_can_delete_an_unreferenced_owner(self, admin_client):
        owner = OwnerFactory()
        res = admin_client.delete(f"/api/v1/owners/{owner.pk}/")
        assert res.status_code == 204
        assert not Owner.objects.filter(pk=owner.pk).exists()


@pytest.mark.django_db
class TestProtectedDeleteReturnsConflict:
    def test_owner_with_properties_returns_409_not_500(self, admin_client):
        owner = OwnerFactory()
        PropertyFactory(owner=owner)

        res = admin_client.delete(f"/api/v1/owners/{owner.pk}/")

        assert res.status_code == 409
        assert res.data["blocked_by"] == {"property": 1}
        assert Owner.objects.filter(pk=owner.pk).exists()

    def test_message_names_what_is_blocking(self, admin_client):
        owner = OwnerFactory()
        PropertyFactory(owner=owner)
        PropertyFactory(owner=owner)

        res = admin_client.delete(f"/api/v1/owners/{owner.pk}/")

        # Django's own plural name — never "2 propertys".
        assert "2 properties" in res.data["detail"]
        assert "propertys" not in res.data["detail"]

    def test_counts_each_blocking_model_separately(self, admin_client):
        lease = LeaseFactory(status=LeaseStatus.ACTIVE)
        InvoiceFactory(lease=lease)
        InvoiceFactory(lease=lease)

        res = admin_client.delete(f"/api/v1/leases/{lease.pk}/")

        assert res.status_code == 409
        assert res.data["blocked_by"] == {"invoice": 2}
        assert Lease.objects.filter(pk=lease.pk).exists()

    def test_nothing_is_logged_when_the_delete_is_blocked(self, admin_client):
        owner = OwnerFactory()
        PropertyFactory(owner=owner)

        admin_client.delete(f"/api/v1/owners/{owner.pk}/")

        assert not AuditLog.objects.filter(object_type="Owner", object_id=str(owner.pk)).exists()


@pytest.mark.django_db
class TestDeleteIsAudited:
    def test_snapshot_is_written_on_delete(self, admin_client):
        tenant = TenantFactory(first_name="Grace", last_name="Hopper")

        res = admin_client.delete(f"/api/v1/tenants/{tenant.pk}/")
        assert res.status_code == 204

        entry = AuditLog.objects.get(object_type="Tenant", object_id=str(tenant.pk))
        assert entry.action == AuditAction.HARD_DELETE
        assert entry.snapshot_json["first_name"] == "Grace"

    def test_snapshot_survives_decimal_valued_read_only_fields(self, admin_client):
        """Lease.monthly_rent_equivalent is a Decimal property exposed via
        ReadOnlyField; unconverted it raises TypeError on JSONField insert."""
        lease = LeaseFactory(status=LeaseStatus.DRAFT, rent_unit_price=Decimal("1000.00"))

        res = admin_client.delete(f"/api/v1/leases/{lease.pk}/")
        assert res.status_code == 204

        entry = AuditLog.objects.get(object_type="Lease", object_id=str(lease.pk))
        assert entry.snapshot_json["rent_unit_price"] == "1000.00"
        # Present and JSON-safe rather than a raw Decimal.
        assert isinstance(entry.snapshot_json["monthly_rent_equivalent"], (str, int, float))


@pytest.mark.django_db
class TestTerminateLease:
    def _payload(self, **over):
        data = {"termination_date": str(date.today()), "reason": "Tenant moved out"}
        data.update(over)
        return data

    def test_terminate_succeeds_with_date_and_reason(self, admin_client):
        lease = LeaseFactory(status=LeaseStatus.ACTIVE)

        res = admin_client.post(
            f"/api/v1/leases/{lease.pk}/terminate/", self._payload(), format="json"
        )

        assert res.status_code == 200
        lease.refresh_from_db()
        assert lease.status == LeaseStatus.TERMINATED
        assert lease.end_date == date.today()

    def test_reason_is_required(self, admin_client):
        """The frontend used to omit this, which produced an opaque 400."""
        lease = LeaseFactory(status=LeaseStatus.ACTIVE)

        res = admin_client.post(
            f"/api/v1/leases/{lease.pk}/terminate/",
            {"termination_date": str(date.today())},
            format="json",
        )

        assert res.status_code == 400
        assert "reason" in res.data

    def test_reason_is_recorded_in_the_audit_log(self, admin_client):
        lease = LeaseFactory(status=LeaseStatus.ACTIVE)

        admin_client.post(
            f"/api/v1/leases/{lease.pk}/terminate/",
            self._payload(reason="Non-payment"),
            format="json",
        )

        entry = AuditLog.objects.get(
            object_type="Lease", object_id=str(lease.pk), action=AuditAction.TERMINATE_LEASE
        )
        assert entry.reason == "Non-payment"

    def test_cannot_terminate_a_lease_that_is_not_active(self, admin_client):
        lease = LeaseFactory(status=LeaseStatus.DRAFT)

        res = admin_client.post(
            f"/api/v1/leases/{lease.pk}/terminate/", self._payload(), format="json"
        )

        # A rule violation, not a server fault — and it says which status blocked it.
        assert res.status_code == 400
        assert "draft" in res.data["detail"]
