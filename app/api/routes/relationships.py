"""
app/api/routes/relationships.py

Relationship Engine endpoints — warm intros and company relationship maps.

Routes:
  GET    /api/v1/relationships/company/{name}     Who do I know at this company?
  POST   /api/v1/relationships/request-intro       Create/draft a warm intro
  GET    /api/v1/relationships/pipeline            All warm intros in pipeline
  PATCH  /api/v1/relationships/{id}/status         Update intro status
  POST   /api/v1/relationships/auto-identify/{app_id}  Auto-find intros for an application
  GET    /api/v1/relationships/stats               Pipeline stats for dashboard
"""

import uuid

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.dependencies import DB, CurrentUserId
from app.schemas.relationship import (
    CompanyMapResponse,
    PipelineResponse,
    PipelineStatsResponse,
    RequestIntroRequest,
    UpdateIntroStatusRequest,
    WarmIntroResponse,
)
from app.services.linkedin.relationship_engine import RelationshipEngine

router = APIRouter(prefix="/api/v1/relationships", tags=["Relationship Engine"])


def _svc(db: DB) -> RelationshipEngine:
    return RelationshipEngine(db=db)


# ── Company map ───────────────────────────────────────────────────────────────

@router.get(
    "/company/{company}",
    response_model=CompanyMapResponse,
    summary="Who do I know at this company? Ranked by usefulness.",
)
async def get_company_map(
    company: str,
    db: DB,
    user_id: CurrentUserId,
) -> CompanyMapResponse:
    result = await _svc(db).get_company_map(user_id=user_id, company=company)
    return CompanyMapResponse(**result)


# ── Request intro ─────────────────────────────────────────────────────────────

@router.post(
    "/request-intro",
    status_code=status.HTTP_201_CREATED,
    response_model=WarmIntroResponse,
    summary="Create or draft a warm intro request",
)
async def request_intro(
    payload: RequestIntroRequest,
    db: DB,
    user_id: CurrentUserId,
) -> WarmIntroResponse:
    try:
        intro = await _svc(db).request_intro(
            user_id=user_id,
            connection_id=payload.connection_id,
            target_company=payload.target_company,
            target_role=payload.target_role,
            application_id=payload.application_id,
            relationship_context=payload.relationship_context,
            custom_message=payload.custom_message,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return WarmIntroResponse.model_validate(intro)


# ── Pipeline ──────────────────────────────────────────────────────────────────

@router.get(
    "/pipeline",
    response_model=PipelineResponse,
    summary="List all warm intros in the outreach pipeline",
)
async def get_pipeline(
    db: DB,
    user_id: CurrentUserId,
    status_filter: str | None = Query(default=None, alias="status"),
) -> PipelineResponse:
    intros = await _svc(db).get_pipeline(user_id=user_id, status_filter=status_filter)
    return PipelineResponse(
        intros=[WarmIntroResponse.model_validate(i) for i in intros],
        total=len(intros),
    )


@router.patch(
    "/{intro_id}/status",
    response_model=WarmIntroResponse,
    summary="Update warm intro pipeline status",
)
async def update_intro_status(
    intro_id: uuid.UUID,
    payload: UpdateIntroStatusRequest,
    db: DB,
    user_id: CurrentUserId,
) -> WarmIntroResponse:
    intro = await _svc(db).update_status(
        user_id=user_id,
        intro_id=intro_id,
        new_status=payload.status,
        response_message=payload.response_message,
        notes=payload.notes,
    )
    if not intro:
        raise HTTPException(status_code=404, detail="Warm intro not found")
    return WarmIntroResponse.model_validate(intro)


# ── Auto-identify ─────────────────────────────────────────────────────────────

@router.post(
    "/auto-identify/{app_id}",
    response_model=list[WarmIntroResponse],
    summary="Auto-find warm intro paths for an application",
)
async def auto_identify(
    app_id: uuid.UUID,
    db: DB,
    user_id: CurrentUserId,
) -> list[WarmIntroResponse]:
    intros = await _svc(db).auto_identify_intros(
        user_id=user_id, application_id=app_id,
    )
    return [WarmIntroResponse.model_validate(i) for i in intros]


# ── Stats ─────────────────────────────────────────────────────────────────────

@router.get(
    "/stats",
    response_model=PipelineStatsResponse,
    summary="Relationship pipeline stats for dashboard",
)
async def pipeline_stats(
    db: DB,
    user_id: CurrentUserId,
) -> PipelineStatsResponse:
    stats = await _svc(db).get_pipeline_stats(user_id=user_id)
    return PipelineStatsResponse(**stats)


# ── Find My Way In (for extension + frontend) ────────────────────────────────

class FindWayInRequest(BaseModel):
    company: str = Field(..., min_length=1, max_length=255)
    role: str | None = Field(default=None, max_length=255)
    application_id: uuid.UUID | None = None


@router.post(
    "/find-way-in",
    summary="Find the best path into a target company",
    description="Returns direct contacts, warm paths, recommended action, and intro messages.",
)
async def find_way_in(
    payload: FindWayInRequest,
    db: DB,
    user_id: CurrentUserId,
) -> dict:
    """
    The killer feature: finds direct contacts and warm intro paths.
    Cross-references LinkedIn connections with target company and role.
    """
    engine = _svc(db)
    result = await engine.find_way_in(
        user_id=user_id,
        company=payload.company,
        role=payload.role,
    )

    # Auto-identify if we have an application
    if payload.application_id:
        try:
            await engine.auto_identify_intros(user_id=user_id, application_id=payload.application_id)
        except Exception:
            pass

    return result
