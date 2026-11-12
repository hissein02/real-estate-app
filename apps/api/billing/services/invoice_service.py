import calendar
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

import logging

from dateutil.relativedelta import relativedelta
from django.db import IntegrityError, transaction
from django.utils import timezone

from tenants.models import Lease, LeaseStatus, BillingCycleAnchor, LateFeeType
from billing.models import Invoice, InvoiceLine, InvoiceStatus, InvoiceLineType

logger = logging.getLogger(__name__)


INVOICE_NUMBER_PREFIX_FMT = "INV-%Y%m-"
INVOICE_NUMBER_SEQ_WIDTH = 6
INVOICE_NUMBER_MAX_ATTEMPTS = 5


def _next_invoice_number() -> str:
    """Next sequential invoice number for the current month, e.g. INV-202609-000042.

    The sequence restarts per YYYYMM prefix. Numbers are zero-padded to a fixed
    width so lexicographic ordering matches numeric ordering.
    """
    prefix = timezone.now().strftime(INVOICE_NUMBER_PREFIX_FMT)
    last = (
        Invoice.objects.filter(invoice_number__startswith=prefix)
        .order_by("-invoice_number")
        .values_list("invoice_number", flat=True)
        .first()
    )
    seq = 0
    if last:
        try:
            seq = int(last[len(prefix):])
        except ValueError:
            # Legacy or hand-entered number that isn't a plain integer. Fall back
            # to the count for this prefix so the sequence still moves forward.
            seq = Invoice.objects.filter(invoice_number__startswith=prefix).count()
    return f"{prefix}{seq + 1:0{INVOICE_NUMBER_SEQ_WIDTH}d}"


def _create_invoice(**fields) -> Invoice:
    """Create an Invoice, auto-assigning a sequential number when none is given.

    Retries on invoice_number collisions, which two workers generating invoices
    concurrently can produce. An explicitly supplied number is never retried:
    the caller chose it and must see the conflict.
    """
    if fields.get("invoice_number"):
        return Invoice.objects.create(**fields)

    for attempt in range(INVOICE_NUMBER_MAX_ATTEMPTS):
        fields["invoice_number"] = _next_invoice_number()
        try:
            # Savepoint, so a collision rolls back only this INSERT.
            with transaction.atomic():
                return Invoice.objects.create(**fields)
        except IntegrityError as exc:
            if "invoice_number" not in str(exc):
                raise
            if attempt == INVOICE_NUMBER_MAX_ATTEMPTS - 1:
                raise
            logger.warning(
                "Invoice number %s collided, retrying (attempt %d)",
                fields["invoice_number"],
                attempt + 1,
            )


def _money_step(reference: Decimal) -> Decimal:
    """Round to whole units for zero-decimal currencies (XAF), cents otherwise."""
    return Decimal("1") if reference % 1 == 0 else Decimal("0.01")


def _calculate_prorated_amount(monthly_rent: Decimal, period_start: date, period_end: date) -> Decimal:
    """Pro rata for part of one calendar month. `monthly_rent` is a single month."""
    days_in_month = calendar.monthrange(period_start.year, period_start.month)[1]
    stub_days = (period_end - period_start).days + 1
    daily_rate = monthly_rent / Decimal(days_in_month)
    return (daily_rate * Decimal(stub_days)).quantize(
        _money_step(monthly_rent), rounding=ROUND_HALF_UP
    )


def _get_audit_log():
    from audit.models import AuditLog, AuditAction
    return AuditLog, AuditAction


