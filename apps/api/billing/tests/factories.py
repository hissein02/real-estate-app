import random
import string
from datetime import date
from decimal import Decimal

import factory
from factory.django import DjangoModelFactory

from billing.models import (
    Invoice,
    InvoiceLine,
    InvoiceStatus,
    InvoiceLineType,
    Payment,
    PaymentStatus,
    PaymentMethod,
    Allocation,
)
from tenants.tests.factories import LeaseFactory, UserFactory


class InvoiceFactory(DjangoModelFactory):
    class Meta:
        model = Invoice

    lease = factory.SubFactory(LeaseFactory)
    invoice_number = factory.LazyFunction(
        lambda: "INV-" + "".join(random.choices(string.digits, k=8))
    )
    period_start = factory.Faker("date_this_year")
    period_end = factory.LazyAttribute(lambda o: o.period_start.replace(day=28))
    due_date = factory.SelfAttribute("period_start")
    currency = "XAF"
    total_amount = factory.Faker("pydecimal", left_digits=5, right_digits=2, positive=True)
    paid_amount = Decimal("0")
    status = InvoiceStatus.ISSUED
    created_by = factory.SubFactory(UserFactory)


class PaymentFactory(DjangoModelFactory):
    class Meta:
        model = Payment

    lease = factory.SubFactory(LeaseFactory)
    amount = factory.Faker("pydecimal", left_digits=5, right_digits=2, positive=True)
    currency = "XAF"
    payment_date = factory.Faker("date_this_year")
    payment_method = PaymentMethod.CASH
    status = PaymentStatus.POSTED
    created_by = factory.SubFactory(UserFactory)
