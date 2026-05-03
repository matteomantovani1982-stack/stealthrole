"""
app/api/routes/email_intelligence.py

Email Intelligence endpoints — deep scan + behavioral insights.

Routes:
  POST   /api/v1/email-intelligence/scan       Trigger 5-year deep scan (async)
  GET    /api/v1/email-intelligence/report      Full intelligence report
  GET    /api/v1/email-intelligence/patterns    Behavioral patterns only
  GET    /api/v1/email-intelligence/insights    AI insights only
  GET    /api/v1/email-intelligence/timeline    Reconstructed application timeline
"""

from fastapi import APIRouter, HTTPException, status

from app.dependencies import DB, CurrentUserId
from app.schemas.email_intelligence import (
    EmailIntelligenceResponse,
    InsightsResponse,
    PatternsResponse,
    ScanTriggerResponse,
)
from app.schemas.common import EmailTimelineResponse
from app.services.email_integration.intelligence_service import EmailIntelligenceService

router = APIRouter(prefix="/api/v1/email-intelligence", tags=["Email Intelligence"])


def _svc(db: DB) -> EmailIntelligenceService:
    return EmailIntelligenceService(db=db)


@router.post(
    "/scan",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ScanTriggerResponse,
    summary="Trigger a deep 5-year email intelligence scan",
)
async def trigger_scan(
    db: DB,
    user_id: CurrentUserId,
) -> ScanTriggerResponse:
    svc = _svc(db)

    # Check if scan already running
    existing = await svc.get_report(user_id)
    if existing and existing.scan_status == "scanning":
        return ScanTriggerResponse(
            message="Scan already in progress",
            scan_status="scanning",
        )

    # Mark as started
    await svc.start_scan(user_id)

    # Dispatch Celery task
    from app.workers.tasks.email_intelligence import run_deep_scan
    task = run_deep_scan.delay(user_id)

    return ScanTriggerResponse(
        message="Deep scan started — this may take several minutes",
        task_id=task.id,
        scan_status="scanning",
    )


@router.get(
    "/report",
    response_model=EmailIntelligenceResponse,
    summary="Get full email intelligence report",
)
async def get_report(
    db: DB,
    user_id: CurrentUserId,
) -> EmailIntelligenceResponse:
    intel = await _svc(db).get_report(user_id)
    if not intel:
        raise HTTPException(
            status_code=404,
            detail="No intelligence report found. Trigger a scan first with POST /email-intelligence/scan",
        )
    return EmailIntelligenceResponse.model_validate(intel)


@router.get(
    "/patterns",
    response_model=PatternsResponse,
    summary="Get behavioral patterns from email analysis",
)
async def get_patterns(
    db: DB,
    user_id: CurrentUserId,
) -> PatternsResponse:
    intel = await _svc(db).get_report(user_id)
    if not intel or not intel.patterns:
        raise HTTPException(status_code=404, detail="No patterns available. Run a scan first.")
    return PatternsResponse(**intel.patterns)


@router.get(
    "/insights",
    response_model=InsightsResponse,
    summary="Get AI-generated behavioral insights",
)
async def get_insights(
    db: DB,
    user_id: CurrentUserId,
) -> InsightsResponse:
    intel = await _svc(db).get_report(user_id)
    if not intel or not intel.insights:
        raise HTTPException(status_code=404, detail="No insights available. Run a scan first.")
    return InsightsResponse(**intel.insights)


@router.get(
    "/writing-style",
    summary="Get extracted writing style profile",
)
async def get_writing_style(
    db: DB,
    user_id: CurrentUserId,
) -> dict:
    intel = await _svc(db).get_report(user_id)
    if not intel or not intel.writing_style:
        raise HTTPException(status_code=404, detail="No writing style data. Run a scan first.")
    return intel.writing_style


@router.get(
    "/timeline",
    summary="Get reconstructed application timeline from emails",
    response_model=EmailTimelineResponse,
)
async def get_timeline(
    db: DB,
    user_id: CurrentUserId,
) -> dict:
    intel = await _svc(db).get_report(user_id)
    if not intel or not intel.reconstructed_timeline:
        raise HTTPException(status_code=404, detail="No timeline available. Run a scan first.")
    return {
        "timeline": intel.reconstructed_timeline,
        "total": len(intel.reconstructed_timeline),
        "applications_reconstructed": intel.applications_reconstructed,
    }
