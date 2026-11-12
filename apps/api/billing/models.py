import calendar
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from tenants.models import Currency


class InvoiceStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    ISSUED = "issued", "Issued"
    PARTIALLY_PAID = "partially_paid", "Partially Paid"
    PAID = "paid", "Paid"
    VOID = "void", "Void"


class InvoiceLineType(models.TextChoices):
    RENT = "rent", "Rent"
    DEPOSIT = "deposit", "Deposit"
    LATE_FEE = "late_fee", "Late Fee"
    ADJUSTMENT = "adjustment", "Adjustment"
    OTHER = "other", "Other"


class PaymentStatus(models.TextChoices):
    POSTED = "posted", "Posted"
    VOID = "void", "Void"


class PaymentMethod(models.TextChoices):
    CASH = "cash", "Cash"
    BANK_TRANSFER = "bank_transfer", "Bank Transfer"
    CHECK = "check", "Check"
    MOBILE_MONEY = "mobile_money", "Mobile Money"
    OTHER = "other", "Other"


class Invoice(models.Model):
    lease = models.ForeignKey(
        "tenants.Lease",
        on_delete=models.PROTECT,
        related_name="invoices",
    )
    invoice_number = models.CharField(max_length=50, unique=True)
    period_start = models.DateField()
    period_end = models.DateField()
    due_date = models.DateField()
    currency = models.CharField(max_length=3, choices=Currency.choices)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    status = models.CharField(
        max_length=20,
        choices=InvoiceStatus.choices,
        default=InvoiceStatus.ISSUED,
    )
    invoice_date = models.DateField(null=True, blank=True)
    is_prorated = models.BooleanField(default=False)
    proration_details = models.JSONField(null=True, blank=True)
    notes = models.TextField(blank=True)
    pdf_overrides = models.JSONField(
        null=True,
        blank=True,
        default=None,
        help_text="Per-invoice PDF display overrides (signatory, RCCM, NIF, bank display). "
                  "When set, these take precedence over company-level defaults.",
    )
    void_reason = models.TextField(blank=True)
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="voided_invoices",
    )
    voided_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_invoices",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-due_date", "-created_at"]
        indexes = [
            # Arrears / overdue sweeps: filter on due_date, then narrow by status.
            models.Index(fields=["due_date", "status"]),
            # Status-first filters from the invoice list UI and dashboard KPIs.
            models.Index(fields=["status", "due_date"]),
            # Idempotency lookup in generate_invoice().
            models.Index(fields=["lease", "period_start"]),
        ]

    @property
    def balance(self):
        return self.total_amount - self.paid_amount

    @property
    def is_overdue(self):
        return (
            self.status not in (InvoiceStatus.PAID, InvoiceStatus.VOID)
            and self.due_date < timezone.now().date()
            and self.balance > 0
        )

    def __str__(self):
        return f"Invoice {self.invoice_number}"


class InvoiceLine(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")
    line_type = models.CharField(max_length=20, choices=InvoiceLineType.choices)
    description = models.CharField(max_length=500)
    quantity = models.DecimalField(max_digits=8, decimal_places=3, default=Decimal("1"))
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    amount = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        ordering = ["pk"]

    def save(self, *args, **kwargs):
        self.amount = (self.quantity * self.unit_price).quantize(Decimal("0.01"))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.line_type}: {self.description}"


class Payment(models.Model):
    lease = models.ForeignKey(
        "tenants.Lease",
        on_delete=models.PROTECT,
        related_name="payments",
    )
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    currency = models.CharField(max_length=3, choices=Currency.choices)
    payment_date = models.DateField()
    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH,
    )
    reference = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.POSTED,
    )
    void_reason = models.TextField(blank=True)
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="voided_payments",
    )
    voided_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_payments",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-payment_date", "-created_at"]
        indexes = [
            # Lease balance queries exclude void payments.
            models.Index(fields=["lease", "status"]),
            models.Index(fields=["payment_date"]),
        ]

    @property
    def allocated_amount(self):
        return (
            self.allocations.filter(
                invoice__status__in=[
                    InvoiceStatus.ISSUED,
                    InvoiceStatus.PARTIALLY_PAID,
                    InvoiceStatus.PAID,
                ]
            ).aggregate(total=models.Sum("amount"))["total"]
            or Decimal("0")
        )

    @property
    def unallocated_amount(self):
        if self.status == PaymentStatus.VOID:
            return Decimal("0")
        return self.amount - self.allocated_amount

    def __str__(self):
        return f"Payment #{self.pk} - {self.amount} {self.currency} ({self.payment_date})"


class Allocation(models.Model):
    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name="allocations")
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="allocations")
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_allocations",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("payment", "invoice")]
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"Allocation {self.amount} from Payment#{self.payment_id} "
            f"to Invoice#{self.invoice_id}"
        )


class Attachment(models.Model):
    payment = models.ForeignKey(
        Payment,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    invoice = models.ForeignKey(
        Invoice,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    file = models.FileField(upload_to="attachments/%Y/%m/")
    filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="uploaded_attachments",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.filename
