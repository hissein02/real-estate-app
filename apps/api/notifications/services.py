import logging
from datetime import date, timedelta

from django.core.mail import EmailMessage
from django.conf import settings
from django.utils import timezone

from notifications.models import Notification, NotificationType, NotificationStatus

logger = logging.getLogger(__name__)


def _load_template(notification_type: str):
    """Load a NotificationTemplate from DB, or return None to fall back."""
    try:
        from settings_app.models import NotificationTemplate

        return NotificationTemplate.objects.get(
            notification_type=notification_type
        )
    except Exception:
        return None


def _fmt():
    """Lazy-import formatting helpers from settings_app."""
    from settings_app.services import format_amount, format_currency, format_date
    return format_date, format_amount, format_currency


def lease_location_context(lease) -> dict:
    """Property / unit / address variables, shared by every lease-related template.

    Every context passed to .format() must carry these keys: a template using a
    variable the context lacks raises KeyError and silently falls back to the
    built-in default, so the operator's edit would appear to be ignored.
    """
    unit = lease.unit
    building = unit.building
    return {
        "property_name": building.name,
        "unit_name": unit.name,
        "property_address": building.full_address,
    }


def _render(template, context: dict, fallback_subject: str, fallback_body: str):
    """Render subject/body from DB template or fall back to hardcoded strings."""
    if template:
        try:
            return (
                template.subject_template.format(**context),
                template.body_template.format(**context),
            )
        except (KeyError, IndexError):
            logger.warning(
                "Template rendering failed for %s, using fallback",
                template.notification_type,
            )
    return fallback_subject, fallback_body


def _send_notification(notification: Notification) -> bool:
    """Send the notification email. Returns True on success."""
    try:
        # Load runtime email settings from DB so SMTP changes
        # take effect in the worker process without restart.
        try:
            from settings_app.models import EmailSettings
            email_settings = EmailSettings.load()
            email_settings.apply_to_django_settings()
            reply_to = [email_settings.reply_to_email] if email_settings.reply_to_email else []
        except Exception:
            reply_to = []  # Fall back to django.conf.settings defaults

        msg = EmailMessage(
            subject=notification.subject,
            body=notification.body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[notification.recipient_email],
            reply_to=reply_to,
        )
        msg.content_subtype = "html"
        msg.send(fail_silently=False)
        notification.status = NotificationStatus.SENT
        notification.sent_at = timezone.now()
        notification.save(update_fields=["status", "sent_at"])
        return True
    except Exception as e:
        notification.status = NotificationStatus.FAILED
        notification.error_message = str(e)
        notification.save(update_fields=["status", "error_message"])
        logger.exception("Failed to send notification %s", notification.pk)
        return False


def send_rent_reminders(days_before: int = 7) -> int:
    """Send reminders for invoices due in `days_before` days."""
    from billing.models import Invoice, InvoiceStatus

    fmt_date, fmt_amount, fmt_currency = _fmt()

    target_date = date.today() + timedelta(days=days_before)
    invoices = (
        Invoice.objects.filter(due_date=target_date)
        .exclude(status__in=[InvoiceStatus.PAID, InvoiceStatus.VOID])
        .select_related("lease__tenant")
    )

    template = _load_template("rent_reminder")

    sent = 0
    for invoice in invoices:
        tenant = invoice.lease.tenant
        if not tenant.email:
            continue

        # Idempotency check
        if Notification.objects.filter(
            lease=invoice.lease,
            notification_type=NotificationType.RENT_REMINDER,
        ).filter(created_at__date=date.today()).exists():
            continue

        context = {
            "tenant_name": tenant.display_name,
            "invoice_number": invoice.invoice_number,
            "total_amount": fmt_amount(invoice.total_amount),
            "currency": fmt_currency(invoice.currency),
            "due_date": fmt_date(invoice.due_date),
            **lease_location_context(invoice.lease),
        }

        fallback_subject = (
            f"Rent reminder – Invoice {invoice.invoice_number} "
            f"due {fmt_date(invoice.due_date)}"
        )
        fallback_body = (
            f"<p>Dear {tenant.display_name},</p>"
            f"<p>This is a reminder that your rent invoice {invoice.invoice_number} "
            f"for {fmt_amount(invoice.total_amount)} {fmt_currency(invoice.currency)} "
            f"is due on {fmt_date(invoice.due_date)}.</p>"
            f"<p>Please ensure payment is made on time.</p><p>Thank you.</p>"
        )

        subject, body = _render(template, context, fallback_subject, fallback_body)

        content = (
            f"Rent reminder for {tenant.display_name} – "
            f"Invoice {invoice.invoice_number}, "
            f"{fmt_amount(invoice.total_amount)} {fmt_currency(invoice.currency)} "
            f"due {fmt_date(invoice.due_date)}"
        )

        notif = Notification.objects.create(
            lease=invoice.lease,
            notification_type=NotificationType.RENT_REMINDER,
            recipient_email=tenant.email,
            subject=subject,
            body=body,
            content=content,
            triggered_by="System",
        )
        _send_notification(notif)
        if notif.status == NotificationStatus.SENT:
            sent += 1

    return sent


