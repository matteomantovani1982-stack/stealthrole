"""
app/api/routes/shadow.py — Shadow Application endpoints.

POST   /api/v1/shadow/generate    — create + enqueue shadow application
GET    /api/v1/shadow             — list user's shadow applications
GET    /api/v1/shadow/{id}        — get shadow application detail
DELETE /api/v1/shadow/{id}        — delete shadow application
PATCH  /api/v1/shadow/{id}/stage  — update pipeline stage
"""

import uuid

import structlog
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from app.dependencies import DB, CurrentUser, CurrentUserId
from app.models.shadow_application import ShadowApplication, ShadowStatus
from app.services.shadow.shadow_schema import (
    ShadowDetailResponse,
    ShadowGenerateRequest,
    ShadowGenerateResponse,
)

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/shadow", tags=["Shadow Applications"])


@router.post(
    "/generate",
    response_model=ShadowGenerateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Generate a Shadow Application Pack",
)
async def generate_shadow(
    payload: ShadowGenerateRequest,
    current_user: CurrentUser,
    db: DB,
) -> ShadowGenerateResponse:
    """
    Create a shadow application and dispatch background generation.

    The response is immediate (202). Poll GET /shadow/{id} for results.
    """
    user_id = str(current_user.id)

    # Create shadow application record
    context = payload.signal_context or ""

    shadow = ShadowApplication(
        user_id=user_id,
        company=payload.company,
        signal_type=payload.signal_type,
        signal_context=context,
        radar_opportunity_id=payload.radar_opportunity_id,
        radar_score=payload.radar_score,
        hidden_signal_id=(
            uuid.UUID(payload.hidden_signal_id)
            if payload.hidden_signal_id
            else None
        ),
        status=ShadowStatus.GENERATING,
    )
    db.add(shadow)
    await db.commit()
    await db.refresh(shadow)

    shadow_id = str(shadow.id)

    # Dispatch Celery task
    from app.workers.tasks.shadow_gen import generate_shadow_application
    generate_shadow_application.delay(shadow_id)

    logger.info(
        "shadow_generation_dispatched",
        shadow_id=shadow_id,
        company=payload.company,
        user_id=user_id,
    )

    return ShadowGenerateResponse(
        id=shadow_id,
        status="generating",
        company=payload.company,
        hypothesis_role=None,
        message="Shadow application generation started. Poll GET /api/v1/shadow/{id} for results.",
    )


@router.get(
    "",
    summary="List shadow applications",
)
async def list_shadows(
    current_user_id: CurrentUserId,
    db: DB,
) -> dict:
    """List all shadow applications for the current user."""
    q = (
        select(ShadowApplication)
        .where(ShadowApplication.user_id == current_user_id)
        .order_by(ShadowApplication.created_at.desc())
        .limit(50)
    )
    rows = (await db.execute(q)).scalars().all()

    return {
        "shadow_applications": [
            {
                "id": str(s.id),
                "company": s.company,
                "signal_type": s.signal_type,
                "hypothesis_role": s.hypothesis_role,
                "radar_score": s.radar_score,
                "confidence": s.confidence,
                "status": s.status,
                "pipeline_stage": s.pipeline_stage,
                "created_at": s.created_at.isoformat(),
            }
            for s in rows
        ],
        "total": len(rows),
    }


@router.get(
    "/{shadow_id}",
    response_model=ShadowDetailResponse,
    summary="Get shadow application detail",
)
async def get_shadow(
    shadow_id: uuid.UUID,
    current_user_id: CurrentUserId,
    db: DB,
) -> ShadowDetailResponse:
    """Get full detail of a shadow application including generated outputs."""
    shadow = await db.get(ShadowApplication, shadow_id)
    if shadow is None or shadow.user_id != current_user_id:
        raise HTTPException(status_code=404, detail="Shadow application not found")

    # Generate download URL if CV exists
    cv_download_url = None
    if shadow.tailored_cv_s3_key:
        from app.services.ingest.storage import S3StorageService
        storage = S3StorageService()
        cv_download_url = storage.generate_presigned_url(shadow.tailored_cv_s3_key)

    return ShadowDetailResponse(
        id=str(shadow.id),
        company=shadow.company,
        signal_type=shadow.signal_type,
        signal_context=shadow.signal_context,
        radar_score=shadow.radar_score,
        status=shadow.status,
        hypothesis_role=shadow.hypothesis_role,
        hiring_hypothesis=shadow.hiring_hypothesis,
        strategy_memo=shadow.strategy_memo,
        outreach_linkedin=shadow.outreach_linkedin,
        outreach_email=shadow.outreach_email,
        outreach_followup=shadow.outreach_followup,
        tailored_cv_download_url=cv_download_url,
        confidence=shadow.confidence,
        reasoning=shadow.reasoning,
        pipeline_stage=shadow.pipeline_stage,
        pipeline_notes=shadow.pipeline_notes,
        created_at=shadow.created_at.isoformat(),
    )


@router.delete(
    "/{shadow_id}",
    summary="Delete a shadow application",
)
async def delete_shadow(
    shadow_id: uuid.UUID,
    current_user_id: CurrentUserId,
    db: DB,
) -> dict:
    """Delete a shadow application. Only the owning user can delete."""
    shadow = await db.get(ShadowApplication, shadow_id)
    if shadow is None or shadow.user_id != current_user_id:
        raise HTTPException(status_code=404, detail="Shadow application not found")

    await db.delete(shadow)
    await db.commit()

    logger.info("shadow_deleted", shadow_id=str(shadow_id), user_id=current_user_id)
    return {"deleted": True, "id": str(shadow_id)}


class ShadowStageUpdate(BaseModel):
    stage: str  # created | sent | responded | interview | offer | rejected | withdrawn
    notes: str | None = None


VALID_SHADOW_STAGES = {"created", "sent", "responded", "interview", "offer", "rejected", "withdrawn"}


@router.patch(
    "/{shadow_id}/stage",
    summary="Update shadow application pipeline stage",
)
async def update_shadow_stage(
    shadow_id: uuid.UUID,
    payload: ShadowStageUpdate,
    current_user_id: CurrentUserId,
    db: DB,
) -> dict:
    """Track shadow application through sent → responded → interview → offer/rejected."""
    if payload.stage not in VALID_SHADOW_STAGES:
        raise HTTPException(status_code=400, detail=f"Invalid stage. Must be one of: {VALID_SHADOW_STAGES}")

    shadow = await db.get(ShadowApplication, shadow_id)
    if shadow is None or shadow.user_id != current_user_id:
        raise HTTPException(status_code=404, detail="Shadow application not found")

    shadow.pipeline_stage = payload.stage
    if payload.notes is not None:
        shadow.pipeline_notes = payload.notes

    await db.flush()
    await db.commit()

    return {
        "id": str(shadow.id),
        "pipeline_stage": shadow.pipeline_stage,
        "pipeline_notes": shadow.pipeline_notes,
    }
