"""
Invoice email rendering and sending service.

Uses the unified template (invoice_unified.html) shared with the PDF renderer.
The NotificationTemplate model provides the configurable subject line.
Display preferences (RCCM, NIF, banks, signatory) come from CompanyInfo.pdf_* fields.

Invoices are sent as PDF attachments with a brief HTML notification body.
"""
import logging

from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string

from settings_app.services import (
    amount_in_words_fr, format_amount, format_currency,
    format_date, format_date_long,
)

logger = logging.getLogger(__name__)

UNIFIED_TEMPLATE = "billing/invoice_unified.html"


# ── Company context helpers ──────────────────────────────────

def _get_email_company_context() -> dict:
    """Load company info for invoice email context.

    Returns logo_url (HTTP URL) – used for the notification record / preview.
    """
    from settings_app.models import CompanyInfo

    info = CompanyInfo.load()
    city_parts = [p for p in [info.city, info.country] if p]

    logo_url = None
    if info.logo:
        try:
            logo_url = info.logo.url
        except Exception:
            logo_url = None

    all_banks = info.bank_accounts or []
    if info.pdf_bank_display == "none":
        pdf_banks = []
    elif info.pdf_bank_display == "selected":
        indices = info.pdf_selected_bank_indices or []
        pdf_banks = [b for i, b in enumerate(all_banks) if i in indices]
    else:
        pdf_banks = all_banks

    signatory_title = ""
    signatory_name = ""
    signatory_image_url = None
    if info.pdf_signatory_id:
        try:
            sig = info.pdf_signatory
            signatory_title = sig.label
            signatory_name = sig.name  # may be empty string
            if sig.signature_image:
                try:
                    signatory_image_url = sig.signature_image.url
                except Exception:
                    pass
        except Exception:
            pass

    return {
        "company_name": info.company_name or info.display_name,
        "company_address": info.address,
        "company_city": ", ".join(city_parts),
        "company_phone": " / ".join(info.phone_numbers) if info.phone_numbers else "",
        "company_email": info.email,
        "logo_src": logo_url,
        "company_bank_accounts": pdf_banks,
        "company_rccm": info.rccm if info.pdf_show_rccm else "",
        "company_nif": info.nif if info.pdf_show_nif else "",
        "company_signatory_title": signatory_title,
        "company_signatory_name": signatory_name,
        "company_signatory_image": signatory_image_url,
    }


def _get_pdf_company_context() -> dict:
    """Load company info for WeasyPrint PDF generation.

    Returns logo_src as a file:// path so WeasyPrint can embed it.
    """
    from settings_app.models import CompanyInfo

    info = CompanyInfo.load()
    city_parts = [p for p in [info.city, info.country] if p]

    logo_src = None
    if info.logo:
        try:
            logo_src = f"file://{info.logo.path}"
        except (NotImplementedError, Exception):
            logo_src = None  # Remote storage (S3) – skip logo in PDF

    all_banks = info.bank_accounts or []
    if info.pdf_bank_display == "none":
        pdf_banks = []
    elif info.pdf_bank_display == "selected":
        indices = info.pdf_selected_bank_indices or []
        pdf_banks = [b for i, b in enumerate(all_banks) if i in indices]
    else:
        pdf_banks = all_banks

    signatory_title = ""
    signatory_name = ""
    signatory_image_src = None
    if info.pdf_signatory_id:
        try:
            sig = info.pdf_signatory
            signatory_title = sig.label
            signatory_name = sig.name  # may be empty string
            if sig.signature_image:
                try:
                    signatory_image_src = f"file://{sig.signature_image.path}"
                except Exception:
                    pass
        except Exception:
            pass

    return {
        "company_name": info.company_name or info.display_name,
        "company_address": info.address,
        "company_city": ", ".join(city_parts),
        "company_phone": " / ".join(info.phone_numbers) if info.phone_numbers else "",
        "company_email": info.email,
        "logo_src": logo_src,
        "company_bank_accounts": pdf_banks,
        "company_rccm": info.rccm if info.pdf_show_rccm else "",
        "company_nif": info.nif if info.pdf_show_nif else "",
        "company_signatory_title": signatory_title,
        "company_signatory_name": signatory_name,
        "company_signatory_image": signatory_image_src,
    }


# ── PDF generation ───────────────────────────────────────────

