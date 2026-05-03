"""
app/api/routes/insights.py

Value / ROI Engine API — surfaces insights and recommendations
derived from the user's signal and action history.

Endpoints
---------
  GET /insights — Full value dashboard
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter

from app.dependencies import DB, CurrentUserId
from app.schemas.insights import InsightsResponse
from app.services.billing.plan_gating import (
    ValueInsightsFeature,
)
from app.services.intelligence.value_engine import ValueEngine

logger = structlog.get_logger(__name__)
router = APIRouter(
    prefix="/api/v1/insights", tags=["Insights"],
)


@router.get("", response_model=InsightsResponse)
async def get_insights(
    current_user_id: CurrentUserId,
    db: DB,
    _gate: ValueInsightsFeature,
) -> InsightsResponse:
    """Return value/ROI insights for the current user.

    Computes signal effectiveness, action effectiveness,
    path performance, timing, and recommendations.
    """
    engine = ValueEngine(db)
    data = await engine.compute_insights(current_user_id)
    return InsightsResponse(**data)
