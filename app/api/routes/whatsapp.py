"""
app/api/routes/whatsapp.py — WhatsApp engagement layer (Twilio sandbox).
POST /api/v1/whatsapp/webhook
POST /api/v1/whatsapp/verify
POST /api/v1/whatsapp/confirm
"""
import structlog
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel

from app.config import settings
from app.dependencies import DB, CurrentUser

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/whatsapp", tags=["WhatsApp"])


# ── Response models ──────────────────────────────────────────────────────────

class WhatsAppVerifyResponse(BaseModel):
    """Verification code sent response."""
    message: str


class WhatsAppConfirmResponse(BaseModel):
    """WhatsApp confirmation response."""
    status: str
    whatsapp_number: str


class WhatsAppSendResponse(BaseModel):
    """WhatsApp message send response."""
    status: str
    message_sid: str
    to: str | None = None


class WhatsAppAlertResponse(BaseModel):
    """Opportunity alert send response."""
    status: str
    message_sid: str
    message: str | None = None


def _twiml(text: str) -> Response:
    """Return a TwiML XML response wrapping a message body."""
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        f"<Message>{text}</Message>"
        "</Response>"
    )
    return Response(content=xml, media_type="application/xml")


class WhatsAppVerifyRequest(BaseModel):
    whatsapp_number: str


class WhatsAppConfirmRequest(BaseModel):
    whatsapp_number: str
    code: str


@router.post("/webhook", summary="Twilio webhook handler")
async def whatsapp_webhook(request: Request) -> Response:
    body = await request.form()
    message = body.get("Body", "").strip().upper()
    from_number = body.get("From", "")
    logger.info("whatsapp_incoming", from_number=from_number, message=message[:50])
    if message == "SCOUT":
        return _twiml("Top opportunities coming soon. Feature in development.")
    elif message.startswith("PACK"):
        return _twiml("Pack generation via WhatsApp coming soon.")
    elif message == "STOP":
        return _twiml("WhatsApp alerts disabled. Send MODE ACTIVE to re-enable.")
    elif message.startswith("MODE"):
        mode = message.replace("MODE", "").strip()
        if mode in ("ACTIVE", "CASUAL", "OFF"):
            return _twiml(f"Alert mode set to {mode}.")
        return _twiml("Valid modes: ACTIVE, CASUAL, OFF")
    return _twiml("Commands: SCOUT, PACK &lt;url&gt;, MODE ACTIVE/CASUAL/OFF, STOP")


def _require_twilio() -> None:
    """Raise 503 if Twilio credentials are not configured."""
    if not (settings.twilio_account_sid and settings.twilio_auth_token):
        raise HTTPException(
            status_code=503,
            detail="WhatsApp integration is not configured.",
        )


def _normalize_phone(phone: str) -> str:
    """Ensure phone is in E.164 format: +<country><number>."""
    p = phone.replace("whatsapp:", "").strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if p.startswith("0") and not p.startswith("00"):
        p = "+971" + p[1:]
    if p.startswith("00"):
        p = "+" + p[2:]
    if not p.startswith("+"):
        p = "+" + p
    return p


@router.post("/verify", summary="Send WhatsApp verification code", response_model=WhatsAppVerifyResponse)
async def verify_whatsapp(payload: WhatsAppVerifyRequest, current_user: CurrentUser, db: DB) -> dict:
    _require_twilio()
    from app.services.whatsapp.verification import WhatsAppVerification, VerificationError

    user_id = str(current_user.id)
    logger.info("whatsapp_verify_requested", user_id=user_id, phone=payload.whatsapp_number)

    normalized_number = _normalize_phone(payload.whatsapp_number)
    try:
        svc = WhatsAppVerification()
        await svc.send_code(user_id, normalized_number)
    except VerificationError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    # Persist the normalized number (unverified) so we can match it on confirm
    current_user.whatsapp_number = normalized_number
    current_user.whatsapp_verified = False
    db.add(current_user)
    await db.commit()

    return {"message": "Verification code sent. Check your WhatsApp."}


@router.post("/confirm", summary="Confirm WhatsApp verification", response_model=WhatsAppConfirmResponse)
async def confirm_whatsapp(payload: WhatsAppConfirmRequest, current_user: CurrentUser, db: DB) -> dict:
    _require_twilio()
    from app.services.whatsapp.verification import WhatsAppVerification, VerificationError

    user_id = str(current_user.id)
    logger.info("whatsapp_confirm_requested", user_id=user_id, phone=payload.whatsapp_number)

    # Ensure the number matches what was sent for verification
    normalized_number = _normalize_phone(payload.whatsapp_number)
    if current_user.whatsapp_number != normalized_number:
        raise HTTPException(
            status_code=400,
            detail="Phone number does not match the one awaiting verification.",
        )

    try:
        svc = WhatsAppVerification()
        await svc.confirm_code(user_id, payload.whatsapp_number, payload.code)
    except VerificationError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    # Mark verified and activate default alert mode
    current_user.whatsapp_verified = True
    current_user.whatsapp_alert_mode = "CASUAL"
    db.add(current_user)
    await db.commit()

    return {"status": "verified", "whatsapp_number": payload.whatsapp_number}


