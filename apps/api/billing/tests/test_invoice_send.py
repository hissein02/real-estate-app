"""Sending is a separate step from generating."""

import pytest
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from billing.services.invoice_service import generate_invoice, void_invoice
from notifications.models import Notification
from tenants.models import LeaseStatus
from tenants.tests.factories import LeaseFactory


@pytest.fixture
def invoice(admin_user):
    lease = LeaseFactory(
        status=LeaseStatus.ACTIVE, rent_unit_price=Decimal("100000"),
        billing_interval_months=1, start_date=date(2026, 6, 1),
    )
    lease.tenant.email = "locataire@example.td"
    lease.tenant.save(update_fields=["email"])
    return generate_invoice(lease, date(2026, 6, 1), admin_user, invoice_date=date(2026, 6, 1))


@pytest.mark.django_db
class TestGenerationDoesNotSend:
    def test_generate_never_emails(self, admin_client):
        lease = LeaseFactory(
            status=LeaseStatus.ACTIVE, rent_unit_price=Decimal("100000"),
            billing_interval_months=1, start_date=date(2026, 7, 1),
        )
        with patch("billing.services.email_service.send_invoice_email") as sender:
            res = admin_client.post(
                "/api/v1/invoices/generate/",
                {"lease_id": lease.pk, "period_start": "2026-07-01"}, format="json",
            )
        assert res.status_code == 201
        sender.assert_not_called()
        assert "email_sent" not in res.data


@pytest.mark.django_db
class TestSendInvoice:
    def test_sends_to_one_recipient(self, admin_client, invoice):
        with patch("billing.services.email_service.send_invoice_email", return_value=True) as sender:
            res = admin_client.post(
                f"/api/v1/invoices/{invoice.pk}/send/",
                {"recipients": ["locataire@example.td"]}, format="json",
            )
        assert res.status_code == 200
        assert res.data["sent"] == ["locataire@example.td"]
        assert res.data["failed"] == []
        assert sender.call_count == 1

    def test_sends_to_several_recipients(self, admin_client, invoice):
        with patch("billing.services.email_service.send_invoice_email", return_value=True) as sender:
            res = admin_client.post(
                f"/api/v1/invoices/{invoice.pk}/send/",
                {"recipients": ["a@example.td", "b@example.td", "c@example.td"]},
                format="json",
            )
        assert res.status_code == 200
        assert len(res.data["sent"]) == 3
        assert sender.call_count == 3

    def test_duplicate_addresses_are_collapsed(self, admin_client, invoice):
        with patch("billing.services.email_service.send_invoice_email", return_value=True) as sender:
            res = admin_client.post(
                f"/api/v1/invoices/{invoice.pk}/send/",
                {"recipients": ["a@example.td", "A@Example.TD", "a@example.td"]},
                format="json",
            )
        assert sender.call_count == 1, "the same address must not receive it twice"
        assert len(res.data["sent"]) == 1

    def test_partial_failure_is_reported(self, admin_client, invoice):
        def flaky(inv, recipient, **kw):
            return recipient != "bad@example.td"

        with patch("billing.services.email_service.send_invoice_email", side_effect=flaky):
            res = admin_client.post(
                f"/api/v1/invoices/{invoice.pk}/send/",
                {"recipients": ["ok@example.td", "bad@example.td"]}, format="json",
            )
        assert res.status_code == 200
        assert res.data["sent"] == ["ok@example.td"]
        assert res.data["failed"] == ["bad@example.td"]

    def test_total_failure_returns_an_error_status(self, admin_client, invoice):
        with patch("billing.services.email_service.send_invoice_email", return_value=False):
            res = admin_client.post(
                f"/api/v1/invoices/{invoice.pk}/send/",
                {"recipients": ["x@example.td"]}, format="json",
            )
        assert res.status_code == 502
        assert res.data["failed"] == ["x@example.td"]

    def test_an_exception_does_not_abort_the_other_recipients(self, admin_client, invoice):
        def boom(inv, recipient, **kw):
            if recipient == "boom@example.td":
                raise RuntimeError("SMTP down")
            return True

        with patch("billing.services.email_service.send_invoice_email", side_effect=boom):
            res = admin_client.post(
                f"/api/v1/invoices/{invoice.pk}/send/",
                {"recipients": ["boom@example.td", "fine@example.td"]}, format="json",
            )
        assert res.data["sent"] == ["fine@example.td"]
        assert res.data["failed"] == ["boom@example.td"]

    def test_recipients_are_required(self, admin_client, invoice):
        res = admin_client.post(
            f"/api/v1/invoices/{invoice.pk}/send/", {"recipients": []}, format="json"
        )
        assert res.status_code == 400

    def test_invalid_address_is_rejected(self, admin_client, invoice):
        res = admin_client.post(
            f"/api/v1/invoices/{invoice.pk}/send/",
            {"recipients": ["pas-une-adresse"]}, format="json",
        )
        assert res.status_code == 400

    def test_a_void_invoice_cannot_be_sent(self, admin_client, invoice, admin_user):
        void_invoice(invoice, reason="erreur", actor=admin_user)
        res = admin_client.post(
            f"/api/v1/invoices/{invoice.pk}/send/",
            {"recipients": ["a@example.td"]}, format="json",
        )
        assert res.status_code == 400

    def test_the_send_is_recorded_as_a_notification(self, admin_client, invoice):
        before = Notification.objects.count()
        admin_client.post(
            f"/api/v1/invoices/{invoice.pk}/send/",
            {"recipients": ["locataire@example.td"]}, format="json",
        )
        assert Notification.objects.count() > before

    @pytest.mark.parametrize("client_name", ["agent_client", "readonly_client"])
    def test_non_finance_roles_cannot_send(self, request, client_name, invoice):
        client = request.getfixturevalue(client_name)
        res = client.post(
            f"/api/v1/invoices/{invoice.pk}/send/",
            {"recipients": ["a@example.td"]}, format="json",
        )
        assert res.status_code == 403


