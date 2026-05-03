"""
app/models/signal_interpretation.py

Signal Interpretation Layer — structured business analysis of market signals.

Sits between the quality filter and the prediction engine. Transforms a raw
signal ("Company X raised Series B") into a structured business analysis:
  - business_change: what is happening to the business
  - org_impact: what organizational changes this implies
  - hiring_reason: why specific roles will be created
  - predicted_roles: array of {role, seniority, confidence, timeline, urgency}
  - hiring_owner_title/dept: who will own the hiring decision

Each interpretation is produced by a versioned rule (rule_id + rule_version),
enabling accuracy tracking and A/B testing of rule variants.
"""

import uuid

from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class SignalInterpretation(Base, UUIDMixin, TimestampMixin):
    """Structured business interpretation of a market signal."""
    __tablename__ = "signal_interpretations"

    # ── Source signal link ────────────────────────────────────────────────
    signal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True,
        comment="FK to hidden_signals.id — the signal that was interpreted",
    )
    user_id: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True,
        comment="User context — relevance was scored against this user",
    )

    # ── Rule provenance ───────────────────────────────────────────────────
    rule_id: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True,
        comment="Interpretation rule identifier, e.g. FUND_SERIES_B_v2",
    )
    rule_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1,
        comment="Version of the rule at time of interpretation",
    )

    # ── Signal classification ─────────────────────────────────────────────
    trigger_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="funding | leadership | expansion | regulatory | competitive | "
        "technology | lifecycle",
    )
    trigger_subtype: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
        comment="Specific event: series_b | ceo_departure | new_market | etc.",
    )

    # ── Interpretation output ─────────────────────────────────────────────
    business_change: Mapped[str] = mapped_column(
        Text, nullable=False,
        comment="What is changing for the business (human-readable)",
    )
    org_impact: Mapped[str] = mapped_column(
        Text, nullable=False,
        comment="What organizational changes this implies (human-readable)",
    )
    hiring_reason: Mapped[str] = mapped_column(
        Text, nullable=False,
        comment="Why specific roles will be created (human-readable)",
    )

    # ── Predicted roles ───────────────────────────────────────────────────
    predicted_roles: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]",
        comment="Array of {role, seniority, confidence, timeline, urgency}",
    )
    # Schema:
    # [
    #   {
    #     "role": "VP Operations",
    #     "seniority": "vp",
    #     "confidence": 0.80,
    #     "timeline": "1_3_months",
    #     "urgency": "imminent"
    #   },
    #   ...
    # ]

    # ── Hiring owner ──────────────────────────────────────────────────────
    hiring_owner_title: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        comment="Predicted hiring decision-maker title, e.g. CEO",
    )
    hiring_owner_dept: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
        comment="Department: operations | engineering | finance | legal | etc.",
    )

    # ── Scores ────────────────────────────────────────────────────────────
    quality_score: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="Signal quality score at time of interpretation (0.0–1.0)",
    )
    interpretation_confidence: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="Rule match confidence — keyword overlap ratio (0.0–1.0)",
    )

    def __repr__(self) -> str:
        return (
            f"<SignalInterpretation id={self.id} rule={self.rule_id} "
            f"trigger={self.trigger_type}/{self.trigger_subtype}>"
        )
