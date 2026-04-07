"""
app/models/interview.py

Interview tracking + compensation benchmarks.

InterviewRound: one round of interviews for an application,
with prep notes, debrief, and questions asked.

CompensationBenchmark: cached salary benchmarks per role/region.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class InterviewRound(Base, UUIDMixin, TimestampMixin):
    """One interview round for an application."""
    __tablename__ = "interview_rounds"

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    user_id: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True,
    )

    # ── Round info ────────────────────────────────────────────────────────
    round_number: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1,
    )
    round_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="phone_screen | technical | behavioral | case_study | onsite | panel | final | hiring_manager",
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    duration_minutes: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
    )

    # ── Interviewer ───────────────────────────────────────────────────────
    interviewer_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
    )
    interviewer_title: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
    )
    interviewer_linkedin: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
    )

    # ── Prep ──────────────────────────────────────────────────────────────
    prep_notes: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="User's preparation notes for this round",
    )
    focus_areas: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment='["system design", "leadership", "culture fit"]',
    )

    # ── Debrief (post-interview) ──────────────────────────────────────────
    debrief: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="How it went — user's notes after the interview",
    )
    questions_asked: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment='["Tell me about a time...", "Design a system..."]',
    )
    confidence_rating: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        comment="1-5 self-assessed confidence after the round",
    )
    outcome: Mapped[str | None] = mapped_column(
        String(30), nullable=True,
        comment="passed | failed | pending | unknown",
    )

    def __repr__(self) -> str:
        return (
            f"<InterviewRound id={self.id} "
            f"type={self.round_type} round={self.round_number}>"
        )


class CompensationBenchmark(Base, UUIDMixin, TimestampMixin):
    """Cached salary benchmark for a role + region combination."""
    __tablename__ = "compensation_benchmarks"

    role_title: Mapped[str] = mapped_column(String(255), nullable=False)
    region: Mapped[str] = mapped_column(String(100), nullable=False)
    seniority_level: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
        comment="junior | mid | senior | lead | director | vp | c_level",
    )
    currency: Mapped[str] = mapped_column(
        String(10), nullable=False, default="USD",
    )
    p25: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="25th percentile salary")
    p50: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="Median salary")
    p75: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="75th percentile salary")
    p90: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="90th percentile salary")
    total_comp_p50: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        comment="Median total compensation (base + bonus + equity)",
    )
    source: Mapped[str | None] = mapped_column(
        String(100), nullable=True,
        comment="Data source: levels.fyi | glassdoor | payscale | manual",
    )
    sample_size: Mapped[int | None] = mapped_column(Integer, nullable=True)

    def __repr__(self) -> str:
        return f"<CompensationBenchmark role={self.role_title} region={self.region}>"
