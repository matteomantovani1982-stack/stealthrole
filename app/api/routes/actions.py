"""
app/api/routes/actions.py

Action Engine API — generate, list, manage, and execute action
recommendations derived from the intelligence pipeline.

Endpoints
---------
  POST   /actions/generate          — Generate actions for a signal
  GET    /actions                   — List user's actions (filterable)
  GET    /actions/top               — Top prioritised actionable items
  PATCH  /actions/{id}/queue        — Move to queued
  PATCH  /actions/{id}/sent         — Mark as sent
  PATCH  /actions/{id}/responded    — Mark as responded
  PATCH  /actions/{id}/dismiss      — Dismiss action
  PATCH  /actions/{id}/message      — Edit message content
  POST   /actions/{id}/execute      — Execute via channel (mock)
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.dependencies import DB, CurrentUserId
from app.models.action_recommendation import ActionRecommendation
from app.models.hidden_signal import HiddenSignal
from app.models.signal_interpretation import SignalInterpretation
from app.schemas.actions import (
    ActionExecuteResponse,
    ActionGenerateRequest,
    ActionGenerateResponse,
    ActionItem,
    ActionsListResponse,
    ActionTransitionResponse,
    ActionUpdateMessageRequest,
    TopActionsResponse,
)
from app.services.action.action_executor import ActionExecutor
from app.services.action.action_generator import ActionGenerator
from app.services.billing.plan_gating import (
    ActionQuotaGate,
)
from app.services.intelligence.decision_engine import DecisionEngine

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/actions", tags=["Actions"])


# ── Helpers ──────────────────────────────────────────────────────────


def _action_to_item(record: ActionRecommendation) -> ActionItem:
    """Convert ORM model to response schema."""
    return ActionItem(
        id=str(record.id),
        action_type=record.action_type,
        status=record.status,
        target_name=record.target_name or "",
        target_title=record.target_title or "",
        target_company=record.target_company,
        reason=record.reason,
        message_subject=record.message_subject,
        message_body=record.message_body,
        timing_label=record.timing_label,
        confidence=record.confidence,
        priority=record.priority,
        decision_score=record.decision_score,
        channel_metadata=record.channel_metadata or {},
        is_user_edited=record.is_user_edited,
        created_at=(
            record.created_at.isoformat() if record.created_at else None
        ),
        expires_at=(
            record.expires_at.isoformat() if record.expires_at else None
        ),
    )


# ── Generate ─────────────────────────────────────────────────────────


@router.post(
    "/generate",
    response_model=ActionGenerateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_actions(
    body: ActionGenerateRequest,
    current_user_id: CurrentUserId,
    db: DB,
    quota: ActionQuotaGate,
) -> ActionGenerateResponse:
    """Generate action recommendations for a specific signal.

    Takes a signal_id, scores it through the decision engine,
    and produces concrete actions the user can take.
    """
    # Load the signal
    result = await db.execute(
        select(HiddenSignal).where(
            HiddenSignal.id == body.signal_id,
            HiddenSignal.user_id == current_user_id,
        )
    )
    signal = result.scalar_one_or_none()
    if not signal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Signal not found",
        )

    # Load interpretation (if exists)
    interp_result = await db.execute(
        select(SignalInterpretation).where(
            SignalInterpretation.signal_id == signal.id,
            SignalInterpretation.user_id == current_user_id,
        )
    )
    interpretation = interp_result.scalar_one_or_none()

    # Score through decision engine
    engine = DecisionEngine(db)
    decision = await engine.score_opportunity(
        signal,
        current_user_id,
        profile_fit=body.profile_fit,
        access_strength=body.access_strength,
    )

    # Generate actions
    generator = ActionGenerator(db)
    actions = await generator.generate_actions(
        signal=signal,
        interpretation=interpretation,
        decision=decision,
        user_id=current_user_id,
    )

    # Persist
    executor = ActionExecutor(db)
    records = await executor.persist_actions(
        actions=actions,
        user_id=current_user_id,
        signal_id=signal.id,
        interpretation_id=(
            interpretation.id if interpretation else None
        ),
    )
    await db.commit()

    return ActionGenerateResponse(
        actions_created=len(records),
        signal_id=str(signal.id),
        action_types=[r.action_type for r in records],
    )


# ── List ─────────────────────────────────────────────────────────────


@router.get("", response_model=ActionsListResponse)
async def list_actions(
    current_user_id: CurrentUserId,
    db: DB,
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, le=200),
) -> ActionsListResponse:
    """List the user's action recommendations.

    Optional filter by status: generated, queued, sent, responded,
    expired, dismissed.
    """
    executor = ActionExecutor(db)
    records = await executor.get_user_actions(
        current_user_id,
        status_filter=status_filter,
        limit=limit,
    )
    return ActionsListResponse(
        actions=[_action_to_item(r) for r in records],
        total=len(records),
    )


@router.get("/top", response_model=TopActionsResponse)
async def get_top_actions(
    current_user_id: CurrentUserId,
    db: DB,
    limit: int = Query(10, le=50),
) -> TopActionsResponse:
    """Return the top prioritised actionable recommendations.

    Only includes actions in generated or queued status.
    """
    executor = ActionExecutor(db)

    # Expire stale actions first
    await executor.expire_stale_actions(current_user_id)

    # Fetch actionable
    q = (
        select(ActionRecommendation)
        .where(
            ActionRecommendation.user_id == current_user_id,
            ActionRecommendation.status.in_(["generated", "queued"]),
        )
        .order_by(
            ActionRecommendation.priority.asc(),
            ActionRecommendation.confidence.desc(),
        )
        .limit(limit)
    )
    result = await db.execute(q)
    records = list(result.scalars().all())

    # Count active signals for context
    sig_q = select(HiddenSignal.id).where(
        HiddenSignal.user_id == current_user_id,
        HiddenSignal.is_dismissed.is_(False),
        HiddenSignal.quality_gate_result.in_(["pass", "conditional"]),
    )
    sig_result = await db.execute(sig_q)
    active_signals = len(sig_result.all())

    return TopActionsResponse(
        actions=[_action_to_item(r) for r in records],
        total=len(records),
        active_signals=active_signals,
    )


# ── Lifecycle transitions ────────────────────────────────────────────


@router.patch("/{action_id}/queue", response_model=ActionTransitionResponse)
async def queue_action(
    action_id: str,
    current_user_id: CurrentUserId,
    db: DB,
) -> ActionTransitionResponse:
    """Move action to queued status."""
    executor = ActionExecutor(db)
    record = await executor.queue_action(action_id, current_user_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot queue this action (not found or invalid transition)",
        )
    await db.commit()
    return ActionTransitionResponse(
        id=str(record.id),
        status=record.status,
        previous_status="generated",
        success=True,
    )


@router.patch("/{action_id}/sent", response_model=ActionTransitionResponse)
async def mark_sent(
    action_id: str,
    current_user_id: CurrentUserId,
    db: DB,
) -> ActionTransitionResponse:
    """Mark action as sent/delivered."""
    executor = ActionExecutor(db)
    record = await executor.mark_sent(action_id, current_user_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot mark as sent (not found or invalid transition)",
        )
    await db.commit()
    return ActionTransitionResponse(
        id=str(record.id),
        status=record.status,
        previous_status="queued",
        success=True,
    )


@router.patch("/{action_id}/responded", response_model=ActionTransitionResponse)
async def mark_responded(
    action_id: str,
    current_user_id: CurrentUserId,
    db: DB,
) -> ActionTransitionResponse:
    """Mark action as responded to."""
    executor = ActionExecutor(db)
    record = await executor.mark_responded(action_id, current_user_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot mark as responded (not found or invalid transition)",
        )
    await db.commit()
    return ActionTransitionResponse(
        id=str(record.id),
        status=record.status,
        previous_status="sent",
        success=True,
    )


@router.patch("/{action_id}/dismiss", response_model=ActionTransitionResponse)
async def dismiss_action(
    action_id: str,
    current_user_id: CurrentUserId,
    db: DB,
) -> ActionTransitionResponse:
    """Dismiss an action the user chooses not to act on."""
    executor = ActionExecutor(db)
    record = await executor.dismiss_action(action_id, current_user_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot dismiss (not found or invalid transition)",
        )
    await db.commit()
    return ActionTransitionResponse(
        id=str(record.id),
        status=record.status,
        previous_status="generated",
        success=True,
    )


# ── Edit message ─────────────────────────────────────────────────────


@router.patch("/{action_id}/message", response_model=ActionItem)
async def update_message(
    action_id: str,
    body: ActionUpdateMessageRequest,
    current_user_id: CurrentUserId,
    db: DB,
) -> ActionItem:
    """Update the message content of an action.

    Only allowed for actions in generated or queued status.
    """
    q = select(ActionRecommendation).where(
        ActionRecommendation.id == action_id,
        ActionRecommendation.user_id == current_user_id,
    )
    result = await db.execute(q)
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Action not found",
        )
    if record.status not in ("generated", "queued"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot edit action in '{record.status}' state",
        )

    if body.message_subject is not None:
        record.message_subject = body.message_subject
    if body.message_body is not None:
        record.message_body = body.message_body

    record.is_user_edited = True
    await db.commit()
    await db.refresh(record)

    return _action_to_item(record)


# ── Execute ──────────────────────────────────────────────────────────


@router.post("/{action_id}/execute", response_model=ActionExecuteResponse)
async def execute_action(
    action_id: str,
    current_user_id: CurrentUserId,
    db: DB,
) -> ActionExecuteResponse:
    """Execute an action through its channel (currently mock).

    Real integrations (LinkedIn via extension, email service) will
    be connected in future phases.
    """
    executor = ActionExecutor(db)
    result = await executor.execute_action(action_id, current_user_id)
    await db.commit()

    return ActionExecuteResponse(
        success=result.get("success", False),
        channel=result.get("channel", ""),
        mock=result.get("mock", True),
        message=result.get("message", ""),
        action_id=action_id,
    )
