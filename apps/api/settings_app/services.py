import logging
import math
import zoneinfo
from datetime import date
from decimal import Decimal

from django.core.mail import send_mail
from django.conf import settings
from django.utils.html import strip_tags
from django_celery_beat.models import CrontabSchedule, PeriodicTask

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# Formatting helpers (used by notification services too)
# ──────────────────────────────────────────────────────────────
CURRENCY_LABELS = {"XAF": "FCFA", "XOF": "FCFA"}


def format_date(d) -> str:
    """Format a date as DD-MM-YYYY."""
    if isinstance(d, date):
        return d.strftime("%d-%m-%Y")
    return str(d)


FRENCH_MONTHS = [
    "", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
    "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre",
]


def format_date_long(d) -> str:
    """Format a date as '1 Avril 2026' (French long format)."""
    if isinstance(d, date):
        return f"{d.day} {FRENCH_MONTHS[d.month]} {d.year}"
    return str(d)


def amount_in_words_fr(amount) -> str:
    """Convert a numeric amount to French words (uppercase).

    Supports integers up to 999 999 999 999.
    Examples:
        150000 → "CENT CINQUANTE MILLE"
        900000 → "NEUF CENT MILLE"
        1250   → "MILLE DEUX CENT CINQUANTE"
    """
    try:
        n = int(float(amount))
    except (ValueError, TypeError):
        return ""
    if n == 0:
        return "ZÉRO"

    ones = [
        "", "UN", "DEUX", "TROIS", "QUATRE", "CINQ", "SIX", "SEPT",
        "HUIT", "NEUF", "DIX", "ONZE", "DOUZE", "TREIZE", "QUATORZE",
        "QUINZE", "SEIZE", "DIX-SEPT", "DIX-HUIT", "DIX-NEUF",
    ]
    tens = [
        "", "", "VINGT", "TRENTE", "QUARANTE", "CINQUANTE",
        "SOIXANTE", "SOIXANTE", "QUATRE-VINGT", "QUATRE-VINGT",
    ]

    def _under_100(n: int) -> str:
        if n < 20:
            return ones[n]
        if n < 70:
            t, u = divmod(n, 10)
            if u == 1:
                return f"{tens[t]} ET UN"
            return f"{tens[t]}-{ones[u]}" if u else tens[t]
        if n < 80:
            # 70-79: soixante-dix ...
            u = n - 60
            if u == 11:
                return "SOIXANTE ET ONZE"
            return f"SOIXANTE-{ones[u]}"
        # 80-99: quatre-vingt ...
        u = n - 80
        if u == 0:
            return "QUATRE-VINGTS"
        return f"QUATRE-VINGT-{ones[u]}" if u < 20 else f"QUATRE-VINGT-{_under_100(u)}"

    def _under_1000(n: int, strip_plural: bool = False) -> str:
        """Convert 0-999. When strip_plural is True, drop trailing S on
        CENTS / VINGTS (French rule: no plural S before another word)."""
        if n < 100:
            return _under_100(n)
        h, r = divmod(n, 100)
        if h == 1:
            return f"CENT {_under_100(r)}".strip() if r else "CENT"
        prefix = f"{ones[h]} CENT"
        if r == 0:
            return prefix if strip_plural else f"{prefix}S"
        return f"{prefix} {_under_100(r)}"

    parts = []
    billions, n = divmod(n, 1_000_000_000)
    millions, n = divmod(n, 1_000_000)
    thousands, remainder = divmod(n, 1_000)

    if billions:
        b = _under_1000(billions, strip_plural=True)
        parts.append(f"{b} MILLIARD" + ("S" if billions > 1 else ""))
    if millions:
        m = _under_1000(millions, strip_plural=True)
        parts.append(f"{m} MILLION" + ("S" if millions > 1 else ""))
    if thousands:
        if thousands == 1:
            parts.append("MILLE")
        else:
            parts.append(f"{_under_1000(thousands, strip_plural=True)} MILLE")
    if remainder:
        parts.append(_under_1000(remainder))

    return " ".join(parts)


def format_amount(amount) -> str:
    """Format a number with space as thousands separator, no decimals for whole."""
    try:
        num = float(amount) if not isinstance(amount, (int, float)) else amount
    except (ValueError, TypeError):
        return str(amount)
    if num == math.floor(num):
        # Whole number — no decimals
        return f"{int(num):,}".replace(",", " ")
    return f"{num:,.2f}".replace(",", " ")


def format_currency(code: str) -> str:
    """Map currency codes to display labels (XAF → FCFA)."""
    return CURRENCY_LABELS.get(code, code)

