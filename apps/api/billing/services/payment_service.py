from datetime import date
from decimal import Decimal
from typing import Optional

from django.db import transaction
from django.utils import timezone

from billing.models import Payment, PaymentStatus, PaymentMethod
from tenants.models import Currency


def post_payment(
    lease,
    amount: Decimal,
    currency: str,
    payment_date: date,
    payment_method: str,
    reference: str,
    notes: str,
    actor,
) -> Payment:
    """Post a new payment against a lease."""
    from audit.models import AuditLog, AuditAction

    if amount <= 0:
        raise ValueError("Payment amount must be positive.")
    if currency not in [c.value for c in Currency]:
        raise ValueError(f"Invalid currency: {currency}")

    with transaction.atomic():
        payment = Payment.objects.create(
            lease=lease,
            amount=amount,
            currency=currency,
            payment_date=payment_date,
            payment_method=payment_method,
            reference=reference,
            notes=notes,
            status=PaymentStatus.POSTED,
            created_by=actor,
        )
        AuditLog.objects.create(
            actor=actor,
            action=AuditAction.CREATE,
            object_type="Payment",
            object_id=str(payment.pk),
            object_repr=str(payment),
        )

    return payment


def void_payment(payment: Payment, reason: str, actor) -> Payment:
    """
    Void a payment. This reverses all allocations: invoice paid_amounts are reduced
    and invoice statuses are recalculated.
    """
    from audit.models import AuditLog, AuditAction
    from billing.services.allocation_service import _recalculate_invoice_status

    if payment.status == PaymentStatus.VOID:
        raise ValueError("Payment is already void.")

    with transaction.atomic():
        # Reverse all allocations
        for allocation in payment.allocations.select_related("invoice").all():
            invoice = allocation.invoice
            invoice.paid_amount = max(Decimal("0"), invoice.paid_amount - allocation.amount)
            _recalculate_invoice_status(invoice)
            invoice.save(update_fields=["paid_amount", "status", "updated_at"])

        payment.allocations.all().delete()

        payment.status = PaymentStatus.VOID
        payment.void_reason = reason
        payment.voided_by = actor
        payment.voided_at = timezone.now()
        payment.save(update_fields=["status", "void_reason", "voided_by", "voided_at", "updated_at"])

        AuditLog.objects.create(
            actor=actor,
            action=AuditAction.VOID,
            object_type="Payment",
            object_id=str(payment.pk),
            object_repr=str(payment),
            reason=reason,
        )

    return payment


def hard_delete_payment(payment: Payment, reason: str, actor) -> None:
    """Admin-only hard delete with full audit snapshot."""
    from audit.models import AuditLog, AuditAction

    with transaction.atomic():
        snapshot = {
            "id": payment.pk,
            "amount": str(payment.amount),
            "currency": payment.currency,
            "payment_date": str(payment.payment_date),
            "status": payment.status,
        }
        AuditLog.objects.create(
            actor=actor,
            action=AuditAction.HARD_DELETE,
            object_type="Payment",
            object_id=str(payment.pk),
            object_repr=str(payment),
            snapshot_json=snapshot,
            reason=reason,
        )
        payment.delete()
