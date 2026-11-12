import factory
from factory.django import DjangoModelFactory
from django.contrib.auth import get_user_model
from faker import Faker

from portfolio.tests.factories import UnitFactory
from tenants.models import Tenant, Lease, LeaseStatus, Currency, BillingCycleAnchor

fake = Faker()
User = get_user_model()


class TenantFactory(DjangoModelFactory):
    class Meta:
        model = Tenant

    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    is_company = False
    email = factory.LazyAttribute(lambda o: f"{o.first_name.lower()}.{o.last_name.lower()}@test.com")
    phone = factory.Faker("phone_number")


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.Sequence(lambda n: f"user{n}@test.com")
    role = "admin"

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        return model_class.objects.create_user(*args, **kwargs)


class LeaseFactory(DjangoModelFactory):
    class Meta:
        model = Lease

    unit = factory.SubFactory(UnitFactory)
    tenant = factory.SubFactory(TenantFactory)
    status = LeaseStatus.DRAFT
    start_date = factory.Faker("date_this_year")
    rent_unit_price = factory.Faker("pydecimal", left_digits=5, right_digits=2, positive=True)
    currency = Currency.XAF
    billing_interval_months = 1
    billing_cycle_anchor = BillingCycleAnchor.LEASE_START
    deposit_amount = factory.LazyAttribute(lambda o: o.rent_unit_price)
    created_by = factory.SubFactory(UserFactory)
