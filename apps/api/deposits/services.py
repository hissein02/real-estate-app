from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from deposits.models import DepositTransaction, DepositTransactionType
from tenants.models import Lease


def get_deposit_balance(lease: Lease) -> Decimal:
    """Return the current deposit balance (positive = held by landlord)."""
    total = (
        DepositTransaction.objects.filter(lease=lease)
        .aggregate(t=Sum("amount"))["t"]
    )
    return total or Decimal("0")


def record_deposit_received(
    lease: Lease,
    amount: Decimal,
    received_date: date,
    notes: str,
    actor,
) -> DepositTransaction:
    """Record receiving a deposit from a tenant."""
    from audit.models import AuditLog, AuditAction

    if amount <= 0:
        raise ValueError("Deposit amount must be positive.")

    with transaction.atomic():
        txn = DepositTransaction.objects.create(
            lease=lease,
            transaction_type=DepositTransactionType.RECEIVED,
            amount=amount,
            date=received_date,
            notes=notes,
            created_by=actor,
        )
        AuditLog.objects.create(
            actor=actor,
            action=AuditAction.CREATE,
            object_type="DepositTransaction",
            object_id=str(txn.pk),
            object_repr=str(txn),
        )
    return txn


def refund_deposit(
    lease: Lease,
    amount: Decimal,
    refund_date: date,
    notes: str,
    actor,
) -> DepositTransaction:
    """Record a deposit refund to the tenant."""
    from audit.models import AuditLog, AuditAction

    if amount <= 0:
        raise ValueError("Refund amount must be positive.")

    current_balance = get_deposit_balance(lease)
    if amount > current_balance:
        raise ValueError(
            f"Refund amount {amount} exceeds current deposit balance {current_balance}."
        )

    with transaction.atomic():
        txn = DepositTransaction.objects.create(
            lease=lease,
            transaction_type=DepositTransactionType.REFUNDED,
            amount=-amount,  # negative = money going out
            date=refund_date,
            notes=notes,
            created_by=actor,
        )
        AuditLog.objects.create(
            actor=actor,
            action=AuditAction.CREATE,
            object_type="DepositTransaction",
            object_id=str(txn.pk),
            object_repr=str(txn),
        )
    return txn
