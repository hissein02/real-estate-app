import zoneinfo

from rest_framework import serializers


class EmailSettingsSerializer(serializers.Serializer):
    smtp_host = serializers.CharField(max_length=255, required=False)
    smtp_port = serializers.IntegerField(
        min_value=1, max_value=65535, required=False
    )
    smtp_use_tls = serializers.BooleanField(required=False)
    smtp_username = serializers.CharField(
        max_length=255, required=False, allow_blank=True
    )
    smtp_password = serializers.CharField(
        max_length=255, required=False, allow_blank=True
    )
    from_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    from_email = serializers.EmailField(required=False)
    reply_to_email = serializers.EmailField(required=False, allow_blank=True)
    task_timezone = serializers.CharField(max_length=63, required=False)

    def validate_task_timezone(self, value):
        try:
            zoneinfo.ZoneInfo(value)
        except (KeyError, Exception):
            raise serializers.ValidationError(f"Invalid timezone: {value}")
        return value

    def to_representation(self, instance):
        data = {
            "smtp_host": instance.smtp_host,
            "smtp_port": instance.smtp_port,
            "smtp_use_tls": instance.smtp_use_tls,
            "smtp_username": instance.smtp_username,
            "smtp_password": "********" if instance.smtp_password else "",
            "from_name": instance.from_name,
            "from_email": instance.from_email,
            "reply_to_email": instance.reply_to_email,
            "task_timezone": instance.task_timezone,
        }
        return data


class TaskConfigSerializer(serializers.Serializer):
    task_key = serializers.CharField(read_only=True)
    task_name = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True)
    is_enabled = serializers.BooleanField(required=False)
    hour = serializers.IntegerField(
        min_value=0, max_value=23, required=False
    )
    minute = serializers.IntegerField(
        min_value=0, max_value=59, required=False
    )
    periodicity = serializers.CharField(read_only=True)


class TaskUpdateSerializer(serializers.Serializer):
    is_enabled = serializers.BooleanField(required=False)
    hour = serializers.IntegerField(
        min_value=0, max_value=23, required=False
    )
    minute = serializers.IntegerField(
        min_value=0, max_value=59, required=False
    )


class NotificationTemplateSerializer(serializers.Serializer):
    notification_type = serializers.CharField(read_only=True)
    subject_template = serializers.CharField(max_length=300, required=False)
    body_template = serializers.CharField(required=False)
    available_variables = serializers.ListField(
        child=serializers.CharField(), read_only=True
    )
    sample_data = serializers.DictField(read_only=True)


class BankAccountSerializer(serializers.Serializer):
    bank_name = serializers.CharField(max_length=200)
    account_number = serializers.CharField(max_length=100)


class SignatorySerializer(serializers.Serializer):
    """Read serializer for Signatory — returned nested inside CompanyInfo and standalone."""

    id = serializers.IntegerField(read_only=True)
    label = serializers.CharField(max_length=100)
    name = serializers.CharField(max_length=200, allow_blank=True, required=False, default="")
    signature_url = serializers.SerializerMethodField()
    order = serializers.IntegerField(min_value=0, required=False, default=0)

    def get_signature_url(self, obj):
        if obj.signature_image:
            try:
                return obj.signature_image.url
            except Exception:
                return None
        return None

    def to_representation(self, instance):
        return {
            "id": instance.id,
            "label": instance.label,
            "name": instance.name,
            "signature_url": self.get_signature_url(instance),
            "order": instance.order,
        }


class SignatoryWriteSerializer(serializers.Serializer):
    """Write serializer for creating/updating a Signatory."""

    label = serializers.CharField(max_length=100)
    name = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    order = serializers.IntegerField(min_value=0, required=False, default=0)


class CompanyInfoSerializer(serializers.Serializer):
    display_name = serializers.CharField(max_length=100, required=False)
    company_name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    address = serializers.CharField(max_length=300, required=False, allow_blank=True)
    city = serializers.CharField(max_length=100, required=False, allow_blank=True)
    country = serializers.CharField(max_length=100, required=False, allow_blank=True)
    phone_numbers = serializers.ListField(
        child=serializers.CharField(max_length=30),
        required=False,
    )
    email = serializers.EmailField(required=False, allow_blank=True)
    bank_accounts = BankAccountSerializer(many=True, required=False)
    rccm = serializers.CharField(max_length=100, required=False, allow_blank=True)
    nif = serializers.CharField(max_length=100, required=False, allow_blank=True)

    # PDF display preferences
    pdf_show_rccm = serializers.BooleanField(required=False)
    pdf_show_nif = serializers.BooleanField(required=False)
    pdf_bank_display = serializers.ChoiceField(
        choices=["none", "all", "selected"], required=False
    )
    pdf_selected_bank_indices = serializers.ListField(
        child=serializers.IntegerField(min_value=0), required=False
    )
    # Signatory is now a FK reference: read as nested object, write as integer ID or null
    pdf_signatory_id = serializers.IntegerField(required=False, allow_null=True)

    def validate_pdf_signatory_id(self, value):
        if value is None:
            return value
        from .models import Signatory
        if not Signatory.objects.filter(pk=value).exists():
            raise serializers.ValidationError(f"Signatory with id={value} does not exist.")
        return value

    def to_representation(self, instance):
        sig_data = None
        if instance.pdf_signatory_id:
            try:
                sig = instance.pdf_signatory
                sig_data = {
                    "id": sig.id,
                    "label": sig.label,
                    "name": sig.name,
                    "signature_url": sig.signature_image.url if sig.signature_image else None,
                    "order": sig.order,
                }
            except Exception:
                sig_data = None
        return {
            "display_name": instance.display_name,
            "company_name": instance.company_name,
            "address": instance.address,
            "city": instance.city,
            "country": instance.country,
            "phone_numbers": instance.phone_numbers or [],
            "email": instance.email,
            "logo_url": instance.logo.url if instance.logo else None,
            "bank_accounts": instance.bank_accounts or [],
            "rccm": instance.rccm,
            "nif": instance.nif,
            "pdf_show_rccm": instance.pdf_show_rccm,
            "pdf_show_nif": instance.pdf_show_nif,
            "pdf_bank_display": instance.pdf_bank_display,
            "pdf_selected_bank_indices": instance.pdf_selected_bank_indices or [],
            "pdf_signatory": sig_data,
        }


class TestEmailSerializer(serializers.Serializer):
    recipient_email = serializers.EmailField()


class InvoiceTestEmailSerializer(serializers.Serializer):
    recipient_email = serializers.EmailField()
