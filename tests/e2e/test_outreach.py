"""
tests/e2e/test_outreach.py

End-to-end tests for the Outreach Generator endpoint.

POST /api/v1/outreach/generate
"""

import uuid

import pytest
import httpx

BASE_URL = "http://localhost:8000"


@pytest.fixture(scope="module")
def auth_headers():
    """Register + login, return auth headers."""
    email = f"outreach_test_{uuid.uuid4().hex[:8]}@test.com"
    password = "TestPass123!"

    r = httpx.post(f"{BASE_URL}/api/v1/auth/register", json={
        "email": email,
        "password": password,
        "full_name": "Outreach Tester",
    })
    assert r.status_code in (200, 201, 409)

    r = httpx.post(f"{BASE_URL}/api/v1/auth/login", json={
        "email": email,
        "password": password,
    })
    assert r.status_code == 200
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestOutreachGenerate:
    """POST /api/v1/outreach/generate"""

    def test_generate_success(self, auth_headers):
        """Should return 200 with all outreach fields."""
        r = httpx.post(
            f"{BASE_URL}/api/v1/outreach/generate",
            headers=auth_headers,
            json={
                "company": "Acme Corp",
                "role": "Senior Engineer",
                "signal_context": "Acme just raised Series B",
                "tone": "confident",
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert "linkedin_note" in data
        assert "cold_email" in data
        assert "follow_up" in data
        assert data["company"] == "Acme Corp"
        assert data["role"] == "Senior Engineer"
        assert data["tone"] == "confident"
        # LinkedIn note should be non-empty
        assert len(data["linkedin_note"]) > 0
        assert len(data["cold_email"]) > 0
        assert len(data["follow_up"]) > 0

    def test_generate_default_tone(self, auth_headers):
        """Should default to 'confident' tone."""
        r = httpx.post(
            f"{BASE_URL}/api/v1/outreach/generate",
            headers=auth_headers,
            json={
                "company": "DefaultCo",
                "role": "Product Manager",
            },
        )
        assert r.status_code == 200
        assert r.json()["tone"] == "confident"

    def test_missing_company(self, auth_headers):
        """Should return 422 when company is missing."""
        r = httpx.post(
            f"{BASE_URL}/api/v1/outreach/generate",
            headers=auth_headers,
            json={
                "role": "Engineer",
            },
        )
        assert r.status_code == 422

    def test_missing_role(self, auth_headers):
        """Should return 422 when role is missing."""
        r = httpx.post(
            f"{BASE_URL}/api/v1/outreach/generate",
            headers=auth_headers,
            json={
                "company": "TestCo",
            },
        )
        assert r.status_code == 422

    def test_invalid_tone(self, auth_headers):
        """Should return 422 for invalid tone value."""
        r = httpx.post(
            f"{BASE_URL}/api/v1/outreach/generate",
            headers=auth_headers,
            json={
                "company": "TestCo",
                "role": "Engineer",
                "tone": "aggressive",
            },
        )
        assert r.status_code == 422

    def test_unauthenticated(self):
        """Should return 401 without auth headers."""
        r = httpx.post(
            f"{BASE_URL}/api/v1/outreach/generate",
            json={
                "company": "TestCo",
                "role": "Engineer",
            },
        )
        assert r.status_code in (401, 403)
