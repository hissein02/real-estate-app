import calendar
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from dateutil.relativedelta import relativedelta


class Tenant(models.Model):
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    company_name = models.CharField(max_length=200, blank=True)
    is_company = models.BooleanField(default=False)
    email = models.EmailField()
    phone = models.CharField(max_length=50, blank=True)
    id_number = models.CharField(max_length=100, blank=True)
    address = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["last_name", "first_name", "company_name"]

    @property
    def display_name(self):
        if self.is_company:
            return self.company_name or f"Company #{self.pk}"
        return f"{self.first_name} {self.last_name}".strip() or f"Tenant #{self.pk}"

    def __str__(self):
        return self.display_name


class Currency(models.TextChoices):
    XAF = "XAF", "CFA Franc BEAC"
    EUR = "EUR", "Euro"
    USD = "USD", "US Dollar"


class BillingCycleAnchor(models.TextChoices):
    LEASE_START = "lease_start", "Lease start date (rolling)"
    MONTH_START = "month_start", "1st of month (calendar)"


class LateFeeType(models.TextChoices):
    NONE = "none", "No late fee"
    FIXED = "fixed", "Fixed amount"
    PERCENTAGE = "percentage", "Percentage of rent"


class LeaseStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    ACTIVE = "active", "Active"
    EXPIRED = "expired", "Expired"
    TERMINATED = "terminated", "Terminated"


class Lease(models.Model):
    unit = models.ForeignKey(
        "portfolio.Unit",
        on_delete=models.PROTECT,
        related_name="leases",
    )
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name="leases")

    # Status
    status = models.CharField(
        max_length=20,
        choices=LeaseStatus.choices,
        default=LeaseStatus.DRAFT,
    )

    # Dates
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)

    # Billing
    # Unit price: what one month of this lease costs. The amount billed for a
    # period is this multiplied by billing_interval_months (the line quantity),
    # which is what keeps invoice lines expressible as qty x unit price.
    rent_unit_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Rent for one month. Billed amount = this x billing interval.",
    )
    currency = models.CharField(max_length=3, choices=Currency.choices, default=Currency.XAF)
    billing_interval_months = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
    )
    billing_cycle_anchor = models.CharField(
        max_length=20,
        choices=BillingCycleAnchor.choices,
        default=BillingCycleAnchor.LEASE_START,
    )
    prorate_first_period = models.BooleanField(
        default=False,
        help_text="Only relevant when anchor=month_start and start_date is not the 1st.",
    )

    # Deposit
    deposit_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
    )

    # Late fees
    late_fee_type = models.CharField(
        max_length=20,
        choices=LateFeeType.choices,
        default=LateFeeType.NONE,
    )
    late_fee_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    late_fee_grace_period_days = models.PositiveIntegerField(default=0)

    # Renewal chain
    renewed_from = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="renewals",
    )

    # Audit
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_leases",
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def rent_period_total(self):
        """Amount invoiced for one billing period: unit price x quantity."""
        return self.rent_unit_price * self.billing_interval_months

    @property
    def monthly_rent_equivalent(self):
        """Kept for the API surface; with a monthly unit price these are the same."""
        return self.rent_unit_price

    def __str__(self):
        return f"Lease #{self.pk} \u2013 {self.tenant.display_name} @ {self.unit}"
