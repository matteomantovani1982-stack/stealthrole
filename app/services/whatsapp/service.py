"""
app/services/whatsapp/service.py

WhatsApp messaging via Twilio HTTP API (no SDK dependency).
"""

import structlog
import httpx

from app.config import settings

logger = structlog.get_logger(__name__)

TWILIO_MSG_URL = (
    "https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
)


class WhatsAppService:
    def __init__(self) -> None:
        self._configured = bool(
            settings.twilio_account_sid
            and settings.twilio_auth_token
            and settings.twilio_whatsapp_from
        )

    def _referral_cta(self, referral_code: str | None) -> str:
        if not referral_code:
            return ""
        return f"\n\nKnow someone job hunting? stealthrole.com/ref/{referral_code}"

    def _normalize_phone(self, phone: str) -> str:
        """Ensure phone is in E.164 format: +<country><number>."""
        # Strip whatsapp: prefix if present
        p = phone.replace("whatsapp:", "").strip()
        # Remove spaces, dashes, parentheses
        p = p.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        # If starts with 0, assume UAE (+971) and replace leading 0
        if p.startswith("0") and not p.startswith("00"):
            p = "+971" + p[1:]
        # If starts with 00, replace with +
        if p.startswith("00"):
            p = "+" + p[2:]
        # Ensure starts with +
        if not p.startswith("+"):
            p = "+" + p
        return p

    async def send_message(self, to: str, body: str) -> bool:
        """Send a WhatsApp message via Twilio. Returns True on success."""
        if not self._configured:
            logger.warning("whatsapp_not_configured")
            return False

        normalized = self._normalize_phone(to)
        url = TWILIO_MSG_URL.format(sid=settings.twilio_account_sid)
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                auth=(settings.twilio_account_sid, settings.twilio_auth_token),
                data={
                    "From": settings.twilio_whatsapp_from,
                    "To": f"whatsapp:{normalized}",
                    "Body": body,
                },
            )
        if resp.status_code >= 400:
            error_body = resp.text
            logger.error("whatsapp_send_failed", status=resp.status_code, body=error_body, to=to[-4:])
            # Common sandbox error: user hasn't opted in
            if "not a valid WhatsApp" in error_body or "sandbox" in error_body.lower() or "63007" in error_body:
                logger.warning("whatsapp_sandbox_optin_needed", to=to[-4:])
            return False
        logger.info("whatsapp_sent", to=to[-4:])
        return True

    async def send_radar_alert(
        self, phone: str, opportunities: list[dict], referral_code: str | None = None
    ) -> bool:
        lines = ["🔍 *New opportunities matched your profile:*\n"]
        for i, opp in enumerate(opportunities[:5], 1):
            title = opp.get("title", "Unknown")
            company = opp.get("company", "")
            lines.append(f"{i}. {title} — {company}")
        lines.append(self._referral_cta(referral_code))
        return await self.send_message(phone, "\n".join(lines))

    async def send_pack_ready(
        self, phone: str, job_run: dict, referral_code: str | None = None
    ) -> bool:
        title = job_run.get("job_title", "your application")
        body = (
            f"📦 Your Intel Pack for *{title}* is ready!\n"
            f"Open StealthRole to review your tailored materials."
            f"{self._referral_cta(referral_code)}"
        )
        return await self.send_message(phone, body)

    async def send_shadow_ready(
        self, phone: str, shadow: dict, referral_code: str | None = None
    ) -> bool:
        company = shadow.get("company", "a company")
        body = (
            f"👻 Shadow application for *{company}* is ready!\n"
            f"Review and submit in StealthRole."
            f"{self._referral_cta(referral_code)}"
        )
        return await self.send_message(phone, body)
