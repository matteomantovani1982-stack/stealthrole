"""
tests/e2e/test_analytics.py

End-to-end tests for GET /api/v1/analytics/summary.
"""

import uuid

import httpx
import pytest

BASE_URL = "http://localhost:8000"


@pytest.fixture(scope="module")
def auth_headers():
    """Register + login, return auth headers."""
    email = f"analytics_test_{uuid.uuid4().hex[:8]}@test.com"
    password = "TestPass123!"

    httpx.post(f"{BASE_URL}/api/v1/auth/register", json={
        "email": email,
        "password": password,
        "full_name": "Analytics Tester",
    })

    r = httpx.post(f"{BASE_URL}/api/v1/auth/login", json={
        "email": email,
        "password": password,
    })
    assert r.status_code == 200
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestAnalyticsSummary:
    """GET /api/v1/analytics/summary"""

    def test_summary_returns_200(self, auth_headers):
        """Should return 200 with expected shape."""
        r = httpx.get(f"{BASE_URL}/api/v1/analytics/summary", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "total_applications" in data
        assert isinstance(data["total_applications"], int)
        assert "by_stage" in data
        assert isinstance(data["by_stage"], dict)
        assert "response_rate" in data
        assert isinstance(data["response_rate"], (int, float))
        assert "avg_keyword_score" in data
        # avg_keyword_score can be float or null
        assert data["avg_keyword_score"] is None or isinstance(data["avg_keyword_score"], (int, float))

    def test_summary_unauthenticated(self):
        """Should return 401 without auth."""
        r = httpx.get(f"{BASE_URL}/api/v1/analytics/summary")
        assert r.status_code in (401, 403)
