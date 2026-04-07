"""
tests/e2e/test_dashboard.py

End-to-end tests for GET /api/v1/dashboard/summary.
"""

import uuid

import httpx
import pytest

BASE_URL = "http://localhost:8000"


@pytest.fixture(scope="module")
def auth_headers():
    """Register + login, return auth headers."""
    email = f"dashboard_test_{uuid.uuid4().hex[:8]}@test.com"
    password = "TestPass123!"

    httpx.post(f"{BASE_URL}/api/v1/auth/register", json={
        "email": email,
        "password": password,
        "full_name": "Dashboard Tester",
    })

    r = httpx.post(f"{BASE_URL}/api/v1/auth/login", json={
        "email": email,
        "password": password,
    })
    assert r.status_code == 200
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestDashboardSummary:
    """GET /api/v1/dashboard/summary"""

    def test_summary_returns_200(self, auth_headers):
        """Should return 200 with expected keys."""
        r = httpx.get(f"{BASE_URL}/api/v1/dashboard/summary", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "profile_strength" in data
        assert "top_opportunities" in data
        assert "recent_applications" in data
        assert "shadow_count" in data
        assert "credit_balance" in data

        # profile_strength shape
        ps = data["profile_strength"]
        assert "score" in ps
        assert "max" in ps
        assert "breakdown" in ps
        assert "next_action" in ps

        assert isinstance(data["top_opportunities"], list)
        assert isinstance(data["recent_applications"], list)
        assert isinstance(data["shadow_count"], int)

    def test_summary_unauthenticated(self):
        """Should return 401 without auth."""
        r = httpx.get(f"{BASE_URL}/api/v1/dashboard/summary")
        assert r.status_code in (401, 403)
