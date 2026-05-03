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

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
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
        comment="Breakdown by data source (cv, profile, linkedin, email, etc.)",
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

    # ── Hybrid Learning Profile (Signal Intelligence Layer) ──────────────
    learning_profile: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment="Per-user learning state across all dimensions with sample counts",
    )
    # Schema:
    # {
    #   "signal_effectiveness": {
    #     "funding": {"success_rate": 0.42, "sample_count": 12,
    #                 "last_updated": "..."},
    #     "leadership": {"success_rate": 0.28, "sample_count": 5,
    #                    "last_updated": "..."},
    #     ...
    #   },
    #   "contact_type": {
    #     "recruiter": {"response_rate": 0.55, "conversion_rate": 0.18,
    #                   "sample_count": 20, ...},
    #     "hiring_manager": {"response_rate": 0.30, "conversion_rate": 0.40,
    #                        "sample_count": 8, ...},
    #     ...
    #   },
    #   "path_success": {
    #     "warm_intro": {"success_rate": 0.45, "sample_count": 10, ...},
    #     "direct_apply": {"success_rate": 0.12, "sample_count": 30, ...},
    #     ...
    #   },
    #   "timing": {
    #     "best_day": "Tuesday",
    #     "best_time_window": "09:00-11:00",
    #     "pre_post_ratio": 0.65,
    #     ...
    #   },
    #   "overrides": {
    #     "signal_type:funding": true,
    #     "company:CompanyX": true,
    #     ...
    #   }
    # }

    learning_sample_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
        comment="Total tracked outcomes (determines blend weight tier)",
    )

    learning_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="Last time any learning dimension was updated",
    )

    short_term_memory: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment="Last 10 actions with outcomes for fast feedback detection",
    )
    # Schema:
    # [
    #   {
    #     "event_type": "outreach_sent",
    #     "company": "Careem",
    #     "path_type": "warm_intro",
    #     "contact_type": "hiring_manager",
    #     "signal_type": "funding",
    #     "outcome": "reply_received",
    #     "success_score": 0.30,
    #     "timestamp": "2026-05-01T10:00:00Z"
    #   },
    #   ...
    # ]

    def __repr__(self) -> str:
        return (
            f"<UserIntelligence user={self.user_id} "
            f"strength={self.profile_strength}>"
        )
