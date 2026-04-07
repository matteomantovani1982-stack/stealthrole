"""
tests/e2e/test_saved_jobs.py

End-to-end tests for Saved Jobs (save/list/unsave from scout).

Tests cover:
  - POST /api/v1/scout/jobs/save — save a job
  - GET /api/v1/scout/jobs/saved — list saved jobs
  - DELETE /api/v1/scout/jobs/saved/{id} — unsave
  - 401 on unauthenticated requests
  - User isolation: user B cannot see/delete user A's jobs
"""

import uuid

import httpx
import pytest

BASE_URL = "http://localhost:8000"


def _register_and_login(name: str = "SavedJobTester") -> dict:
    email = f"savedjob_{uuid.uuid4().hex[:8]}@test.com"
    password = "TestPass123!"
    httpx.post(f"{BASE_URL}/api/v1/auth/register", json={
        "email": email,
        "password": password,
        "full_name": name,
    })
    r = httpx.post(f"{BASE_URL}/api/v1/auth/login", json={
        "email": email,
        "password": password,
    })
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def auth_headers():
    return _register_and_login("SavedJobTesterA")


@pytest.fixture(scope="module")
def auth_headers_b():
    return _register_and_login("SavedJobTesterB")


JOB_PAYLOAD = {
    "source": "LinkedIn",
    "external_id": "li-12345",
    "title": "VP Engineering",
    "company": "TestCorp",
    "location": "Dubai, UAE",
    "url": "https://linkedin.com/jobs/12345",
    "salary_min": 300000,
    "salary_max": 500000,
    "metadata": {"posted": "2026-03-01"},
}


class TestSaveJob:
    """POST /api/v1/scout/jobs/save"""

    def test_save_job_success(self, auth_headers):
        r = httpx.post(
            f"{BASE_URL}/api/v1/scout/jobs/save",
            headers=auth_headers,
            json=JOB_PAYLOAD,
        )
        assert r.status_code == 201
        data = r.json()
        assert "id" in data
        assert data["title"] == "VP Engineering"
        assert data["company"] == "TestCorp"
        assert data["source"] == "LinkedIn"

    def test_save_duplicate_returns_existing(self, auth_headers):
        """Saving the same job twice returns the existing record."""
        r1 = httpx.post(
            f"{BASE_URL}/api/v1/scout/jobs/save",
            headers=auth_headers,
            json=JOB_PAYLOAD,
        )
        r2 = httpx.post(
            f"{BASE_URL}/api/v1/scout/jobs/save",
            headers=auth_headers,
            json=JOB_PAYLOAD,
        )
        assert r1.json()["id"] == r2.json()["id"]

    def test_save_job_unauthenticated(self):
        r = httpx.post(
            f"{BASE_URL}/api/v1/scout/jobs/save",
            json=JOB_PAYLOAD,
        )
        assert r.status_code in (401, 403)


class TestListSavedJobs:
    """GET /api/v1/scout/jobs/saved"""

    def test_list_contains_saved_job(self, auth_headers):
        # Save a job first
        httpx.post(
            f"{BASE_URL}/api/v1/scout/jobs/save",
            headers=auth_headers,
            json=JOB_PAYLOAD,
        )
        r = httpx.get(f"{BASE_URL}/api/v1/scout/jobs/saved", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "saved_jobs" in data
        assert data["total"] >= 1
        ids = [j["external_id"] for j in data["saved_jobs"]]
        assert "li-12345" in ids

    def test_list_unauthenticated(self):
        r = httpx.get(f"{BASE_URL}/api/v1/scout/jobs/saved")
        assert r.status_code in (401, 403)


class TestUnsaveJob:
    """DELETE /api/v1/scout/jobs/saved/{id}"""

    def test_unsave_job(self, auth_headers):
        # Save
        payload = {**JOB_PAYLOAD, "external_id": f"del-{uuid.uuid4().hex[:8]}"}
        r = httpx.post(
            f"{BASE_URL}/api/v1/scout/jobs/save",
            headers=auth_headers,
            json=payload,
        )
        job_id = r.json()["id"]

        # Delete
        r = httpx.delete(
            f"{BASE_URL}/api/v1/scout/jobs/saved/{job_id}",
            headers=auth_headers,
        )
        assert r.status_code == 200

        # Verify gone
        r = httpx.get(f"{BASE_URL}/api/v1/scout/jobs/saved", headers=auth_headers)
        ids = [j["id"] for j in r.json()["saved_jobs"]]
        assert job_id not in ids

    def test_unsave_nonexistent(self, auth_headers):
        fake_id = str(uuid.uuid4())
        r = httpx.delete(
            f"{BASE_URL}/api/v1/scout/jobs/saved/{fake_id}",
            headers=auth_headers,
        )
        assert r.status_code == 404

    def test_unsave_unauthenticated(self):
        fake_id = str(uuid.uuid4())
        r = httpx.delete(f"{BASE_URL}/api/v1/scout/jobs/saved/{fake_id}")
        assert r.status_code in (401, 403)


class TestUserIsolation:
    """User B cannot see or delete user A's saved jobs."""

    def test_user_b_cannot_see_user_a_jobs(self, auth_headers, auth_headers_b):
        # User A saves a job
        payload = {**JOB_PAYLOAD, "external_id": f"iso-{uuid.uuid4().hex[:8]}"}
        r = httpx.post(
            f"{BASE_URL}/api/v1/scout/jobs/save",
            headers=auth_headers,
            json=payload,
        )
        job_id = r.json()["id"]

        # User B lists — should not contain user A's job
        r = httpx.get(f"{BASE_URL}/api/v1/scout/jobs/saved", headers=auth_headers_b)
        ids = [j["id"] for j in r.json()["saved_jobs"]]
        assert job_id not in ids

    def test_user_b_cannot_delete_user_a_jobs(self, auth_headers, auth_headers_b):
        # User A saves a job
        payload = {**JOB_PAYLOAD, "external_id": f"iso2-{uuid.uuid4().hex[:8]}"}
        r = httpx.post(
            f"{BASE_URL}/api/v1/scout/jobs/save",
            headers=auth_headers,
            json=payload,
        )
        job_id = r.json()["id"]

        # User B tries to delete
        r = httpx.delete(
            f"{BASE_URL}/api/v1/scout/jobs/saved/{job_id}",
            headers=auth_headers_b,
        )
        assert r.status_code == 404

        # Confirm still exists for user A
        r = httpx.get(f"{BASE_URL}/api/v1/scout/jobs/saved", headers=auth_headers)
        ids = [j["id"] for j in r.json()["saved_jobs"]]
        assert job_id in ids
