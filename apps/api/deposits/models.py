from decimal import Decimal

from django.conf import settings
from django.db import models


class DepositTransactionType(models.TextChoices):
    RECEIVED = "received", "Received"
    REFUNDED = "refunded", "Refunded"
    APPLIED = "applied", "Applied to Arrears"
    ADJUSTMENT = "adjustment", "Adjustment"


class DepositTransaction(models.Model):
    lease = models.ForeignKey(
        "tenants.Lease",
        on_delete=models.PROTECT,
        related_name="deposit_transactions",
    )
    transaction_type = models.CharField(max_length=20, choices=DepositTransactionType.choices)
    # Signed amount: positive = money in (received), negative = money out (refunded/applied)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    date = models.DateField()
    notes = models.TextField(blank=True)
    reference_invoice = models.ForeignKey(
        "billing.Invoice",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="deposit_transactions",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="deposit_transactions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"Deposit {self.transaction_type} {self.amount} for Lease#{self.lease_id}"
