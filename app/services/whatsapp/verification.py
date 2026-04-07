"""
app/services/whatsapp/verification.py

OTP-based WhatsApp number verification using Redis for ephemeral code storage.

Flow:
  1. User calls POST /verify with their WhatsApp number
  2. We generate a 6-digit code, store SHA-256 hash in Redis (10-min TTL)
  3. Send the code to the user via Twilio WhatsApp
  4. User calls POST /confirm with the code
  5. We verify the hash and mark the user as verified
"""

import hashlib
import secrets
import structlog

import redis.asyncio as aioredis

from app.config import settings
from app.services.whatsapp.service import WhatsAppService

logger = structlog.get_logger(__name__)

CODE_TTL_SECONDS = 600  # 10 minutes
RATE_LIMIT_SECONDS = 900  # 15 minutes
MAX_VERIFY_ATTEMPTS = 3
MAX_CONFIRM_ATTEMPTS = 5


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def _otp_key(user_id: str) -> str:
    return f"whatsapp:otp:{user_id}"


def _rate_key(user_id: str) -> str:
    return f"whatsapp:rate:{user_id}"


def _confirm_attempts_key(user_id: str) -> str:
    return f"whatsapp:confirm_attempts:{user_id}"


class VerificationError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class WhatsAppVerification:
    def __init__(self) -> None:
        self._wa = WhatsAppService()

    async def _get_redis(self) -> aioredis.Redis:
        return aioredis.from_url(settings.redis_url, decode_responses=True)

    async def send_code(self, user_id: str, phone: str) -> None:
        """Generate OTP, store in Redis, send via WhatsApp."""
        r = await self._get_redis()
        try:
            # Rate limit: max N requests per window
            rate_key = _rate_key(user_id)
            count = await r.get(rate_key)
            if count and int(count) >= MAX_VERIFY_ATTEMPTS:
                raise VerificationError(
                    "Too many verification attempts. Please try again later.",
                    status_code=429,
                )

            # Generate 6-digit code
            code = f"{secrets.randbelow(900000) + 100000}"

            # Store hashed code in Redis with TTL
            otp_key = _otp_key(user_id)
            await r.setex(otp_key, CODE_TTL_SECONDS, _hash_code(code))

            # Increment rate limiter
            pipe = r.pipeline()
            pipe.incr(rate_key)
            pipe.expire(rate_key, RATE_LIMIT_SECONDS)
            await pipe.execute()

            # Reset confirm attempts on new code
            await r.delete(_confirm_attempts_key(user_id))

            # Send via Twilio
            body = f"Your StealthRole verification code is: {code}\n\nThis code expires in 10 minutes."
            sent = await self._wa.send_message(phone, body)
            if not sent:
                raise VerificationError(
                    "Failed to send verification message. Please try again.",
                    status_code=502,
                )

            logger.info("whatsapp_otp_sent", user_id=user_id, phone=phone[-4:])
        finally:
            await r.aclose()

    async def confirm_code(self, user_id: str, phone: str, code: str) -> bool:
        """Verify the OTP code. Returns True if valid."""
        r = await self._get_redis()
        try:
            # Brute-force protection on confirm attempts
            attempts_key = _confirm_attempts_key(user_id)
            attempts = await r.get(attempts_key)
            if attempts and int(attempts) >= MAX_CONFIRM_ATTEMPTS:
                # Delete the OTP to force re-send
                await r.delete(_otp_key(user_id))
                raise VerificationError(
                    "Too many failed attempts. Please request a new code.",
                    status_code=429,
                )

            otp_key = _otp_key(user_id)
            stored_hash = await r.get(otp_key)

            if not stored_hash:
                raise VerificationError("No pending verification code. Please request a new one.")

            if _hash_code(code) != stored_hash:
                # Track failed attempt
                pipe = r.pipeline()
                pipe.incr(attempts_key)
                pipe.expire(attempts_key, CODE_TTL_SECONDS)
                await pipe.execute()
                raise VerificationError("Invalid verification code.")

            # Code matches — clean up
            await r.delete(otp_key)
            await r.delete(attempts_key)
            logger.info("whatsapp_otp_verified", user_id=user_id)
            return True
        finally:
            await r.aclose()
