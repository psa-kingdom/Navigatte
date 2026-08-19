"""Pytest fixtures and test database setup."""

import asyncio
import pytest
from fastapi.testclient import TestClient
from server import app
import core.database as db_module
from core.database import get_database
from core.security import create_access_token, hash_password
from models.admin import AdminUser
from services.seeder import seed_demo_projects
from tests.mock_db import MockDatabase

TEST_ADMIN_EMAIL = "testadmin@navigatte.com"
TEST_ADMIN_PASSWORD = "TestAdmin@Navigatte2026"

# Create a shared in-memory test database
mock_db_instance = MockDatabase()


async def _init_mock_db():
    await seed_demo_projects(mock_db_instance)
    admin = AdminUser(
        email=TEST_ADMIN_EMAIL,
        password_hash=hash_password(TEST_ADMIN_PASSWORD),
    )
    await mock_db_instance.admin_users.insert_one(admin.to_mongo())
    return admin


test_admin_record = asyncio.run(_init_mock_db())


def get_mock_database():
    return mock_db_instance


# Override database dependency across the entire app
app.dependency_overrides[get_database] = get_mock_database
db_module.db = mock_db_instance


@pytest.fixture(scope="session")
def client():
    """Provides a synchronous FastAPI TestClient connected to the mock database."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def test_admin_user():
    """Provides test admin user info and access token."""
    token = create_access_token(test_admin_record.id, test_admin_record.email)
    return {
        "admin": test_admin_record,
        "token": token,
        "email": TEST_ADMIN_EMAIL,
        "password": TEST_ADMIN_PASSWORD,
    }


@pytest.fixture
def auth_headers(test_admin_user):
    """Returns headers with Authorization Bearer token."""
    return {"Authorization": f"Bearer {test_admin_user['token']}"}


@pytest.fixture
def authenticated_client(client, test_admin_user):
    """Provides a TestClient with pre-authenticated admin cookies and Bearer headers."""
    client.cookies.set("access_token", test_admin_user["token"])
    client.headers.update({"Authorization": f"Bearer {test_admin_user['token']}"})
    return client
