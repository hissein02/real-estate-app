import calendar
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from dateutil.relativedelta import relativedelta
from django.db import transaction

from audit.models import AuditLog, AuditAction
from .models import Lease, LeaseStatus, BillingCycleAnchor


def get_next_invoice_period_start(lease: Lease) -> Optional[date]:
    """
    Returns the period_start for the next invoice to be generated, or None if none is due.
    Invoices are due in advance: a period_start invoice should be generated when today >= period_start.
    """
    if lease.status != LeaseStatus.ACTIVE:
        return None

    today = date.today()

    # If lease has a fixed end date already in the past, no more invoices
    if lease.end_date and lease.end_date < today:
        return None

    from billing.models import Invoice, InvoiceStatus, InvoiceLineType

    # Last non-void rent invoice (exclude deposit-only invoices)
    last_rent_invoice = (
        Invoice.objects.filter(lease=lease)
        .exclude(status=InvoiceStatus.VOID)
        .filter(lines__line_type=InvoiceLineType.RENT)
        .order_by("-period_start")
        .first()
    )

    # Last non-void stub invoice (prorated first period)
    last_stub_invoice = (
        Invoice.objects.filter(lease=lease, is_prorated=True)
        .exclude(status=InvoiceStatus.VOID)
        .order_by("-period_start")
        .first()
    )

    if last_rent_invoice is None and last_stub_invoice is None:
        # No invoices yet – determine first billing date
        if lease.billing_cycle_anchor == BillingCycleAnchor.LEASE_START:
            candidate = lease.start_date
        else:  # MONTH_START
            if lease.prorate_first_period and lease.start_date.day != 1:
                # Stub invoice first
                candidate = lease.start_date
            else:
                candidate = lease.start_date.replace(day=1)
    elif last_stub_invoice and last_rent_invoice is None:
        # Stub was generated; next is the first full-month invoice
        next_month_first = lease.start_date.replace(day=1) + relativedelta(months=1)
        candidate = next_month_first
    else:
        # Normal next period
        assert last_rent_invoice is not None
        candidate = last_rent_invoice.period_end + timedelta(days=1)

    if candidate > today:
        return None

    # Don't go past lease end date
    if lease.end_date and candidate > lease.end_date:
        return None

    return candidate


def activate_lease(lease: Lease, actor) -> Lease:
    """Transition a lease from DRAFT to ACTIVE and generate initial invoices."""
    if lease.status != LeaseStatus.DRAFT:
        raise ValueError(f"Cannot activate lease in status '{lease.status}'.")

    with transaction.atomic():
        lease.status = LeaseStatus.ACTIVE
        lease.save(update_fields=["status", "updated_at"])

        AuditLog.objects.create(
            actor=actor,
            action=AuditAction.UPDATE,
            object_type="Lease",
            object_id=str(lease.pk),
            object_repr=str(lease),
            reason="Lease activated",
        )

        # Generate deposit invoice if applicable
        from billing.services.invoice_service import generate_deposit_invoice, generate_stub_invoice
        generate_deposit_invoice(lease, actor)
        generate_stub_invoice(lease, actor)

    return lease


def terminate_lease(lease: Lease, reason: str, termination_date: date, actor) -> Lease:
    """Terminate an active lease."""
    if lease.status != LeaseStatus.ACTIVE:
        raise ValueError(f"Cannot terminate lease in status '{lease.status}'.")

    with transaction.atomic():
        lease.status = LeaseStatus.TERMINATED
        lease.end_date = termination_date
        lease.notes = f"{lease.notes}\n[TERMINATED {termination_date}] {reason}".strip()
        lease.save(update_fields=["status", "end_date", "notes", "updated_at"])

        AuditLog.objects.create(
            actor=actor,
            action=AuditAction.TERMINATE_LEASE,
            object_type="Lease",
            object_id=str(lease.pk),
            object_repr=str(lease),
            reason=reason,
        )

    return lease


