import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        username="admin",
        email="admin@test.com",
        password="TestPass123!",
        role="admin",
        first_name="Admin",
        last_name="User",
    )


@pytest.fixture
def manager_user(db):
    return User.objects.create_user(
        username="manager",
        email="manager@test.com",
        password="TestPass123!",
        role="manager",
        first_name="Manager",
        last_name="User",
    )


@pytest.fixture
def accountant_user(db):
    return User.objects.create_user(
        username="accountant",
        email="accountant@test.com",
        password="TestPass123!",
        role="accountant",
        first_name="Accountant",
        last_name="User",
    )


@pytest.fixture
def agent_user(db):
    return User.objects.create_user(
        username="agent",
        email="agent@test.com",
        password="TestPass123!",
        role="agent",
        first_name="Agent",
        last_name="User",
    )


@pytest.fixture
def readonly_user(db):
    return User.objects.create_user(
        username="readonly",
        email="readonly@test.com",
        password="TestPass123!",
        role="read_only",
        first_name="Read",
        last_name="Only",
    )


@pytest.fixture
def admin_client(api_client, admin_user):
    api_client.force_authenticate(user=admin_user)
    return api_client


@pytest.fixture
def manager_client(api_client, manager_user):
    api_client.force_authenticate(user=manager_user)
    return api_client


@pytest.fixture
def accountant_client(api_client, accountant_user):
    api_client.force_authenticate(user=accountant_user)
    return api_client


@pytest.fixture
def agent_client(api_client, agent_user):
    api_client.force_authenticate(user=agent_user)
    return api_client


@pytest.fixture
def readonly_client(api_client, readonly_user):
    api_client.force_authenticate(user=readonly_user)
    return api_client
