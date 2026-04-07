"""
app/api/routes/dashboard.py — Dashboard hub aggregation.
GET /api/v1/dashboard/summary
"""
import structlog
from fastapi import APIRouter
from sqlalchemy import func, select
from app.dependencies import DB, CurrentUserId

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard"])

@router.get("/summary", summary="Dashboard summary")
async def dashboard_summary(current_user_id: CurrentUserId, db: DB) -> dict:
    from app.services.radar.opportunity_radar import run_radar
    from app.services.profile.profile_service import ProfileService
    svc = ProfileService(db)
    profile = await svc.get_active_profile_orm(current_user_id)
    profile_dict = profile.to_prompt_dict() if profile else None
    prefs = {}
    if profile and profile.preferences:
        prefs = profile.preferences
    radar = await run_radar(db=db, user_id=current_user_id, user_prefs=prefs, profile_dict=profile_dict, limit=5)

    from app.models.job_run import JobRun
    apps = (await db.execute(select(JobRun).where(JobRun.user_id == current_user_id).order_by(JobRun.created_at.desc()).limit(3))).scalars().all()
    recent_apps = [{"id": str(a.id), "role_title": a.role_title, "company_name": a.company_name,
                    "status": a.status, "pipeline_stage": a.pipeline_stage,
                    "keyword_match_score": a.keyword_match_score, "created_at": a.created_at.isoformat()} for a in apps]

    from app.models.shadow_application import ShadowApplication
    shadows = (await db.execute(select(ShadowApplication).where(ShadowApplication.user_id == current_user_id).order_by(ShadowApplication.created_at.desc()).limit(3))).scalars().all()
    recent_shadows = [{"id": str(s.id), "company": s.company, "hypothesis_role": s.hypothesis_role,
                       "status": s.status, "confidence": s.confidence, "created_at": s.created_at.isoformat()} for s in shadows]

    total_apps = (await db.execute(select(func.count()).where(JobRun.user_id == current_user_id))).scalar() or 0
    total_shadows = (await db.execute(select(func.count()).where(ShadowApplication.user_id == current_user_id))).scalar() or 0

    scoring = radar["scoring"]
    completeness = scoring["profile_completeness"]
    profile_strength = {
        "score": completeness,
        "max": 1.0,
        "breakdown": scoring,
        "next_action": "Complete your profile to improve matching." if completeness < 1.0 else "Profile complete!",
    }

    return {
        "profile_strength": profile_strength,
        "top_opportunities": radar["opportunities"],
        "radar_opportunities": radar["opportunities"],
        "recent_applications": recent_apps,
        "recent_shadow_applications": recent_shadows,
        "shadow_count": total_shadows,
        "total_applications": total_apps,
        "total_shadow_applications": total_shadows,
        "credit_balance": 0,
        "radar_total": radar["total"],
        "profile_completeness": completeness,
        "sources_active": scoring["sources_active"],
    }