def generate_invoice(lease: Lease, period_start: date, actor, invoice_date: date | None = None, invoice_number: str | None = None) -> Optional[Invoice]:
    """
    Idempotently generate a rent invoice for the given period_start.
    Returns existing invoice if already generated (non-void). Returns None if lease inactive.
    invoice_number: if provided, used as-is; otherwise auto-generated (Celery / seed paths).
    """
    if lease.status != LeaseStatus.ACTIVE:
        return None

    existing = (
        Invoice.objects.filter(lease=lease, period_start=period_start)
        .exclude(status=InvoiceStatus.VOID)
        .filter(lines__line_type=InvoiceLineType.RENT)
        .first()
    )
    if existing:
        return existing

    full_period_end = (
        period_start + relativedelta(months=lease.billing_interval_months) - timedelta(days=1)
    )
    period_end = full_period_end
    # A lease ending mid-period is billed only for the days it actually covers.
    if lease.end_date and period_end > lease.end_date:
        period_end = lease.end_date

    full_days = (full_period_end - period_start).days + 1
    billed_days = (period_end - period_start).days + 1
    is_partial = billed_days < full_days

    if is_partial:
        daily_rate = lease.rent_period_total / Decimal(full_days)
        total_amount = (daily_rate * Decimal(billed_days)).quantize(
            _money_step(lease.rent_period_total), rounding=ROUND_HALF_UP
        )
        line_quantity = Decimal(billed_days)
        line_unit_price = daily_rate.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        line_description = (
            f"Rent (prorated) {period_start.strftime('%d/%m/%Y')} – "
            f"{period_end.strftime('%d/%m/%Y')}"
        )
        details = {
            "reason": "lease_end",
            "full_period_days": full_days,
            "billed_days": billed_days,
            "daily_rate": str(line_unit_price),
            "full_period_rent": str(lease.rent_period_total),
        }
    else:
        total_amount = lease.rent_period_total
        line_quantity = Decimal(lease.billing_interval_months)
        line_unit_price = lease.rent_unit_price
        line_description = (
            f"Rent {period_start.strftime('%d/%m/%Y')} – {period_end.strftime('%d/%m/%Y')}"
        )
        details = None

    AuditLog, AuditAction = _get_audit_log()

    with transaction.atomic():
        invoice = _create_invoice(
            lease=lease,
            invoice_number=invoice_number,
            period_start=period_start,
            period_end=period_end,
            due_date=period_start,
            currency=lease.currency,
            total_amount=total_amount,
            status=InvoiceStatus.ISSUED,
            invoice_date=invoice_date or date.today(),
            is_prorated=is_partial,
            proration_details=details,
            created_by=actor,
        )
        InvoiceLine.objects.create(
            invoice=invoice,
            line_type=InvoiceLineType.RENT,
            description=line_description,
            quantity=line_quantity,
            unit_price=line_unit_price,
            amount=total_amount,
        )
        AuditLog.objects.create(
            actor=actor,
            action=AuditAction.CREATE,
            object_type="Invoice",
            object_id=str(invoice.pk),
            object_repr=str(invoice),
        )

    return invoice


def generate_stub_invoice(lease: Lease, actor) -> Optional[Invoice]:
    """Generate a prorated first-month invoice when anchor=month_start and start_date != 1st."""
    if lease.billing_cycle_anchor != BillingCycleAnchor.MONTH_START:
        return None
    if not lease.prorate_first_period:
        return None
    if lease.start_date.day == 1:
        return None

    stub_start = lease.start_date
    first_of_next = lease.start_date.replace(day=1) + relativedelta(months=1)
    stub_end = first_of_next - timedelta(days=1)

    existing = (
        Invoice.objects.filter(lease=lease, period_start=stub_start, is_prorated=True)
        .exclude(status=InvoiceStatus.VOID)
        .first()
    )
    if existing:
        return existing

    prorated_amount = _calculate_prorated_amount(lease.rent_unit_price, stub_start, stub_end)
    days_in_month = calendar.monthrange(stub_start.year, stub_start.month)[1]
    stub_days = (stub_end - stub_start).days + 1

    AuditLog, AuditAction = _get_audit_log()

    with transaction.atomic():
        invoice = _create_invoice(
            lease=lease,
            period_start=stub_start,
            period_end=stub_end,
            due_date=stub_start,
            currency=lease.currency,
            total_amount=prorated_amount,
            status=InvoiceStatus.ISSUED,
            is_prorated=True,
            proration_details={
                "days_in_month": days_in_month,
                "stub_days": stub_days,
                "daily_rate": str((lease.rent_unit_price / Decimal(days_in_month)).quantize(Decimal("0.01"))),
                "full_month_rent": str(lease.rent_unit_price),
            },
            created_by=actor,
        )
        InvoiceLine.objects.create(
            invoice=invoice,
            line_type=InvoiceLineType.RENT,
            description=f"Rent (prorated) {stub_start.strftime('%d/%m/%Y')} – {stub_end.strftime('%d/%m/%Y')}",
            quantity=Decimal(stub_days),
            unit_price=lease.rent_unit_price / Decimal(days_in_month),
            amount=prorated_amount,
        )
        AuditLog.objects.create(
            actor=actor,
            action=AuditAction.CREATE,
            object_type="Invoice",
            object_id=str(invoice.pk),
            object_repr=str(invoice),
        )

    return invoice