# ──────────────────────────────────────────────────────────────
# Task Registry — single source of truth for managed tasks
# ──────────────────────────────────────────────────────────────
TASK_REGISTRY = {
    "generate-invoices-daily": {
        "task_name": "billing.tasks.generate_due_invoices",
        "description": (
            "Generates rent invoices for all active leases whose billing "
            "period is due today. Runs idempotently — existing invoices "
            "are never duplicated."
        ),
        "default_hour": 1,
        "default_minute": 0,
    },
    "generate-late-fees-daily": {
        "task_name": "billing.tasks.generate_late_fees",
        "description": (
            "Generates late fee invoices for all overdue invoices that "
            "have exceeded their grace period. Supports fixed and "
            "percentage-based fee types."
        ),
        "default_hour": 2,
        "default_minute": 0,
    },
    "send-rent-reminders-daily": {
        "task_name": "notifications.tasks.send_rent_reminders",
        "description": (
            "Sends email reminders to tenants whose rent invoices are "
            "due in 7 days. One reminder per lease per day (idempotent)."
        ),
        "default_hour": 8,
        "default_minute": 0,
    },
    "send-lease-expiry-warnings-daily": {
        "task_name": "notifications.tasks.send_lease_expiry_warnings",
        "description": (
            "Sends email warnings to tenants whose lease expires in "
            "30 days, giving them time to discuss renewal or plan "
            "their move-out."
        ),
        "default_hour": 8,
        "default_minute": 30,
    },
    "send-overdue-notices-daily": {
        "task_name": "notifications.tasks.send_overdue_notices",
        "description": (
            "Sends email notices for invoices that are past their due "
            "date. Includes the number of days overdue in the message. "
            "One notice per lease per day."
        ),
        "default_hour": 9,
        "default_minute": 0,
    },
}

# ──────────────────────────────────────────────────────────────
# Email Template Defaults — seeded into NotificationTemplate
# ──────────────────────────────────────────────────────────────
TEMPLATE_DEFAULTS = {
    "rent_reminder": {
        "subject": "Rent reminder – Invoice {invoice_number} due {due_date}",
        "body": (
            "<p>Dear {tenant_name},</p>"
            "<p>This is a reminder that your rent invoice "
            "<strong>{invoice_number}</strong> for "
            "<strong>{total_amount} {currency}</strong> "
            "is due on <strong>{due_date}</strong>.</p>"
            "<p>Please ensure payment is made on time.</p>"
            "<p>Thank you.</p>"
        ),
        "variables": [
            "tenant_name",
            "invoice_number",
            "total_amount",
            "currency",
            "due_date",
            "property_name",
            "unit_name",
            "property_address",
        ],
        "sample_data": {
            "tenant_name": "John Doe",
            "invoice_number": "INV-2026-001",
            "total_amount": "150 000",
            "currency": "FCFA",
            "due_date": "01-04-2026",
            "property_name": "Résidence Les Manguiers",
            "unit_name": "Appartement 3B",
            "property_address": "Avenue Charles de Gaulle, N'Djaména, Tchad",
        },
    },
    "overdue_notice": {
        "subject": "Overdue invoice – {invoice_number} ({days_overdue} days overdue)",
        "body": (
            "<p>Dear {tenant_name},</p>"
            "<p>Your invoice <strong>{invoice_number}</strong> for "
            "<strong>{balance} {currency}</strong> was due on "
            "<strong>{due_date}</strong> and is now "
            "<strong>{days_overdue} day(s) overdue</strong>.</p>"
            "<p>Please make payment immediately to avoid further charges.</p>"
            "<p>Thank you.</p>"
        ),
        "variables": [
            "tenant_name",
            "invoice_number",
            "balance",
            "currency",
            "due_date",
            "days_overdue",
            "property_name",
            "unit_name",
            "property_address",
        ],
        "sample_data": {
            "tenant_name": "John Doe",
            "invoice_number": "INV-2026-001",
            "balance": "150 000",
            "currency": "FCFA",
            "due_date": "01-03-2026",
            "days_overdue": "5",
            "property_name": "Résidence Les Manguiers",
            "unit_name": "Appartement 3B",
            "property_address": "Avenue Charles de Gaulle, N'Djaména, Tchad",
        },
    },
    "lease_expiry_warning": {
        "subject": "Your lease expires on {end_date}",
        "body": (
            "<p>Dear {tenant_name},</p>"
            "<p>Your lease for <strong>{unit}</strong> expires on "
            "<strong>{end_date}</strong>.</p>"
            "<p>Please contact us to discuss renewal options.</p>"
            "<p>Thank you.</p>"
        ),
        "variables": [
            "tenant_name",
            "unit",
            "end_date",
            "property_name",
            "unit_name",
            "property_address",
        ],
        "sample_data": {
            "tenant_name": "John Doe",
            "unit": "Apt 3B – Sunrise Residences",
            "end_date": "01-05-2026",
            "property_name": "Résidence Les Manguiers",
            "unit_name": "Appartement 3B",
            "property_address": "Avenue Charles de Gaulle, N'Djaména, Tchad",
        },
    },
    "invoice_generated": {
        "subject": "Facture {invoice_number} – {company_name}",
        "body": (
            "<p>Bonjour {tenant_name},</p>"
            "<p>Veuillez trouver ci-joint votre facture <strong>{invoice_number}</strong> "
            "d&rsquo;un montant de <strong>{total_amount}&nbsp;{currency}</strong>, "
            "&eacute;ch&eacute;ance le <strong>{due_date}</strong>.</p>"
            "<p>Cordialement,<br><strong>{company_name}</strong></p>"
        ),
        "variables": [
            "tenant_name",
            "invoice_number",
            "total_amount",
            "currency",
            "due_date",
            "company_name",
            "property_name",
            "unit_name",
            "property_address",
        ],
        "sample_data": {
            "tenant_name": "John Doe",
            "invoice_number": "INV-2026-001",
            "total_amount": "150 000",
            "currency": "FCFA",
            "due_date": "01-04-2026",
            "company_name": "Immobilière ABC",
            "property_name": "Résidence Les Manguiers",
            "unit_name": "Appartement 3B",
            "property_address": "Avenue Charles de Gaulle, N'Djaména, Tchad",
        },
    },
}


