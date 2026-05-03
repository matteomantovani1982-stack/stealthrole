"""
app/models/propagation_adjustment.py

Global Intelligence Propagation — cross-user learning adjustments.

When outcome patterns are detected across multiple users, the system creates
propagation adjustments that modify global weights for signals, companies,
contacts, and paths. Each adjustment follows a 7-day gradual rollout and
can be overridden at the user level.

Dimensions tracked:
  - signal_type: effectiveness of each signal type
  - company: company-level responsiveness
  - contact_type: contact type effectiveness
  - path_type: success rate per application path
  - combo: signal_type + path_type combination effectiveness
  - rule: interpretation rule accuracy

Adjustment types:
  - downgrade: reduce weight/priority (e.g., -50%)
  - upgrade: increase weight/priority (e.g., +30%)
  - suppress: remove from recommendation candidates
  - deactivate: disable an interpretation rule
  - promote: mark as "recommended" path/signal
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class PropagationAdjustment(Base, UUIDMixin, TimestampMixin):
    """Global intelligence adjustment applied across all users."""
    __tablename__ = "propagation_adjustments"

    # ── What is being adjusted ────────────────────────────────────────────
    dimension: Mapped[str] = mapped_column(
        String(30), nullable=False, index=True,
        comment="signal_type | company | contact_type | path_type | combo | rule",
    )
    target_key: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True,
        comment="What is adjusted: signal type name, company name, rule_id, etc.",
    )

    # ── Adjustment details ────────────────────────────────────────────────
    adjustment_type: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="downgrade | upgrade | suppress | deactivate | promote",
    )
    adjustment_value: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="Magnitude: e.g., -0.50 = reduce weight by 50%",
    )
    previous_value: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="Value before adjustment (for rollback)",
    )

    # ── Evidence ──────────────────────────────────────────────────────────
    activation_metric: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Metric that triggered the adjustment",
    )
    distinct_users: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="Number of distinct users whose data contributed",
    )
    total_outcomes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="Number of outcomes in the computation",
    )

    # ── Rollout ───────────────────────────────────────────────────────────
    rollout_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="When gradual rollout begins",
    )
    rollout_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="When adjustment reaches full effect (start + 7 days)",
    )
    rollout_progress: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default="0.0",
        comment="0.0–1.0 current rollout progress",
    )

    # ── Lifecycle ─────────────────────────────────────────────────────────
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true",
        comment="False if reversed or superseded",
    )
    reversed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="When the adjustment was rolled back",
    )
    reversal_reason: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Why the adjustment was reversed",
    )

    def __repr__(self) -> str:
        return (
            f"<PropagationAdjustment id={self.id} dim={self.dimension} "
            f"target={self.target_key} type={self.adjustment_type} "
            f"active={self.is_active}>"
        )