def _render_invoice_pdf_bytes(invoice) -> bytes | None:
    """PDF bytes for a real invoice, from the same context as the download.

    Built its own context before, which meant the emailed copy ignored the
    invoice's pdf_overrides and truncated cents.
    """
    try:
        from weasyprint import HTML
    except ImportError:
        logger.error("WeasyPrint is not installed – cannot generate PDF attachment")
        return None

    from .invoice_document import render_invoice_document

    html = render_invoice_document(invoice, for_pdf=True)
    try:
        return HTML(string=html).write_pdf()
    except Exception:
        logger.exception("WeasyPrint PDF generation failed for invoice %s", invoice.invoice_number)
        return None


def _render_sample_pdf_bytes(extra_context: dict | None = None) -> bytes | None:
    """Generate a sample PDF for test emails."""
    try:
        from weasyprint import HTML
    except ImportError:
        return None

    pdf_ctx = _get_pdf_company_context()
    context = {
        **SAMPLE_CONTEXT,
        **pdf_ctx,
        "is_pdf": True,
    }
    if extra_context:
        context.update(extra_context)
    html = render_to_string(UNIFIED_TEMPLATE, context)
    try:
        return HTML(string=html).write_pdf()
    except Exception:
        logger.exception("WeasyPrint sample PDF generation failed")
        return None


# ── Brief notification body ──────────────────────────────────

_FALLBACK_BODY = (
    "<p>Bonjour {tenant_name},</p>"
    "<p>Veuillez trouver ci-joint votre facture <strong>{invoice_number}</strong> "
    "d&rsquo;un montant de <strong>{total_amount}&nbsp;{currency}</strong>, "
    "&eacute;ch&eacute;ance le <strong>{due_date}</strong>.</p>"
    "<p>Cordialement,<br><strong>{company_name}</strong></p>"
)


def _render_brief_body(
    tenant_name: str,
    invoice_number: str,
    total_amount: str,
    currency: str,
    due_date: str,
    company_name: str,
    location: dict | None = None,
) -> str:
    """Render the email body from the DB template (invoice_generated), with variable
    substitution. Falls back to the built-in default if the template cannot be loaded."""
    ctx = {
        "tenant_name": tenant_name,
        "invoice_number": invoice_number,
        "total_amount": total_amount,
        "currency": currency,
        "due_date": due_date,
        "company_name": company_name,
        **(location or {}),
    }
    try:
        from settings_app.models import NotificationTemplate
        tpl = NotificationTemplate.objects.get(notification_type="invoice_generated")
        body_html = tpl.body_template.format(**ctx)
    except Exception:
        body_html = _FALLBACK_BODY.format(**ctx)

    return (
        '<html><body style="font-family:sans-serif;color:#333;line-height:1.6;max-width:560px">'
        + body_html
        + "</body></html>"
    )


# ── Subject template ─────────────────────────────────────────

def _get_subject_template() -> str:
    """Load the invoice_generated subject template from the DB."""
    from settings_app.services import TEMPLATE_DEFAULTS

    try:
        from settings_app.models import NotificationTemplate
        tpl = NotificationTemplate.objects.get(
            notification_type="invoice_generated"
        )
        return tpl.subject_template
    except Exception:
        return TEMPLATE_DEFAULTS["invoice_generated"]["subject"]


# ── Sample data for previews ─────────────────────────────────

SAMPLE_LINES = [
    {
        "line_type": "rent",
        "description": "Loyer du 1 Avril 2026 au 30 Avril 2026",
        "quantity": 1,
        "unit_price": "150 000",
        "amount": "150 000",
    },
]

SAMPLE_CONTEXT = {
    "is_pdf": False,
    "invoice_number": "INV-2026-001",
    "issue_date": "1 Avril 2026",
    "due_date": "15 Avril 2026",
    "period_start": "1 Avril 2026",
    "period_end": "30 Avril 2026",
    "tenant_name": "John Doe",
    "unit_name": "Apt 3B",
    "property_name": "Sunrise Residences",
    "property_address": "123 Avenue Charles de Gaulle",
    "property_city": "N'Djaména",
    "currency": "FCFA",
    "total_amount": "150 000",
    "total_in_words": "CENT CINQUANTE MILLE",
    "lines": SAMPLE_LINES,
    "notes": "",
}


def render_invoice_email_preview() -> str:
    """Render the unified template with sample data for preview."""
    company_ctx = _get_email_company_context()
    context = {**SAMPLE_CONTEXT, **company_ctx}
    return render_to_string(UNIFIED_TEMPLATE, context)


