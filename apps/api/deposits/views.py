import datetime
from decimal import Decimal

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.permissions import CanManageFinance
from .models import DepositTransaction
from .serializers import DepositTransactionSerializer, DepositBalanceSerializer
from .services import get_deposit_balance, record_deposit_received, refund_deposit


class DepositTransactionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DepositTransaction.objects.select_related("lease__tenant", "created_by").all()
    serializer_class = DepositTransactionSerializer
    permission_classes = [IsAuthenticated, CanManageFinance]
    filterset_fields = ["lease", "transaction_type"]
    ordering = ["-date"]

    @action(detail=False, methods=["post"], url_path="receive")
    def receive(self, request):
        from tenants.models import Lease

        lease_id = request.data.get("lease_id")
        amount = request.data.get("amount")
        date_val = request.data.get("date")
        notes = request.data.get("notes", "")

        try:
            lease = Lease.objects.get(pk=lease_id)
        except Lease.DoesNotExist:
            return Response({"detail": "Lease not found."}, status=status.HTTP_404_NOT_FOUND)

        txn = record_deposit_received(
            lease,
            Decimal(str(amount)),
            datetime.date.fromisoformat(date_val),
            notes,
            request.user,
        )
        return Response(
            DepositTransactionSerializer(txn, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["post"], url_path="refund")
    def refund(self, request):
        from tenants.models import Lease

        lease_id = request.data.get("lease_id")
        amount = request.data.get("amount")
        date_val = request.data.get("date")
        notes = request.data.get("notes", "")

        try:
            lease = Lease.objects.get(pk=lease_id)
        except Lease.DoesNotExist:
            return Response({"detail": "Lease not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            txn = refund_deposit(
                lease,
                Decimal(str(amount)),
                datetime.date.fromisoformat(date_val),
                notes,
                request.user,
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            DepositTransactionSerializer(txn, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["get"], url_path="balance")
    def balance(self, request):
        from tenants.models import Lease

        lease_id = request.query_params.get("lease_id")
        if not lease_id:
            return Response({"detail": "lease_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            lease = Lease.objects.get(pk=lease_id)
        except Lease.DoesNotExist:
            return Response({"detail": "Lease not found."}, status=status.HTTP_404_NOT_FOUND)

        bal = get_deposit_balance(lease)
        return Response({"lease_id": lease.pk, "balance": str(bal)})
