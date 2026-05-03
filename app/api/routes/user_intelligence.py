"""
app/api/routes/user_intelligence.py

User Intelligence Engine endpoints.

Routes:
  POST   /api/v1/intelligence/compute    Recompute intelligence profile
  GET    /api/v1/intelligence             Get current intelligence profile
"""

from fastapi import APIRouter, HTTPException

from app.dependencies import DB, CurrentUserId
from app.schemas.user_intelligence import UserIntelligenceResponse
from app.services.intelligence.user_intelligence_service import UserIntelligenceService

router = APIRouter(prefix="/api/v1/intelligence", tags=["User Intelligence"])


def _svc(db: DB) -> UserIntelligenceService:
    return UserIntelligenceService(db=db)


@router.post(
    "/compute",
    response_model=UserIntelligenceResponse,
    summary="Recompute user intelligence profile from all data sources",
)
async def compute_intelligence(
    db: DB, user_id: CurrentUserId,
) -> UserIntelligenceResponse:
    svc = _svc(db)
    intel = await svc.compute(user_id)
    return UserIntelligenceResponse.model_validate(intel)


@router.get(
    "",
    response_model=UserIntelligenceResponse,
    summary="Get current user intelligence profile",
)
async def get_intelligence(
    db: DB, user_id: CurrentUserId,
) -> UserIntelligenceResponse:
    svc = _svc(db)
    intel = await svc.get(user_id)
    if not intel:
        raise HTTPException(
            status_code=404,
            detail="No intelligence profile yet. POST /intelligence/compute to generate one.",
        )
    return UserIntelligenceResponse.model_validate(intel)
