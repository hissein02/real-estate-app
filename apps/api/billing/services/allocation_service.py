from decimal import Decimal

from django.db import transaction

from billing.models import Allocation, Invoice, InvoiceStatus, Payment, PaymentStatus


def _recalculate_invoice_status(invoice: Invoice) -> None:
    """Update invoice status based on paid_amount. Does NOT save — caller must save."""
    if invoice.status == InvoiceStatus.VOID:
        return
    if invoice.paid_amount <= 0:
        invoice.status = InvoiceStatus.ISSUED
    elif invoice.paid_amount >= invoice.total_amount:
        invoice.paid_amount = invoice.total_amount
        invoice.status = InvoiceStatus.PAID
    else:
        invoice.status = InvoiceStatus.PARTIALLY_PAID


def allocate(payment: Payment, invoice: Invoice, amount: Decimal, actor) -> Allocation:
    """
    Allocate `amount` from `payment` to `invoice`.
    Validates unallocated_amount on payment and balance on invoice.
    """
    from audit.models import AuditLog, AuditAction

    if payment.status == PaymentStatus.VOID:
        raise ValueError("Cannot allocate from a void payment.")
    if invoice.status == InvoiceStatus.VOID:
        raise ValueError("Cannot allocate to a void invoice.")
    if invoice.status == InvoiceStatus.PAID:
        raise ValueError("Invoice is already fully paid.")
    if payment.lease_id != invoice.lease_id:
        raise ValueError("Payment and invoice must belong to the same lease.")
    if amount <= 0:
        raise ValueError("Allocation amount must be positive.")

    unallocated = payment.unallocated_amount
    if amount > unallocated:
        raise ValueError(
            f"Allocation amount {amount} exceeds payment unallocated amount {unallocated}."
        )

    invoice_balance = invoice.balance
    if amount > invoice_balance:
        raise ValueError(
            f"Allocation amount {amount} exceeds invoice balance {invoice_balance}."
        )

    with transaction.atomic():
        allocation, created = Allocation.objects.get_or_create(
            payment=payment,
            invoice=invoice,
            defaults={"amount": amount, "created_by": actor},
        )
        if not created:
            # Update existing allocation
            old_amount = allocation.amount
            allocation.amount = amount
            allocation.save(update_fields=["amount"])
            # Reverse old amount from invoice
            invoice.paid_amount = max(Decimal("0"), invoice.paid_amount - old_amount)
        else:
            old_amount = Decimal("0")

        invoice.paid_amount = invoice.paid_amount + amount
        _recalculate_invoice_status(invoice)
        invoice.save(update_fields=["paid_amount", "status", "updated_at"])

        AuditLog.objects.create(
            actor=actor,
            action=AuditAction.CREATE,
            object_type="Allocation",
            object_id=str(allocation.pk),
            object_repr=str(allocation),
        )

    return allocation


def remove_allocation(allocation: Allocation, reason: str, actor) -> None:
    """Remove an allocation and recalculate the invoice status."""
    from audit.models import AuditLog, AuditAction

    with transaction.atomic():
        invoice = allocation.invoice
        invoice.paid_amount = max(Decimal("0"), invoice.paid_amount - allocation.amount)
        _recalculate_invoice_status(invoice)
        invoice.save(update_fields=["paid_amount", "status", "updated_at"])

        AuditLog.objects.create(
            actor=actor,
            action=AuditAction.HARD_DELETE,
            object_type="Allocation",
            object_id=str(allocation.pk),
            object_repr=str(allocation),
            reason=reason,
        )

        allocation.delete()