# ── Send message endpoint ─────────────────────────────────────────────────────

class WhatsAppSendRequest(BaseModel):
    message: str
    phone_number: str | None = None  # If None, uses the user's verified number


@router.post("/send", summary="Send a WhatsApp message to the user", response_model=WhatsAppSendResponse)
async def send_whatsapp(
    payload: WhatsAppSendRequest,
    current_user: CurrentUser,
    db: DB,
) -> dict:
    """Send a WhatsApp message via Twilio. Requires verified number."""
    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        raise HTTPException(status_code=501, detail="Twilio not configured")

    phone = payload.phone_number or current_user.whatsapp_number
    if not phone:
        raise HTTPException(status_code=400, detail="No WhatsApp number. Verify your number first.")

    try:
        from twilio.rest import Client
        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        normalized = _normalize_phone(phone)
        msg = client.messages.create(
            body=payload.message,
            from_=settings.twilio_whatsapp_from,
            to=f"whatsapp:{normalized}",
        )
        logger.info("whatsapp_sent", to=normalized, sid=msg.sid)
        return {"status": "sent", "message_sid": msg.sid, "to": normalized}
    except Exception as e:
        logger.error("whatsapp_send_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Send failed: {str(e)}")


@router.post("/send-test", summary="Send a test WhatsApp alert", response_model=WhatsAppSendResponse)
async def send_test_whatsapp(
    current_user: CurrentUser,
    db: DB,
) -> dict:
    """Send a test message to verify WhatsApp works."""
    if not settings.twilio_account_sid:
        raise HTTPException(status_code=501, detail="Twilio not configured")

    phone = current_user.whatsapp_number
    if not phone:
        raise HTTPException(status_code=400, detail="No WhatsApp number registered")

    try:
        from twilio.rest import Client
        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        normalized = _normalize_phone(phone)
        msg = client.messages.create(
            body="StealthRole test: WhatsApp alerts are working! You'll receive daily opportunity alerts, follow-up reminders, and pack notifications here.",
            from_=settings.twilio_whatsapp_from,
            to=f"whatsapp:{normalized}",
        )
        return {"status": "sent", "message_sid": msg.sid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Test failed: {str(e)}")

    return {"message": "WhatsApp verified successfully.", "verified": True}


# ── Opportunity alert (formatted) ─────────────────────────────────────────────

class OpportunityAlertRequest(BaseModel):
    company: str
    role: str
    fit_score: int
    signal_count: int = 1
    signal_summary: str = ""
    urgency: str = "medium"
    app_url: str | None = None


@router.post("/alert-opportunity", summary="Send a formatted opportunity alert via WhatsApp", response_model=WhatsAppAlertResponse)
async def send_opportunity_alert(
    payload: OpportunityAlertRequest,
    current_user: CurrentUser,
    db: DB,
) -> dict:
    if not settings.twilio_account_sid:
        raise HTTPException(status_code=501, detail="Twilio not configured")

    phone = current_user.whatsapp_number
    if not phone:
        raise HTTPException(status_code=400, detail="No WhatsApp number registered")

    # Build formatted alert
    fire = "🔥" if payload.fit_score >= 85 else "⚡" if payload.fit_score >= 70 else "📋"
    urgency_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(payload.urgency, "⚪")

    # Build deep link to the opportunity in StealthRole
    app_base = settings.app_base_url or "http://localhost:3000"
    deep_link = f"{app_base}/scout"

    msg_lines = [
        f"{fire} *Hidden opportunity detected*",
        f"",
        f"*{payload.role}*",
        f"📍 {payload.company}",
        f"🎯 Match: *{payload.fit_score}%* {urgency_emoji}",
    ]
    if payload.signal_count > 1 and payload.signal_summary:
        msg_lines.append(f"📡 {payload.signal_count} signals stacked:")
        msg_lines.append(f"_{payload.signal_summary}_")
    msg_lines.append(f"")
    msg_lines.append(f"👉 View details & generate Intelligence Pack:")
    msg_lines.append(f"{deep_link}")
    msg_lines.append(f"")
    msg_lines.append(f"_1 pack = 3 credits — includes tailored CV, strategy, salary intel, key contacts_")

    message = "\n".join(msg_lines)

    try:
        from twilio.rest import Client
        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        normalized = _normalize_phone(phone)
        result = client.messages.create(
            body=message,
            from_=settings.twilio_whatsapp_from,
            to=f"whatsapp:{normalized}",
        )
        return {"status": "sent", "message_sid": result.sid, "message": message}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Alert failed: {str(e)}")
