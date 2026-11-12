from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("settings_app", "0009_add_signature_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="companyinfo",
            name="pdf_show_signatory_image",
            field=models.BooleanField(
                default=True,
                help_text="Include the uploaded signature image on invoices",
            ),
        ),
    ]
