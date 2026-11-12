"""The on-screen document must match how the invoice was generated."""

import pytest
from datetime import date
from decimal import Decimal

from billing.services.invoice_service import generate_invoice_with_extras
from settings_app.models import CompanyInfo, Signatory
from tenants.models import LeaseStatus
from tenants.tests.factories import LeaseFactory


@pytest.fixture
def company(db):
    info = CompanyInfo.load()
    info.company_name = "Laborde Immobilier"
    info.rccm = "TC-NDJ-287/A/1997"
    info.nif = "9039377A"
    info.bank_accounts = [{"bank_name": "ORABANK", "account_number": "1234567"}]
    info.pdf_show_rccm = True
    info.pdf_show_nif = True
    info.pdf_bank_display = "all"
    info.save()
    return info


@pytest.fixture
def lease(db):
    return LeaseFactory(
        status=LeaseStatus.ACTIVE, rent_unit_price=Decimal("100000"),
        billing_interval_months=1, start_date=date(2026, 8, 1),
    )


def _make(lease, actor, number, **kwargs):
    return generate_invoice_with_extras(
        lease=lease, period_start=date(2026, 8, 1), extra_lines=kwargs.pop("extra_lines", []),
        notes=kwargs.pop("notes", ""), actor=actor, invoice_number=number, **kwargs,
    )


@pytest.mark.django_db
class TestPreviewReflectsGeneration:
    def test_notes_appear_when_the_invoice_has_them(self, admin_client, company, lease, admin_user):
        inv = _make(lease, admin_user, "PRV-1", notes="Paiement par virement uniquement.")
        html = admin_client.get(f"/api/v1/invoices/{inv.pk}/preview/").data["html"]
        assert "Paiement par virement uniquement." in html

    def test_adjustment_lines_appear(self, admin_client, company, lease, admin_user):
        inv = _make(lease, admin_user, "PRV-2", extra_lines=[
            {"line_type": "adjustment", "description": "Nettoyage",
             "quantity": Decimal("2"), "unit_price": Decimal("5000")},
        ])
        html = admin_client.get(f"/api/v1/invoices/{inv.pk}/preview/").data["html"]
        assert "Nettoyage" in html

    def test_signatory_shown_when_the_invoice_selected_one(
        self, admin_client, company, lease, admin_user
    ):
        sig = Signatory.objects.create(label="Directeur Général", name="H. Doudou")
        inv = _make(lease, admin_user, "PRV-3",
                    pdf_overrides={"pdf_signatory_id": sig.pk})
        html = admin_client.get(f"/api/v1/invoices/{inv.pk}/preview/").data["html"]
        assert "Directeur Général" in html
        assert "H. Doudou" in html

    def test_no_signatory_block_when_the_invoice_had_none(
        self, admin_client, company, lease, admin_user
    ):
        sig = Signatory.objects.create(label="Directeur Général", name="H. Doudou")
        company.pdf_signatory = sig
        company.save()
        # This invoice explicitly opted out of a signatory.
        inv = _make(lease, admin_user, "PRV-4", pdf_overrides={"pdf_signatory_id": None})
        html = admin_client.get(f"/api/v1/invoices/{inv.pk}/preview/").data["html"]
        assert "Directeur Général" not in html

    def test_rccm_and_nif_follow_the_invoice_overrides(
        self, admin_client, company, lease, admin_user
    ):
        inv = _make(lease, admin_user, "PRV-5",
                    pdf_overrides={"pdf_show_rccm": False, "pdf_show_nif": True})
        html = admin_client.get(f"/api/v1/invoices/{inv.pk}/preview/").data["html"]
        assert "TC-NDJ-287/A/1997" not in html
        assert "9039377A" in html

    def test_bank_details_hidden_when_the_invoice_said_so(
        self, admin_client, company, lease, admin_user
    ):
        inv = _make(lease, admin_user, "PRV-6", pdf_overrides={"pdf_bank_display": "none"})
        html = admin_client.get(f"/api/v1/invoices/{inv.pk}/preview/").data["html"]
        assert "ORABANK" not in html

    def test_preview_uses_http_urls_not_file_paths(
        self, admin_client, company, lease, admin_user
    ):
        """file:// works for WeasyPrint but renders nothing in a browser."""
        inv = _make(lease, admin_user, "PRV-7")
        html = admin_client.get(f"/api/v1/invoices/{inv.pk}/preview/").data["html"]
        assert "file://" not in html

    def test_preview_and_pdf_are_both_available(self, admin_client, company, lease, admin_user):
        inv = _make(lease, admin_user, "PRV-8")
        assert admin_client.get(f"/api/v1/invoices/{inv.pk}/preview/").status_code == 200
        pdf = admin_client.get(f"/api/v1/invoices/{inv.pk}/pdf/")
        assert pdf.status_code == 200
        assert pdf["Content-Type"] == "application/pdf"

    def test_a_void_invoice_can_still_be_viewed(self, admin_client, company, lease, admin_user):
        """Voided documents must remain inspectable for the audit trail."""
        from billing.services.invoice_service import void_invoice

        inv = _make(lease, admin_user, "PRV-9")
        void_invoice(inv, reason="erreur", actor=admin_user)
        assert admin_client.get(f"/api/v1/invoices/{inv.pk}/preview/").status_code == 200

    @pytest.mark.parametrize("client_name", ["agent_client", "readonly_client"])
    def test_preview_is_finance_only(self, request, client_name, company, lease, admin_user):
        inv = _make(lease, admin_user, "PRV-10")
        client = request.getfixturevalue(client_name)
        assert client.get(f"/api/v1/invoices/{inv.pk}/preview/").status_code == 403
