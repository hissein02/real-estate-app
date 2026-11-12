from django.contrib import admin

from .models import Tenant, Lease


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ["display_name", "is_company", "email", "phone", "created_at"]
    list_filter = ["is_company"]
    search_fields = ["first_name", "last_name", "company_name", "email"]


@admin.register(Lease)
class LeaseAdmin(admin.ModelAdmin):
    list_display = [
        "__str__", "status", "start_date", "end_date",
        "rent_unit_price", "currency", "billing_interval_months",
    ]
    list_filter = ["status", "currency", "billing_cycle_anchor"]
    search_fields = ["tenant__first_name", "tenant__last_name", "unit__name"]
    raw_id_fields = ["unit", "tenant", "created_by", "renewed_from"]
    date_hierarchy = "start_date"
