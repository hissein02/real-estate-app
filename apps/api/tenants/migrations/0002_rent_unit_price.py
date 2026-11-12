"""Rent becomes an explicit unit price.

`rent_amount` held the amount for a whole billing period, which made the field
ambiguous (a 6-month lease showing "9 600 000" tells you nothing about the
monthly rate) and made proration divide a multi-month figure by days in a single
month. It is renamed to `rent_unit_price` and converted to a per-month rate;
the billed amount is now unit price x billing_interval_months.
"""

from decimal import ROUND_HALF_UP, Decimal

import django.core.validators
from django.db import migrations, models


def period_total_to_unit_price(apps, schema_editor):
    Lease = apps.get_model("tenants", "Lease")
    for lease in Lease.objects.all().iterator():
        interval = lease.billing_interval_months or 1
        if interval == 1:
            continue
        lease.rent_unit_price = (lease.rent_unit_price / interval).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        lease.save(update_fields=["rent_unit_price"])


def unit_price_to_period_total(apps, schema_editor):
    Lease = apps.get_model("tenants", "Lease")
    for lease in Lease.objects.all().iterator():
        interval = lease.billing_interval_months or 1
        if interval == 1:
            continue
        lease.rent_unit_price = (lease.rent_unit_price * interval).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        lease.save(update_fields=["rent_unit_price"])


class Migration(migrations.Migration):

    dependencies = [("tenants", "0001_initial")]

    operations = [
        migrations.RenameField(
            model_name="lease",
            old_name="rent_amount",
            new_name="rent_unit_price",
        ),
        migrations.AlterField(
            model_name="lease",
            name="rent_unit_price",
            field=models.DecimalField(
                decimal_places=2,
                max_digits=14,
                help_text="Rent for one month. Billed amount = this x billing interval.",
                validators=[django.core.validators.MinValueValidator(Decimal("0"))],
            ),
        ),
        migrations.RunPython(period_total_to_unit_price, unit_price_to_period_total),
    ]
