"""Payment schedule computation service.

Generates a rent-roll style schedule showing past invoices and projected
future billing periods for all active leases, grouped by property → unit.
"""

import calendar
from datetime import date, timedelta
from decimal import Decimal

from dateutil.relativedelta import relativedelta

from billing.models import Invoice, InvoiceStatus, InvoiceLineType
from tenants.models import Lease, LeaseStatus, BillingCycleAnchor


def _iter_billing_periods(lease: Lease, window_start: date, window_end: date):
    """Yield (period_start, period_end) tuples for a lease within a date window.

    Handles both LEASE_START and MONTH_START anchors, including prorated stubs.
    """
    interval = lease.billing_interval_months

    if lease.billing_cycle_anchor == BillingCycleAnchor.MONTH_START:
        # Possible prorated stub first
        if lease.prorate_first_period and lease.start_date.day != 1:
            stub_start = lease.start_date
            first_of_next = lease.start_date.replace(day=1) + relativedelta(months=1)
            stub_end = first_of_next - timedelta(days=1)
            if stub_end >= window_start and stub_start <= window_end:
                yield stub_start, stub_end, True
            cursor = first_of_next
        else:
            cursor = lease.start_date.replace(day=1)
    else:
        # LEASE_START anchor
        cursor = lease.start_date

    # Generate regular periods
    lease_end = lease.end_date or (window_end + relativedelta(months=6))  # project well past window

    while cursor <= window_end and cursor <= lease_end:
        period_end = cursor + relativedelta(months=interval) - timedelta(days=1)
        if lease.end_date and period_end > lease.end_date:
            period_end = lease.end_date

        if period_end >= window_start:
            yield cursor, period_end, False

        cursor = period_end + timedelta(days=1)


def _get_month_key(dt: date) -> str:
    """Return YYYY-MM string for a date."""
    return dt.strftime("%Y-%m")


def _period_status(invoice, today: date) -> str:
    """Determine display status for a period with an existing invoice."""
    if invoice is None:
        return "future"
    status = invoice.status
    if status == InvoiceStatus.PAID:
        return "paid"
    if status == InvoiceStatus.VOID:
        return "void"
    if status == InvoiceStatus.PARTIALLY_PAID:
        return "partially_paid"
    # ISSUED or DRAFT
    if invoice.due_date < today and invoice.balance > 0:
        return "overdue"
    return "issued"


def compute_payment_schedule(
    months_back: int = 3,
    months_ahead: int = 6,
    property_id: int | None = None,
) -> dict:
    """Compute a full payment schedule for all active leases.

    Returns a dict with:
        - months: list of YYYY-MM strings
        - properties: list of property dicts with nested units and periods
        - summary: aggregated totals
    """
    today = date.today()
    window_start = (today.replace(day=1) - relativedelta(months=months_back))
    window_end = (today.replace(day=1) + relativedelta(months=months_ahead)) - timedelta(days=1)

    # Build month list
    months = []
    cursor = window_start.replace(day=1)
    while cursor <= window_end:
        months.append(_get_month_key(cursor))
        cursor += relativedelta(months=1)

    # Query leases
    leases_qs = (
        Lease.objects.filter(status=LeaseStatus.ACTIVE)
        .select_related("unit__building", "tenant")
    )
    if property_id:
        leases_qs = leases_qs.filter(unit__building_id=property_id)

    # Prefetch all relevant invoices for these leases
    lease_ids = list(leases_qs.values_list("id", flat=True))
    invoices = (
        Invoice.objects.filter(lease_id__in=lease_ids)
        .exclude(status=InvoiceStatus.VOID)
        .filter(lines__line_type=InvoiceLineType.RENT)
        .distinct()
    )
    # Build lookup: (lease_id, period_start) -> invoice
    invoice_map: dict[tuple[int, date], Invoice] = {}
    for inv in invoices:
        invoice_map[(inv.lease_id, inv.period_start)] = inv

    # Group by property
    property_map: dict[int, dict] = {}
    summary = {
        "total_expected": Decimal("0"),
        "total_paid": Decimal("0"),
        "total_overdue": Decimal("0"),
        "total_upcoming": Decimal("0"),
    }

    for lease in leases_qs:
        prop = lease.unit.building
        if prop.id not in property_map:
            property_map[prop.id] = {
                "id": prop.id,
                "name": prop.name,
                "units": [],
            }

        # Generate periods for this lease
        periods = []
        month_set = set()

        for period_start, period_end, is_prorated in _iter_billing_periods(lease, window_start, window_end):
            month_key = _get_month_key(period_start)
            if month_key in month_set:
                continue  # avoid duplicates (stub + full in same month edge case)
            month_set.add(month_key)

            invoice = invoice_map.get((lease.id, period_start))
            status = _period_status(invoice, today)

            if invoice:
                amount = str(invoice.total_amount)
                paid = str(invoice.paid_amount)
                invoice_id = invoice.id
            else:
                # Projected period: quantity x unit price, same as a real invoice.
                amount = str(lease.rent_period_total)
                paid = None
                invoice_id = None
                status = "future"

            periods.append({
                "month": month_key,
                "status": status,
                "amount": amount,
                "paid": paid,
                "invoice_id": invoice_id,
                "is_prorated": is_prorated if invoice is None else (invoice.is_prorated if invoice else False),
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
            })

            # Update summary
            amt = Decimal(amount)
            summary["total_expected"] += amt
            if status == "paid":
                summary["total_paid"] += amt
            elif status == "overdue":
                summary["total_overdue"] += amt
            elif status == "future":
                summary["total_upcoming"] += amt

        # Fill missing months with no_lease
        period_months = {p["month"] for p in periods}
        for m in months:
            if m not in period_months:
                periods.append({
                    "month": m,
                    "status": "no_lease",
                    "amount": None,
                    "paid": None,
                    "invoice_id": None,
                    "is_prorated": False,
                    "period_start": None,
                    "period_end": None,
                })

        # Sort periods by month
        periods.sort(key=lambda p: p["month"])

        property_map[prop.id]["units"].append({
            "unit_id": lease.unit.id,
            "unit_name": lease.unit.name,
            "tenant_name": lease.tenant.display_name,
            # Prefills the recipient field when sending the generated invoice.
            "tenant_email": lease.tenant.email or "",
            # Both figures, so the client never has to infer one from the other.
            "rent_unit_price": str(lease.rent_unit_price),
            "rent_period_total": str(lease.rent_period_total),
            "currency": lease.currency,
            "billing_interval_months": lease.billing_interval_months,
            "lease_id": lease.id,
            "periods": periods,
        })

    # Sort properties by name, units by name
    properties = sorted(property_map.values(), key=lambda p: p["name"])
    for prop in properties:
        prop["units"].sort(key=lambda u: u["unit_name"])

    return {
        "months": months,
        "properties": properties,
        "summary": {k: str(v) for k, v in summary.items()},
    }
