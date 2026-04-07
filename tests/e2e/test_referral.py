"""
tests/e2e/test_referral.py

End-to-end tests for referral endpoints.
"""

import uuid

import httpx
import pytest

BASE_URL = "http://localhost:8000"


def _register_and_login(name_prefix: str) -> dict:
    email = f"{name_prefix}_{uuid.uuid4().hex[:8]}@test.com"
    password = "TestPass123!"
    httpx.post(f"{BASE_URL}/api/v1/auth/register", json={
        "email": email,
        "password": password,
        "full_name": f"{name_prefix} Tester",
    })
    r = httpx.post(f"{BASE_URL}/api/v1/auth/login", json={
        "email": email,
        "password": password,
    })
    assert r.status_code == 200
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def auth_headers():
    return _register_and_login("ref_test")


@pytest.fixture(scope="module")
def second_user_headers():
    return _register_and_login("ref_test2")


class TestReferralStats:
    def test_stats_returns_200(self, auth_headers):
        r = httpx.get(f"{BASE_URL}/api/v1/referral/stats", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "referral_code" in data
        assert isinstance(data["referral_code"], str)
        assert len(data["referral_code"]) == 8
        assert "referral_count" in data
        assert "credits_earned" in data

    def test_stats_lazy_code_generation(self, auth_headers):
        """Calling stats twice should return the same code."""
        r1 = httpx.get(f"{BASE_URL}/api/v1/referral/stats", headers=auth_headers)
        r2 = httpx.get(f"{BASE_URL}/api/v1/referral/stats", headers=auth_headers)
        assert r1.json()["referral_code"] == r2.json()["referral_code"]

    def test_stats_unauthenticated(self):
        r = httpx.get(f"{BASE_URL}/api/v1/referral/stats")
        assert r.status_code in (401, 403)


class TestReferralApply:
    def test_apply_valid_code(self, auth_headers, second_user_headers):
        # Get the first user's referral code
        r = httpx.get(f"{BASE_URL}/api/v1/referral/stats", headers=auth_headers)
        code = r.json()["referral_code"]

        # Second user applies the code
        r = httpx.post(
            f"{BASE_URL}/api/v1/referral/apply",
            json={"referral_code": code},
            headers=second_user_headers,
        )
        assert r.status_code == 200
        assert r.json()["referred_by"] == code

        # First user should now have referral_count = 1
        r = httpx.get(f"{BASE_URL}/api/v1/referral/stats", headers=auth_headers)
        assert r.json()["referral_count"] >= 1

    def test_apply_duplicate_rejected(self, auth_headers, second_user_headers):
        """Applying a second referral code should be rejected."""
        r = httpx.get(f"{BASE_URL}/api/v1/referral/stats", headers=auth_headers)
        code = r.json()["referral_code"]

        r = httpx.post(
            f"{BASE_URL}/api/v1/referral/apply",
            json={"referral_code": code},
            headers=second_user_headers,
        )
        assert r.status_code == 409

    def test_apply_invalid_code(self, auth_headers):
        r = httpx.post(
            f"{BASE_URL}/api/v1/referral/apply",
            json={"referral_code": "ZZZZZZZZ"},
            headers=auth_headers,
        )
        assert r.status_code == 404

    def test_apply_unauthenticated(self):
        r = httpx.post(
            f"{BASE_URL}/api/v1/referral/apply",
            json={"referral_code": "anything"},
        )
        assert r.status_code in (401, 403)
