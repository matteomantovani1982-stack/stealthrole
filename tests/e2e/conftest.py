"""
tests/e2e/conftest.py

Shared fixtures for end-to-end tests.
"""

import uuid
import pytest
import httpx

BASE_URL = "http://localhost:8000"


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


@pytest.fixture(scope="session")
def test_user():
    """Register a unique test user and return credentials."""
    email = f"e2e_test_{uuid.uuid4().hex[:8]}@test.com"
    password = "E2eTestPass123!"
    name = "E2E Test User"

    r = httpx.post(f"{BASE_URL}/api/v1/auth/register", json={
        "email": email,
        "password": password,
        "full_name": name,
    }, timeout=10)
    assert r.status_code in (200, 201), f"Registration failed: {r.text}"

    return {"email": email, "password": password, "full_name": name}


@pytest.fixture(scope="session")
def auth_headers(test_user):
    """Login and return auth headers."""
    r = httpx.post(f"{BASE_URL}/api/v1/auth/login", json={
        "email": test_user["email"],
        "password": test_user["password"],
    }, timeout=10)
    assert r.status_code == 200, f"Login failed: {r.text}"
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
