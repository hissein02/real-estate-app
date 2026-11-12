"""CSV and Excel exports."""

import io
import pytest
from datetime import date
from decimal import Decimal

from billing.services.invoice_service import generate_invoice, void_invoice
from billing.services.payment_service import post_payment
from tenants.models import LeaseStatus
from tenants.tests.factories import LeaseFactory, TenantFactory

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@pytest.fixture
def data(db, admin_user):
    tenant = TenantFactory(is_company=True, company_name="MOOV AFRICA",
                           first_name="", last_name="")
    lease = LeaseFactory(
        tenant=tenant, status=LeaseStatus.ACTIVE, rent_unit_price=Decimal("100000"),
        billing_interval_months=1, start_date=date(2026, 9, 1),
    )
    inv = generate_invoice(lease, date(2026, 9, 1), admin_user, invoice_number="EXP-1")
    post_payment(lease, Decimal("50000"), lease.currency, date(2026, 9, 2),
                 "cash", "REF-EXP", "", admin_user)
    return {"lease": lease, "invoice": inv, "tenant": tenant}


@pytest.mark.django_db
class TestCsvExport:
    def test_invoices_csv(self, admin_client, data):
        res = admin_client.get("/api/v1/reports/export/invoices/")
        assert res.status_code == 200
        assert "text/csv" in res["Content-Type"]
        assert 'filename="invoices.csv"' in res["Content-Disposition"]
        body = res.content.decode("utf-8")
        assert body.startswith("﻿"), "Excel needs the BOM to read accents correctly"
        assert "EXP-1" in body
        assert "MOOV AFRICA" in body

    def test_payments_csv(self, admin_client, data):
        res = admin_client.get("/api/v1/reports/export/payments/")
        assert res.status_code == 200
        assert "REF-EXP" in res.content.decode("utf-8")

    def test_void_invoices_are_excluded(self, admin_client, data, admin_user):
        void_invoice(data["invoice"], reason="erreur", actor=admin_user)
        body = admin_client.get("/api/v1/reports/export/invoices/").content.decode("utf-8")
        assert "EXP-1" not in body


@pytest.mark.django_db
class TestXlsxExport:
    def test_invoices_xlsx_is_a_real_workbook(self, admin_client, data):
        res = admin_client.get("/api/v1/reports/export/invoices/?fmt=xlsx")
        assert res.status_code == 200
        assert res["Content-Type"] == XLSX_MIME
        assert 'filename="invoices.xlsx"' in res["Content-Disposition"]
        assert res.content[:4] == b"PK\x03\x04", "not a valid xlsx container"

        from openpyxl import load_workbook

        wb = load_workbook(io.BytesIO(res.content))
        ws = wb.active
        assert ws.title == "Factures"
        assert ws.freeze_panes == "A2"
        headers = [c.value for c in ws[1]]
        assert "Invoice Number" in headers and "Invoice Date" in headers
        values = [c.value for row in ws.iter_rows(min_row=2) for c in row]
        assert "EXP-1" in values
        assert "MOOV AFRICA" in values

    def test_payments_xlsx(self, admin_client, data):
        res = admin_client.get("/api/v1/reports/export/payments/?fmt=xlsx")
        assert res.status_code == 200
        from openpyxl import load_workbook

        ws = load_workbook(io.BytesIO(res.content)).active
        assert ws.title == "Paiements"
        values = [c.value for row in ws.iter_rows(min_row=2) for c in row]
        assert "REF-EXP" in values

    def test_amounts_keep_their_precision(self, admin_client, admin_user):
        lease = LeaseFactory(
            status=LeaseStatus.ACTIVE, rent_unit_price=Decimal("1234.56"),
            billing_interval_months=1, start_date=date(2026, 9, 1), currency="EUR",
        )
        generate_invoice(lease, date(2026, 9, 1), admin_user, invoice_number="EXP-EUR")
        res = admin_client.get("/api/v1/reports/export/invoices/?fmt=xlsx")
        from openpyxl import load_workbook

        ws = load_workbook(io.BytesIO(res.content)).active
        values = [str(c.value) for row in ws.iter_rows(min_row=2) for c in row]
        assert "1234.56" in values

    def test_unknown_format_falls_back_to_csv(self, admin_client, data):
        res = admin_client.get("/api/v1/reports/export/invoices/?fmt=pdf")
        assert "text/csv" in res["Content-Type"]

    def test_both_formats_carry_the_same_rows(self, admin_client, data):
        from openpyxl import load_workbook

        csv_body = admin_client.get("/api/v1/reports/export/invoices/").content.decode("utf-8")
        ws = load_workbook(
            io.BytesIO(admin_client.get("/api/v1/reports/export/invoices/?fmt=xlsx").content)
        ).active
        csv_rows = [l for l in csv_body.strip().splitlines() if l]
        assert len(csv_rows) == ws.max_row


@pytest.mark.django_db
class TestExportPermissions:
    def test_anonymous_is_rejected(self, api_client, data):
        """The original bug: a plain <a href> sends no token and gets this."""
        assert api_client.get("/api/v1/reports/export/invoices/").status_code == 401

    @pytest.mark.parametrize("client_name", ["agent_client", "readonly_client"])
    def test_non_finance_roles_are_rejected(self, request, client_name, data):
        client = request.getfixturevalue(client_name)
        assert client.get("/api/v1/reports/export/invoices/").status_code == 403

    def test_accountant_can_export(self, accountant_client, data):
        assert accountant_client.get("/api/v1/reports/export/invoices/?fmt=xlsx").status_code == 200
