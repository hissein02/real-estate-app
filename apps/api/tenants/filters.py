import django_filters

from .models import Tenant, Lease, LeaseStatus


class TenantFilter(django_filters.FilterSet):
    is_company = django_filters.BooleanFilter()
    email = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = Tenant
        fields = ["is_company", "email"]


class LeaseFilter(django_filters.FilterSet):
    status = django_filters.MultipleChoiceFilter(choices=LeaseStatus.choices)
    tenant = django_filters.NumberFilter(field_name="tenant_id")
    unit = django_filters.NumberFilter(field_name="unit_id")
    building = django_filters.NumberFilter(field_name="unit__building_id")
    start_date_after = django_filters.DateFilter(field_name="start_date", lookup_expr="gte")
    end_date_before = django_filters.DateFilter(field_name="end_date", lookup_expr="lte")
    currency = django_filters.CharFilter()

    class Meta:
        model = Lease
        fields = ["status", "tenant", "unit", "currency"]
