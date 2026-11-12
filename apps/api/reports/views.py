import calendar
import csv
import io
from datetime import date, timedelta

from django.http import HttpResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from billing.models import Invoice, InvoiceStatus, Payment, PaymentStatus
from billing.services.arrears_service import get_portfolio_arrears_summary
from tenants.models import Lease, LeaseStatus
from core.permissions import CanManageFinance


class DashboardKPIView(APIView):
    """Extended dashboard KPIs with trends and breakdowns."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.db.models import Sum, Count, Q, F
        from django.db.models.functions import TruncMonth
        from decimal import Decimal
        from portfolio.models import Unit, Property
        from tenants.models import Tenant

        today = date.today()
        month_start = today.replace(day=1)
        last_day = calendar.monthrange(today.year, today.month)[1]
        month_end = today.replace(day=last_day)

        # --- Core KPIs ---
        active_leases = Lease.objects.filter(status=LeaseStatus.ACTIVE).count()

        expiring_30d = Lease.objects.filter(
            status=LeaseStatus.ACTIVE,
            end_date__gte=today,
            end_date__lte=today + timedelta(days=30),
        ).count()

        overdue_invoices = (
            Invoice.objects.filter(due_date__lt=today)
            .exclude(status__in=[InvoiceStatus.PAID, InvoiceStatus.VOID])
        )
        overdue_count = overdue_invoices.count()
        overdue_agg = overdue_invoices.aggregate(
            total=Sum("total_amount"),
            paid=Sum("paid_amount"),
        )
        total_overdue_amount = max(
            Decimal("0"),
            (overdue_agg["total"] or Decimal("0")) - (overdue_agg["paid"] or Decimal("0")),
        )

        # Monthly invoices for the full current month
        month_invoice_agg = (
            Invoice.objects.filter(
                due_date__gte=month_start,
                due_date__lte=month_end,
            )
            .exclude(status=InvoiceStatus.VOID)
            .aggregate(total=Sum("total_amount"), paid=Sum("paid_amount"))
        )
        monthly_invoiced = month_invoice_agg["total"] or Decimal("0")
        monthly_collected = month_invoice_agg["paid"] or Decimal("0")  # actual paid this month

        total_units = Unit.objects.filter(is_active=True).count()
        occupied_units = (
            Unit.objects.filter(is_active=True, leases__status=LeaseStatus.ACTIVE)
            .distinct()
            .count()
        )
        occupancy_rate = (occupied_units / total_units * 100) if total_units else 0

        # Monthly expected rent from active leases
        monthly_expected = (
            Lease.objects.filter(status=LeaseStatus.ACTIVE)
            .aggregate(total=Sum("rent_unit_price"))["total"]
            or Decimal("0")
        )

        # Collection rate: actual paid vs total invoiced this month
        collection_rate = (
            round(float(monthly_collected) / float(monthly_invoiced) * 100, 1)
            if monthly_invoiced > 0 else 0
        )

        tenant_count = Tenant.objects.filter(leases__status=LeaseStatus.ACTIVE).distinct().count()
        property_count = Property.objects.count()

        # --- Revenue Trend (last 12 months, by invoice due_date) ---
        twelve_months_ago = (month_start - timedelta(days=365)).replace(day=1)
        revenue_trend = list(
            Invoice.objects.filter(
                due_date__gte=twelve_months_ago,
            )
            .exclude(status=InvoiceStatus.VOID)
            .annotate(month=TruncMonth("due_date"))
            .values("month")
            .annotate(amount=Sum("total_amount"))
            .order_by("month")
        )
        revenue_trend_data = [
            {"month": str(r["month"])[:10], "amount": str(r["amount"])}
            for r in revenue_trend
        ]

        # --- Year Trend: all 12 months of current year (actual paid + expected/invoiced) ---
        year_invoices = list(
            Invoice.objects
            .filter(due_date__year=today.year)
            .exclude(status=InvoiceStatus.VOID)
            .annotate(month=TruncMonth("due_date"))
            .values("month")
            .annotate(
                expected=Sum("total_amount"),
                actual=Sum("paid_amount"),
            )
            .order_by("month")
        )
        year_by_month = {str(r["month"])[:7]: r for r in year_invoices}
        year_trend_data = []
        for m in range(1, 13):
            key = f"{today.year}-{m:02d}"
            row = year_by_month.get(key, {})
            year_trend_data.append({
                "month": key,
                "expected": str(row.get("expected") or Decimal("0")),
                "actual": str(row.get("actual") or Decimal("0")),
            })

        # --- Month Tenants: invoices due this month ---
        month_invoices_qs = (
            Invoice.objects
            .filter(due_date__gte=month_start, due_date__lte=month_end)
            .exclude(status=InvoiceStatus.VOID)
            .select_related("lease__tenant", "lease__unit__building")
            .order_by("due_date", "lease__tenant__last_name")
        )
        month_tenants_data = [
            {
                "tenant": inv.lease.tenant.display_name,
                "unit": inv.lease.unit.name,
                "property": inv.lease.unit.building.name,
                "amount": str(inv.total_amount),
                "paid": str(inv.paid_amount),
                "balance": str(inv.balance),
                "status": inv.status,
                "is_overdue": inv.is_overdue,
                "due_date": str(inv.due_date),
                "invoice_number": inv.invoice_number,
                "currency": inv.currency,
            }
            for inv in month_invoices_qs
        ]

        # --- Payment Method Breakdown (last 12 months) ---
        method_breakdown = list(
            Payment.objects.filter(payment_date__gte=twelve_months_ago)
            .exclude(status=PaymentStatus.VOID)
            .values("payment_method")
            .annotate(total=Sum("amount"), count=Count("id"))
            .order_by("-total")
        )
        payment_methods = [
            {"method": m["payment_method"], "amount": str(m["total"]), "count": m["count"]}
            for m in method_breakdown
        ]

        # --- Invoice Status Distribution ---
        status_counts = dict(
            Invoice.objects.exclude(status=InvoiceStatus.VOID)
            .values_list("status")
            .annotate(c=Count("id"))
            .values_list("status", "c")
        )
        invoice_statuses = {
            "draft": status_counts.get(InvoiceStatus.DRAFT, 0),
            "issued": status_counts.get(InvoiceStatus.ISSUED, 0),
            "partially_paid": status_counts.get(InvoiceStatus.PARTIALLY_PAID, 0),
            "paid": status_counts.get(InvoiceStatus.PAID, 0),
            "overdue": overdue_count,
        }

        # --- Top Properties by Revenue (last 12 months) ---
        top_properties = list(
            Payment.objects.filter(payment_date__gte=twelve_months_ago)
            .exclude(status=PaymentStatus.VOID)
            .values(
                property_name=F("lease__unit__building__name"),
                property_id=F("lease__unit__building_id"),
            )
            .annotate(revenue=Sum("amount"))
            .order_by("-revenue")[:5]
        )
        top_props_data = []
        for tp in top_properties:
            prop_units = Unit.objects.filter(building_id=tp["property_id"], is_active=True).count()
            prop_occupied = (
                Unit.objects.filter(
                    building_id=tp["property_id"],
                    is_active=True,
                    leases__status=LeaseStatus.ACTIVE,
                ).distinct().count()
            )
            top_props_data.append({
                "name": tp["property_name"],
                "revenue": str(tp["revenue"]),
                "total_units": prop_units,
                "occupied_units": prop_occupied,
            })

        return Response({
            "active_leases": active_leases,
            "expiring_30d": expiring_30d,
            "overdue_invoice_count": overdue_count,
            "total_overdue_amount": str(total_overdue_amount),
            "monthly_collected": str(monthly_collected),
            "monthly_invoiced": str(monthly_invoiced),
            "monthly_expected": str(monthly_expected.quantize(Decimal("0.01"))),
            "collection_rate": collection_rate,
            "total_units": total_units,
            "occupied_units": occupied_units,
            "occupancy_rate": round(occupancy_rate, 1),
            "tenant_count": tenant_count,
            "property_count": property_count,
            "revenue_trend": revenue_trend_data,
            "year_trend": year_trend_data,
            "month_tenants": month_tenants_data,
            "payment_methods": payment_methods,
            "invoice_statuses": invoice_statuses,
            "top_properties": top_props_data,
        })


class ArrearsReportView(APIView):
    """Detailed arrears report."""
    permission_classes = [IsAuthenticated, CanManageFinance]

    def get(self, request):
        summary = get_portfolio_arrears_summary()
        summary["total_overdue_amount"] = str(summary["total_overdue_amount"])
        summary["as_of_date"] = str(summary["as_of_date"])

        today = date.today()
        overdue_invoices = (
            Invoice.objects.filter(due_date__lt=today)
            .exclude(status__in=[InvoiceStatus.PAID, InvoiceStatus.VOID])
            .select_related("lease__tenant", "lease__unit__building")
            .order_by("due_date")
        )

        items = []
        for inv in overdue_invoices:
            items.append({
                "invoice_number": inv.invoice_number,
                "tenant": inv.lease.tenant.display_name,
                "unit": str(inv.lease.unit),
                "due_date": str(inv.due_date),
                "days_overdue": (today - inv.due_date).days,
                "total_amount": str(inv.total_amount),
                "paid_amount": str(inv.paid_amount),
                "balance": str(inv.balance),
                "currency": inv.currency,
            })

        return Response({**summary, "items": items})


# ── Exports ──────────────────────────────────────────────────
EXPORT_ROW_CAP = 10000


def _csv_response(headers, rows, filename):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(rows)
    # BOM so Excel opens accented text correctly instead of mojibake.
    response = HttpResponse("\ufeff" + output.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}.csv"'
    return response


def _xlsx_response(headers, rows, filename, sheet_title):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = sheet_title
    ws.append(headers)

    head_font = Font(bold=True, color="FFFFFF")
    head_fill = PatternFill("solid", fgColor="2D5A73")   # brand primary-600
    for cell in ws[1]:
        cell.font = head_font
        cell.fill = head_fill
        cell.alignment = Alignment(vertical="center")

    for row in rows:
        ws.append(row)

    for i, header in enumerate(headers, start=1):
        longest = max([len(str(header))] + [len(str(r[i - 1])) for r in rows] or [0])
        ws.column_dimensions[get_column_letter(i)].width = min(max(longest + 2, 10), 42)

    ws.freeze_panes = "A2"          # headers stay visible while scrolling
    ws.auto_filter.ref = ws.dimensions

    buffer = io.BytesIO()
    wb.save(buffer)
    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}.xlsx"'
    return response


def _export(request, headers, rows, filename, sheet_title):
    """Serve the same rows as CSV or XLSX, chosen with ?fmt=."""
    if request.query_params.get("fmt", "csv").lower() in ("xlsx", "excel"):
        return _xlsx_response(headers, rows, filename, sheet_title)
    return _csv_response(headers, rows, filename)


class InvoicesCsvExportView(APIView):
    """Export invoices as CSV or Excel."""
    permission_classes = [IsAuthenticated, CanManageFinance]

    def get(self, request):
        invoices = (
            Invoice.objects.select_related("lease__tenant", "lease__unit__building")
            .exclude(status=InvoiceStatus.VOID)
            .order_by("-due_date")[:EXPORT_ROW_CAP]
        )
        headers = [
            "Invoice Number", "Tenant", "Unit", "Property",
            "Invoice Date", "Period Start", "Period End", "Due Date",
            "Total Amount", "Paid Amount", "Balance", "Status", "Currency",
        ]
        rows = [
            [
                inv.invoice_number,
                inv.lease.tenant.display_name,
                inv.lease.unit.name,
                inv.lease.unit.building.name,
                inv.invoice_date or inv.created_at.date(),
                inv.period_start,
                inv.period_end,
                inv.due_date,
                inv.total_amount,
                inv.paid_amount,
                inv.balance,
                inv.status,
                inv.currency,
            ]
            for inv in invoices
        ]
        return _export(request, headers, rows, "invoices", "Factures")


class PaymentScheduleView(APIView):
    """Rent-roll style payment schedule across all active leases."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .services import compute_payment_schedule

        months_ahead = int(request.query_params.get("months", 6))
        months_back = int(request.query_params.get("months_back", 3))
        property_id = request.query_params.get("property")
        property_id = int(property_id) if property_id else None

        schedule = compute_payment_schedule(
            months_back=months_back,
            months_ahead=months_ahead,
            property_id=property_id,
        )
        return Response(schedule)


class PaymentsCsvExportView(APIView):
    """Export payments as CSV or Excel."""
    permission_classes = [IsAuthenticated, CanManageFinance]

    def get(self, request):
        payments = (
            Payment.objects.select_related("lease__tenant", "lease__unit")
            .exclude(status=PaymentStatus.VOID)
            .order_by("-payment_date")[:EXPORT_ROW_CAP]
        )
        headers = [
            "ID", "Tenant", "Unit", "Amount", "Currency",
            "Payment Date", "Method", "Reference", "Notes",
        ]
        rows = [
            [
                p.pk,
                p.lease.tenant.display_name,
                p.lease.unit.name,
                p.amount,
                p.currency,
                p.payment_date,
                p.payment_method,
                p.reference,
                p.notes,
            ]
            for p in payments
        ]
        return _export(request, headers, rows, "payments", "Paiements")
