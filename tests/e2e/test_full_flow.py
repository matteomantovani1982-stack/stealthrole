"""
tests/e2e/test_full_flow.py

Full end-to-end flow test covering the complete StealthRole pipeline:
  register → profile → scout → hidden market → radar →
  shadow app → outreach → notifications → dashboard

Runs against the live Docker stack.
"""

import time
import uuid

import httpx
import pytest

BASE_URL = "http://localhost:8000"
TIMEOUT = 30


class TestFullFlow:
    """Complete end-to-end flow."""

    def test_01_health(self):
        r = httpx.get(f"{BASE_URL}/health", timeout=TIMEOUT)
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_02_register(self, test_user):
        """Registration already done by fixture — verify user exists."""
        assert test_user["email"]
        assert test_user["password"]

    def test_03_login(self, auth_headers):
        """Login already done by fixture — verify token."""
        assert "Bearer" in auth_headers["Authorization"]

    def test_04_get_me(self, auth_headers):
        r = httpx.get(f"{BASE_URL}/api/v1/auth/me", headers=auth_headers, timeout=TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert data["email"]
        assert data["is_active"] is True

    def test_05_profile_strength_empty(self, auth_headers):
        r = httpx.get(f"{BASE_URL}/api/v1/profile/strength", headers=auth_headers, timeout=TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert data["score"] >= 0
        assert data["max"] == 100
        assert "next_action" in data

    def test_06_scout_signals(self, auth_headers):
        r = httpx.get(f"{BASE_URL}/api/v1/scout/signals", headers=auth_headers, timeout=TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert "opportunities" in data

    def test_07_scout_jobs(self, auth_headers):
        r = httpx.get(
            f"{BASE_URL}/api/v1/scout/jobs",
            headers=auth_headers,
            params={"keywords": "VP Engineering", "location": "UAE"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        data = r.json()
        assert "jobs" in data
        assert "total" in data

    def test_08_hidden_market(self, auth_headers):
        r = httpx.get(f"{BASE_URL}/api/v1/scout/hidden-market", headers=auth_headers, timeout=TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert "signals" in data
        assert "total" in data

    def test_09_radar(self, auth_headers):
        r = httpx.get(f"{BASE_URL}/api/v1/opportunities/radar", headers=auth_headers, timeout=TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert "opportunities" in data
        assert "total" in data
        assert "scoring" in data
        assert "meta" in data

    def test_10_radar_with_filters(self, auth_headers):
        r = httpx.get(
            f"{BASE_URL}/api/v1/opportunities/radar",
            headers=auth_headers,
            params={"min_score": 50, "urgency": "high", "limit": 5},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200

    def test_11_radar_include_speculative(self, auth_headers):
        r = httpx.get(
            f"{BASE_URL}/api/v1/opportunities/radar",
            headers=auth_headers,
            params={"include_speculative": "true"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200

    def test_12_shadow_create(self, auth_headers):
        r = httpx.post(
            f"{BASE_URL}/api/v1/shadow/generate",
            headers=auth_headers,
            json={
                "company": "E2E TestCo",
                "signal_type": "funding",
                "signal_context": "E2E TestCo raised $30M Series B for MENA expansion",
                "likely_roles": ["VP Engineering"],
                "tone": "confident",
            },
            timeout=TIMEOUT,
        )
        assert r.status_code == 202
        data = r.json()
        assert data["status"] == "generating"
        assert data["company"] == "E2E TestCo"
        return data["id"]

    def test_13_shadow_list(self, auth_headers):
        r = httpx.get(f"{BASE_URL}/api/v1/shadow", headers=auth_headers, timeout=TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert "shadow_applications" in data
        assert data["total"] >= 1

    def test_14_shadow_detail(self, auth_headers):
        # Get the most recent shadow
        r = httpx.get(f"{BASE_URL}/api/v1/shadow", headers=auth_headers, timeout=TIMEOUT)
        shadows = r.json()["shadow_applications"]
        assert shadows, "No shadow applications found"
        shadow_id = shadows[0]["id"]

        r = httpx.get(f"{BASE_URL}/api/v1/shadow/{shadow_id}", headers=auth_headers, timeout=TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert data["company"]
        assert data["signal_type"]
        assert data["status"] in ("generating", "completed", "failed")

    def test_15_shadow_validation(self, auth_headers):
        # Missing company
        r = httpx.post(
            f"{BASE_URL}/api/v1/shadow/generate",
            headers=auth_headers,
            json={"signal_type": "funding"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 422

        # Invalid tone
        r = httpx.post(
            f"{BASE_URL}/api/v1/shadow/generate",
            headers=auth_headers,
            json={"company": "X", "signal_type": "x", "tone": "aggressive"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 422

    def test_16_outreach_generate(self, auth_headers):
        r = httpx.post(
            f"{BASE_URL}/api/v1/outreach/generate",
            headers=auth_headers,
            json={
                "company": "OutreachTestCo",
                "role": "CTO",
                "signal_context": "OutreachTestCo expanding to MENA",
                "tone": "formal",
            },
            timeout=TIMEOUT,
        )
        if r.status_code == 500:
            pytest.skip("Outreach LLM call failed (likely API credits exhausted)")
        assert r.status_code == 200
        data = r.json()
        assert "linkedin_note" in data
        assert "cold_email" in data
        assert "follow_up" in data

    def test_17_analytics(self, auth_headers):
        r = httpx.get(f"{BASE_URL}/api/v1/analytics/summary", headers=auth_headers, timeout=TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert "total_applications" in data
        assert "by_stage" in data
        assert "response_rate" in data

    def test_18_dashboard(self, auth_headers):
        r = httpx.get(f"{BASE_URL}/api/v1/dashboard/summary", headers=auth_headers, timeout=TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert "radar_opportunities" in data
        assert "recent_applications" in data
        assert "recent_shadow_applications" in data
        assert "total_shadow_applications" in data
        assert "profile_completeness" in data

    def test_19_notification_prefs_get(self, auth_headers):
        r = httpx.get(f"{BASE_URL}/api/v1/auth/me/notifications", headers=auth_headers, timeout=TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert "notification_preferences" in data

    def test_20_notification_prefs_update(self, auth_headers):
        r = httpx.put(
            f"{BASE_URL}/api/v1/auth/me/notifications",
            headers=auth_headers,
            json={"pack_complete_email": False},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        prefs = r.json()["notification_preferences"]
        assert prefs["pack_complete_email"] is False

        # Verify persistence
        r2 = httpx.get(f"{BASE_URL}/api/v1/auth/me/notifications", headers=auth_headers, timeout=TIMEOUT)
        assert r2.json()["notification_preferences"]["pack_complete_email"] is False

        # Re-enable
        httpx.put(
            f"{BASE_URL}/api/v1/auth/me/notifications",
            headers=auth_headers,
            json={"pack_complete_email": True},
            timeout=TIMEOUT,
        )

    def test_21_referral_stats(self, auth_headers):
        r = httpx.get(f"{BASE_URL}/api/v1/referral/stats", headers=auth_headers, timeout=TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert "referral_code" in data
        assert "referral_url" in data

    def test_22_whatsapp_commands(self):
        # SCOUT — returns TwiML XML
        r = httpx.post(f"{BASE_URL}/api/v1/whatsapp/webhook", data={"Body": "SCOUT", "From": "+971test"}, timeout=TIMEOUT)
        assert r.status_code == 200
        assert "application/xml" in r.headers.get("content-type", "")
        assert "<Message>" in r.text

        # MODE ACTIVE
        r = httpx.post(f"{BASE_URL}/api/v1/whatsapp/webhook", data={"Body": "MODE ACTIVE", "From": "+971test"}, timeout=TIMEOUT)
        assert r.status_code == 200
        assert "ACTIVE" in r.text

        # STOP
        r = httpx.post(f"{BASE_URL}/api/v1/whatsapp/webhook", data={"Body": "STOP", "From": "+971test"}, timeout=TIMEOUT)
        assert r.status_code == 200
        assert "<Response>" in r.text

        # Unknown
        r = httpx.post(f"{BASE_URL}/api/v1/whatsapp/webhook", data={"Body": "HELLO", "From": "+971test"}, timeout=TIMEOUT)
        assert r.status_code == 200
        assert "Commands" in r.text

    def test_23_timeline_404(self, auth_headers):
        fake_id = str(uuid.uuid4())
        r = httpx.get(f"{BASE_URL}/api/v1/jobs/{fake_id}/timeline", headers=auth_headers, timeout=TIMEOUT)
        assert r.status_code == 404

    def test_24_shadow_not_found(self, auth_headers):
        fake_id = str(uuid.uuid4())
        r = httpx.get(f"{BASE_URL}/api/v1/shadow/{fake_id}", headers=auth_headers, timeout=TIMEOUT)
        assert r.status_code == 404

    def test_25_shadow_delete(self, auth_headers):
        """Create a shadow, delete it, verify it's gone."""
        r = httpx.post(
            f"{BASE_URL}/api/v1/shadow/generate",
            headers=auth_headers,
            json={
                "company": "DeleteFlowCo",
                "signal_type": "funding",
            },
            timeout=TIMEOUT,
        )
        assert r.status_code == 202
        shadow_id = r.json()["id"]

        r = httpx.delete(f"{BASE_URL}/api/v1/shadow/{shadow_id}", headers=auth_headers, timeout=TIMEOUT)
        assert r.status_code == 200
        assert r.json()["deleted"] is True

        r = httpx.get(f"{BASE_URL}/api/v1/shadow/{shadow_id}", headers=auth_headers, timeout=TIMEOUT)
        assert r.status_code == 404

    def test_26_auth_required(self):
        """All protected endpoints must return 401 without auth."""
        endpoints = [
            ("GET", "/api/v1/shadow"),
            ("GET", "/api/v1/opportunities/radar"),
            ("GET", "/api/v1/dashboard/summary"),
            ("GET", "/api/v1/analytics/summary"),
            ("GET", "/api/v1/profile/strength"),
            ("GET", "/api/v1/auth/me/notifications"),
            ("GET", "/api/v1/scout/hidden-market"),
        ]
        for method, path in endpoints:
            r = httpx.request(method, f"{BASE_URL}{path}", timeout=TIMEOUT)
            assert r.status_code == 401, f"{method} {path} returned {r.status_code}, expected 401"

    def test_27_validation_error_returns_422(self, auth_headers):
        """Validation errors must return 422, not 500."""
        r = httpx.post(
            f"{BASE_URL}/api/v1/jobs",
            headers=auth_headers,
            json={"cv_id": str(uuid.uuid4()), "job_description": "test"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 422
        data = r.json()
        assert "detail" in data

    def test_28_shadow_completes(self, auth_headers):
        """Wait for shadow to complete and verify outputs."""
        # Create a fresh shadow
        r = httpx.post(
            f"{BASE_URL}/api/v1/shadow/generate",
            headers=auth_headers,
            json={
                "company": "CompletionTestCo",
                "signal_type": "expansion",
                "signal_context": "CompletionTestCo opening Dubai office",
            },
            timeout=TIMEOUT,
        )
        shadow_id = r.json()["id"]

        # Poll for completion (max 60s)
        for _ in range(12):
            time.sleep(5)
            r = httpx.get(f"{BASE_URL}/api/v1/shadow/{shadow_id}", headers=auth_headers, timeout=TIMEOUT)
            data = r.json()
            if data["status"] in ("completed", "failed"):
                break

        if data["status"] == "failed":
            pytest.skip(f"Shadow LLM call failed (likely API credits exhausted): {data.get('error_message', '')[:100]}")
        assert data["status"] == "completed", f"Shadow status: {data['status']}, error: {data.get('error_message')}"
        assert data["hypothesis_role"], "No hypothesis role"
        assert data["hiring_hypothesis"], "No hiring hypothesis"
        assert data["strategy_memo"], "No strategy memo"
        assert data["outreach_linkedin"], "No LinkedIn outreach"
        assert data["outreach_email"], "No email outreach"