def generate_deposit_invoice(lease: Lease, actor) -> Optional[Invoice]:
    """Generate a deposit invoice if the lease has a deposit amount."""
    if not lease.deposit_amount or lease.deposit_amount <= 0:
        return None

    existing = (
        Invoice.objects.filter(lease=lease)
        .exclude(status=InvoiceStatus.VOID)
        .filter(lines__line_type=InvoiceLineType.DEPOSIT)
        .first()
    )
    if existing:
        return existing

    AuditLog, AuditAction = _get_audit_log()

    with transaction.atomic():
        invoice = _create_invoice(
            lease=lease,
            period_start=lease.start_date,
            period_end=lease.start_date,
            due_date=lease.start_date,
            currency=lease.currency,
            total_amount=lease.deposit_amount,
            status=InvoiceStatus.ISSUED,
            notes="Security deposit",
            created_by=actor,
        )
        InvoiceLine.objects.create(
            invoice=invoice,
            line_type=InvoiceLineType.DEPOSIT,
            description="Security deposit",
            quantity=Decimal("1"),
            unit_price=lease.deposit_amount,
            amount=lease.deposit_amount,
        )
        AuditLog.objects.create(
            actor=actor,
            action=AuditAction.CREATE,
            object_type="Invoice",
            object_id=str(invoice.pk),
            object_repr=str(invoice),
        )

    return invoice


def void_invoice(invoice: Invoice, reason: str, actor) -> Invoice:
    """Void an invoice. Cannot void an invoice with payments allocated to it."""
    if invoice.status == InvoiceStatus.VOID:
        raise ValueError("Invoice is already void.")
    if invoice.paid_amount > 0:
        raise ValueError(
            "Cannot void a partially or fully paid invoice. Reverse allocations first."
        )

    AuditLog, AuditAction = _get_audit_log()

    with transaction.atomic():
        invoice.status = InvoiceStatus.VOID
        invoice.void_reason = reason
        invoice.voided_by = actor
        invoice.voided_at = timezone.now()
        invoice.save(update_fields=["status", "void_reason", "voided_by", "voided_at", "updated_at"])

        AuditLog.objects.create(
            actor=actor,
            action=AuditAction.VOID,
            object_type="Invoice",
            object_id=str(invoice.pk),
            object_repr=str(invoice),
            reason=reason,
        )

    return invoice


def hard_delete_invoice(invoice: Invoice, reason: str, actor) -> None:
    """Admin-only hard delete with full audit snapshot before deletion."""
    from billing.serializers import InvoiceDetailSerializer
    from core.snapshots import to_jsonable

    AuditLog, AuditAction = _get_audit_log()

    with transaction.atomic():
        snapshot = to_jsonable(InvoiceDetailSerializer(invoice).data)
        AuditLog.objects.create(
            actor=actor,
            action=AuditAction.HARD_DELETE,
            object_type="Invoice",
            object_id=str(invoice.pk),
            object_repr=str(invoice),
            snapshot_json=snapshot,
            reason=reason,
        )
        invoice.delete()


