import django_filters
from django.db.models import F

from .models import Invoice, Payment, InvoiceStatus, PaymentStatus


class InvoiceFilter(django_filters.FilterSet):
    lease = django_filters.NumberFilter(field_name="lease_id")
    status = django_filters.MultipleChoiceFilter(choices=InvoiceStatus.choices)
    due_date_after = django_filters.DateFilter(field_name="due_date", lookup_expr="gte")
    due_date_before = django_filters.DateFilter(field_name="due_date", lookup_expr="lte")
    is_overdue = django_filters.BooleanFilter(method="filter_overdue")
    currency = django_filters.CharFilter()
    tenant = django_filters.NumberFilter(field_name="lease__tenant_id")
    building = django_filters.NumberFilter(field_name="lease__unit__building_id")

    class Meta:
        model = Invoice
        fields = ["lease", "status", "currency"]

    def filter_overdue(self, queryset, name, value):
        from django.utils import timezone
        today = timezone.now().date()
        if value:
            return (
                queryset.filter(due_date__lt=today)
                .filter(paid_amount__lt=F("total_amount"))
                .exclude(status__in=[InvoiceStatus.PAID, InvoiceStatus.VOID])
            )
        return queryset


class PaymentFilter(django_filters.FilterSet):
    lease = django_filters.NumberFilter(field_name="lease_id")
    status = django_filters.MultipleChoiceFilter(choices=PaymentStatus.choices)
    payment_date_after = django_filters.DateFilter(field_name="payment_date", lookup_expr="gte")
    payment_date_before = django_filters.DateFilter(field_name="payment_date", lookup_expr="lte")
    currency = django_filters.CharFilter()
    tenant = django_filters.NumberFilter(field_name="lease__tenant_id")

    class Meta:
        model = Payment
        fields = ["lease", "status", "currency"]
