"""The escape hatch: cascading lease delete for test data and mistaken entries."""

import pytest
from decimal import Decimal

from audit.models import AuditAction, AuditLog
from billing.models import Allocation, Invoice, InvoiceLine, Payment
from billing.tests.factories import InvoiceFactory, PaymentFactory
from deposits.models import DepositTransaction
from tenants.models import Lease, LeaseStatus
from tenants.tests.factories import LeaseFactory


@pytest.fixture
def loaded_lease(admin_user):
    """A lease carrying one of everything that blocks a normal delete."""
    lease = LeaseFactory(status=LeaseStatus.ACTIVE)
    invoice = InvoiceFactory(lease=lease, total_amount=Decimal("1000.00"))
    InvoiceLine.objects.create(
        invoice=invoice, line_type="rent", description="Rent",
        quantity=Decimal("1"), unit_price=Decimal("1000.00"), amount=Decimal("1000.00"),
    )
    payment = PaymentFactory(lease=lease, amount=Decimal("400.00"))
    Allocation.objects.create(
        payment=payment, invoice=invoice, amount=Decimal("400.00"), created_by=admin_user
    )
    DepositTransaction.objects.create(
        lease=lease, transaction_type="received", amount=Decimal("500.00"),
        date=lease.start_date, created_by=admin_user,
    )
    return lease


@pytest.mark.django_db
class TestNormalDeleteStillRefuses:
    def test_plain_delete_is_still_blocked(self, admin_client, loaded_lease):
        """The safe default must not change — money records are not casually removed."""
        res = admin_client.delete(f"/api/v1/leases/{loaded_lease.pk}/")
        assert res.status_code == 409
        assert Lease.objects.filter(pk=loaded_lease.pk).exists()


@pytest.mark.django_db
class TestDeletionPreview:
    def test_preview_counts_everything_that_would_go(self, admin_client, loaded_lease):
        res = admin_client.get(f"/api/v1/leases/{loaded_lease.pk}/deletion-preview/")

        assert res.status_code == 200
        assert res.data["will_delete"] == {
            "invoice": 1, "payment": 1, "allocation": 1,
            "deposit transaction": 1, "invoice line": 1,
        }
        assert res.data["total"] == 5

    def test_preview_changes_nothing(self, admin_client, loaded_lease):
        admin_client.get(f"/api/v1/leases/{loaded_lease.pk}/deletion-preview/")

        assert Lease.objects.filter(pk=loaded_lease.pk).exists()
        assert Invoice.objects.filter(lease=loaded_lease).count() == 1

    @pytest.mark.parametrize(
        "client_name", ["manager_client", "accountant_client", "agent_client", "readonly_client"]
    )
    def test_preview_is_admin_only(self, request, client_name, loaded_lease):
        client = request.getfixturevalue(client_name)
        res = client.get(f"/api/v1/leases/{loaded_lease.pk}/deletion-preview/")
        assert res.status_code == 403


@pytest.mark.django_db
class TestForceDelete:
    def test_removes_the_lease_and_every_attached_record(self, admin_client, loaded_lease):
        lease_id = loaded_lease.pk

        res = admin_client.delete(
            f"/api/v1/leases/{lease_id}/force-delete/", {"confirm": True}, format="json"
        )

        assert res.status_code == 200
        assert not Lease.objects.filter(pk=lease_id).exists()
        assert not Invoice.objects.filter(lease_id=lease_id).exists()
        assert not Payment.objects.filter(lease_id=lease_id).exists()
        assert not DepositTransaction.objects.filter(lease_id=lease_id).exists()
        assert Allocation.objects.count() == 0
        # Invoice lines cascade with their invoice.
        assert InvoiceLine.objects.count() == 0

    def test_confirm_is_required(self, admin_client, loaded_lease):
        res = admin_client.delete(
            f"/api/v1/leases/{loaded_lease.pk}/force-delete/", {"confirm": False}, format="json"
        )
        assert res.status_code == 400
        assert Lease.objects.filter(pk=loaded_lease.pk).exists()

    @pytest.mark.parametrize(
        "client_name", ["manager_client", "accountant_client", "agent_client", "readonly_client"]
    )
    def test_force_delete_is_admin_only(self, request, client_name, loaded_lease):
        client = request.getfixturevalue(client_name)
        res = client.delete(
            f"/api/v1/leases/{loaded_lease.pk}/force-delete/", {"confirm": True}, format="json"
        )
        assert res.status_code == 403
        assert Lease.objects.filter(pk=loaded_lease.pk).exists()

    def test_everything_destroyed_is_recoverable_from_the_audit_log(
        self, admin_client, loaded_lease
    ):
        lease_id = loaded_lease.pk
        invoice_number = Invoice.objects.get(lease_id=lease_id).invoice_number

        admin_client.delete(
            f"/api/v1/leases/{lease_id}/force-delete/",
            {"confirm": True, "reason": "test data"},
            format="json",
        )

        entry = AuditLog.objects.get(
            object_type="Lease", object_id=str(lease_id), action=AuditAction.HARD_DELETE
        )
        assert entry.reason == "test data"
        snap = entry.snapshot_json
        assert snap["lease"]["id"] == lease_id
        assert snap["invoices"][0]["invoice_number"] == invoice_number
        assert len(snap["payments"]) == 1
        assert len(snap["allocations"]) == 1
        assert len(snap["deposit_transactions"]) == 1

    def test_works_on_a_lease_with_no_attachments_at_all(self, admin_client):
        lease = LeaseFactory(status=LeaseStatus.DRAFT)

        res = admin_client.delete(
            f"/api/v1/leases/{lease.pk}/force-delete/", {"confirm": True}, format="json"
        )

        assert res.status_code == 200
        assert res.data["will_delete"] == {}
        assert not Lease.objects.filter(pk=lease.pk).exists()

    def test_leaves_other_leases_untouched(self, admin_client, loaded_lease):
        """The cascade must be scoped to one lease, not the whole table."""
        bystander = LeaseFactory(status=LeaseStatus.ACTIVE)
        bystander_invoice = InvoiceFactory(lease=bystander)

        admin_client.delete(
            f"/api/v1/leases/{loaded_lease.pk}/force-delete/", {"confirm": True}, format="json"
        )

        assert Lease.objects.filter(pk=bystander.pk).exists()
        assert Invoice.objects.filter(pk=bystander_invoice.pk).exists()