def generate_invoice_with_extras(
    lease: Lease, period_start: date, extra_lines: list, notes: str, actor,
    invoice_date: date | None = None, pdf_overrides: dict | None = None,
    invoice_number: str | None = None,
) -> Invoice:
    """
    Generate a rent invoice for the given period and add optional extra lines.
    extra_lines: list of dicts with keys: line_type, description, quantity, unit_price
    pdf_overrides: optional per-invoice PDF display overrides.
    invoice_number: user-supplied number; required for manual generation via API.

    Unlike generate_invoice(), this raises if a rent invoice already exists for the
    period. Silently returning the existing one would discard the caller's
    invoice_number and append their extra lines to an already-issued invoice.
    """
    already_invoiced = (
        Invoice.objects.filter(lease=lease, period_start=period_start)
        .exclude(status=InvoiceStatus.VOID)
        .filter(lines__line_type=InvoiceLineType.RENT)
        .first()
    )
    if already_invoiced:
        raise ValueError(
            f"An invoice already exists for this period: "
            f"{already_invoiced.invoice_number}. Void it first to reissue."
        )

    invoice = generate_invoice(lease, period_start, actor, invoice_date=invoice_date, invoice_number=invoice_number)
    if invoice is None:
        raise ValueError("Cannot generate invoice: lease is not active.")

    # Store PDF overrides if provided
    if pdf_overrides:
        invoice.pdf_overrides = pdf_overrides
        invoice.save(update_fields=["pdf_overrides", "updated_at"])

    if not extra_lines and not notes:
        return invoice

    AuditLog, AuditAction = _get_audit_log()

    with transaction.atomic():
        if notes and not invoice.notes:
            invoice.notes = notes
            invoice.save(update_fields=["notes", "updated_at"])

        for line_data in extra_lines:
            qty = Decimal(str(line_data["quantity"]))
            unit_price = Decimal(str(line_data["unit_price"]))
            amount = (qty * unit_price).quantize(Decimal("0.01"))
            InvoiceLine.objects.create(
                invoice=invoice,
                line_type=line_data["line_type"],
                description=line_data["description"],
                quantity=qty,
                unit_price=unit_price,
                amount=amount,
            )

        if extra_lines:
            from billing.services.allocation_service import _recalculate_invoice_status

            # Recalculate total from all lines
            total = sum(
                line.amount for line in invoice.lines.all()
            )
            invoice.total_amount = total
            # The total moved, so paid_amount may no longer settle the invoice.
            _recalculate_invoice_status(invoice)
            invoice.save(update_fields=["total_amount", "status", "updated_at"])

            AuditLog.objects.create(
                actor=actor,
                action=AuditAction.UPDATE,
                object_type="Invoice",
                object_id=str(invoice.pk),
                object_repr=str(invoice),
            )

    invoice.refresh_from_db()
    return invoice


# A lease can be behind by more than one period: back-dated start date, the
# scheduler disabled for a while, or an outage. Cap the catch-up per lease per
# run so a bad date can never spin forever.
MAX_CATCH_UP_PERIODS = 60


def generate_due_invoices_for_all_active_leases(actor) -> list:
    """Called daily by Celery beat. Generates every invoice that is due.

    Keeps going per lease until nothing further is due, so a lease that is
    several periods behind is brought fully up to date in one run rather than
    one period per night.
    """
    from tenants.services import get_next_invoice_period_start

    today = date.today()
    generated = []

    active_leases = Lease.objects.filter(status=LeaseStatus.ACTIVE).select_related("unit", "tenant")

    for lease in active_leases:
        try:
            for _ in range(MAX_CATCH_UP_PERIODS):
                next_period_start = get_next_invoice_period_start(lease)
                if not next_period_start or next_period_start > today:
                    break
                invoice = generate_invoice(lease, next_period_start, actor)
                if invoice is None:
                    break
                generated.append(invoice)
            else:
                logger.warning(
                    "Lease %s hit the catch-up cap of %d periods in one run; "
                    "check its start date and billing interval.",
                    lease.pk,
                    MAX_CATCH_UP_PERIODS,
                )
        except Exception:
            logger.exception("Failed to generate invoice for lease %s", lease.pk)

    return generated


