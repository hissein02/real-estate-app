import pytest
from django.urls import reverse

from portfolio.tests.factories import OwnerFactory, PropertyFactory, UnitFactory


@pytest.mark.django_db
class TestOwnerViewSet:
    def test_list_requires_auth(self, api_client):
        resp = api_client.get(reverse("owner-list"))
        assert resp.status_code == 401

    def test_list_returns_owners(self, admin_client):
        OwnerFactory.create_batch(3)
        resp = admin_client.get(reverse("owner-list"))
        assert resp.status_code == 200
        assert resp.data["count"] == 3

    def test_create_owner(self, manager_client):
        resp = manager_client.post(
            reverse("owner-list"),
            {"first_name": "Jean", "last_name": "Dupont", "email": "jean@test.com"},
        )
        assert resp.status_code == 201
        assert resp.data["last_name"] == "Dupont"

    def test_readonly_cannot_create(self, readonly_client):
        resp = readonly_client.post(
            reverse("owner-list"),
            {"first_name": "Jean", "last_name": "Dupont"},
        )
        assert resp.status_code == 403


@pytest.mark.django_db
class TestPropertyViewSet:
    def test_list(self, admin_client):
        PropertyFactory.create_batch(2)
        resp = admin_client.get(reverse("property-list"))
        assert resp.status_code == 200
        assert resp.data["count"] == 2

    def test_detail_includes_units(self, admin_client):
        prop = PropertyFactory()
        UnitFactory.create_batch(3, building=prop)
        resp = admin_client.get(reverse("property-detail", args=[prop.pk]))
        assert resp.status_code == 200
        assert len(resp.data["units"]) == 3

    def test_filter_by_city(self, admin_client):
        PropertyFactory(city="Ndjamena")
        PropertyFactory(city="Moundou")
        resp = admin_client.get(reverse("property-list") + "?city=Ndjamena")
        assert resp.status_code == 200
        assert resp.data["count"] == 1


@pytest.mark.django_db
class TestUnitViewSet:
    def test_filter_by_property(self, admin_client):
        prop = PropertyFactory()
        UnitFactory.create_batch(3, building=prop)
        UnitFactory.create_batch(2)  # different property
        resp = admin_client.get(reverse("unit-list") + f"?building={prop.pk}")
        assert resp.status_code == 200
        assert resp.data["count"] == 3
