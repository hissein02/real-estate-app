import pytest
from django.urls import reverse


@pytest.mark.django_db
class TestLoginView:
    def test_login_success(self, api_client, admin_user):
        url = reverse("auth-login")
        resp = api_client.post(url, {"username": "admin", "password": "TestPass123!"})
        assert resp.status_code == 200
        assert "access" in resp.data
        assert "refresh" in resp.data

    def test_login_wrong_password(self, api_client, admin_user):
        url = reverse("auth-login")
        resp = api_client.post(url, {"username": "admin", "password": "wrong"})
        assert resp.status_code == 401

    def test_me_requires_auth(self, api_client):
        url = reverse("auth-me")
        resp = api_client.get(url)
        assert resp.status_code == 401

    def test_me_returns_user(self, admin_client, admin_user):
        url = reverse("auth-me")
        resp = admin_client.get(url)
        assert resp.status_code == 200
        assert resp.data["username"] == "admin"
        assert resp.data["role"] == "admin"


@pytest.mark.django_db
class TestPermissions:
    def test_admin_can_write(self, admin_user):
        assert admin_user.can_write is True
        assert admin_user.can_manage_finance is True
        assert admin_user.is_admin_role is True

    def test_manager_can_write(self, manager_user):
        assert manager_user.can_write is True
        assert manager_user.can_manage_finance is True
        assert manager_user.is_admin_role is False

    def test_accountant_can_manage_finance(self, accountant_user):
        assert accountant_user.can_write is True
        assert accountant_user.can_manage_finance is True

    def test_agent_can_write(self, agent_user):
        assert agent_user.can_write is True
        assert agent_user.can_manage_finance is False

    def test_readonly_cannot_write(self, readonly_user):
        assert readonly_user.can_write is False
        assert readonly_user.can_manage_finance is False
