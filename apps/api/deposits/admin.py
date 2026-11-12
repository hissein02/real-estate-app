from django.contrib import admin

from .models import DepositTransaction


@admin.register(DepositTransaction)
class DepositTransactionAdmin(admin.ModelAdmin):
    list_display = ["pk", "lease", "transaction_type", "amount", "date", "created_at"]
    list_filter = ["transaction_type"]
    raw_id_fields = ["lease", "created_by", "reference_invoice"]
    date_hierarchy = "date"
