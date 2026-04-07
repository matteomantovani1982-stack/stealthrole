"""
app/api/routes/export.py — CSV data export endpoints.

GET /api/v1/export/applications  — export job applications as CSV
GET /api/v1/export/shadows       — export shadow applications as CSV
"""

import csv
import io
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.dependencies import DB, CurrentUserId
from app.models.job_run import JobRun
from app.models.shadow_application import ShadowApplication

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/export", tags=["Export"])

_APP_COLUMNS = [
    "id",
    "role_title",
    "company_name",
    "status",
    "pipeline_stage",
    "keyword_match_score",
    "apply_url",
    "created_at",
]

_SHADOW_COLUMNS = [
    "id",
    "company",
    "signal_type",
    "hypothesis_role",
    "status",
    "pipeline_stage",
    "confidence",
    "radar_score",
    "created_at",
]


def _to_csv(rows: list[dict], columns: list[str]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def _csv_response(content: str, filename: str) -> StreamingResponse:
    return StreamingResponse(
        iter([content]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/applications",
    summary="Export job applications as CSV",
    description="Downloads all job applications for the current user as a CSV file.",
)
async def export_applications(
    current_user_id: CurrentUserId,
    db: DB,
) -> StreamingResponse:
    q = (
        select(JobRun)
        .where(JobRun.user_id == current_user_id)
        .order_by(JobRun.created_at.desc())
    )
    rows = (await db.execute(q)).scalars().all()

    data = [
        {
            "id": str(r.id),
            "role_title": r.role_title or "",
            "company_name": r.company_name or "",
            "status": r.status,
            "pipeline_stage": r.pipeline_stage or "",
            "keyword_match_score": r.keyword_match_score if r.keyword_match_score is not None else "",
            "apply_url": r.apply_url or "",
            "created_at": r.created_at.isoformat() if r.created_at else "",
        }
        for r in rows
    ]

    ts = datetime.now(UTC).strftime("%Y%m%d")
    csv_content = _to_csv(data, _APP_COLUMNS)

    logger.info("export_applications", user_id=current_user_id, count=len(data))
    return _csv_response(csv_content, f"applications_{ts}.csv")


@router.get(
    "/shadows",
    summary="Export shadow applications as CSV",
    description="Downloads all shadow applications for the current user as a CSV file.",
)
async def export_shadows(
    current_user_id: CurrentUserId,
    db: DB,
) -> StreamingResponse:
    q = (
        select(ShadowApplication)
        .where(ShadowApplication.user_id == current_user_id)
        .order_by(ShadowApplication.created_at.desc())
    )
    rows = (await db.execute(q)).scalars().all()

    data = [
        {
            "id": str(s.id),
            "company": s.company or "",
            "signal_type": s.signal_type or "",
            "hypothesis_role": s.hypothesis_role or "",
            "status": s.status,
            "pipeline_stage": s.pipeline_stage or "",
            "confidence": round(s.confidence, 2) if s.confidence is not None else "",
            "radar_score": s.radar_score if s.radar_score is not None else "",
            "created_at": s.created_at.isoformat() if s.created_at else "",
        }
        for s in rows
    ]

    ts = datetime.now(UTC).strftime("%Y%m%d")
    csv_content = _to_csv(data, _SHADOW_COLUMNS)

    logger.info("export_shadows", user_id=current_user_id, count=len(data))
    return _csv_response(csv_content, f"shadow_applications_{ts}.csv")
