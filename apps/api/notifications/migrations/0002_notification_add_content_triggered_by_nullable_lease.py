import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0001_initial"),
        ("tenants", "0001_initial"),
    ]

    operations = [
        # Make lease nullable (SET_NULL so history survives lease deletion)
        migrations.AlterField(
            model_name="notification",
            name="lease",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="notifications",
                to="tenants.lease",
            ),
        ),
        # Add content field (plain-text summary shown in the log)
        migrations.AddField(
            model_name="notification",
            name="content",
            field=models.TextField(
                blank=True,
                default="",
                help_text="Plain-text summary of the email, displayed in the notification log",
            ),
        ),
        # Add triggered_by field
        migrations.AddField(
            model_name="notification",
            name="triggered_by",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Who triggered the send – e.g. 'System', 'Admin: John Doe'",
                max_length=200,
            ),
        ),
    ]
