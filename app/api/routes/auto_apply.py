"""
app/api/routes/auto_apply.py

Auto-Apply Engine endpoints.

Routes:
  GET    /api/v1/auto-apply/profile                Get/create auto-apply profile
  PATCH  /api/v1/auto-apply/profile                Update profile fields
  POST   /api/v1/auto-apply/prepare                Generate form payload for ATS
  POST   /api/v1/auto-apply/report-submitted       Extension: form submitted OK
  POST   /api/v1/auto-apply/report-failed          Extension: form fill failed
  GET    /api/v1/auto-apply/submissions             List submission history
  GET    /api/v1/auto-apply/stats                   Submission stats
  GET    /api/v1/auto-apply/platforms               Supported ATS platforms
"""


from fastapi import APIRouter, HTTPException, Query, status

from app.dependencies import DB, CurrentUserId
from app.schemas.auto_apply import (
    AutoApplyProfileResponse,
    AutoApplyProfileUpdate,
    AutoApplyStatsResponse,
    PlatformInfo,
    PrepareRequest,
    ReportFailedRequest,
    ReportSubmittedRequest,
    SubmissionResponse,
)
from app.services.auto_apply.ats_service import AutoApplyService

router = APIRouter(prefix="/api/v1/auto-apply", tags=["Auto-Apply"])


def _svc(db: DB) -> AutoApplyService:
    return AutoApplyService(db=db)


# ── Profile ───────────────────────────────────────────────────────────────────

@router.get(
    "/profile",
    response_model=AutoApplyProfileResponse,
    summary="Get auto-apply profile (creates if missing)",
)
async def get_profile(
    db: DB, user_id: CurrentUserId,
) -> AutoApplyProfileResponse:
    profile = await _svc(db).get_or_create_profile(user_id)
    return AutoApplyProfileResponse.model_validate(profile)


@router.patch(
    "/profile",
    response_model=AutoApplyProfileResponse,
    summary="Update auto-apply profile fields",
)
async def update_profile(
    payload: AutoApplyProfileUpdate,
    db: DB, user_id: CurrentUserId,
) -> AutoApplyProfileResponse:
    profile = await _svc(db).update_profile(
        user_id, **payload.model_dump(exclude_unset=True),
    )
    return AutoApplyProfileResponse.model_validate(profile)


# ── Prepare ───────────────────────────────────────────────────────────────────

@router.post(
    "/prepare",
    status_code=status.HTTP_201_CREATED,
    response_model=SubmissionResponse,
    summary="Generate form payload for an ATS job page",
)
async def prepare_apply(
    payload: PrepareRequest,
    db: DB, user_id: CurrentUserId,
) -> SubmissionResponse:
    sub = await _svc(db).prepare(
        user_id=user_id,
        company=payload.company,
        role=payload.role,
        apply_url=payload.apply_url,
        application_id=payload.application_id,
        job_run_id=payload.job_run_id,
    )
    return SubmissionResponse.model_validate(sub)


# ── Extension callbacks ───────────────────────────────────────────────────────

@router.post(
    "/report-submitted",
    response_model=SubmissionResponse,
    summary="Extension reports successful form submission",
)
async def report_submitted(
    payload: ReportSubmittedRequest,
    db: DB, user_id: CurrentUserId,
) -> SubmissionResponse:
    sub = await _svc(db).report_submitted(user_id, payload.submission_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    return SubmissionResponse.model_validate(sub)


@router.post(
    "/report-failed",
    response_model=SubmissionResponse,
    summary="Extension reports form fill failure",
)
async def report_failed(
    payload: ReportFailedRequest,
    db: DB, user_id: CurrentUserId,
) -> SubmissionResponse:
    sub = await _svc(db).report_failed(user_id, payload.submission_id, payload.error)
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    return SubmissionResponse.model_validate(sub)


# ── Queries ───────────────────────────────────────────────────────────────────

@router.get(
    "/submissions",
    response_model=list[SubmissionResponse],
    summary="List auto-apply submission history",
)
async def list_submissions(
    db: DB, user_id: CurrentUserId,
    status_filter: str | None = Query(default=None, alias="status"),
) -> list[SubmissionResponse]:
    subs = await _svc(db).list_submissions(user_id, status_filter)
    return [SubmissionResponse.model_validate(s) for s in subs]


@router.get(
    "/stats",
    response_model=AutoApplyStatsResponse,
    summary="Auto-apply submission stats",
)
async def get_stats(
    db: DB, user_id: CurrentUserId,
) -> AutoApplyStatsResponse:
    stats = await _svc(db).get_stats(user_id)
    return AutoApplyStatsResponse(**stats)


@router.get(
    "/platforms",
    response_model=list[PlatformInfo],
    summary="List supported ATS platforms",
)
async def list_platforms(
    db: DB, user_id: CurrentUserId,
) -> list[PlatformInfo]:
    return [PlatformInfo(**p) for p in _svc(db).get_supported_platforms()]