def _get_or_create_crontab(hour: int, minute: int, timezone_str: str):
    """Get or create a CrontabSchedule for the given hour/minute/tz."""
    tz = zoneinfo.ZoneInfo(timezone_str)
    schedule, _ = CrontabSchedule.objects.get_or_create(
        minute=str(minute),
        hour=str(hour),
        day_of_week="*",
        day_of_month="*",
        month_of_year="*",
        timezone=tz,
    )
    return schedule


def ensure_tasks_exist(timezone_str: str = "Africa/Ndjamena"):
    """
    Seed PeriodicTask rows from the registry if they don't already exist.
    Called on app startup (AppConfig.ready) and on first API list call.
    """
    for task_key, meta in TASK_REGISTRY.items():
        if not PeriodicTask.objects.filter(name=task_key).exists():
            schedule = _get_or_create_crontab(
                meta["default_hour"], meta["default_minute"], timezone_str
            )
            PeriodicTask.objects.create(
                name=task_key,
                task=meta["task_name"],
                crontab=schedule,
                enabled=True,
                description=meta["description"],
            )
            logger.info("Seeded periodic task: %s", task_key)


def ensure_templates_exist():
    """Seed NotificationTemplate rows from TEMPLATE_DEFAULTS if missing.
    Also upgrades plain-text templates to HTML (one-time self-healing).
    """
    from .models import NotificationTemplate

    for ntype, defaults in TEMPLATE_DEFAULTS.items():
        tpl, created = NotificationTemplate.objects.get_or_create(
            notification_type=ntype,
            defaults={
                "subject_template": defaults["subject"],
                "body_template": defaults["body"],
            },
        )
        # Self-heal: upgrade old plain-text body to HTML, or minimal placeholder body
        OLD_MINIMAL = "<p>Veuillez trouver ci-dessous votre facture.</p>"
        if not created and (
            "<p>" not in tpl.body_template
            or tpl.body_template.strip() == OLD_MINIMAL
        ):
            tpl.body_template = defaults["body"]
            tpl.save(update_fields=["body_template"])


def _fix_crontab_timezone(pt, expected_tz_str: str):
    """If a task's crontab timezone doesn't match, update it (self-healing)."""
    if not pt.crontab:
        return
    current_tz = str(pt.crontab.timezone) if pt.crontab.timezone else ""
    if current_tz != expected_tz_str:
        pt.crontab = _get_or_create_crontab(
            int(pt.crontab.hour), int(pt.crontab.minute), expected_tz_str
        )
        pt.save(update_fields=["crontab"])


def list_tasks() -> list[dict]:
    """Return all managed tasks with their current config + metadata."""
    from .models import EmailSettings

    email_settings = EmailSettings.load()
    ensure_tasks_exist(email_settings.task_timezone)

    tasks = []
    for task_key, meta in TASK_REGISTRY.items():
        try:
            pt = PeriodicTask.objects.select_related("crontab").get(
                name=task_key
            )
        except PeriodicTask.DoesNotExist:
            continue

        # Self-heal: fix timezone if it doesn't match current settings
        _fix_crontab_timezone(pt, email_settings.task_timezone)
        pt.refresh_from_db()

        crontab = pt.crontab
        tasks.append(
            {
                "task_key": task_key,
                "task_name": meta["task_name"],
                "description": meta["description"],
                "is_enabled": pt.enabled,
                "hour": int(crontab.hour) if crontab else meta["default_hour"],
                "minute": (
                    int(crontab.minute)
                    if crontab
                    else meta["default_minute"]
                ),
                "periodicity": _describe_periodicity(crontab),
            }
        )
    return tasks


