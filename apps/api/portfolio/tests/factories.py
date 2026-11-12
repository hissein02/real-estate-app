import factory
from factory.django import DjangoModelFactory

from portfolio.models import Owner, Property, Unit


class OwnerFactory(DjangoModelFactory):
    class Meta:
        model = Owner

    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    is_company = False
    email = factory.Faker("email")
    phone = factory.Faker("phone_number")


class PropertyFactory(DjangoModelFactory):
    class Meta:
        model = Property

    name = factory.Faker("company")
    property_type = "residential"
    owner = factory.SubFactory(OwnerFactory)
    address_line1 = factory.Faker("street_address")
    city = "Ndjamena"
    country = "Tchad"


class UnitFactory(DjangoModelFactory):
    class Meta:
        model = Unit

    building = factory.SubFactory(PropertyFactory)
    name = factory.Sequence(lambda n: f"Unit {n + 1}")
    unit_type = "apartment"
    is_active = True