def render_invoice_email(invoice) -> tuple[str, str]:
    """Render the email subject and the full HTML body (stored on the Notification record).

    Returns (subject, html_body).
    """
    from settings_app.services import TEMPLATE_DEFAULTS  # noqa: F401

    company_ctx = _get_email_company_context()

    lines = []
    for line in invoice.lines.all():
        if line.line_type == "rent" and invoice.period_start and invoice.period_end:
            description = (
                f"Loyer du {format_date_long(invoice.period_start)} "
                f"au {format_date_long(invoice.period_end)}"
            )
        else:
            description = line.description
        lines.append({
            "line_type": line.line_type,
            "description": description,
            "quantity": int(line.quantity),
            "unit_price": format_amount(int(line.unit_price)),
            "amount": format_amount(int(line.amount)),
        })

    currency_label = format_currency(invoice.currency)

    context = {
        **company_ctx,
        "is_pdf": False,
        "invoice_number": invoice.invoice_number,
        "issue_date": format_date_long(invoice.invoice_date or invoice.created_at.date()),
        "due_date": format_date_long(invoice.due_date) if invoice.due_date else "—",
        "period_start": format_date_long(invoice.period_start) if invoice.period_start else "—",
        "period_end": format_date_long(invoice.period_end) if invoice.period_end else "—",
        "tenant_name": invoice.lease.tenant.display_name,
        "unit_name": invoice.lease.unit.name,
        "property_name": invoice.lease.unit.building.name,
        "property_address": invoice.lease.unit.building.address_line1,
        "property_city": invoice.lease.unit.building.city,
        "currency": currency_label,
        "total_amount": format_amount(int(invoice.total_amount)),
        "total_in_words": amount_in_words_fr(invoice.total_amount),
        "lines": lines,
        "notes": invoice.notes or "",
    }

    html_body = render_to_string(UNIFIED_TEMPLATE, context)

    subject_template = _get_subject_template()
    try:
        subject = subject_template.format(
            invoice_number=invoice.invoice_number,
            company_name=company_ctx["company_name"],
            tenant_name=invoice.lease.tenant.display_name,
            total_amount=format_amount(invoice.total_amount),
            currency=currency_label,
            due_date=format_date(invoice.due_date),
        )
    except (KeyError, IndexError):
        subject = f"Facture {invoice.invoice_number}"

    return subject, html_body


# ── Send functions ───────────────────────────────────────────

def build_invoice_email_draft(invoice) -> dict:
    """Subject and body the tenant would actually receive for this invoice.

    Used to prefill the preview the operator edits before sending, and by the
    send itself when no override is supplied.
    """
    from notifications.services import lease_location_context

    company_ctx = _get_email_company_context()
    currency_label = format_currency(invoice.currency)
    location = lease_location_context(invoice.lease)
    common = {
        "invoice_number": invoice.invoice_number,
        "tenant_name": invoice.lease.tenant.display_name,
        "company_name": company_ctx["company_name"],
        "total_amount": format_amount(invoice.total_amount),
        "currency": currency_label,
        "due_date": format_date_long(invoice.due_date) if invoice.due_date else "—",
    }
    return {
        "subject": _get_subject_template().format(**common, **location),
        "body": _render_brief_body(**common, location=location),
    }


