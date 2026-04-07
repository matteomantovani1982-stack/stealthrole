"""
app/api/routes/interviews.py

Interview Coach + Compensation endpoints.

Routes:
  POST   /api/v1/interviews/applications/{id}/rounds     Add interview round
  GET    /api/v1/interviews/applications/{id}/rounds     List rounds
  PATCH  /api/v1/interviews/rounds/{id}                  Update round (debrief, outcome)
  DELETE /api/v1/interviews/rounds/{id}                  Delete round
  GET    /api/v1/interviews/rounds/{id}/prep             Get prep guide for round
  GET    /api/v1/interviews/applications/{id}/negotiation  Negotiation guide
  GET    /api/v1/interviews/compensation                  Salary benchmark lookup
  GET    /api/v1/interviews/stats                         Interview analytics
"""

import uuid

from fastapi import APIRouter, HTTPException, Query, status

from app.dependencies import DB, CurrentUserId
from app.schemas.interview import (
    CompensationBenchmarkResponse,
    InterviewRoundCreate,
    InterviewRoundResponse,
    InterviewRoundUpdate,
    InterviewStatsResponse,
    NegotiationGuideResponse,
    PrepGuideResponse,
)
from app.services.interview.coach_service import InterviewCoachService

router = APIRouter(prefix="/api/v1/interviews", tags=["Interview Coach"])


def _svc(db: DB) -> InterviewCoachService:
    return InterviewCoachService(db=db)


# ── Rounds CRUD ───────────────────────────────────────────────────────────────

@router.post(
    "/applications/{app_id}/rounds",
    status_code=status.HTTP_201_CREATED,
    response_model=InterviewRoundResponse,
    summary="Add an interview round",
)
async def add_round(
    app_id: uuid.UUID,
    payload: InterviewRoundCreate,
    db: DB, user_id: CurrentUserId,
) -> InterviewRoundResponse:
    try:
        round_ = await _svc(db).add_round(
            user_id=user_id,
            application_id=app_id,
            **payload.model_dump(exclude_unset=True),
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return InterviewRoundResponse.model_validate(round_)


@router.get(
    "/applications/{app_id}/rounds",
    response_model=list[InterviewRoundResponse],
    summary="List interview rounds for an application",
)
async def list_rounds(
    app_id: uuid.UUID,
    db: DB, user_id: CurrentUserId,
) -> list[InterviewRoundResponse]:
    rounds = await _svc(db).list_rounds(user_id, app_id)
    return [InterviewRoundResponse.model_validate(r) for r in rounds]


@router.patch(
    "/rounds/{round_id}",
    response_model=InterviewRoundResponse,
    summary="Update round (debrief, outcome, etc.)",
)
async def update_round(
    round_id: uuid.UUID,
    payload: InterviewRoundUpdate,
    db: DB, user_id: CurrentUserId,
) -> InterviewRoundResponse:
    round_ = await _svc(db).update_round(
        user_id, round_id, **payload.model_dump(exclude_unset=True),
    )
    if not round_:
        raise HTTPException(status_code=404, detail="Round not found")
    return InterviewRoundResponse.model_validate(round_)


@router.delete(
    "/rounds/{round_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an interview round",
)
async def delete_round(
    round_id: uuid.UUID,
    db: DB, user_id: CurrentUserId,
) -> None:
    if not await _svc(db).delete_round(user_id, round_id):
        raise HTTPException(status_code=404, detail="Round not found")


# ── Prep + Negotiation ────────────────────────────────────────────────────────

@router.get(
    "/rounds/{round_id}/prep",
    response_model=PrepGuideResponse,
    summary="Get interview prep guide for a round",
)
async def get_prep_guide(
    round_id: uuid.UUID,
    db: DB, user_id: CurrentUserId,
) -> PrepGuideResponse:
    guide = await _svc(db).get_prep_guide(user_id, round_id)
    if "error" in guide:
        raise HTTPException(status_code=404, detail=guide["error"])
    return PrepGuideResponse(**guide)


@router.get(
    "/applications/{app_id}/negotiation",
    response_model=NegotiationGuideResponse,
    summary="Get negotiation guide + compensation data",
)
async def get_negotiation(
    app_id: uuid.UUID,
    db: DB, user_id: CurrentUserId,
    offer_amount: int | None = Query(default=None, description="Offer amount for comparison"),
) -> NegotiationGuideResponse:
    guide = await _svc(db).get_negotiation_guide(user_id, app_id, offer_amount)
    if "error" in guide:
        raise HTTPException(status_code=404, detail=guide["error"])
    return NegotiationGuideResponse(**guide)


# ── Compensation ──────────────────────────────────────────────────────────────

@router.get(
    "/compensation",
    summary="Look up salary benchmark",
)
async def get_compensation(
    db: DB, user_id: CurrentUserId,
    role: str = Query(..., min_length=1),
    region: str = Query(default="global"),
) -> dict:
    benchmark = await _svc(db).get_benchmark(role, region)
    if not benchmark:
        return {"message": "No benchmark data available for this role/region", "role": role, "region": region}
    return CompensationBenchmarkResponse.model_validate(benchmark).model_dump()


# ── Stats ─────────────────────────────────────────────────────────────────────

@router.get(
    "/stats",
    response_model=InterviewStatsResponse,
    summary="Interview performance analytics",
)
async def get_stats(
    db: DB, user_id: CurrentUserId,
) -> InterviewStatsResponse:
    stats = await _svc(db).get_interview_stats(user_id)
    return InterviewStatsResponse(**stats)
