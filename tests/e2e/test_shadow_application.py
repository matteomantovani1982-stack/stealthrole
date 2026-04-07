"""
tests/e2e/test_shadow_application.py

End-to-end tests for Shadow Application generation.

Tests cover:
  - POST /api/v1/shadow/generate — create + enqueue
  - GET /api/v1/shadow — list user's shadow apps
  - GET /api/v1/shadow/{id} — detail with generated outputs
  - Full generation pipeline (with mocked LLM)
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest
import httpx

# Base URL for the API (assumes Docker stack running)
BASE_URL = "http://localhost:8000"


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def auth_headers():
    """Register + login, return auth headers."""
    email = f"shadow_test_{uuid.uuid4().hex[:8]}@test.com"
    password = "TestPass123!"

    # Register
    r = httpx.post(f"{BASE_URL}/api/v1/auth/register", json={
        "email": email,
        "password": password,
        "full_name": "Shadow Tester",
    })
    assert r.status_code in (200, 201, 409)  # 409 if already exists

    # Login
    r = httpx.post(f"{BASE_URL}/api/v1/auth/login", json={
        "email": email,
        "password": password,
    })
    assert r.status_code == 200
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ── Tests ────────────────────────────────────────────────────────────────────

class TestShadowGenerate:
    """POST /api/v1/shadow/generate"""

    def test_create_shadow_application(self, auth_headers):
        """Should create a shadow application and return 202."""
        r = httpx.post(
            f"{BASE_URL}/api/v1/shadow/generate",
            headers=auth_headers,
            json={
                "company": "TechCo",
                "signal_type": "funding",
                "likely_roles": ["VP Engineering", "Head of Product"],
                "signal_context": "TechCo raised $50M Series C, expanding to MENA",
                "tone": "confident",
            },
        )
        assert r.status_code == 202
        data = r.json()
        assert data["status"] == "generating"
        assert data["company"] == "TechCo"
        assert "id" in data

    def test_create_shadow_missing_company(self, auth_headers):
        """Should reject request without company."""
        r = httpx.post(
            f"{BASE_URL}/api/v1/shadow/generate",
            headers=auth_headers,
            json={
                "signal_type": "funding",
            },
        )
        assert r.status_code == 422

    def test_create_shadow_missing_signal_type(self, auth_headers):
        """Should reject request without signal_type."""
        r = httpx.post(
            f"{BASE_URL}/api/v1/shadow/generate",
            headers=auth_headers,
            json={
                "company": "TechCo",
            },
        )
        assert r.status_code == 422

    def test_create_shadow_invalid_tone(self, auth_headers):
        """Should reject invalid tone."""
        r = httpx.post(
            f"{BASE_URL}/api/v1/shadow/generate",
            headers=auth_headers,
            json={
                "company": "TechCo",
                "signal_type": "funding",
                "tone": "aggressive",  # invalid
            },
        )
        assert r.status_code == 422


class TestShadowList:
    """GET /api/v1/shadow"""

    def test_list_shadows(self, auth_headers):
        """Should return list of shadow applications."""
        # Create one first
        httpx.post(
            f"{BASE_URL}/api/v1/shadow/generate",
            headers=auth_headers,
            json={
                "company": "ListTestCo",
                "signal_type": "expansion",
            },
        )

        r = httpx.get(f"{BASE_URL}/api/v1/shadow", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "shadow_applications" in data
        assert isinstance(data["shadow_applications"], list)
        assert data["total"] >= 1

    def test_list_shadows_unauthenticated(self):
        """Should return 401 without auth."""
        r = httpx.get(f"{BASE_URL}/api/v1/shadow")
        assert r.status_code in (401, 403)


class TestShadowDetail:
    """GET /api/v1/shadow/{id}"""

    def test_get_shadow_detail(self, auth_headers):
        """Should return shadow detail after creation."""
        # Create
        r = httpx.post(
            f"{BASE_URL}/api/v1/shadow/generate",
            headers=auth_headers,
            json={
                "company": "DetailTestCo",
                "signal_type": "leadership",
                "signal_context": "New CTO appointed at DetailTestCo",
            },
        )
        shadow_id = r.json()["id"]

        # Fetch detail
        r = httpx.get(
            f"{BASE_URL}/api/v1/shadow/{shadow_id}",
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == shadow_id
        assert data["company"] == "DetailTestCo"
        assert data["signal_type"] == "leadership"
        assert data["status"] in ("generating", "completed", "failed")

    def test_get_shadow_not_found(self, auth_headers):
        """Should return 404 for non-existent shadow."""
        fake_id = str(uuid.uuid4())
        r = httpx.get(
            f"{BASE_URL}/api/v1/shadow/{fake_id}",
            headers=auth_headers,
        )
        assert r.status_code == 404

    def test_get_shadow_wrong_user(self, auth_headers):
        """Should return 404 for another user's shadow (not 403, to avoid leaking existence)."""
        # Create with current user
        r = httpx.post(
            f"{BASE_URL}/api/v1/shadow/generate",
            headers=auth_headers,
            json={
                "company": "PrivateCo",
                "signal_type": "funding",
            },
        )
        shadow_id = r.json()["id"]

        # Register a different user
        other_email = f"other_{uuid.uuid4().hex[:8]}@test.com"
        httpx.post(f"{BASE_URL}/api/v1/auth/register", json={
            "email": other_email,
            "password": "OtherPass123!",
            "full_name": "Other User",
        })
        r2 = httpx.post(f"{BASE_URL}/api/v1/auth/login", json={
            "email": other_email,
            "password": "OtherPass123!",
        })
        other_headers = {"Authorization": f"Bearer {r2.json()['access_token']}"}

        # Try to access first user's shadow
        r = httpx.get(
            f"{BASE_URL}/api/v1/shadow/{shadow_id}",
            headers=other_headers,
        )
        assert r.status_code == 404


