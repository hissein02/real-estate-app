import django_filters

from .models import Property, Unit


class PropertyFilter(django_filters.FilterSet):
    owner = django_filters.NumberFilter(field_name="owner_id")
    property_type = django_filters.CharFilter(field_name="property_type")
    city = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = Property
        fields = ["owner", "property_type", "city"]


class UnitFilter(django_filters.FilterSet):
    building = django_filters.NumberFilter(field_name="building_id")
    unit_type = django_filters.CharFilter(field_name="unit_type")
    is_active = django_filters.BooleanFilter()
    is_occupied = django_filters.BooleanFilter(method="filter_occupied")

    class Meta:
        model = Unit
        fields = ["building", "unit_type", "is_active"]

    def filter_occupied(self, queryset, name, value):
        from tenants.models import LeaseStatus
        occupied_unit_ids = (
            Unit.objects.filter(leases__status=LeaseStatus.ACTIVE)
            .values_list("id", flat=True)
        )
        if value:
            return queryset.filter(id__in=occupied_unit_ids)
        return queryset.exclude(id__in=occupied_unit_ids)