def send_invoice_email(
    invoice,
    recipient_email: str,
    triggered_by: str = "System",
    subject: str | None = None,
    body: str | None = None,
) -> bool:
    """Send the invoice as a PDF attachment with a brief HTML body.

    Also creates a Notification record (body stores the full HTML for audit).
    Pass ``triggered_by`` to record who initiated the send (e.g. "Admin: John Doe").
    """
    from notifications.models import (
        Notification, NotificationType, NotificationStatus,
    )

    try:
        from settings_app.models import EmailSettings
        email_settings = EmailSettings.load()
        email_settings.apply_to_django_settings()
    except Exception:
        email_settings = None

    draft = build_invoice_email_draft(invoice)
    # An operator-edited subject/body wins over the template.
    subject = subject if subject else draft["subject"]
    brief_body = body if body else draft["body"]

    currency_label = format_currency(invoice.currency)
    content = (
        f"Invoice {invoice.invoice_number} for "
        f"{invoice.lease.tenant.display_name} – "
        f"{format_amount(int(invoice.total_amount))} {currency_label}"
    )

    # Store full HTML on the notification record for audit purposes
    notif = Notification.objects.create(
        lease=invoice.lease,
        notification_type=NotificationType.INVOICE_GENERATED,
        recipient_email=recipient_email,
        subject=subject,
        body=brief_body,
        content=content,
        triggered_by=triggered_by,
    )

    try:
        reply_to = [email_settings.reply_to_email] if (email_settings and email_settings.reply_to_email) else []
        msg = EmailMessage(
            subject=subject,
            body=brief_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient_email],
            reply_to=reply_to,
        )
        msg.content_subtype = "html"

        # Attach the PDF
        pdf_bytes = _render_invoice_pdf_bytes(invoice)
        if pdf_bytes:
            msg.attach(f"{invoice.invoice_number}.pdf", pdf_bytes, "application/pdf")
        else:
            logger.warning(
                "PDF generation failed for %s – sending email without attachment",
                invoice.invoice_number,
            )

        msg.send(fail_silently=False)

        notif.status = NotificationStatus.SENT
        from django.utils import timezone
        notif.sent_at = timezone.now()
        notif.save(update_fields=["status", "sent_at"])
        return True
    except Exception as e:
        notif.status = NotificationStatus.FAILED
        notif.error_message = str(e)
        notif.save(update_fields=["status", "error_message"])
        logger.exception("Failed to send invoice email for %s", invoice.invoice_number)
        return False


def send_test_invoice_email(
    recipient_email: str,
    triggered_by: str = "System",
) -> bool:
    """Send a test invoice email with sample data and a sample PDF attachment.

    ``triggered_by`` records who initiated the send in the notification log.
    """
    from notifications.models import Notification, NotificationType, NotificationStatus

    try:
        from settings_app.models import EmailSettings
        email_settings = EmailSettings.load()
        email_settings.apply_to_django_settings()
        reply_to = [email_settings.reply_to_email] if email_settings.reply_to_email else []
    except Exception:
        reply_to = []

    company_ctx = _get_email_company_context()

    subject_template = _get_subject_template()
    sample = {
        "invoice_number": SAMPLE_CONTEXT["invoice_number"],
        "company_name": company_ctx["company_name"],
        "tenant_name": SAMPLE_CONTEXT["tenant_name"],
        "total_amount": SAMPLE_CONTEXT["total_amount"],
        "currency": SAMPLE_CONTEXT["currency"],
        "due_date": SAMPLE_CONTEXT["due_date"],
    }
    try:
        subject = f"[TEST] {subject_template.format(**sample)}"
    except (KeyError, IndexError):
        subject = f"[TEST] Facture {SAMPLE_CONTEXT['invoice_number']}"

    brief_body = _render_brief_body(
        tenant_name=SAMPLE_CONTEXT["tenant_name"],
        invoice_number=SAMPLE_CONTEXT["invoice_number"],
        total_amount=SAMPLE_CONTEXT["total_amount"],
        currency=SAMPLE_CONTEXT["currency"],
        due_date=SAMPLE_CONTEXT["due_date"],
        company_name=company_ctx["company_name"],
    )

    content = (
        f"Test invoice email – Sample data "
        f"({SAMPLE_CONTEXT['invoice_number']}, {SAMPLE_CONTEXT['total_amount']} {SAMPLE_CONTEXT['currency']})"
    )

    # Create notification record before sending (audit trail)
    notif = Notification.objects.create(
        lease=None,  # Test emails have no associated lease
        notification_type=NotificationType.INVOICE_GENERATED,
        recipient_email=recipient_email,
        subject=subject,
        body=brief_body,
        content=content,
        triggered_by=triggered_by,
    )

    try:
        msg = EmailMessage(
            subject=subject,
            body=brief_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient_email],
            reply_to=reply_to,
        )
        msg.content_subtype = "html"

        # Attach sample PDF
        pdf_bytes = _render_sample_pdf_bytes()
        if pdf_bytes:
            msg.attach(f"{SAMPLE_CONTEXT['invoice_number']}.pdf", pdf_bytes, "application/pdf")
        else:
            logger.warning("Sample PDF generation failed – sending test email without attachment")

        msg.send(fail_silently=False)

        notif.status = NotificationStatus.SENT
        from django.utils import timezone
        notif.sent_at = timezone.now()
        notif.save(update_fields=["status", "sent_at"])
    except Exception as e:
        notif.status = NotificationStatus.FAILED
        notif.error_message = str(e)
        notif.save(update_fields=["status", "error_message"])
        logger.exception("Failed to send test invoice email to %s", recipient_email)
        raise

    return True
