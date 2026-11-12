from django.conf import settings
from django.db import models


class NotificationType(models.TextChoices):
    RENT_REMINDER = "rent_reminder", "Rent Reminder"
    OVERDUE_NOTICE = "overdue_notice", "Overdue Notice"
    LEASE_EXPIRY_WARNING = "lease_expiry_warning", "Lease Expiry Warning"
    INVOICE_GENERATED = "invoice_generated", "Invoice Generated"
    PAYMENT_RECEIVED = "payment_received", "Payment Received"


class NotificationStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    SENT = "sent", "Sent"
    FAILED = "failed", "Failed"


class Notification(models.Model):
    lease = models.ForeignKey(
        "tenants.Lease",
        on_delete=models.SET_NULL,
        related_name="notifications",
        null=True,
        blank=True,
    )
    notification_type = models.CharField(max_length=30, choices=NotificationType.choices)
    recipient_email = models.EmailField()
    subject = models.CharField(max_length=300, blank=True)
    body = models.TextField(blank=True)
    content = models.TextField(
        blank=True,
        default="",
        help_text="Plain-text summary of the email, displayed in the notification log",
    )
    triggered_by = models.CharField(
        max_length=200,
        blank=True,
        default="",
        help_text="Who triggered the send – e.g. 'System', 'Admin: John Doe'",
    )
    status = models.CharField(
        max_length=20,
        choices=NotificationStatus.choices,
        default=NotificationStatus.PENDING,
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            # Per-invoice idempotency check in the daily notification tasks.
            models.Index(fields=["lease", "notification_type", "created_at"]),
        ]

    def __str__(self):
        return f"{self.notification_type} to {self.recipient_email}"
