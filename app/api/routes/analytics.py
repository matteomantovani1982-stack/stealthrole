"""
app/api/routes/analytics.py — Application & shadow analytics.
GET /api/v1/analytics/summary
GET /api/v1/analytics/trends
"""
import structlog
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Query
from sqlalchemy import func, select, cast, Date
from app.dependencies import DB, CurrentUserId
from app.models.job_run import JobRun
from app.models.shadow_application import ShadowApplication

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/analytics", tags=["Analytics"])


@router.get("/summary", summary="Application analytics summary")
async def analytics_summary(current_user_id: CurrentUserId, db: DB) -> dict:
    # ── Job run metrics ───────────────────────────────────────────────
    total = (await db.execute(select(func.count()).where(JobRun.user_id == current_user_id))).scalar() or 0
    stage_rows = (await db.execute(
        select(JobRun.pipeline_stage, func.count()).where(JobRun.user_id == current_user_id).group_by(JobRun.pipeline_stage)
    )).all()
    by_stage = {row[0] or "watching": row[1] for row in stage_rows}
    applied = by_stage.get("applied", 0)
    interviewing = by_stage.get("interviewing", 0)
    offer = by_stage.get("offer", 0)
    rejected = by_stage.get("rejected", 0)
    denom = applied + interviewing + offer + rejected
    response_rate = round((interviewing + offer) / denom * 100, 1) if denom > 0 else 0.0
    avg_score = (await db.execute(
        select(func.avg(JobRun.keyword_match_score)).where(JobRun.user_id == current_user_id, JobRun.keyword_match_score.isnot(None))
    )).scalar()

    # ── Shadow metrics ────────────────────────────────────────────────
    total_shadows = (await db.execute(
        select(func.count()).where(ShadowApplication.user_id == current_user_id)
    )).scalar() or 0

    shadow_status_rows = (await db.execute(
        select(ShadowApplication.status, func.count())
        .where(ShadowApplication.user_id == current_user_id)
        .group_by(ShadowApplication.status)
    )).all()
    shadow_by_status = {row[0]: row[1] for row in shadow_status_rows}

    shadow_by_signal_rows = (await db.execute(
        select(ShadowApplication.signal_type, func.count())
        .where(ShadowApplication.user_id == current_user_id)
        .group_by(ShadowApplication.signal_type)
    )).all()
    shadow_by_signal = {row[0]: row[1] for row in shadow_by_signal_rows}

    avg_confidence = (await db.execute(
        select(func.avg(ShadowApplication.confidence))
        .where(ShadowApplication.user_id == current_user_id, ShadowApplication.confidence.isnot(None))
    )).scalar()

    return {
        "total_applications": total,
        "by_stage": by_stage,
        "response_rate": response_rate,
        "avg_keyword_score": round(avg_score, 1) if avg_score else 0.0,
        "total_shadows": total_shadows,
        "shadow_by_status": shadow_by_status,
        "shadow_by_signal": shadow_by_signal,
        "avg_shadow_confidence": round(avg_confidence, 2) if avg_confidence is not None else None,
    }


@router.get("/trends", summary="Weekly activity trends")
async def analytics_trends(
    current_user_id: CurrentUserId,
    db: DB,
    weeks: int = Query(default=8, ge=1, le=52, description="Number of weeks to look back"),
) -> dict:
    cutoff = datetime.now(UTC) - timedelta(weeks=weeks)

    # ── Applications per week ─────────────────────────────────────────
    app_rows = (await db.execute(
        select(
            func.date_trunc("week", JobRun.created_at).label("week"),
            func.count(),
        )
        .where(JobRun.user_id == current_user_id, JobRun.created_at >= cutoff)
        .group_by("week")
        .order_by("week")
    )).all()

    # ── Shadows per week ──────────────────────────────────────────────
    shadow_rows = (await db.execute(
        select(
            func.date_trunc("week", ShadowApplication.created_at).label("week"),
            func.count(),
        )
        .where(ShadowApplication.user_id == current_user_id, ShadowApplication.created_at >= cutoff)
        .group_by("week")
        .order_by("week")
    )).all()

    return {
        "weeks": weeks,
        "applications": [
            {"week": row[0].isoformat(), "count": row[1]} for row in app_rows
        ],
        "shadows": [
            {"week": row[0].isoformat(), "count": row[1]} for row in shadow_rows
        ],
    }