def update_task(
    task_key: str,
    is_enabled: bool | None = None,
    hour: int | None = None,
    minute: int | None = None,
) -> dict:
    """Update a task's enabled state and/or schedule."""
    from .models import EmailSettings

    if task_key not in TASK_REGISTRY:
        raise ValueError(f"Unknown task: {task_key}")

    email_settings = EmailSettings.load()
    pt = PeriodicTask.objects.select_related("crontab").get(name=task_key)

    if is_enabled is not None:
        pt.enabled = is_enabled

    if hour is not None or minute is not None:
        current_hour = int(pt.crontab.hour) if pt.crontab else 0
        current_minute = int(pt.crontab.minute) if pt.crontab else 0
        new_hour = hour if hour is not None else current_hour
        new_minute = minute if minute is not None else current_minute
        pt.crontab = _get_or_create_crontab(
            new_hour, new_minute, email_settings.task_timezone
        )

    pt.save()

    crontab = pt.crontab
    meta = TASK_REGISTRY[task_key]
    return {
        "task_key": task_key,
        "task_name": meta["task_name"],
        "description": meta["description"],
        "is_enabled": pt.enabled,
        "hour": int(crontab.hour),
        "minute": int(crontab.minute),
        "periodicity": _describe_periodicity(crontab),
    }


def get_template(notification_type: str) -> dict:
    """Return a template with its metadata."""
    from .models import NotificationTemplate

    if notification_type not in TEMPLATE_DEFAULTS:
        raise ValueError(f"Unknown notification type: {notification_type}")

    ensure_templates_exist()
    tpl = NotificationTemplate.objects.get(notification_type=notification_type)
    defaults = TEMPLATE_DEFAULTS[notification_type]

    return {
        "notification_type": tpl.notification_type,
        "subject_template": tpl.subject_template,
        "body_template": tpl.body_template,
        "available_variables": defaults["variables"],
        "sample_data": defaults["sample_data"],
    }


def update_template(
    notification_type: str,
    subject_template: str | None = None,
    body_template: str | None = None,
) -> dict:
    """Update an email template."""
    from .models import NotificationTemplate

    if notification_type not in TEMPLATE_DEFAULTS:
        raise ValueError(f"Unknown notification type: {notification_type}")

    ensure_templates_exist()
    tpl = NotificationTemplate.objects.get(notification_type=notification_type)

    if subject_template is not None:
        tpl.subject_template = subject_template
    if body_template is not None:
        tpl.body_template = body_template
    tpl.save()

    defaults = TEMPLATE_DEFAULTS[notification_type]
    return {
        "notification_type": tpl.notification_type,
        "subject_template": tpl.subject_template,
        "body_template": tpl.body_template,
        "available_variables": defaults["variables"],
        "sample_data": defaults["sample_data"],
    }


def send_test_email(notification_type: str, recipient_email: str) -> bool:
    """Render a template with sample data and send it to the given address."""
    from .models import EmailSettings

    if notification_type not in TEMPLATE_DEFAULTS:
        raise ValueError(f"Unknown notification type: {notification_type}")

    # Ensure runtime SMTP settings are loaded
    try:
        EmailSettings.load().apply_to_django_settings()
    except Exception:
        pass

    ensure_templates_exist()
    tpl_data = get_template(notification_type)
    sample = TEMPLATE_DEFAULTS[notification_type]["sample_data"]

    try:
        subject = tpl_data["subject_template"].format(**sample)
        body = tpl_data["body_template"].format(**sample)
    except KeyError as e:
        raise ValueError(f"Template contains unknown variable: {e}")

    subject = f"[TEST] {subject}"

    send_mail(
        subject=subject,
        message=strip_tags(body),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[recipient_email],
        html_message=body,
        fail_silently=False,
    )
    return True


def _describe_periodicity(crontab) -> str:
    """Generate a human-readable periodicity string."""
    if not crontab:
        return "Not scheduled"
    h = str(crontab.hour).zfill(2)
    m = str(crontab.minute).zfill(2)
    tz = str(crontab.timezone) if crontab.timezone else "UTC"
    return f"Every day at {h}:{m} ({tz})"
