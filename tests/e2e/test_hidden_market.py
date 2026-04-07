"""
tests/e2e/test_hidden_market.py

End-to-end tests for Hidden Market signal detection.

Tests cover:
  - GET /api/v1/scout/hidden-market — returns 200 with expected shape
  - Response has signals array
  - 401 on unauthenticated request
  - Each signal has required fields
"""

import uuid

import pytest
import httpx

BASE_URL = "http://localhost:8000"

REQUIRED_SIGNAL_FIELDS = {"id", "company_name", "signal_type", "confidence", "likely_roles"}


@pytest.fixture(scope="module")
def auth_headers():
    """Register + login, return auth headers."""
    email = f"hidden_test_{uuid.uuid4().hex[:8]}@test.com"
    password = "TestPass123!"

    r = httpx.post(f"{BASE_URL}/api/v1/auth/register", json={
        "email": email,
        "password": password,
        "full_name": "Hidden Market Tester",
    })
    assert r.status_code in (200, 201, 409)

    r = httpx.post(f"{BASE_URL}/api/v1/auth/login", json={
        "email": email,
        "password": password,
    })
    assert r.status_code == 200
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestHiddenMarket:
    """GET /api/v1/scout/hidden-market"""

    def test_returns_200_with_expected_shape(self, auth_headers):
        """Should return 200 with signals array and total count."""
        r = httpx.get(
            f"{BASE_URL}/api/v1/scout/hidden-market",
            headers=auth_headers,
            timeout=30.0,
        )
        assert r.status_code == 200
        data = r.json()
        assert "signals" in data
        assert "total" in data
        assert isinstance(data["signals"], list)
        assert isinstance(data["total"], int)
        assert data["total"] == len(data["signals"])

    def test_signals_array_present(self, auth_headers):
        """Response should always contain a signals array (may be empty without API keys)."""
        r = httpx.get(
            f"{BASE_URL}/api/v1/scout/hidden-market",
            headers=auth_headers,
            timeout=30.0,
        )
        assert r.status_code == 200
        data = r.json()
        assert "signals" in data
        assert isinstance(data["signals"], list)

    def test_signal_has_required_fields(self, auth_headers):
        """If signals are returned, each must have required fields."""
        r = httpx.get(
            f"{BASE_URL}/api/v1/scout/hidden-market",
            headers=auth_headers,
            timeout=30.0,
        )
        assert r.status_code == 200
        data = r.json()
        for signal in data["signals"]:
            missing = REQUIRED_SIGNAL_FIELDS - set(signal.keys())
            assert not missing, f"Signal missing fields: {missing}"

    def test_unauthenticated_returns_401(self):
        """Should return 401/403 without auth token."""
        r = httpx.get(f"{BASE_URL}/api/v1/scout/hidden-market", timeout=10.0)
        assert r.status_code in (401, 403)
