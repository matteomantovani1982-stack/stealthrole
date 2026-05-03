"""
app/models/shadow_application.py

Shadow Application — approach companies BEFORE jobs exist.

A ShadowApplication is generated from a Hidden Market signal or
OpportunityRadar opportunity. It contains:
  - A hiring hypothesis (why this company likely needs this role)
  - A tailored CV (edited via the existing edit_plan pipeline)
  - A strategy memo (positioning + approach)
  - Outreach messages (LinkedIn + email + follow-up)

Lifecycle:
  GENERATING → COMPLETED
                   ↓
                FAILED
"""

import uuid
from enum import StrEnum

from sqlalchemy import Float, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class ShadowStatus(StrEnum):
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class ShadowApplication(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "shadow_applications"

    # ── Owner ────────────────────────────────────────────────────────────
    user_id: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True,
    )
    profile_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True,
    )
    cv_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True,
    )

    # ── Signal context ───────────────────────────────────────────────────
    company: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True,
    )
    signal_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
    )
    signal_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    hidden_signal_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True,
    )
    radar_opportunity_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
    )
    radar_score: Mapped[int | None] = mapped_column(nullable=True)

    # ── Generated outputs ────────────────────────────────────────────────
    hypothesis_role: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
    )
    hiring_hypothesis: Mapped[str | None] = mapped_column(Text, nullable=True)
    strategy_memo: Mapped[str | None] = mapped_column(Text, nullable=True)
    outreach_linkedin: Mapped[str | None] = mapped_column(Text, nullable=True)
    outreach_email: Mapped[str | None] = mapped_column(Text, nullable=True)
    outreach_followup: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Tailored CV ──────────────────────────────────────────────────────
    tailored_cv_s3_key: Mapped[str | None] = mapped_column(
        String(1000), nullable=True,
    )
    tailored_cv_s3_bucket: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
    )

    # ── Scoring ──────────────────────────────────────────────────────────
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Lifecycle ────────────────────────────────────────────────────────
    status: Mapped[ShadowStatus] = mapped_column(
        String(20),
        nullable=False,
        default=ShadowStatus.GENERATING,
        server_default=ShadowStatus.GENERATING,
        index=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
    )

    # ── User tracking ────────────────────────────────────────────────────
    pipeline_stage: Mapped[str | None] = mapped_column(
        String(20), nullable=True, default="created",
    )
    pipeline_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<ShadowApplication id={self.id} company={self.company} "
            f"status={self.status}>"
        )

    @property
    def is_terminal(self) -> bool:
        return self.status in (ShadowStatus.COMPLETED, ShadowStatus.FAILED)
