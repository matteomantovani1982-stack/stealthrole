"""
app/api/routes/admin_costs.py

Admin endpoint for tracking LLM API costs.
Reads from JobStep.metadata_json which is populated by ClaudeClient on every call.

GET /api/v1/admin/costs — total cost today / week / month, broken down by feature
"""
from datetime import datetime, timedelta, UTC

import structlog
from fastapi import APIRouter
from sqlalchemy import select

from app.dependencies import DB, CurrentUser
from app.models.job_step import JobStep

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])


@router.get("/costs", summary="LLM API cost breakdown")
async def get_costs(
    db: DB,
    current_user: CurrentUser,
) -> dict:
    """
    Return total LLM API cost for today, this week, and this month,
    broken down by step name and model.

    Only accessible to authenticated users (we'll add admin role check later).
    """
    now = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=7)
    month_start = today_start - timedelta(days=30)

    # Pull all steps in the last month
    result = await db.execute(
        select(JobStep)
        .where(JobStep.created_at >= month_start)
    )
    steps = result.scalars().all()

    def _cost_of(step: JobStep) -> float:
        meta = step.metadata_json or {}
        return float(meta.get("cost_usd", 0) or 0)

    def _tokens_of(step: JobStep) -> tuple[int, int]:
        meta = step.metadata_json or {}
        return (int(meta.get("input_tokens", 0) or 0), int(meta.get("output_tokens", 0) or 0))

    def _model_of(step: JobStep) -> str:
        meta = step.metadata_json or {}
        return str(meta.get("model", "unknown"))

    today_total = 0.0
    week_total = 0.0
    month_total = 0.0
    by_feature: dict[str, dict] = {}
    by_model: dict[str, dict] = {}

    for step in steps:
        cost = _cost_of(step)
        if cost == 0:
            continue
        in_tok, out_tok = _tokens_of(step)
        model = _model_of(step)
        feature = step.step_name or "unknown"

        if step.created_at >= today_start:
            today_total += cost
        if step.created_at >= week_start:
            week_total += cost
        month_total += cost

        # By feature
        if feature not in by_feature:
            by_feature[feature] = {"calls": 0, "cost_usd": 0.0, "input_tokens": 0, "output_tokens": 0}
        by_feature[feature]["calls"] += 1
        by_feature[feature]["cost_usd"] += cost
        by_feature[feature]["input_tokens"] += in_tok
        by_feature[feature]["output_tokens"] += out_tok

        # By model
        if model not in by_model:
            by_model[model] = {"calls": 0, "cost_usd": 0.0}
        by_model[model]["calls"] += 1
        by_model[model]["cost_usd"] += cost

    # Round
    for d in by_feature.values():
        d["cost_usd"] = round(d["cost_usd"], 4)
    for d in by_model.values():
        d["cost_usd"] = round(d["cost_usd"], 4)

    return {
        "totals": {
            "today_usd": round(today_total, 4),
            "week_usd": round(week_total, 4),
            "month_usd": round(month_total, 4),
        },
        "by_feature": dict(sorted(by_feature.items(), key=lambda x: -x[1]["cost_usd"])),
        "by_model": dict(sorted(by_model.items(), key=lambda x: -x[1]["cost_usd"])),
        "as_of": now.isoformat(),
    }
