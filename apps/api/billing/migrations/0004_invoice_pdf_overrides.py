from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0003_add_invoice_date"),
    ]

    operations = [
        migrations.AddField(
            model_name="invoice",
            name="pdf_overrides",
            field=models.JSONField(
                blank=True,
                default=None,
                help_text=(
                    "Per-invoice PDF display overrides (signatory, RCCM, NIF, bank display). "
                    "When set, these take precedence over company-level defaults."
                ),
                null=True,
            ),
        ),
    ]
