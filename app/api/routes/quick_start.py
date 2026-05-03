"""
app/api/routes/quick_start.py

Quick Start API — instant entry point for new users.
Accepts minimal input, returns immediate actionable output.

Endpoints
---------
  POST /quick-start — Instant signals + actions
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, status

from app.dependencies import DB, CurrentUserId
from app.schemas.quick_start import (
    QuickStartRequest,
    QuickStartResponse,
)
from app.services.billing.plan_gating import (
    QuickStartQuotaGate,
)
from app.services.entry.quick_start_engine import (
    QuickStartEngine,
)

logger = structlog.get_logger(__name__)
router = APIRouter(
    prefix="/api/v1/quick-start", tags=["Quick Start"],
)


@router.post(
    "",
    response_model=QuickStartResponse,
    status_code=status.HTTP_200_OK,
)
async def quick_start(
    body: QuickStartRequest,
    current_user_id: CurrentUserId,
    db: DB,
    quota: QuickStartQuotaGate,
) -> QuickStartResponse:
    """Run quick-start flow for immediate value.

    Accepts optional CV text, LinkedIn URL, target role,
    and target companies. Returns top signals and
    recommended actions without full setup.
    """
    engine = QuickStartEngine(db)
    data = await engine.quick_start(
        user_id=current_user_id,
        cv_text=body.cv_text,
        linkedin_url=body.linkedin_url,
        target_role=body.target_role,
        target_companies=(
            body.target_companies or None
        ),
    )
    return QuickStartResponse(**data)
