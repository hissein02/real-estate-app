from django.urls import path

from .views import (
    DashboardKPIView,
    ArrearsReportView,
    PaymentScheduleView,
    InvoicesCsvExportView,
    PaymentsCsvExportView,
)

urlpatterns = [
    path("reports/dashboard/", DashboardKPIView.as_view(), name="report-dashboard"),
    path("reports/arrears/", ArrearsReportView.as_view(), name="report-arrears"),
    path("reports/payment-schedule/", PaymentScheduleView.as_view(), name="report-payment-schedule"),
    path("reports/export/invoices/", InvoicesCsvExportView.as_view(), name="export-invoices"),
    path("reports/export/payments/", PaymentsCsvExportView.as_view(), name="export-payments"),
]