def send_overdue_notices() -> int:
    """Send overdue notices for all overdue invoices."""
    from billing.models import Invoice, InvoiceStatus

    fmt_date, fmt_amount, fmt_currency = _fmt()

    today = date.today()
    overdue = (
        Invoice.objects.filter(due_date__lt=today)
        .exclude(status__in=[InvoiceStatus.PAID, InvoiceStatus.VOID])
        .select_related("lease__tenant")
    )

    template = _load_template("overdue_notice")

    sent = 0
    for invoice in overdue:
        tenant = invoice.lease.tenant
        if not tenant.email:
            continue

        days_overdue = (today - invoice.due_date).days

        if Notification.objects.filter(
            lease=invoice.lease,
            notification_type=NotificationType.OVERDUE_NOTICE,
        ).filter(created_at__date=today).exists():
            continue

        context = {
            "tenant_name": tenant.display_name,
            "invoice_number": invoice.invoice_number,
            "balance": fmt_amount(invoice.balance),
            "currency": fmt_currency(invoice.currency),
            "due_date": fmt_date(invoice.due_date),
            "days_overdue": str(days_overdue),
            **lease_location_context(invoice.lease),
        }

        fallback_subject = (
            f"Overdue invoice – {invoice.invoice_number} "
            f"({days_overdue} days overdue)"
        )
        fallback_body = (
            f"<p>Dear {tenant.display_name},</p>"
            f"<p>Your invoice {invoice.invoice_number} for "
            f"{fmt_amount(invoice.balance)} {fmt_currency(invoice.currency)} "
            f"was due on {fmt_date(invoice.due_date)} and is now "
            f"{days_overdue} day(s) overdue.</p>"
            f"<p>Please make payment immediately to avoid further charges.</p>"
            f"<p>Thank you.</p>"
        )

        subject, body = _render(template, context, fallback_subject, fallback_body)

        content = (
            f"Overdue notice for {tenant.display_name} – "
            f"Invoice {invoice.invoice_number}, "
            f"{fmt_amount(invoice.balance)} {fmt_currency(invoice.currency)} "
            f"({days_overdue} day{'s' if days_overdue != 1 else ''} overdue)"
        )

        notif = Notification.objects.create(
            lease=invoice.lease,
            notification_type=NotificationType.OVERDUE_NOTICE,
            recipient_email=tenant.email,
            subject=subject,
            body=body,
            content=content,
            triggered_by="System",
        )
        _send_notification(notif)
        if notif.status == NotificationStatus.SENT:
            sent += 1

    return sent


def send_lease_expiry_warnings(days_before: int = 30) -> int:
    """Send warnings for leases expiring in `days_before` days."""
    from tenants.models import Lease, LeaseStatus

    fmt_date, _fmt_amount, _fmt_currency = _fmt()

    target_date = date.today() + timedelta(days=days_before)
    expiring = Lease.objects.filter(
        status=LeaseStatus.ACTIVE,
        end_date=target_date,
    ).select_related("tenant")

    template = _load_template("lease_expiry_warning")

    sent = 0
    for lease in expiring:
        tenant = lease.tenant
        if not tenant.email:
            continue

        context = {
            "tenant_name": tenant.display_name,
            "unit": str(lease.unit),
            "end_date": fmt_date(lease.end_date),
            **lease_location_context(lease),
        }

        fallback_subject = f"Your lease expires on {fmt_date(lease.end_date)}"
        fallback_body = (
            f"<p>Dear {tenant.display_name},</p>"
            f"<p>Your lease for {lease.unit} expires on "
            f"{fmt_date(lease.end_date)}.</p>"
            f"<p>Please contact us to discuss renewal options.</p>"
            f"<p>Thank you.</p>"
        )

        subject, body = _render(template, context, fallback_subject, fallback_body)

        content = (
            f"Lease expiry warning for {tenant.display_name} – "
            f"{lease.unit}, expires {fmt_date(lease.end_date)}"
        )

        notif = Notification.objects.create(
            lease=lease,
            notification_type=NotificationType.LEASE_EXPIRY_WARNING,
            recipient_email=tenant.email,
            subject=subject,
            body=body,
            content=content,
            triggered_by="System",
        )
        _send_notification(notif)
        if notif.status == NotificationStatus.SENT:
            sent += 1

    return sent
