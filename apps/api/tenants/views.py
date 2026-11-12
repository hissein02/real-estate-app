from datetime import date

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.mixins import AuditedDestroyMixin
from core.permissions import CanWriteManagerDelete, IsAdminRole, IsManagerOrAbove
from .filters import TenantFilter, LeaseFilter
from .models import Tenant, Lease
from .serializers import (
    LeaseForceDeleteSerializer,
    LeaseRenewSerializer,
    LeaseSerializer,
    LeaseTerminateSerializer,
    TenantSerializer,
)
from .services import (
    activate_lease,
    force_delete_lease,
    get_lease_deletion_plan,
    renew_lease,
    terminate_lease,
)


class TenantViewSet(AuditedDestroyMixin, viewsets.ModelViewSet):
    queryset = Tenant.objects.all()
    serializer_class = TenantSerializer
    permission_classes = [IsAuthenticated, CanWriteManagerDelete]
    filterset_class = TenantFilter
    search_fields = ["first_name", "last_name", "company_name", "email", "phone"]
    ordering_fields = ["last_name", "company_name", "created_at"]
    ordering = ["last_name"]


class LeaseViewSet(AuditedDestroyMixin, viewsets.ModelViewSet):
    queryset = Lease.objects.select_related("unit__building", "tenant", "created_by").all()
    serializer_class = LeaseSerializer
    permission_classes = [IsAuthenticated, CanWriteManagerDelete]
    filterset_class = LeaseFilter
    search_fields = ["tenant__first_name", "tenant__last_name", "tenant__company_name", "unit__name"]
    ordering_fields = ["start_date", "end_date", "rent_unit_price", "created_at"]
    ordering = ["-created_at"]

    @action(
        detail=True,
        methods=["post"],
        url_path="activate",
        permission_classes=[IsAuthenticated, IsManagerOrAbove],
    )
    def activate(self, request, pk=None):
        lease = self.get_object()
        result = activate_lease(lease, request.user)
        return Response(LeaseSerializer(result, context={"request": request}).data)

    @action(
        detail=True,
        methods=["post"],
        url_path="terminate",
        permission_classes=[IsAuthenticated, IsManagerOrAbove],
    )
    def terminate(self, request, pk=None):
        lease = self.get_object()
        serializer = LeaseTerminateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = terminate_lease(
            lease,
            reason=serializer.validated_data["reason"],
            termination_date=serializer.validated_data["termination_date"],
            actor=request.user,
        )
        return Response(LeaseSerializer(result, context={"request": request}).data)

    @action(
        detail=True,
        methods=["get"],
        url_path="deletion-preview",
        permission_classes=[IsAuthenticated, IsAdminRole],
    )
    def deletion_preview(self, request, pk=None):
        """What a force delete would destroy. Read-only — changes nothing."""
        return Response(get_lease_deletion_plan(self.get_object()))

    @action(
        detail=True,
        methods=["delete"],
        url_path="force-delete",
        permission_classes=[IsAuthenticated, IsAdminRole],
    )
    def force_delete(self, request, pk=None):
        """Delete the lease and every financial record attached to it.

        Deliberately separate from the normal delete: that one is blocked by
        PROTECT so posted invoices and payments get voided rather than removed.
        """
        lease = self.get_object()
        serializer = LeaseForceDeleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan = force_delete_lease(
            lease, actor=request.user, reason=serializer.validated_data.get("reason", "")
        )
        return Response(plan, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=["post"],
        url_path="renew",
        permission_classes=[IsAuthenticated, IsManagerOrAbove],
    )
    def renew(self, request, pk=None):
        lease = self.get_object()
        serializer = LeaseRenewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_lease = renew_lease(
            lease,
            new_end_date=serializer.validated_data.get("new_end_date"),
            new_rent_unit_price=serializer.validated_data.get("new_rent_unit_price"),
            actor=request.user,
        )
        return Response(
            LeaseSerializer(new_lease, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )
