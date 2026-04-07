"""
tests/e2e/test_profile_strength.py

End-to-end tests for GET /api/v1/profile/strength.
"""

import uuid

import httpx
import pytest

BASE_URL = "http://localhost:8000"


@pytest.fixture(scope="module")
def auth_headers():
    """Register + login, return auth headers."""
    email = f"strength_test_{uuid.uuid4().hex[:8]}@test.com"
    password = "TestPass123!"

    httpx.post(f"{BASE_URL}/api/v1/auth/register", json={
        "email": email,
        "password": password,
        "full_name": "Strength Tester",
    })

    r = httpx.post(f"{BASE_URL}/api/v1/auth/login", json={
        "email": email,
        "password": password,
    })
    assert r.status_code == 200
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestProfileStrength:
    """GET /api/v1/profile/strength"""

    def test_strength_returns_200(self, auth_headers):
        """Should return 200 with score, max, breakdown."""
        r = httpx.get(f"{BASE_URL}/api/v1/profile/strength", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "score" in data
        assert "max" in data
        assert data["max"] == 100
        assert "breakdown" in data
        assert isinstance(data["breakdown"], list)
        assert "next_action" in data
        assert isinstance(data["next_action"], str)

    def test_strength_score_range(self, auth_headers):
        """Score should be between 0 and max."""
        r = httpx.get(f"{BASE_URL}/api/v1/profile/strength", headers=auth_headers)
        data = r.json()
        assert 0 <= data["score"] <= data["max"]

    def test_strength_unauthenticated(self):
        """Should return 401 without auth."""
        r = httpx.get(f"{BASE_URL}/api/v1/profile/strength")
        assert r.status_code in (401, 403)
