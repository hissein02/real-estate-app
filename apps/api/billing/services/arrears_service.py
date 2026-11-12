from datetime import date
from decimal import Decimal

from django.db.models import Sum, F

from billing.models import Invoice, InvoiceStatus, Payment, PaymentStatus
from tenants.models import Lease, LeaseStatus


def get_overdue_invoices(as_of_date: date = None):
    """Return all overdue invoices as of the given date (defaults to today)."""
    if as_of_date is None:
        as_of_date = date.today()

    return (
        Invoice.objects.filter(
            due_date__lt=as_of_date,
        )
        .exclude(status__in=[InvoiceStatus.PAID, InvoiceStatus.VOID])
        .filter(paid_amount__lt=F("total_amount"))
        .select_related("lease__tenant", "lease__unit__building")
        .order_by("due_date")
    )


def get_lease_balance(lease: Lease) -> dict:
    """Financial summary for a lease.

    `balance` is what is still outstanding **on invoices**, i.e. invoiced minus
    what has actually been allocated to them. Money received but not yet
    applied to an invoice is reported separately as `unallocated_credit`.

    Deriving the balance from payments alone used to make a lease look settled
    while its invoices were still open (and still accruing late fees), because
    posting a payment and allocating it are two separate steps.
    """
    today = date.today()

    invoices_qs = Invoice.objects.filter(lease=lease).exclude(status=InvoiceStatus.VOID)
    payments_qs = Payment.objects.filter(lease=lease).exclude(status=PaymentStatus.VOID)

    invoice_agg = invoices_qs.aggregate(total=Sum("total_amount"), allocated=Sum("paid_amount"))
    total_invoiced = invoice_agg["total"] or Decimal("0")
    total_allocated = invoice_agg["allocated"] or Decimal("0")
    total_paid = payments_qs.aggregate(t=Sum("amount"))["t"] or Decimal("0")

    overdue_agg = (
        invoices_qs.filter(due_date__lt=today)
        .exclude(status=InvoiceStatus.PAID)
        .aggregate(total=Sum("total_amount"), paid=Sum("paid_amount"))
    )
    overdue_amount = max(
        Decimal("0"),
        (overdue_agg["total"] or Decimal("0")) - (overdue_agg["paid"] or Decimal("0")),
    )

    return {
        "lease_id": lease.pk,
        "currency": lease.currency,
        "total_invoiced": total_invoiced,
        "total_paid": total_paid,
        "total_allocated": total_allocated,
        "balance": total_invoiced - total_allocated,
        "unallocated_credit": max(Decimal("0"), total_paid - total_allocated),
        "overdue_amount": overdue_amount,
    }


def get_tenant_balance(tenant) -> dict:
    """Aggregate balance across all leases for a tenant."""
    total_invoiced = Decimal("0")
    total_paid = Decimal("0")
    total_allocated = Decimal("0")
    overdue_amount = Decimal("0")
    unallocated_credit = Decimal("0")

    for lease in tenant.leases.all():
        lb = get_lease_balance(lease)
        total_invoiced += lb["total_invoiced"]
        total_paid += lb["total_paid"]
        total_allocated += lb["total_allocated"]
        overdue_amount += lb["overdue_amount"]
        unallocated_credit += lb["unallocated_credit"]

    return {
        "tenant_id": tenant.pk,
        "total_invoiced": total_invoiced,
        "total_paid": total_paid,
        "total_allocated": total_allocated,
        "balance": total_invoiced - total_allocated,
        "unallocated_credit": unallocated_credit,
        "overdue_amount": overdue_amount,
    }


def get_portfolio_arrears_summary() -> dict:
    """Overall portfolio arrears summary."""
    today = date.today()

    overdue_invoices = (
        Invoice.objects.filter(due_date__lt=today)
        .exclude(status__in=[InvoiceStatus.PAID, InvoiceStatus.VOID])
    )

    agg = overdue_invoices.aggregate(
        total=Sum("total_amount"),
        paid=Sum("paid_amount"),
    )
    total_overdue = max(
        Decimal("0"),
        (agg["total"] or Decimal("0")) - (agg["paid"] or Decimal("0")),
    )

    overdue_count = overdue_invoices.count()
    affected_leases = overdue_invoices.values("lease_id").distinct().count()

    return {
        "total_overdue_amount": total_overdue,
        "overdue_invoice_count": overdue_count,
        "affected_lease_count": affected_leases,
        "as_of_date": today,
    }
