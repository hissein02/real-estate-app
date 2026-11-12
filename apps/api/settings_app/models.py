from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator

TEMPLATE_NOTIFICATION_TYPES = [
    ("rent_reminder", "Rent Reminder"),
    ("overdue_notice", "Overdue Notice"),
    ("lease_expiry_warning", "Lease Expiry Warning"),
]


class NotificationTemplate(models.Model):
    """Editable email templates for each notification type."""

    notification_type = models.CharField(
        max_length=30,
        choices=TEMPLATE_NOTIFICATION_TYPES,
        unique=True,
    )
    subject_template = models.CharField(
        max_length=300,
        help_text="Use {variable} placeholders. E.g. 'Rent reminder – Invoice {invoice_number}'",
    )
    body_template = models.TextField(
        help_text="Use {variable} placeholders. E.g. 'Dear {tenant_name}, ...'",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["notification_type"]

    def __str__(self):
        return f"Template: {self.get_notification_type_display()}"


class Signatory(models.Model):
    """A person authorized to sign invoices. Replaces hardcoded director/accountant fields."""

    label = models.CharField(
        max_length=100,
        help_text="Title shown on invoice, e.g. 'Directeur Général', 'Comptable'",
    )
    name = models.CharField(
        max_length=200,
        blank=True,
        default="",
        help_text="Optional full name of the signatory",
    )
    signature_image = models.FileField(
        upload_to="company/signatures/",
        blank=True,
        default="",
        help_text="Optional handwritten signature image (PNG, JPG, WEBP). Max 2 MB.",
    )
    order = models.PositiveIntegerField(
        default=0,
        help_text="Display order (lower = first)",
    )

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Signatory"
        verbose_name_plural = "Signatories"

    def __str__(self):
        if self.name:
            return f"{self.label} – {self.name}"
        return self.label


class CompanyInfo(models.Model):
    """Singleton model for company / organisation details used in invoices, navbar, etc."""

    display_name = models.CharField(
        max_length=100,
        default="RealEstate",
        help_text="Displayed in the sidebar and browser title",
    )
    company_name = models.CharField(
        max_length=200,
        blank=True,
        default="",
        help_text="Used on invoices and official documents",
    )
    address = models.CharField(max_length=300, blank=True, default="")
    city = models.CharField(max_length=100, blank=True, default="")
    country = models.CharField(max_length=100, blank=True, default="")
    phone_numbers = models.JSONField(
        default=list,
        blank=True,
        help_text="List of phone numbers",
    )
    email = models.EmailField(blank=True, default="")
    logo = models.FileField(
        upload_to="company/",
        blank=True,
        default="",
        help_text="Company logo (PNG, JPG, WEBP, SVG). Max 2 MB.",
    )
    bank_accounts = models.JSONField(
        default=list,
        blank=True,
        help_text="List of bank accounts [{bank_name, account_number}]",
    )
    rccm = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="RCCM (Registre du Commerce et du Crédit Mobilier)",
    )
    nif = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="NIF (Numéro d'Identification Fiscale)",
    )

    # ── Invoice PDF display preferences ──
    PDF_BANK_CHOICES = [
        ("none", "None"),
        ("all", "All"),
        ("selected", "Selected"),
    ]

    pdf_show_rccm = models.BooleanField(default=True)
    pdf_show_nif = models.BooleanField(default=True)
    pdf_bank_display = models.CharField(
        max_length=10,
        choices=PDF_BANK_CHOICES,
        default="all",
        help_text="Which bank accounts to show on invoices",
    )
    pdf_selected_bank_indices = models.JSONField(
        default=list,
        blank=True,
        help_text="Indices of bank accounts to show when pdf_bank_display='selected'",
    )
    pdf_signatory = models.ForeignKey(
        "Signatory",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="selected_for_invoices",
        help_text="Which signatory to display on the invoice footer",
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Company Info"
        verbose_name_plural = "Company Info"

    def __str__(self):
        return "Company Info"

    def save(self, *args, **kwargs):
        self.pk = 1
        # Clean up old logo file when replaced
        try:
            old = CompanyInfo.objects.get(pk=1)
            if old.logo and self.logo and old.logo.name != self.logo.name:
                old.logo.delete(save=False)
        except CompanyInfo.DoesNotExist:
            pass
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass  # Prevent deletion of the singleton

    @classmethod
    def load(cls):
        """Load the singleton instance, creating with defaults if needed."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class EmailSettings(models.Model):
    """Singleton model for runtime-configurable email / SMTP settings."""

    smtp_host = models.CharField(max_length=255, default="localhost")
    smtp_port = models.PositiveIntegerField(
        default=587,
        validators=[MinValueValidator(1), MaxValueValidator(65535)],
    )
    smtp_use_tls = models.BooleanField(default=True)
    smtp_username = models.CharField(max_length=255, blank=True, default="")
    smtp_password = models.CharField(max_length=255, blank=True, default="")
    from_name = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Sender display name, e.g. 'Immobilière ABC'",
    )
    from_email = models.EmailField(default="noreply@realestate.local")
    reply_to_email = models.EmailField(
        blank=True,
        default="",
        help_text="If set, replies from recipients will go to this address instead of the From address.",
    )
    task_timezone = models.CharField(
        max_length=63,
        default="Africa/Ndjamena",
        help_text="IANA timezone for scheduled task execution",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Email Settings"
        verbose_name_plural = "Email Settings"

    def __str__(self):
        return "Email Settings"

    def save(self, *args, **kwargs):
        # Enforce singleton — always pk=1
        self.pk = 1
        super().save(*args, **kwargs)
        self.apply_to_django_settings()

    def delete(self, *args, **kwargs):
        pass  # Prevent deletion of the singleton

    @classmethod
    def load(cls):
        """Load the singleton instance, creating with defaults if needed."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def apply_to_django_settings(self):
        """Push current values into django.conf.settings at runtime."""
        from django.conf import settings as django_settings

        django_settings.EMAIL_HOST = self.smtp_host
        django_settings.EMAIL_PORT = self.smtp_port
        django_settings.EMAIL_USE_TLS = self.smtp_use_tls
        django_settings.EMAIL_HOST_USER = self.smtp_username
        django_settings.EMAIL_HOST_PASSWORD = self.smtp_password
        if self.from_name:
            django_settings.DEFAULT_FROM_EMAIL = f"{self.from_name} <{self.from_email}>"
        else:
            django_settings.DEFAULT_FROM_EMAIL = self.from_email
        # Switch to SMTP backend if host and credentials are configured
        if self.smtp_host and self.smtp_host != "localhost":
            django_settings.EMAIL_BACKEND = (
                "django.core.mail.backends.smtp.EmailBackend"
            )
