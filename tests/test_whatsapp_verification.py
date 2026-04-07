"""
tests/test_whatsapp_verification.py

Unit tests for WhatsApp OTP verification flow (Sprint R).

Coverage:
  - OTP generation and Redis storage
  - Code verification (correct code, wrong code, expired code)
  - Rate limiting on send attempts
  - Brute-force protection on confirm attempts
  - Route-level integration (verify + confirm endpoints)
"""

import hashlib
import sys
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure asyncpg is available as a mock so the import chain doesn't fail
if "asyncpg" not in sys.modules:
    sys.modules["asyncpg"] = ModuleType("asyncpg")


# ════════════════════════════════════════════════════════════
# WhatsAppVerification service tests
# ════════════════════════════════════════════════════════════

class TestWhatsAppVerificationService:

    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client with pipeline support."""
        r = AsyncMock()
        r.get = AsyncMock(return_value=None)
        r.setex = AsyncMock()
        r.delete = AsyncMock()
        r.aclose = AsyncMock()

        pipe = AsyncMock()
        pipe.incr = MagicMock()
        pipe.expire = MagicMock()
        pipe.execute = AsyncMock()
        r.pipeline = MagicMock(return_value=pipe)

        return r

    @pytest.fixture
    def mock_wa_service(self):
        svc = AsyncMock()
        svc.send_message = AsyncMock(return_value=True)
        return svc

    @pytest.mark.asyncio
    async def test_send_code_success(self, mock_redis, mock_wa_service):
        """send_code should generate OTP, store hash, and send via WhatsApp."""
        from app.services.whatsapp.verification import WhatsAppVerification

        with (
            patch("app.services.whatsapp.verification.aioredis") as mock_aioredis,
            patch("app.services.whatsapp.verification.WhatsAppService", return_value=mock_wa_service),
        ):
            mock_aioredis.from_url.return_value = mock_redis
            svc = WhatsAppVerification()
            await svc.send_code("user-123", "+1234567890")

        # Should have stored a hashed code
        mock_redis.setex.assert_called_once()
        args = mock_redis.setex.call_args
        assert args[0][0] == "whatsapp:otp:user-123"
        assert args[0][1] == 600  # TTL

        # Should have sent a message
        mock_wa_service.send_message.assert_called_once()
        call_args = mock_wa_service.send_message.call_args
        assert "+1234567890" in call_args[0]
        assert "verification code" in call_args[0][1].lower()

    @pytest.mark.asyncio
    async def test_send_code_rate_limited(self, mock_redis, mock_wa_service):
        """send_code should raise 429 when rate limit exceeded."""
        from app.services.whatsapp.verification import (
            MAX_VERIFY_ATTEMPTS,
            VerificationError,
            WhatsAppVerification,
        )

        mock_redis.get = AsyncMock(return_value=str(MAX_VERIFY_ATTEMPTS))

        with (
            patch("app.services.whatsapp.verification.aioredis") as mock_aioredis,
            patch("app.services.whatsapp.verification.WhatsAppService", return_value=mock_wa_service),
        ):
            mock_aioredis.from_url.return_value = mock_redis
            svc = WhatsAppVerification()
            with pytest.raises(VerificationError) as exc_info:
                await svc.send_code("user-123", "+1234567890")

        assert exc_info.value.status_code == 429
        assert "too many" in exc_info.value.message.lower()
        mock_wa_service.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_code_twilio_failure(self, mock_redis, mock_wa_service):
        """send_code should raise 502 when Twilio send fails."""
        from app.services.whatsapp.verification import VerificationError, WhatsAppVerification

        mock_wa_service.send_message = AsyncMock(return_value=False)

        with (
            patch("app.services.whatsapp.verification.aioredis") as mock_aioredis,
            patch("app.services.whatsapp.verification.WhatsAppService", return_value=mock_wa_service),
        ):
            mock_aioredis.from_url.return_value = mock_redis
            svc = WhatsAppVerification()
            with pytest.raises(VerificationError) as exc_info:
                await svc.send_code("user-123", "+1234567890")

        assert exc_info.value.status_code == 502

    @pytest.mark.asyncio
    async def test_confirm_code_success(self, mock_redis):
        """confirm_code should return True when code matches."""
        from app.services.whatsapp.verification import WhatsAppVerification, _hash_code

        stored_hash = _hash_code("123456")
        # First call: confirm attempts (None = no attempts yet)
        # Second call: stored OTP hash
        mock_redis.get = AsyncMock(side_effect=[None, stored_hash])

        with patch("app.services.whatsapp.verification.aioredis") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_redis
            svc = WhatsAppVerification()
            result = await svc.confirm_code("user-123", "+1234567890", "123456")

        assert result is True
        # Should clean up OTP and attempts keys
        assert mock_redis.delete.call_count == 2

    @pytest.mark.asyncio
    async def test_confirm_code_wrong(self, mock_redis):
        """confirm_code should raise error on wrong code."""
        from app.services.whatsapp.verification import VerificationError, WhatsAppVerification, _hash_code

        stored_hash = _hash_code("123456")
        mock_redis.get = AsyncMock(side_effect=[None, stored_hash])

        with patch("app.services.whatsapp.verification.aioredis") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_redis
            svc = WhatsAppVerification()
            with pytest.raises(VerificationError) as exc_info:
                await svc.confirm_code("user-123", "+1234567890", "999999")

        assert exc_info.value.status_code == 400
        assert "invalid" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    async def test_confirm_code_expired(self, mock_redis):
        """confirm_code should raise error when no OTP exists (expired)."""
        from app.services.whatsapp.verification import VerificationError, WhatsAppVerification

        mock_redis.get = AsyncMock(side_effect=[None, None])

        with patch("app.services.whatsapp.verification.aioredis") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_redis
            svc = WhatsAppVerification()
            with pytest.raises(VerificationError) as exc_info:
                await svc.confirm_code("user-123", "+1234567890", "123456")

        assert "request a new one" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    async def test_confirm_code_brute_force_lockout(self, mock_redis):
        """confirm_code should lock out after too many failed attempts."""
        from app.services.whatsapp.verification import (
            MAX_CONFIRM_ATTEMPTS,
            VerificationError,
            WhatsAppVerification,
        )

        mock_redis.get = AsyncMock(return_value=str(MAX_CONFIRM_ATTEMPTS))

        with patch("app.services.whatsapp.verification.aioredis") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_redis
            svc = WhatsAppVerification()
            with pytest.raises(VerificationError) as exc_info:
                await svc.confirm_code("user-123", "+1234567890", "123456")

        assert exc_info.value.status_code == 429
        # Should delete the OTP key to force re-send
        mock_redis.delete.assert_called_once_with("whatsapp:otp:user-123")


# ════════════════════════════════════════════════════════════
# Route-level tests
# ════════════════════════════════════════════════════════════

class TestVerifyEndpoint:

    @pytest.mark.asyncio
    async def test_verify_sends_code_and_persists_number(self):
        """POST /verify should send OTP and save number on user."""
        from app.api.routes.whatsapp import verify_whatsapp, WhatsAppVerifyRequest

        mock_user = MagicMock()
        mock_user.id = "user-abc"
        mock_user.whatsapp_number = None
        mock_user.whatsapp_verified = False

        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()

        payload = WhatsAppVerifyRequest(whatsapp_number="+1234567890")

        with (
            patch("app.api.routes.whatsapp._require_twilio"),
            patch("app.services.whatsapp.verification.WhatsAppVerification") as MockSvc,
        ):
            instance = AsyncMock()
            instance.send_code = AsyncMock()
            MockSvc.return_value = instance

            result = await verify_whatsapp(payload, mock_user, mock_db)

        assert result["message"] == "Verification code sent. Check your WhatsApp."
        assert mock_user.whatsapp_number == "+1234567890"
        assert mock_user.whatsapp_verified is False
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_verify_returns_429_on_rate_limit(self):
        """POST /verify should return 429 when rate limited."""
        from fastapi import HTTPException

        from app.api.routes.whatsapp import verify_whatsapp, WhatsAppVerifyRequest
        from app.services.whatsapp.verification import VerificationError

        mock_user = MagicMock()
        mock_user.id = "user-abc"
        mock_db = AsyncMock()

        payload = WhatsAppVerifyRequest(whatsapp_number="+1234567890")

        with (
            patch("app.api.routes.whatsapp._require_twilio"),
            patch("app.services.whatsapp.verification.WhatsAppVerification") as MockSvc,
        ):
            instance = AsyncMock()
            instance.send_code = AsyncMock(
                side_effect=VerificationError("Too many", status_code=429)
            )
            MockSvc.return_value = instance

            with pytest.raises(HTTPException) as exc_info:
                await verify_whatsapp(payload, mock_user, mock_db)

        assert exc_info.value.status_code == 429


class TestConfirmEndpoint:

    @pytest.mark.asyncio
    async def test_confirm_marks_user_verified(self):
        """POST /confirm should mark user verified and set CASUAL mode."""
        from app.api.routes.whatsapp import confirm_whatsapp, WhatsAppConfirmRequest

        mock_user = MagicMock()
        mock_user.id = "user-abc"
        mock_user.whatsapp_number = "+1234567890"
        mock_user.whatsapp_verified = False
        mock_user.whatsapp_alert_mode = "OFF"

        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()

        payload = WhatsAppConfirmRequest(whatsapp_number="+1234567890", code="123456")

        with (
            patch("app.api.routes.whatsapp._require_twilio"),
            patch("app.services.whatsapp.verification.WhatsAppVerification") as MockSvc,
        ):
            instance = AsyncMock()
            instance.confirm_code = AsyncMock(return_value=True)
            MockSvc.return_value = instance

            result = await confirm_whatsapp(payload, mock_user, mock_db)

        assert result["verified"] is True
        assert mock_user.whatsapp_verified is True
        assert mock_user.whatsapp_alert_mode == "CASUAL"
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_confirm_rejects_mismatched_number(self):
        """POST /confirm should reject if number doesn't match pending verification."""
        from fastapi import HTTPException

        from app.api.routes.whatsapp import confirm_whatsapp, WhatsAppConfirmRequest

        mock_user = MagicMock()
        mock_user.id = "user-abc"
        mock_user.whatsapp_number = "+1111111111"

        mock_db = AsyncMock()

        payload = WhatsAppConfirmRequest(whatsapp_number="+9999999999", code="123456")

        with patch("app.api.routes.whatsapp._require_twilio"):
            with pytest.raises(HTTPException) as exc_info:
                await confirm_whatsapp(payload, mock_user, mock_db)

        assert exc_info.value.status_code == 400
        assert "does not match" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_confirm_returns_error_on_wrong_code(self):
        """POST /confirm should return error when code is wrong."""
        from fastapi import HTTPException

        from app.api.routes.whatsapp import confirm_whatsapp, WhatsAppConfirmRequest
        from app.services.whatsapp.verification import VerificationError

        mock_user = MagicMock()
        mock_user.id = "user-abc"
        mock_user.whatsapp_number = "+1234567890"

        mock_db = AsyncMock()

        payload = WhatsAppConfirmRequest(whatsapp_number="+1234567890", code="000000")

        with (
            patch("app.api.routes.whatsapp._require_twilio"),
            patch("app.services.whatsapp.verification.WhatsAppVerification") as MockSvc,
        ):
            instance = AsyncMock()
            instance.confirm_code = AsyncMock(
                side_effect=VerificationError("Invalid verification code.")
            )
            MockSvc.return_value = instance

            with pytest.raises(HTTPException) as exc_info:
                await confirm_whatsapp(payload, mock_user, mock_db)

        assert exc_info.value.status_code == 400
