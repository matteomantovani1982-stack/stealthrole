"""
app/models/action_recommendation.py

Action Recommendation — a concrete, prioritised step the user should take
to act on a signal-driven opportunity.

Lifecycle:
  generated → queued → sent → responded
  generated → expired  (TTL passed without action)
  generated → dismissed (user chose not to act)

Each recommendation is linked to the signal that triggered it and
optionally to the interpretation + decision score that shaped it.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class ActionRecommendation(Base, UUIDMixin, TimestampMixin):
    """A single recommended action derived from the intelligence pipeline."""
    __tablename__ = "action_recommendations"

    # ── Owner ────────────────────────────────────────────────────────────
    user_id: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True,
    )

    # ── Source links ─────────────────────────────────────────────────────
    signal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True,
        comment="FK to hidden_signals.id — the trigger signal",
    )
    interpretation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True,
        comment="FK to signal_interpretations.id (if one exists)",
    )

    # ── Action type ──────────────────────────────────────────────────────
    action_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True,
        comment="linkedin_message | email_outreach | "
        "referral_request | follow_up_sequence",
    )

    # ── Target ───────────────────────────────────────────────────────────
    target_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        comment="Name of the person/entity to reach out to",
    )
    target_title: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        comment="Title of the target contact (e.g. VP Engineering)",
    )
    target_company: Mapped[str] = mapped_column(
        String(255), nullable=False,
        comment="Company name for this action",
    )

    # ── Content ──────────────────────────────────────────────────────────
    reason: Mapped[str] = mapped_column(
        Text, nullable=False,
        comment="Why now — human-readable justification",
    )
    message_subject: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
        comment="Subject line for email outreach",
    )
    message_body: Mapped[str] = mapped_column(
        Text, nullable=False,
        comment="Structured message content (LLM-generated)",
    )

    # ── Timing ───────────────────────────────────────────────────────────
    timing_label: Mapped[str] = mapped_column(
        String(50), nullable=False, default="this_week",
        comment="immediate | today | this_week | next_week | flexible",
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="After this date, action is no longer relevant",
    )

    # ── Scoring ──────────────────────────────────────────────────────────
    confidence: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.5,
        comment="Action confidence score 0.0–1.0",
    )
    priority: Mapped[int] = mapped_column(
        Integer, nullable=False, default=50,
        comment="Priority rank 1-100 (lower = higher priority)",
    )
    decision_score: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="Composite decision score that generated this action",
    )

    # ── Lifecycle ────────────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="generated", index=True,
        comment="generated | queued | sent | responded | expired | dismissed",
    )
    queued_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # ── Execution metadata ───────────────────────────────────────────────
    channel_metadata: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, default=dict, server_default="{}",
        comment="Channel-specific data: linkedin_profile_url, email_address, etc.",
    )
    response_data: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, default=dict, server_default="{}",
        comment="Outcome data: reply text, meeting scheduled, etc.",
    )

    # ── Flags ────────────────────────────────────────────────────────────
    is_user_edited: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false",
        comment="Whether user modified the generated message",
    )

    def __repr__(self) -> str:
        return (
            f"<ActionRecommendation id={self.id} type={self.action_type} "
            f"status={self.status} company={self.target_company}>"
        )
