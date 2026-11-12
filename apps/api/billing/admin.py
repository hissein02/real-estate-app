from django.contrib import admin

from .models import Invoice, InvoiceLine, Payment, Allocation


class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 0
    readonly_fields = ["amount"]


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = [
        "invoice_number", "lease", "period_start", "period_end",
        "total_amount", "paid_amount", "status", "due_date",
    ]
    list_filter = ["status", "currency", "is_prorated"]
    search_fields = ["invoice_number", "lease__tenant__first_name", "lease__tenant__last_name"]
    raw_id_fields = ["lease", "created_by", "voided_by"]
    inlines = [InvoiceLineInline]
    date_hierarchy = "due_date"
    readonly_fields = ["paid_amount", "status", "voided_at"]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        "pk", "lease", "amount", "currency", "payment_date",
        "payment_method", "status", "reference",
    ]
    list_filter = ["status", "currency", "payment_method"]
    search_fields = ["reference", "lease__tenant__first_name", "lease__tenant__last_name"]
    raw_id_fields = ["lease", "created_by", "voided_by"]
    date_hierarchy = "payment_date"


@admin.register(Allocation)
class AllocationAdmin(admin.ModelAdmin):
    list_display = ["pk", "payment", "invoice", "amount", "created_at"]
    raw_id_fields = ["payment", "invoice", "created_by"]