@pytest.mark.django_db
class TestEmailPreview:
    def test_preview_returns_subject_body_and_default_recipient(self, admin_client, invoice):
        res = admin_client.get(f"/api/v1/invoices/{invoice.pk}/email-preview/")

        assert res.status_code == 200
        assert invoice.invoice_number in res.data["subject"]
        assert res.data["body"].strip() != ""
        assert res.data["default_recipient"] == "locataire@example.td"

    def test_preview_matches_what_would_actually_be_sent(self, admin_client, invoice):
        """Preview and send share one builder, so they cannot drift apart."""
        from billing.services.email_service import build_invoice_email_draft

        res = admin_client.get(f"/api/v1/invoices/{invoice.pk}/email-preview/")
        draft = build_invoice_email_draft(invoice)

        assert res.data["subject"] == draft["subject"]
        assert res.data["body"] == draft["body"]

    def test_preview_changes_nothing(self, admin_client, invoice):
        before = Notification.objects.count()
        admin_client.get(f"/api/v1/invoices/{invoice.pk}/email-preview/")
        assert Notification.objects.count() == before

    @pytest.mark.parametrize("client_name", ["agent_client", "readonly_client"])
    def test_preview_is_finance_only(self, request, client_name, invoice):
        client = request.getfixturevalue(client_name)
        res = client.get(f"/api/v1/invoices/{invoice.pk}/email-preview/")
        assert res.status_code == 403


@pytest.mark.django_db
class TestEditedMessage:
    def test_edited_subject_and_body_are_used(self, admin_client, invoice):
        captured = {}

        def capture(inv, recipient, triggered_by="System", subject=None, body=None):
            captured["subject"], captured["body"] = subject, body
            return True

        with patch("billing.services.email_service.send_invoice_email", side_effect=capture):
            admin_client.post(
                f"/api/v1/invoices/{invoice.pk}/send/",
                {
                    "recipients": ["a@example.td"],
                    "subject": "Votre facture de juin",
                    "body": "<p>Bonjour, veuillez trouver votre facture.</p>",
                },
                format="json",
            )
        assert captured["subject"] == "Votre facture de juin"
        assert captured["body"] == "<p>Bonjour, veuillez trouver votre facture.</p>"

    def test_omitting_them_falls_back_to_the_template(self, admin_client, invoice):
        captured = {}

        def capture(inv, recipient, triggered_by="System", subject=None, body=None):
            captured["subject"], captured["body"] = subject, body
            return True

        with patch("billing.services.email_service.send_invoice_email", side_effect=capture):
            admin_client.post(
                f"/api/v1/invoices/{invoice.pk}/send/",
                {"recipients": ["a@example.td"]}, format="json",
            )
        assert captured["subject"] is None
        assert captured["body"] is None

    def test_the_notification_records_the_edited_body(self, admin_client, invoice):
        admin_client.post(
            f"/api/v1/invoices/{invoice.pk}/send/",
            {"recipients": ["a@example.td"], "subject": "Sujet modifié",
             "body": "<p>Corps modifié</p>"},
            format="json",
        )
        notif = Notification.objects.filter(recipient_email="a@example.td").latest("id")
        assert notif.subject == "Sujet modifié"
        assert "Corps modifié" in notif.body
