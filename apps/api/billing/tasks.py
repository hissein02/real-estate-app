import logging

from celery import shared_task
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()


def _get_system_user():
    """Get or create a system user for automated tasks."""
    user, _ = User.objects.get_or_create(
        username="system",
        defaults={
            "email": "system@realestate.local",
            "is_active": False,
            "role": "admin",
        },
    )
    return user


@shared_task(name="billing.tasks.generate_due_invoices")
def generate_due_invoices():
    """Generate all invoices due today for active leases."""
    from billing.services.invoice_service import generate_due_invoices_for_all_active_leases

    actor = _get_system_user()
    generated = generate_due_invoices_for_all_active_leases(actor)
    logger.info("Generated %d invoices", len(generated))
    return {"generated": len(generated)}


@shared_task(name="billing.tasks.generate_late_fees")
def generate_late_fees():
    """Generate late fee invoices for all overdue invoices past their grace period."""
    from billing.models import Invoice, InvoiceStatus
    from billing.services.invoice_service import generate_late_fee_for_invoice
    from django.utils import timezone

    today = timezone.now().date()
    actor = _get_system_user()

    overdue = (
        Invoice.objects.filter(due_date__lt=today)
        .exclude(status__in=[InvoiceStatus.PAID, InvoiceStatus.VOID])
        .select_related("lease")
    )

    count = 0
    for invoice in overdue:
        try:
            result = generate_late_fee_for_invoice(invoice, actor)
            if result:
                count += 1
        except Exception:
            logger.exception("Failed to generate late fee for invoice %s", invoice.pk)

    logger.info("Generated %d late fee invoices", count)
    return {"generated": count}
