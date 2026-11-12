import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="notifications.tasks.send_rent_reminders")
def send_rent_reminders():
    from notifications.services import send_rent_reminders as _send
    sent = _send(days_before=7)
    logger.info("Sent %d rent reminders", sent)
    return {"sent": sent}


@shared_task(name="notifications.tasks.send_overdue_notices")
def send_overdue_notices():
    from notifications.services import send_overdue_notices as _send
    sent = _send()
    logger.info("Sent %d overdue notices", sent)
    return {"sent": sent}


@shared_task(name="notifications.tasks.send_lease_expiry_warnings")
def send_lease_expiry_warnings():
    from notifications.services import send_lease_expiry_warnings as _send
    sent = _send(days_before=30)
    logger.info("Sent %d lease expiry warnings", sent)
    return {"sent": sent}
