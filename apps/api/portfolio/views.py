from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.mixins import AuditedDestroyMixin
from core.permissions import CanWriteManagerDelete
from .filters import PropertyFilter, UnitFilter
from .models import Owner, Property, Unit
from .serializers import (
    OwnerSerializer,
    PropertySerializer,
    PropertyDetailSerializer,
    UnitSerializer,
)


class OwnerViewSet(AuditedDestroyMixin, viewsets.ModelViewSet):
    queryset = Owner.objects.all()
    serializer_class = OwnerSerializer
    permission_classes = [IsAuthenticated, CanWriteManagerDelete]
    search_fields = ["first_name", "last_name", "company_name", "email", "phone"]
    ordering_fields = ["last_name", "company_name", "created_at"]
    ordering = ["last_name"]


class PropertyViewSet(AuditedDestroyMixin, viewsets.ModelViewSet):
    queryset = Property.objects.select_related("owner").all()
    permission_classes = [IsAuthenticated, CanWriteManagerDelete]
    filterset_class = PropertyFilter
    search_fields = ["name", "address_line1", "city"]
    ordering_fields = ["name", "city", "created_at"]
    ordering = ["name"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return PropertyDetailSerializer
        return PropertySerializer

    @action(detail=True, methods=["get"], url_path="units")
    def units(self, request, pk=None):
        prop = self.get_object()
        units = prop.units.filter(is_active=True)
        serializer = UnitSerializer(units, many=True)
        return Response(serializer.data)


class UnitViewSet(AuditedDestroyMixin, viewsets.ModelViewSet):
    queryset = Unit.objects.select_related("building", "building__owner").all()
    serializer_class = UnitSerializer
    permission_classes = [IsAuthenticated, CanWriteManagerDelete]
    filterset_class = UnitFilter
    search_fields = ["name", "building__name"]
    ordering_fields = ["name", "building__name", "created_at"]
    ordering = ["building__name", "name"]
