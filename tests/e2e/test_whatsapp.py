"""
tests/e2e/test_whatsapp.py

End-to-end tests for WhatsApp endpoints.
"""

import uuid

import httpx
import pytest

BASE_URL = "http://localhost:8000"


@pytest.fixture(scope="module")
def auth_headers():
    email = f"wa_test_{uuid.uuid4().hex[:8]}@test.com"
    password = "TestPass123!"

    httpx.post(f"{BASE_URL}/api/v1/auth/register", json={
        "email": email,
        "password": password,
        "full_name": "WhatsApp Tester",
    })

    r = httpx.post(f"{BASE_URL}/api/v1/auth/login", json={
        "email": email,
        "password": password,
    })
    assert r.status_code == 200
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestWhatsAppVerify:
    def test_verify_unauthenticated(self):
        r = httpx.post(f"{BASE_URL}/api/v1/whatsapp/verify", json={"whatsapp_number": "+1234567890"})
        assert r.status_code in (401, 403)

    def test_confirm_unauthenticated(self):
        r = httpx.post(f"{BASE_URL}/api/v1/whatsapp/confirm", json={"whatsapp_number": "+1234567890", "code": "123456"})
        assert r.status_code in (401, 403)

    def test_verify_returns_200_or_503(self, auth_headers):
        """Should return 200 if Twilio configured, 503 if not."""
        r = httpx.post(
            f"{BASE_URL}/api/v1/whatsapp/verify",
            json={"whatsapp_number": "+1234567890"},
            headers=auth_headers,
        )
        assert r.status_code in (200, 503)


class TestWhatsAppWebhook:
    def test_webhook_scout_command(self):
        """POST with Body=SCOUT should return 200 with XML."""
        r = httpx.post(
            f"{BASE_URL}/api/v1/whatsapp/webhook",
            data={"Body": "SCOUT", "From": "whatsapp:+10000000000"},
        )
        assert r.status_code == 200
        assert "xml" in r.headers["content-type"]

    def test_webhook_unknown_number(self):
        """Unknown number should still return 200 with XML help message."""
        r = httpx.post(
            f"{BASE_URL}/api/v1/whatsapp/webhook",
            data={"Body": "HELLO", "From": "whatsapp:+19999999999"},
        )
        assert r.status_code == 200
        assert "xml" in r.headers["content-type"]
