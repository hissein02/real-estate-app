"""The invoice must be identical wherever it is produced: download, on-screen
preview, and the PDF attached to the e-mail."""

import pytest
from datetime import date
from decimal import Decimal

from billing.services.email_service import _render_invoice_pdf_bytes
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
    info.pdf_signatory = Signatory.objects.create(label="Directeur Général", name="H. Doudou")
    info.save()
    return info


@pytest.fixture
def invoice_with_overrides(db, company, admin_user):
    """An invoice generated with choices that differ from the company defaults."""
    lease = LeaseFactory(
        status=LeaseStatus.ACTIVE, rent_unit_price=Decimal("100000"),
        billing_interval_months=1, start_date=date(2026, 9, 1),
    )
    return generate_invoice_with_extras(
        lease=lease, period_start=date(2026, 9, 1), extra_lines=[], notes="",
        actor=admin_user, invoice_number="DOC-1",
        pdf_overrides={
            "pdf_show_rccm": False,       # company says show
            "pdf_bank_display": "none",   # company says all
            "pdf_signatory_id": None,     # company has one
        },
    )


def _email_pdf_html(invoice, monkeypatch):
    """Capture the HTML the e-mail attachment is rendered from."""
    captured = {}
    import billing.services.invoice_document as doc

    real = doc.render_to_string

    def spy(template, ctx=None, *a, **kw):
        html = real(template, ctx, *a, **kw)
        captured["html"] = html
        return html

    monkeypatch.setattr(doc, "render_to_string", spy)
    _render_invoice_pdf_bytes(invoice)
    html = captured.get("html", "")
    # A silent empty capture would make every "not in html" assertion pass.
    assert html, "the e-mail attachment rendered no HTML — the spy missed it"
    return html


@pytest.mark.django_db
class TestEmailAttachmentHonoursInvoiceOverrides:
    def test_rccm_hidden_by_the_invoice_stays_hidden_in_the_email(
        self, admin_client, invoice_with_overrides, monkeypatch
    ):
        html = _email_pdf_html(invoice_with_overrides, monkeypatch)
        assert "TC-NDJ-287/A/1997" not in html

    def test_bank_details_hidden_by_the_invoice_stay_hidden(
        self, invoice_with_overrides, monkeypatch
    ):
        html = _email_pdf_html(invoice_with_overrides, monkeypatch)
        assert "ORABANK" not in html

    def test_signatory_declined_by_the_invoice_is_absent(
        self, invoice_with_overrides, monkeypatch
    ):
        html = _email_pdf_html(invoice_with_overrides, monkeypatch)
        assert "Directeur Général" not in html

    def test_email_matches_the_downloaded_pdf(
        self, admin_client, invoice_with_overrides, monkeypatch
    ):
        """Strongest check: both documents render from the same HTML."""
        email_html = _email_pdf_html(invoice_with_overrides, monkeypatch)
        for marker in ("TC-NDJ-287/A/1997", "ORABANK", "Directeur Général"):
            in_email = marker in email_html
            preview = admin_client.get(
                f"/api/v1/invoices/{invoice_with_overrides.pk}/preview/"
            ).data["html"]
            assert in_email == (marker in preview), f"{marker} differs between email and document"


@pytest.mark.django_db
class TestEmailAttachmentFormatting:
    def test_cents_are_not_truncated(self, company, admin_user, monkeypatch):
        lease = LeaseFactory(
            status=LeaseStatus.ACTIVE, rent_unit_price=Decimal("1234.56"),
            billing_interval_months=1, start_date=date(2026, 9, 1), currency="EUR",
        )
        inv = generate_invoice_with_extras(
            lease=lease, period_start=date(2026, 9, 1), extra_lines=[], notes="",
            actor=admin_user, invoice_number="DOC-EUR",
        )
        html = _email_pdf_html(inv, monkeypatch)
        assert "1 234.56" in html, "the emailed PDF dropped the cents"
