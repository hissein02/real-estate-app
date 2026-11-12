"""Policy: delete and lease-lifecycle actions are admin/manager only.

Accountants and agents keep create/update; read_only keeps read.
Enforced server-side — hiding a button is not access control.
"""

import pytest
from datetime import date

from portfolio.models import Owner
from portfolio.tests.factories import OwnerFactory
from tenants.models import Lease, LeaseStatus
from tenants.tests.factories import LeaseFactory

PRIVILEGED = ["admin_client", "manager_client"]
UNPRIVILEGED = ["accountant_client", "agent_client", "readonly_client"]


def client_for(request, name):
    return request.getfixturevalue(name)


@pytest.mark.django_db
class TestDeleteIsAdminOrManager:
    @pytest.mark.parametrize("client_name", PRIVILEGED)
    def test_privileged_roles_can_delete(self, request, client_name):
        owner = OwnerFactory()
        res = client_for(request, client_name).delete(f"/api/v1/owners/{owner.pk}/")
        assert res.status_code == 204, f"{client_name} got {res.status_code}"
        assert not Owner.objects.filter(pk=owner.pk).exists()

    @pytest.mark.parametrize("client_name", UNPRIVILEGED)
    def test_other_roles_cannot_delete(self, request, client_name):
        owner = OwnerFactory()
        res = client_for(request, client_name).delete(f"/api/v1/owners/{owner.pk}/")
        assert res.status_code == 403, f"{client_name} got {res.status_code}"
        assert Owner.objects.filter(pk=owner.pk).exists()

    @pytest.mark.parametrize("client_name", ["accountant_client", "agent_client"])
    def test_other_writers_keep_create_and_update(self, request, client_name):
        client = client_for(request, client_name)
        created = client.post(
            "/api/v1/owners/",
            {"first_name": "Ada", "last_name": "Lovelace", "is_company": False},
            format="json",
        )
        assert created.status_code == 201
        updated = client.patch(
            f"/api/v1/owners/{created.data['id']}/", {"phone": "+235 60 00 00 00"}, format="json"
        )
        assert updated.status_code == 200


@pytest.mark.django_db
class TestLeaseLifecycleIsAdminOrManager:
    """terminate / activate / renew change a lease's legal state."""

    def _payload(self):
        return {"termination_date": str(date.today()), "reason": "Tenant moved out"}

    @pytest.mark.parametrize("client_name", PRIVILEGED)
    def test_privileged_roles_can_terminate(self, request, client_name):
        lease = LeaseFactory(status=LeaseStatus.ACTIVE)
        res = client_for(request, client_name).post(
            f"/api/v1/leases/{lease.pk}/terminate/", self._payload(), format="json"
        )
        assert res.status_code == 200, f"{client_name} got {res.status_code}"
        lease.refresh_from_db()
        assert lease.status == LeaseStatus.TERMINATED

    @pytest.mark.parametrize("client_name", UNPRIVILEGED)
    def test_other_roles_cannot_terminate(self, request, client_name):
        lease = LeaseFactory(status=LeaseStatus.ACTIVE)
        res = client_for(request, client_name).post(
            f"/api/v1/leases/{lease.pk}/terminate/", self._payload(), format="json"
        )
        assert res.status_code == 403, f"{client_name} got {res.status_code}"
        lease.refresh_from_db()
        assert lease.status == LeaseStatus.ACTIVE

    @pytest.mark.parametrize("client_name", UNPRIVILEGED)
    def test_other_roles_cannot_activate(self, request, client_name):
        lease = LeaseFactory(status=LeaseStatus.DRAFT)
        res = client_for(request, client_name).post(f"/api/v1/leases/{lease.pk}/activate/")
        assert res.status_code == 403, f"{client_name} got {res.status_code}"
        lease.refresh_from_db()
        assert lease.status == LeaseStatus.DRAFT

    @pytest.mark.parametrize("client_name", UNPRIVILEGED)
    def test_other_roles_cannot_renew(self, request, client_name):
        lease = LeaseFactory(status=LeaseStatus.ACTIVE)
        before = Lease.objects.count()
        res = client_for(request, client_name).post(
            f"/api/v1/leases/{lease.pk}/renew/", {"new_end_date": str(date.today())}, format="json"
        )
        assert res.status_code == 403, f"{client_name} got {res.status_code}"
        assert Lease.objects.count() == before

    def test_agent_can_still_create_a_lease(self, agent_client):
        """Restricting lifecycle actions must not remove ordinary write access."""
        from portfolio.tests.factories import UnitFactory
        from tenants.tests.factories import TenantFactory

        unit, tenant = UnitFactory(), TenantFactory()
        res = agent_client.post(
            "/api/v1/leases/",
            {
                "unit": unit.pk,
                "tenant": tenant.pk,
                "start_date": str(date.today()),
                "rent_unit_price": "1000.00",
                "currency": "XAF",
                "billing_interval_months": 1,
            },
            format="json",
        )
        assert res.status_code == 201
