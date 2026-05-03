"""
app/services/action/action_executor.py

Action Executor — manages the lifecycle of action recommendations
from generation through execution and response tracking.

Lifecycle states
----------------
  generated  — action created by ActionGenerator
  queued     — user approved / scheduled for delivery
  sent       — delivered through channel (LinkedIn, email, etc.)
  responded  — target replied or meeting booked
  expired    — TTL passed without user action
  dismissed  — user chose not to act

Execution hooks (mock for now)
------------------------------
  send_linkedin_message()  — placeholder for extension integration
  send_email()             — placeholder for email service integration

These will be connected to real channels in later phases
(Chrome extension for LinkedIn, email service for outreach).

Usage
-----
    executor = ActionExecutor(db)

    # Persist generated actions
    records = await executor.persist_actions(actions, user_id, signal_id)

    # Move through lifecycle
    await executor.queue_action(action_id, user_id)
    await executor.mark_sent(action_id, user_id)
    await executor.mark_responded(action_id, user_id, response_data)

    # Mock execution
    result = await executor.execute_action(action_id, user_id)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select, update

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

from app.models.action_recommendation import ActionRecommendation
from app.services.action.action_generator import GeneratedAction

logger = structlog.get_logger(__name__)

# ── Valid lifecycle transitions ──────────────────────────────────────
_VALID_TRANSITIONS: dict[str, set[str]] = {
    "generated": {"queued", "dismissed", "expired"},
    "queued": {"sent", "dismissed", "expired"},
    "sent": {"responded", "expired"},
    "responded": set(),  # terminal
    "expired": set(),     # terminal
    "dismissed": set(),   # terminal
}


class ActionExecutor:
    """Manages action persistence, lifecycle, and (mock) execution."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Persistence ──────────────────────────────────────────────────

    async def persist_actions(
        self,
        actions: list[GeneratedAction],
        user_id: str,
        signal_id: uuid.UUID,
        interpretation_id: uuid.UUID | None = None,
    ) -> list[ActionRecommendation]:
        """Save generated actions to the database.

        Returns the created ActionRecommendation ORM instances.
        """
        records: list[ActionRecommendation] = []

        for action in actions:
            record = ActionRecommendation(
                user_id=user_id,
                signal_id=signal_id,
                interpretation_id=interpretation_id,
                action_type=action.action_type,
                target_name=action.target_name or "",
                target_title=action.target_title or "",
                target_company=action.target_company,
                reason=action.reason,
                message_subject=action.message_subject,
                message_body=action.message_body,
                timing_label=action.timing_label,
                expires_at=action.expires_at,
                confidence=action.confidence,
                priority=action.priority,
                decision_score=action.decision_score,
                status="generated",
                channel_metadata=action.channel_metadata or {},
            )
            self._db.add(record)
            records.append(record)

        await self._db.flush()

        logger.info(
            "actions_persisted",
            user_id=user_id,
            signal_id=str(signal_id),
            count=len(records),
        )
        return records

    # ── Lifecycle management ─────────────────────────────────────────

    async def _transition(
        self,
        action_id: str,
        user_id: str,
        new_status: str,
        **extra_fields: object,
    ) -> ActionRecommendation | None:
        """Move an action to a new lifecycle state.

        Validates the transition is legal and updates timestamp fields.
        """
        record = await self._load_action(action_id, user_id)
        if not record:
            return None

        valid_next = _VALID_TRANSITIONS.get(record.status, set())
        if new_status not in valid_next:
            logger.warning(
                "invalid_action_transition",
                action_id=action_id,
                current=record.status,
                attempted=new_status,
            )
            return None

        record.status = new_status

        # Set timestamp for the new state
        now = datetime.now(timezone.utc)
        if new_status == "queued":
            record.queued_at = now
        elif new_status == "sent":
            record.sent_at = now
        elif new_status == "responded":
            record.responded_at = now

        # Apply any extra fields
        for key, value in extra_fields.items():
            if hasattr(record, key):
                setattr(record, key, value)

        await self._db.flush()

        logger.info(
            "action_transitioned",
            action_id=action_id,
            new_status=new_status,
        )
        return record

    async def queue_action(
        self,
        action_id: str,
        user_id: str,
    ) -> ActionRecommendation | None:
        """Mark action as queued for delivery."""
        return await self._transition(action_id, user_id, "queued")

    async def mark_sent(
        self,
        action_id: str,
        user_id: str,
    ) -> ActionRecommendation | None:
        """Mark action as sent/delivered."""
        return await self._transition(action_id, user_id, "sent")

    async def mark_responded(
        self,
        action_id: str,
        user_id: str,
        response_data: dict | None = None,
    ) -> ActionRecommendation | None:
        """Mark action as responded to."""
        return await self._transition(
            action_id, user_id, "responded",
            response_data=response_data or {},
        )

    async def dismiss_action(
        self,
        action_id: str,
        user_id: str,
    ) -> ActionRecommendation | None:
        """User dismissed this action."""
        return await self._transition(action_id, user_id, "dismissed")

    async def expire_stale_actions(
        self,
        user_id: str | None = None,
    ) -> int:
        """Expire actions past their expires_at date.

        Returns count of expired actions.
        """
        now = datetime.now(timezone.utc)
        q = (
            update(ActionRecommendation)
            .where(
                ActionRecommendation.status.in_(["generated", "queued"]),
                ActionRecommendation.expires_at.isnot(None),
                ActionRecommendation.expires_at < now,
            )
            .values(status="expired")
        )
        if user_id:
            q = q.where(ActionRecommendation.user_id == user_id)

        result = await self._db.execute(q)
        count = result.rowcount  # type: ignore[union-attr]
        if count > 0:
            logger.info("actions_expired", count=count, user_id=user_id)
        return count

    # ── Mock execution hooks ─────────────────────────────────────────

    async def execute_action(
        self,
        action_id: str,
        user_id: str,
    ) -> dict:
        """Execute an action through the appropriate channel.

        Currently returns mock results. Real integrations
        (LinkedIn API via extension, email service) will be
        connected in future phases.
        """
        record = await self._load_action(action_id, user_id)
        if not record:
            return {"success": False, "error": "Action not found"}

        if record.status not in ("generated", "queued"):
            return {
                "success": False,
                "error": f"Cannot execute action in '{record.status}' state",
            }

        action_type = record.action_type
        result: dict

        if action_type == "linkedin_message":
            result = await self._send_linkedin_message(record)
        elif action_type == "email_outreach":
            result = await self._send_email(record)
        elif action_type == "referral_request":
            result = await self._send_referral_request(record)
        elif action_type == "follow_up_sequence":
            result = await self._start_follow_up(record)
        else:
            result = {"success": False, "error": f"Unknown action type: {action_type}"}

        if result.get("success"):
            record.status = "sent"
            record.sent_at = datetime.now(timezone.utc)
            await self._db.flush()

        return result

    # ── Channel stubs ────────────────────────────────────────────────

    @staticmethod
    async def _send_linkedin_message(
        record: ActionRecommendation,
    ) -> dict:
        """Mock LinkedIn message send.

        Will be replaced with Chrome extension bridge in Phase 4.
        """
        logger.info(
            "mock_linkedin_send",
            action_id=str(record.id),
            company=record.target_company,
        )
        return {
            "success": True,
            "channel": "linkedin",
            "mock": True,
            "message": "LinkedIn message queued (mock — extension integration pending)",
        }

    @staticmethod
    async def _send_email(
        record: ActionRecommendation,
    ) -> dict:
        """Mock email send.

        Will be connected to email service in a future phase.
        """
        logger.info(
            "mock_email_send",
            action_id=str(record.id),
            company=record.target_company,
        )
        return {
            "success": True,
            "channel": "email",
            "mock": True,
            "message": "Email queued (mock — email service integration pending)",
        }

    @staticmethod
    async def _send_referral_request(
        record: ActionRecommendation,
    ) -> dict:
        """Mock referral request."""
        logger.info(
            "mock_referral_send",
            action_id=str(record.id),
            company=record.target_company,
        )
        return {
            "success": True,
            "channel": "referral",
            "mock": True,
            "message": "Referral request created (mock — awaiting connection mapping)",
        }

    @staticmethod
    async def _start_follow_up(
        record: ActionRecommendation,
    ) -> dict:
        """Mock follow-up sequence start."""
        logger.info(
            "mock_followup_start",
            action_id=str(record.id),
            company=record.target_company,
        )
        return {
            "success": True,
            "channel": "multi_channel",
            "mock": True,
            "message": (
                "Follow-up sequence initiated "
                "(mock — scheduler integration pending)"
            ),
        }

    # ── Query helpers ────────────────────────────────────────────────

    async def _load_action(
        self,
        action_id: str,
        user_id: str,
    ) -> ActionRecommendation | None:
        """Load a single action ensuring it belongs to the user."""
        q = select(ActionRecommendation).where(
            ActionRecommendation.id == action_id,
            ActionRecommendation.user_id == user_id,
        )
        result = await self._db.execute(q)
        return result.scalar_one_or_none()

    async def get_user_actions(
        self,
        user_id: str,
        *,
        status_filter: str | None = None,
        limit: int = 50,
    ) -> list[ActionRecommendation]:
        """Fetch actions for a user, optionally filtered by status."""
        q = (
            select(ActionRecommendation)
            .where(ActionRecommendation.user_id == user_id)
            .order_by(
                ActionRecommendation.priority.asc(),
                ActionRecommendation.confidence.desc(),
            )
            .limit(limit)
        )
        if status_filter:
            q = q.where(ActionRecommendation.status == status_filter)

        result = await self._db.execute(q)
        return list(result.scalars().all())

    async def get_top_actions(
        self,
        user_id: str,
        limit: int = 10,
    ) -> list[ActionRecommendation]:
        """Fetch the top N actionable recommendations.

        Filters for generated/queued status only (actionable).
        """
        return await self.get_user_actions(
            user_id,
            status_filter=None,
            limit=limit,
        )
