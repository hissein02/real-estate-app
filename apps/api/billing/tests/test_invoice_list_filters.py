"""Searching and filtering the invoice list."""

import pytest
from datetime import date
from decimal import Decimal

from billing.services.invoice_service import generate_invoice
from tenants.models import LeaseStatus
from tenants.tests.factories import LeaseFactory, TenantFactory


@pytest.fixture
def data(db, admin_user):
    company = TenantFactory(is_company=True, company_name="MOOV AFRICA", first_name="", last_name="")
    person = TenantFactory(is_company=False, first_name="Aïcha", last_name="Abdoulaye")

    leases = {}
    for key, tenant, number in (("company", company, "INV-CO-001"), ("person", person, "INV-PE-002")):
        lease = LeaseFactory(
            tenant=tenant, status=LeaseStatus.ACTIVE,
            rent_unit_price=Decimal("100000"), billing_interval_months=1,
            start_date=date(2026, 9, 1),
        )
        generate_invoice(lease, date(2026, 9, 1), admin_user, invoice_number=number)
        leases[key] = lease
    return {"company": company, "person": person, "leases": leases}


def numbers(res):
    return {r["invoice_number"] for r in res.data["results"]}


@pytest.mark.django_db
class TestSearch:
    def test_by_full_invoice_number(self, admin_client, data):
        res = admin_client.get("/api/v1/invoices/?search=INV-CO-001")
        assert numbers(res) == {"INV-CO-001"}

    def test_by_partial_invoice_number(self, admin_client, data):
        res = admin_client.get("/api/v1/invoices/?search=CO-001")
        assert numbers(res) == {"INV-CO-001"}

    def test_by_company_tenant_name(self, admin_client, data):
        """Company tenants have no first/last name; without company_name in the
        search fields they were unreachable."""
        res = admin_client.get("/api/v1/invoices/?search=MOOV")
        assert numbers(res) == {"INV-CO-001"}

    def test_by_individual_tenant_name(self, admin_client, data):
        res = admin_client.get("/api/v1/invoices/?search=Abdoulaye")
        assert numbers(res) == {"INV-PE-002"}

    def test_no_match_returns_nothing(self, admin_client, data):
        res = admin_client.get("/api/v1/invoices/?search=zzz-inexistant")
        assert res.data["count"] == 0


@pytest.mark.django_db
class TestTenantFilter:
    def test_filters_to_one_tenant(self, admin_client, data):
        res = admin_client.get(f"/api/v1/invoices/?tenant={data['company'].pk}")
        assert numbers(res) == {"INV-CO-001"}

    def test_combines_with_status(self, admin_client, data):
        res = admin_client.get(f"/api/v1/invoices/?tenant={data['company'].pk}&status=issued")
        assert numbers(res) == {"INV-CO-001"}

    def test_combines_with_search(self, admin_client, data):
        res = admin_client.get(
            f"/api/v1/invoices/?tenant={data['person'].pk}&search=INV-CO-001"
        )
        assert res.data["count"] == 0, "the two conditions must intersect, not union"


@pytest.mark.django_db
class TestGenerationDateIsExposed:
    def test_invoice_date_is_returned_for_the_column(self, admin_client, data):
        res = admin_client.get("/api/v1/invoices/?search=INV-CO-001")
        row = res.data["results"][0]
        assert "invoice_date" in row
        assert "created_at" in row  # fallback when invoice_date is null

    def test_orderable_by_generation_date(self, admin_client, data):
        res = admin_client.get("/api/v1/invoices/?ordering=invoice_date")
        assert res.status_code == 200
        assert res.data["count"] == 2


@pytest.mark.django_db
class TestPaymentSearchToo:
    def test_payments_find_company_tenants(self, admin_client, data, admin_user):
        from billing.services.payment_service import post_payment

        lease = data["leases"]["company"]
        post_payment(lease, Decimal("1000"), lease.currency, date(2026, 9, 1),
                     "cash", "REF-1", "", admin_user)
        res = admin_client.get("/api/v1/payments/?search=MOOV")
        assert res.data["count"] == 1
