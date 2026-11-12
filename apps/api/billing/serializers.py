from rest_framework import serializers

from .models import Invoice, InvoiceLine, Payment, Allocation


class InvoiceLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceLine
        fields = ["id", "line_type", "description", "quantity", "unit_price", "amount"]


class InvoiceSerializer(serializers.ModelSerializer):
    balance = serializers.ReadOnlyField()
    is_overdue = serializers.ReadOnlyField()
    tenant_name = serializers.CharField(source="lease.tenant.display_name", read_only=True)
    unit_name = serializers.CharField(source="lease.unit.__str__", read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "id", "lease", "tenant_name", "unit_name",
            "invoice_number", "period_start", "period_end",
            "invoice_date", "due_date",
            "currency", "total_amount", "paid_amount", "balance", "status",
            "is_prorated", "is_overdue", "notes",
            "void_reason", "voided_at",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "invoice_number", "paid_amount", "status",
            "void_reason", "voided_at", "created_at", "updated_at",
        ]


class InvoiceDetailSerializer(InvoiceSerializer):
    lines = InvoiceLineSerializer(many=True, read_only=True)

    class Meta(InvoiceSerializer.Meta):
        fields = InvoiceSerializer.Meta.fields + ["lines", "proration_details"]


class VoidSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=1)


class HardDeleteSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=1)
    confirm = serializers.BooleanField()

    def validate_confirm(self, value):
        if not value:
            raise serializers.ValidationError("Must confirm hard delete.")
        return value


class PaymentSerializer(serializers.ModelSerializer):
    unallocated_amount = serializers.ReadOnlyField()
    tenant_name = serializers.CharField(source="lease.tenant.display_name", read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id", "lease", "tenant_name",
            "amount", "currency", "payment_date", "payment_method",
            "reference", "notes", "status",
            "unallocated_amount",
            "void_reason", "voided_at",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "status", "unallocated_amount",
            "void_reason", "voided_at", "created_at", "updated_at",
        ]


class AllocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Allocation
        fields = ["id", "payment", "invoice", "amount", "created_at"]
        read_only_fields = ["id", "created_at"]


class AllocateSerializer(serializers.Serializer):
    payment_id = serializers.IntegerField()
    invoice_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=14, decimal_places=2)


class InvoiceLineInputSerializer(serializers.Serializer):
    line_type = serializers.ChoiceField(choices=["adjustment", "other"])
    description = serializers.CharField(max_length=255)
    quantity = serializers.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_price = serializers.DecimalField(max_digits=14, decimal_places=2)


class PdfOverridesSerializer(serializers.Serializer):
    """Optional per-invoice PDF display overrides."""
    pdf_show_rccm = serializers.BooleanField(required=False)
    pdf_show_nif = serializers.BooleanField(required=False)
    pdf_bank_display = serializers.ChoiceField(
        choices=["none", "all", "selected"], required=False
    )
    pdf_selected_bank_indices = serializers.ListField(
        child=serializers.IntegerField(min_value=0), required=False
    )
    pdf_signatory_id = serializers.IntegerField(required=False, allow_null=True)

    def validate_pdf_signatory_id(self, value):
        if value is None:
            return value
        from settings_app.models import Signatory
        if not Signatory.objects.filter(pk=value).exists():
            raise serializers.ValidationError(f"Signatory with id={value} does not exist.")
        return value


class InvoiceGenerateSerializer(serializers.Serializer):
    lease_id = serializers.IntegerField()
    # Optional: left blank, the next sequential number for the month is assigned.
    # Supply one only to override the sequence (e.g. matching a paper book).
    invoice_number = serializers.CharField(
        max_length=50, required=False, allow_blank=True, default=""
    )
    period_start = serializers.DateField()
    invoice_date = serializers.DateField(required=False, default=None)
    extra_lines = InvoiceLineInputSerializer(many=True, required=False, default=[])
    notes = serializers.CharField(required=False, default="")
    pdf_overrides = PdfOverridesSerializer(required=False, default=None)

    def validate_invoice_number(self, value):
        value = (value or "").strip()
        if not value:
            return ""  # generator assigns the next number in sequence
        if Invoice.objects.filter(invoice_number=value).exists():
            raise serializers.ValidationError(f"Invoice number '{value}' already exists.")
        return value

    def validate_pdf_overrides(self, value):
        if value is None or value == {}:
            return None
        return value


class InvoiceDatesSerializer(serializers.Serializer):
    """Edit the issue date and/or the due date of an existing invoice."""

    invoice_date = serializers.DateField(required=False, allow_null=True)
    due_date = serializers.DateField(required=False)
    reason = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        if attrs.get("invoice_date") is None and attrs.get("due_date") is None:
            raise serializers.ValidationError(
                "Provide invoice_date, due_date, or both."
            )
        return attrs


class InvoiceSendSerializer(serializers.Serializer):
    """Send an already-generated invoice to one or more recipients."""

    recipients = serializers.ListField(
        child=serializers.EmailField(), min_length=1, max_length=10, allow_empty=False
    )

    subject = serializers.CharField(required=False, allow_blank=True, default="")
    body = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_recipients(self, value):
        # Same address twice would send the same invoice twice.
        seen, unique = set(), []
        for email in value:
            key = email.strip().lower()
            if key and key not in seen:
                seen.add(key)
                unique.append(email.strip())
        if not unique:
            raise serializers.ValidationError("At least one recipient is required.")
        return unique
