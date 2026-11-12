import django_filters
from rest_framework import viewsets

from core.permissions import IsManagerOrAbove
from .models import AuditLog
from .serializers import AuditLogSerializer


class AuditLogFilter(django_filters.FilterSet):
    object_type = django_filters.CharFilter()
    object_id = django_filters.CharFilter()
    action = django_filters.CharFilter()
    actor = django_filters.NumberFilter(field_name="actor_id")
    created_after = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model = AuditLog
        fields = ["object_type", "object_id", "action", "actor"]


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.select_related("actor").all()
    serializer_class = AuditLogSerializer
    permission_classes = [IsManagerOrAbove]
    filterset_class = AuditLogFilter
    search_fields = ["object_repr", "reason"]
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]
