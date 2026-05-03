"""
app/api/routes/opportunities.py — OpportunityRadar endpoint.

GET /api/v1/opportunities/radar — unified ranked opportunity list
"""

import structlog
from fastapi import APIRouter, Query

from app.dependencies import DB, CurrentUserId
from app.api.routes.scout import _extract_prefs
from app.schemas.common import OpportunityRadarResponse

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/opportunities", tags=["OpportunityRadar"])


@router.get(
    "/radar",
    summary="Get ranked opportunities from all sources",
    response_model=OpportunityRadarResponse,
)
async def get_radar(
    current_user_id: CurrentUserId,
    db: DB,
    limit: int = Query(default=20, ge=1, le=50),
    min_score: int = Query(default=0, ge=0, le=100),
    source: str = Query(default="all"),
    urgency: str = Query(default="all"),
    include_speculative: bool = Query(default=False),
) -> dict:
    """
    OpportunityRadar — unified ranking across Hidden Market, Job Scout,
    and Signal Engine.

    Returns ranked opportunities with scores, reasoning, and actions.
    Speculative opportunities (role inferred without evidence) are hidden
    by default. Set include_speculative=true to see them.
    """
    from app.services.profile.profile_service import ProfileService

    # Load user profile + preferences
    svc = ProfileService(db)
    profile = await svc.get_active_profile_orm(current_user_id)
    profile_dict = profile.to_prompt_dict() if profile else None

    # Extract preferences using shared helper
    prefs = _extract_prefs({
        "preferences": profile.preferences if profile else None,
        "global_context": profile.global_context if profile else None,
    })

    from app.services.radar.opportunity_radar import run_radar

    result = await run_radar(
        db=db,
        user_id=current_user_id,
        user_prefs=prefs,
        profile_dict=profile_dict,
        limit=limit,
        min_score=min_score,
        source_filter=source,
        urgency_filter=urgency,
        include_speculative=include_speculative,
    )

    logger.info(
        "radar_served",
        user_id=current_user_id,
        total=result["total"],
        returned=result["returned"],
        scored_in_ms=result["meta"]["scored_in_ms"],
    )

    return result
