"""
app/models/user_intelligence.py

User Intelligence Engine — aggregated behavioral profile.

Combines signals from all data sources:
  - Application tracker (conversion rates, stage patterns)
  - Interview rounds (pass rates, round types)
  - Email intelligence (response rates, writing style)
  - LinkedIn connections (network strength)
  - Warm intros (conversion pipeline)

Updated periodically or on-demand. One record per user.
"""

from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class UserIntelligence(Base, UUIDMixin, TimestampMixin):
    """Aggregated intelligence profile for a user."""
    __tablename__ = "user_intelligence"

    user_id: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True,
    )

    # ── Profile strength (0-100) ──────────────────────────────────────────
    profile_strength: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
        comment="Overall profile completeness + quality score",
    )
    strength_breakdown: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment='{"cv": 80, "profile": 70, "linkedin": 40, "email": 0, "applications": 60}',
    )

    # ── Behavioral insights ───────────────────────────────────────────────
    behavioral_profile: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment="Aggregated behavioral data from all sources",
    )
    # Schema:
    # {
    #   "application_velocity": 3.5,       # apps per week
    #   "avg_time_in_stage": {"applied": 5, "interview": 12},
    #   "follow_up_rate": 0.6,             # % of applications with follow-up
    #   "networking_active": true,
    #   "preferred_channels": ["linkedin", "referral"],
    #   "peak_activity_day": "Tuesday",
    #   "writing_style_summary": "Professional, confident tone",
    # }

    # ── Success patterns ──────────────────────────────────────────────────
    success_patterns: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
    )
    # Schema:
    # {
    #   "best_industries": ["fintech", "saas"],
    #   "best_company_size": "50-200",
    #   "best_source_channel": "referral",
    #   "interview_pass_rate": 0.65,
    #   "offer_rate": 0.12,
    #   "strongest_round_type": "behavioral",
    #   "avg_salary_achieved": 150000,
    # }

    # ── Failure patterns ──────────────────────────────────────────────────
    failure_patterns: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
    )
    # Schema:
    # {
    #   "worst_industries": ["enterprise"],
    #   "common_rejection_stage": "technical",
    #   "ghosted_rate": 0.35,
    #   "weak_areas": ["system design", "case studies"],
    #   "low_response_channels": ["job_board"],
    # }

    # ── Recommendations ───────────────────────────────────────────────────
    recommendations: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment="Actionable recommendations based on all intelligence",
    )

    def __repr__(self) -> str:
        return f"<UserIntelligence user={self.user_id} strength={self.profile_strength}>"
