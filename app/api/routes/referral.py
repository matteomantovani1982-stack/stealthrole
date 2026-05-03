"""
app/api/routes/referral.py — Viral referral mechanism.
GET  /api/v1/referral/stats
POST /api/v1/referral/apply
"""
import secrets

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select, update

from app.dependencies import DB, CurrentUser
from app.models.user import User
from app.schemas.common import ReferralStatsResponse, ReferralApplyResponse

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/referral", tags=["Referral"])


def _generate_code() -> str:
    """Generate an 8-character alphanumeric referral code."""
    return secrets.token_urlsafe(6)[:8]


class ApplyReferralRequest(BaseModel):
    referral_code: str


@router.get("/stats", summary="Referral statistics", response_model=ReferralStatsResponse)
async def referral_stats(current_user: CurrentUser, db: DB) -> dict:
    # Lazy referral code generation: create on first access
    if not current_user.referral_code:
        code = _generate_code()
        # Ensure uniqueness — retry up to 3 times on collision
        for _ in range(3):
            existing = await db.scalar(
                select(User.id).where(User.referral_code == code)
            )
            if existing is None:
                break
            code = _generate_code()
        await db.execute(
            update(User)
            .where(User.id == current_user.id)
            .values(referral_code=code)
        )
        await db.commit()
        await db.refresh(current_user)

    # Count users who were referred by this user's code
    referral_count = await db.scalar(
        select(func.count()).select_from(User).where(
            User.referred_by == current_user.referral_code
        )
    ) or 0

    return {
        "referral_code": current_user.referral_code,
        "referral_url": f"https://stealthrole.com/ref/{current_user.referral_code}",
        "referral_count": referral_count,
        "credits_earned": current_user.referral_credits_granted,
    }


@router.post("/apply", summary="Apply a referral code", response_model=ReferralApplyResponse)
async def apply_referral(
    payload: ApplyReferralRequest,
    current_user: CurrentUser,
    db: DB,
) -> dict:
    code = payload.referral_code.strip()

    # Cannot apply if already referred
    if current_user.referred_by:
        raise HTTPException(status_code=409, detail="Referral code already applied.")

    # Cannot refer yourself
    if current_user.referral_code == code:
        raise HTTPException(status_code=400, detail="Cannot use your own referral code.")

    # Validate the referral code exists
    referrer = await db.scalar(
        select(User).where(User.referral_code == code)
    )
    if referrer is None:
        raise HTTPException(status_code=404, detail="Invalid referral code.")

    # Apply the referral
    await db.execute(
        update(User)
        .where(User.id == current_user.id)
        .values(referred_by=code)
    )

    # Grant credit to referrer
    await db.execute(
        update(User)
        .where(User.id == referrer.id)
        .values(referral_credits_granted=referrer.referral_credits_granted + 1)
    )

    await db.commit()
    logger.info("referral_applied", user_id=str(current_user.id), referrer_id=str(referrer.id), code=code)

    return {"message": "Referral code applied.", "referred_by": code}