def generate_late_fee_for_invoice(invoice: Invoice, actor) -> Optional[Invoice]:
    """Generate a late fee invoice for an overdue invoice."""
    lease = invoice.lease

    if lease.late_fee_type == LateFeeType.NONE:
        return None
    if not invoice.is_overdue:
        return None

    days_overdue = (date.today() - invoice.due_date).days
    if days_overdue <= lease.late_fee_grace_period_days:
        return None

    # Check idempotency: one late fee per source invoice
    existing = (
        Invoice.objects.filter(lease=lease, notes=f"late_fee_source_{invoice.pk}")
        .exclude(status=InvoiceStatus.VOID)
        .first()
    )
    if existing:
        return existing

    if lease.late_fee_type == LateFeeType.FIXED:
        late_fee_amount = lease.late_fee_value
    else:
        late_fee_amount = (invoice.balance * lease.late_fee_value / 100).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    if late_fee_amount <= 0:
        return None

    AuditLog, AuditAction = _get_audit_log()

    with transaction.atomic():
        late_fee_invoice = _create_invoice(
            lease=lease,
            period_start=date.today(),
            period_end=date.today(),
            due_date=date.today(),
            currency=lease.currency,
            total_amount=late_fee_amount,
            status=InvoiceStatus.ISSUED,
            notes=f"late_fee_source_{invoice.pk}",
            created_by=actor,
        )
        InvoiceLine.objects.create(
            invoice=late_fee_invoice,
            line_type=InvoiceLineType.LATE_FEE,
            description=f"Late fee for invoice {invoice.invoice_number}",
            quantity=Decimal("1"),
            unit_price=late_fee_amount,
            amount=late_fee_amount,
        )
        AuditLog.objects.create(
            actor=actor,
            action=AuditAction.CREATE,
            object_type="Invoice",
            object_id=str(late_fee_invoice.pk),
            object_repr=str(late_fee_invoice),
        )

    return late_fee_invoice


def update_invoice_dates(
    invoice: Invoice,
    actor,
    invoice_date: date | None = None,
    due_date: date | None = None,
    reason: str = "",
) -> dict:
    """Change an invoice's issue date and/or due date.

    The due date is not cosmetic: it drives overdue status, late-fee accrual,
    the D-7 reminder, overdue notices and the month a figure lands in on the
    reports. The change is audited and the caller is told what it affected.
    """
    if invoice.status == InvoiceStatus.VOID:
        raise ValueError("Cannot change the dates of a void invoice.")

    new_invoice_date = invoice_date if invoice_date is not None else invoice.invoice_date
    new_due_date = due_date if due_date is not None else invoice.due_date

    before = {"invoice_date": str(invoice.invoice_date), "due_date": str(invoice.due_date)}
    was_overdue = invoice.is_overdue

    AuditLog, AuditAction = _get_audit_log()
    today = date.today()
    warnings = []

    with transaction.atomic():
        invoice.invoice_date = new_invoice_date
        invoice.due_date = new_due_date
        invoice.save(update_fields=["invoice_date", "due_date", "updated_at"])
        invoice.refresh_from_db()

        after = {"invoice_date": str(invoice.invoice_date), "due_date": str(invoice.due_date)}

        # A late fee already raised against this invoice is a posted document;
        # moving the due date does not retract it.
        existing_fee = (
            Invoice.objects.filter(lease=invoice.lease, notes=f"late_fee_source_{invoice.pk}")
            .exclude(status=InvoiceStatus.VOID)
            .first()
        )
        if existing_fee and new_due_date > today:
            warnings.append(
                f"A late fee ({existing_fee.invoice_number}) was already raised for this "
                f"invoice. Moving the due date does not cancel it — void it separately "
                f"if it no longer applies."
            )

        if was_overdue and not invoice.is_overdue:
            warnings.append("This invoice is no longer counted as overdue.")
        elif not was_overdue and invoice.is_overdue:
            warnings.append(
                "This invoice is now overdue and may attract a late fee on the next run."
            )

        if new_invoice_date and new_due_date and new_due_date < new_invoice_date:
            warnings.append(
                "The due date falls before the invoice date — normal when billing "
                "a past period, worth a second look otherwise."
            )

        if before["due_date"][:7] != after["due_date"][:7]:
            warnings.append(
                "The due date moved to a different month; dashboard and revenue "
                "figures for both months will change."
            )

        AuditLog.objects.create(
            actor=actor,
            action=AuditAction.UPDATE,
            object_type="Invoice",
            object_id=str(invoice.pk),
            object_repr=str(invoice),
            snapshot_json={"before": before, "after": after},
            reason=reason or "Invoice dates changed",
        )

    return {"before": before, "after": after, "warnings": warnings}
