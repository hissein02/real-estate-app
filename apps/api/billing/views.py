import logging

from django.http import HttpResponse
from django.template.loader import render_to_string
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.permissions import CanManageFinance, IsAdminRole
from .filters import InvoiceFilter, PaymentFilter
from .models import Allocation, Invoice, InvoiceStatus, Payment
from .serializers import (
    InvoiceSerializer,
    InvoiceDetailSerializer,
    PaymentSerializer,
    AllocationSerializer,
    AllocateSerializer,
    VoidSerializer,
    HardDeleteSerializer,
    InvoiceGenerateSerializer,
    InvoiceDatesSerializer,
    InvoiceSendSerializer,
)
from .services.invoice_document import render_invoice_document
from .services.invoice_service import (
    generate_invoice_with_extras,
    hard_delete_invoice,
    update_invoice_dates,
    void_invoice,
)
from .services.payment_service import post_payment, void_payment, hard_delete_payment
from .services.allocation_service import allocate, remove_allocation

logger = logging.getLogger(__name__)

STATUS_LABELS = {
    "draft": "Brouillon",
    "issued": "Émise",
    "partially_paid": "Partiellement payée",
    "paid": "Payée",
    "void": "Annulée",
}


class InvoiceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Invoice.objects.select_related(
        "lease__tenant", "lease__unit__building", "created_by"
    ).prefetch_related("lines").all()
    permission_classes = [IsAuthenticated, CanManageFinance]
    filterset_class = InvoiceFilter
    # company_name matters: a company tenant has no first/last name, so without
    # it searching for "MOOV AFRICA" returns nothing.
    search_fields = [
        "invoice_number",
        "lease__tenant__first_name",
        "lease__tenant__last_name",
        "lease__tenant__company_name",
    ]
    ordering_fields = ["due_date", "invoice_date", "total_amount", "created_at"]
    ordering = ["-due_date"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return InvoiceDetailSerializer
        return InvoiceSerializer

    @action(detail=True, methods=["get"], url_path="preview")
    def preview(self, request, pk=None):
        """The invoice document as HTML, for viewing without downloading."""
        invoice = self.get_object()
        return Response(
            {
                "html": render_invoice_document(invoice, request=request, for_pdf=False),
                "invoice_number": invoice.invoice_number,
            }
        )

    @action(detail=True, methods=["get"], url_path="pdf")
    def pdf(self, request, pk=None):
        """Render the invoice as a PDF and return it as a binary response."""
        invoice = self.get_object()
        html = render_invoice_document(invoice, request=request, for_pdf=True)

        try:
            from weasyprint import HTML
            pdf_bytes = HTML(string=html, base_url=request.build_absolute_uri("/")).write_pdf()
        except Exception:
            logger.exception("WeasyPrint failed for invoice %s", invoice.invoice_number)
            return Response(
                {"detail": "PDF generation failed."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        filename = f"{invoice.invoice_number}.pdf"
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response["Content-Length"] = len(pdf_bytes)
        return response

    @action(detail=True, methods=["get"], url_path="email-preview")
    def email_preview(self, request, pk=None):
        """Subject and body the tenant would receive, for the operator to edit."""
        from .services.email_service import build_invoice_email_draft

        invoice = self.get_object()
        draft = build_invoice_email_draft(invoice)
        draft["default_recipient"] = invoice.lease.tenant.email or ""
        return Response(draft)

    @action(detail=True, methods=["post"], url_path="send")
    def send(self, request, pk=None):
        """E-mail an existing invoice as a PDF to the given recipients.

        Separate from generation on purpose: an invoice is created once, but may
        be sent, resent, or sent to a different address later.
        """
        from .services.email_service import send_invoice_email

        invoice = self.get_object()
        if invoice.status == InvoiceStatus.VOID:
            return Response(
                {"detail": "This invoice is void and cannot be sent."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = InvoiceSendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        name = request.user.get_full_name() or request.user.username
        triggered_by = f"{request.user.role.title()}: {name}"

        sent, failed = [], []
        for recipient in serializer.validated_data["recipients"]:
            try:
                if send_invoice_email(
                    invoice,
                    recipient,
                    triggered_by=triggered_by,
                    subject=serializer.validated_data.get("subject") or None,
                    body=serializer.validated_data.get("body") or None,
                ):
                    sent.append(recipient)
                else:
                    failed.append(recipient)
            except Exception:
                logger.exception("Invoice %s could not be sent to %s", invoice.pk, recipient)
                failed.append(recipient)

        return Response(
            {"sent": sent, "failed": failed},
            status=status.HTTP_200_OK if sent else status.HTTP_502_BAD_GATEWAY,
        )

    @action(detail=True, methods=["patch"], url_path="dates")
    def dates(self, request, pk=None):
        """Change the issue date and/or due date of an issued invoice."""
        invoice = self.get_object()
        serializer = InvoiceDatesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vd = serializer.validated_data

        result = update_invoice_dates(
            invoice,
            actor=request.user,
            invoice_date=vd.get("invoice_date"),
            due_date=vd.get("due_date"),
            reason=vd.get("reason", ""),
        )
        invoice.refresh_from_db()
        data = InvoiceDetailSerializer(invoice).data
        data["warnings"] = result["warnings"]
        return Response(data)

    @action(detail=True, methods=["post"], url_path="void")
    def void(self, request, pk=None):
        invoice = self.get_object()
        serializer = VoidSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = void_invoice(invoice, reason=serializer.validated_data["reason"], actor=request.user)
        return Response(InvoiceDetailSerializer(result).data)

    @action(
        detail=True,
        methods=["delete"],
        url_path="hard-delete",
        permission_classes=[IsAuthenticated, IsAdminRole],
    )
    def hard_delete(self, request, pk=None):
        invoice = self.get_object()
        serializer = HardDeleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        hard_delete_invoice(invoice, reason=serializer.validated_data["reason"], actor=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["post"], url_path="generate")
    def generate(self, request):
        from tenants.models import Lease

        serializer = InvoiceGenerateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vd = serializer.validated_data

        try:
            lease = Lease.objects.get(pk=vd["lease_id"])
        except Lease.DoesNotExist:
            return Response(
                {"detail": "Lease not found."}, status=status.HTTP_404_NOT_FOUND
            )

        try:
            invoice = generate_invoice_with_extras(
                lease=lease,
                period_start=vd["period_start"],
                extra_lines=vd["extra_lines"],
                notes=vd["notes"],
                actor=request.user,
                invoice_date=vd.get("invoice_date"),
                pdf_overrides=vd.get("pdf_overrides"),
                invoice_number=vd.get("invoice_number") or None,
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # Generation never sends. Use the `send` action once the invoice exists.
        return Response(
            InvoiceDetailSerializer(invoice).data, status=status.HTTP_201_CREATED
        )


class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.select_related(
        "lease__tenant", "lease__unit", "created_by"
    ).prefetch_related("allocations").all()
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated, CanManageFinance]
    filterset_class = PaymentFilter
    search_fields = [
        "reference",
        "lease__tenant__first_name",
        "lease__tenant__last_name",
        "lease__tenant__company_name",
    ]
    ordering_fields = ["payment_date", "amount", "created_at"]
    ordering = ["-payment_date"]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vd = serializer.validated_data
        lease = vd["lease"]
        payment = post_payment(
            lease=lease,
            amount=vd["amount"],
            currency=vd["currency"],
            payment_date=vd["payment_date"],
            payment_method=vd.get("payment_method", "cash"),
            reference=vd.get("reference", ""),
            notes=vd.get("notes", ""),
            actor=request.user,
        )
        return Response(PaymentSerializer(payment).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="void")
    def void(self, request, pk=None):
        payment = self.get_object()
        serializer = VoidSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = void_payment(payment, reason=serializer.validated_data["reason"], actor=request.user)
        return Response(PaymentSerializer(result).data)

    @action(
        detail=True,
        methods=["delete"],
        url_path="hard-delete",
        permission_classes=[IsAuthenticated, IsAdminRole],
    )
    def hard_delete(self, request, pk=None):
        payment = self.get_object()
        serializer = HardDeleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        hard_delete_payment(payment, reason=serializer.validated_data["reason"], actor=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["post"], url_path="allocate")
    def allocate(self, request):
        serializer = AllocateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vd = serializer.validated_data
        try:
            payment = Payment.objects.get(pk=vd["payment_id"])
            invoice = Invoice.objects.get(pk=vd["invoice_id"])
        except (Payment.DoesNotExist, Invoice.DoesNotExist) as e:
            return Response({"detail": str(e)}, status=status.HTTP_404_NOT_FOUND)

        allocation = allocate(payment, invoice, vd["amount"], request.user)
        return Response(AllocationSerializer(allocation).data, status=status.HTTP_201_CREATED)


class AllocationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Allocation.objects.select_related("payment", "invoice", "created_by").all()
    serializer_class = AllocationSerializer
    permission_classes = [IsAuthenticated, CanManageFinance]

    @action(
        detail=True,
        methods=["delete"],
        url_path="remove",
        permission_classes=[IsAuthenticated, IsAdminRole],
    )
    def remove(self, request, pk=None):
        allocation = self.get_object()
        serializer = VoidSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        remove_allocation(allocation, reason=serializer.validated_data["reason"], actor=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)