def renew_lease(
    lease: Lease,
    new_end_date: Optional[date],
    new_rent_unit_price: Optional[Decimal],
    actor,
) -> Lease:
    """Create a new lease as a renewal of the expiring one."""
    if lease.status not in (LeaseStatus.ACTIVE, LeaseStatus.EXPIRED):
        raise ValueError(f"Cannot renew lease in status '{lease.status}'.")

    with transaction.atomic():
        # Expire the old lease
        old_end = lease.end_date or date.today()
        lease.status = LeaseStatus.EXPIRED
        lease.save(update_fields=["status", "updated_at"])

        new_start = old_end + timedelta(days=1)
        new_lease = Lease.objects.create(
            unit=lease.unit,
            tenant=lease.tenant,
            status=LeaseStatus.ACTIVE,
            start_date=new_start,
            end_date=new_end_date,
            rent_unit_price=new_rent_unit_price if new_rent_unit_price is not None else lease.rent_unit_price,
            currency=lease.currency,
            billing_interval_months=lease.billing_interval_months,
            billing_cycle_anchor=lease.billing_cycle_anchor,
            prorate_first_period=lease.prorate_first_period,
            deposit_amount=lease.deposit_amount,
            late_fee_type=lease.late_fee_type,
            late_fee_value=lease.late_fee_value,
            late_fee_grace_period_days=lease.late_fee_grace_period_days,
            renewed_from=lease,
            created_by=actor,
        )

        AuditLog.objects.create(
            actor=actor,
            action=AuditAction.RENEW_LEASE,
            object_type="Lease",
            object_id=str(new_lease.pk),
            object_repr=str(new_lease),
            reason=f"Renewed from lease #{lease.pk}",
        )

    return new_lease


def get_lease_deletion_plan(lease: Lease) -> dict:
    """Count every record a force delete of this lease would destroy.

    Used to show the operator exactly what they are about to lose before they
    confirm. Rows that cascade on their own (invoice lines, attachments) are
    counted too so the total is honest.
    """
    from django.db.models import Q

    from billing.models import Allocation, Invoice, InvoiceLine, Payment
    from deposits.models import DepositTransaction

    invoices = Invoice.objects.filter(lease=lease)
    payments = Payment.objects.filter(lease=lease)
    allocations = Allocation.objects.filter(
        Q(invoice__in=invoices) | Q(payment__in=payments)
    ).distinct()

    counts = {
        "invoice": invoices.count(),
        "payment": payments.count(),
        "allocation": allocations.count(),
        "deposit transaction": DepositTransaction.objects.filter(lease=lease).count(),
        "invoice line": InvoiceLine.objects.filter(invoice__in=invoices).count(),
    }
    return {
        "lease_id": lease.pk,
        "lease_repr": str(lease),
        "will_delete": {k: v for k, v in counts.items() if v},
        "total": sum(counts.values()),
    }


def force_delete_lease(lease: Lease, actor, reason: str = "") -> dict:
    """Delete a lease together with every financial record attached to it.

    The normal delete is blocked by PROTECT on purpose — posted invoices and
    payments are financial records and should be voided, not removed. This is
    the deliberate escape hatch for test data and mistaken entries: it snapshots
    everything to the audit log first, then deletes in dependency order.
    """
    from django.db.models import Q

    from audit.models import AuditAction, AuditLog
    from billing.models import Allocation, Invoice, Payment
    from billing.serializers import (
        AllocationSerializer,
        InvoiceDetailSerializer,
        PaymentSerializer,
    )
    from core.snapshots import to_jsonable
    from deposits.models import DepositTransaction
    from deposits.serializers import DepositTransactionSerializer
    from .serializers import LeaseSerializer

    plan = get_lease_deletion_plan(lease)

    with transaction.atomic():
        invoices = Invoice.objects.filter(lease=lease)
        payments = Payment.objects.filter(lease=lease)
        allocations = Allocation.objects.filter(
            Q(invoice__in=invoices) | Q(payment__in=payments)
        ).distinct()
        deposits = DepositTransaction.objects.filter(lease=lease)

        # Capture everything before any of it disappears.
        snapshot = to_jsonable(
            {
                "lease": LeaseSerializer(lease).data,
                "invoices": InvoiceDetailSerializer(invoices, many=True).data,
                "payments": PaymentSerializer(payments, many=True).data,
                "allocations": AllocationSerializer(allocations, many=True).data,
                "deposit_transactions": DepositTransactionSerializer(deposits, many=True).data,
            }
        )
        lease_repr = str(lease)
        lease_id = str(lease.pk)

        # Dependency order: allocations hold invoices AND payments; deposits hold
        # the lease. Invoice lines and attachments cascade on their own.
        allocations.delete()
        deposits.delete()
        invoices.delete()
        payments.delete()
        lease.delete()

        AuditLog.objects.create(
            actor=actor,
            action=AuditAction.HARD_DELETE,
            object_type="Lease",
            object_id=lease_id,
            object_repr=lease_repr,
            snapshot_json=snapshot,
            reason=reason or "Force delete (lease and all attached records)",
        )

    return plan
