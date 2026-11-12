import django.db.models.deletion
from django.db import migrations, models


def migrate_signatory_data(apps, schema_editor):
    """Migrate existing director/accountant data to Signatory records."""
    CompanyInfo = apps.get_model("settings_app", "CompanyInfo")
    Signatory = apps.get_model("settings_app", "Signatory")

    for info in CompanyInfo.objects.all():
        old_signatory_choice = getattr(info, "pdf_signatory_old", "") or ""
        director_name = getattr(info, "director_name", "") or ""
        accountant_name = getattr(info, "accountant_name", "") or ""

        director_sig = None
        accountant_sig = None

        if director_name:
            director_sig = Signatory.objects.create(
                label="Directeur Gérant",
                name=director_name,
                order=0,
            )

        if accountant_name:
            accountant_sig = Signatory.objects.create(
                label="Comptabilité",
                name=accountant_name,
                order=1,
            )

        # Set selected signatory based on old choice
        selected = None
        if old_signatory_choice == "director":
            selected = director_sig
        elif old_signatory_choice == "accountant":
            selected = accountant_sig

        if selected is not None:
            CompanyInfo.objects.filter(pk=info.pk).update(pdf_signatory_new=selected)


class Migration(migrations.Migration):

    dependencies = [
        ("settings_app", "0010_add_pdf_show_signatory_image"),
    ]

    operations = [
        # 1. Create Signatory model
        migrations.CreateModel(
            name="Signatory",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("label", models.CharField(help_text="Title shown on invoice, e.g. 'Directeur Général', 'Comptable'", max_length=100)),
                ("name", models.CharField(blank=True, default="", help_text="Optional full name of the signatory", max_length=200)),
                ("signature_image", models.FileField(blank=True, default="", help_text="Optional handwritten signature image (PNG, JPG, WEBP). Max 2 MB.", upload_to="company/signatures/")),
                ("order", models.PositiveIntegerField(default=0, help_text="Display order (lower = first)")),
            ],
            options={
                "verbose_name": "Signatory",
                "verbose_name_plural": "Signatories",
                "ordering": ["order", "id"],
            },
        ),
        # 2. Add temporary FK field to CompanyInfo (db column: pdf_signatory_new_id)
        migrations.AddField(
            model_name="companyinfo",
            name="pdf_signatory_new",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="selected_for_invoices",
                to="settings_app.signatory",
            ),
        ),
        # 3. Rename old pdf_signatory CharField to pdf_signatory_old to avoid collision
        migrations.RenameField(
            model_name="companyinfo",
            old_name="pdf_signatory",
            new_name="pdf_signatory_old",
        ),
        # 4. Migrate data from old director/accountant fields to Signatory records
        migrations.RunPython(migrate_signatory_data, reverse_code=migrations.RunPython.noop),
        # 5. Remove old fields
        migrations.RemoveField(model_name="companyinfo", name="director_name"),
        migrations.RemoveField(model_name="companyinfo", name="accountant_name"),
        migrations.RemoveField(model_name="companyinfo", name="director_signature"),
        migrations.RemoveField(model_name="companyinfo", name="accountant_signature"),
        migrations.RemoveField(model_name="companyinfo", name="pdf_signatory_old"),
        migrations.RemoveField(model_name="companyinfo", name="pdf_signatory_show_name"),
        migrations.RemoveField(model_name="companyinfo", name="pdf_show_signatory_image"),
        # 6. Rename pdf_signatory_new -> pdf_signatory
        migrations.RenameField(
            model_name="companyinfo",
            old_name="pdf_signatory_new",
            new_name="pdf_signatory",
        ),
    ]