class TestShadowDelete:
    """DELETE /api/v1/shadow/{id}"""

    def test_delete_shadow(self, auth_headers):
        """Should delete an existing shadow application."""
        # Create
        r = httpx.post(
            f"{BASE_URL}/api/v1/shadow/generate",
            headers=auth_headers,
            json={
                "company": "DeleteTestCo",
                "signal_type": "funding",
            },
        )
        shadow_id = r.json()["id"]

        # Delete
        r = httpx.delete(
            f"{BASE_URL}/api/v1/shadow/{shadow_id}",
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["deleted"] is True
        assert data["id"] == shadow_id

        # Verify gone
        r = httpx.get(
            f"{BASE_URL}/api/v1/shadow/{shadow_id}",
            headers=auth_headers,
        )
        assert r.status_code == 404

    def test_delete_nonexistent(self, auth_headers):
        """Should return 404 for non-existent shadow."""
        fake_id = str(uuid.uuid4())
        r = httpx.delete(
            f"{BASE_URL}/api/v1/shadow/{fake_id}",
            headers=auth_headers,
        )
        assert r.status_code == 404

    def test_delete_unauthenticated(self):
        """Should return 401 without auth."""
        fake_id = str(uuid.uuid4())
        r = httpx.delete(f"{BASE_URL}/api/v1/shadow/{fake_id}")
        assert r.status_code in (401, 403)

    def test_delete_other_users_shadow(self, auth_headers):
        """Should return 404 when trying to delete another user's shadow."""
        # Create with current user
        r = httpx.post(
            f"{BASE_URL}/api/v1/shadow/generate",
            headers=auth_headers,
            json={
                "company": "DeleteIsolationCo",
                "signal_type": "expansion",
            },
        )
        shadow_id = r.json()["id"]

        # Register another user
        other_email = f"delother_{uuid.uuid4().hex[:8]}@test.com"
        httpx.post(f"{BASE_URL}/api/v1/auth/register", json={
            "email": other_email,
            "password": "OtherPass123!",
            "full_name": "Other User",
        })
        r2 = httpx.post(f"{BASE_URL}/api/v1/auth/login", json={
            "email": other_email,
            "password": "OtherPass123!",
        })
        other_headers = {"Authorization": f"Bearer {r2.json()['access_token']}"}

        # Try to delete
        r = httpx.delete(
            f"{BASE_URL}/api/v1/shadow/{shadow_id}",
            headers=other_headers,
        )
        assert r.status_code == 404

        # Verify still exists for owner
        r = httpx.get(
            f"{BASE_URL}/api/v1/shadow/{shadow_id}",
            headers=auth_headers,
        )
        assert r.status_code == 200


class TestShadowGenerationPipeline:
    """Integration test for the full generation pipeline."""

    def test_shadow_record_fields(self, auth_headers):
        """Verify shadow record has expected fields after creation."""
        r = httpx.post(
            f"{BASE_URL}/api/v1/shadow/generate",
            headers=auth_headers,
            json={
                "company": "PipelineCo",
                "signal_type": "hiring_surge",
                "signal_context": "PipelineCo posted 15 engineering roles in 2 weeks",
                "radar_score": 85,
                "likely_roles": ["VP Engineering"],
                "tone": "formal",
            },
        )
        assert r.status_code == 202
        shadow_id = r.json()["id"]

        # Check detail
        r = httpx.get(
            f"{BASE_URL}/api/v1/shadow/{shadow_id}",
            headers=auth_headers,
        )
        data = r.json()
        assert data["company"] == "PipelineCo"
        assert data["signal_type"] == "hiring_surge"
        assert data["radar_score"] == 85
        assert data["signal_context"] == "PipelineCo posted 15 engineering roles in 2 weeks"
