"""
app/models/email_intelligence.py

Full Email Intelligence — 5-year deep scan results.

Stores the output of a deep email analysis:
  - Reconstructed application timelines
  - Behavioral patterns (best times, industries, response rates)
  - Success/failure analysis
  - Career trajectory insights

One record per user per scan. New scans replace the old one.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class EmailIntelligence(Base, UUIDMixin, TimestampMixin):
    """Results of a deep email intelligence scan."""
    __tablename__ = "email_intelligence"

    user_id: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True,
    )

    # ── Scan metadata ─────────────────────────────────────────────────────
    scan_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="pending",
        server_default="pending",
        comment="pending | scanning | analyzing | completed | failed",
    )
    scan_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    scan_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    scan_period_years: Mapped[int] = mapped_column(
        Integer, nullable=False, default=5,
        comment="How many years back the scan covered",
    )
    total_emails_scanned: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
    )
    job_emails_found: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
    )
    applications_reconstructed: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Reconstructed timeline ────────────────────────────────────────────
    # List of {company, role, stage, date, source_email_subject}
    reconstructed_timeline: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment="Chronological list of all detected applications from email history",
    )

    # ── Behavioral patterns ───────────────────────────────────────────────
    patterns: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment="Detected patterns: response_rates, timing, industry_focus, etc.",
    )
    # Schema:
    # {
    #   "avg_response_days": 5.2,
    #   "response_rate_pct": 32.1,
    #   "best_day_to_apply": "Tuesday",
    #   "best_time_to_apply": "morning",
    #   "avg_interviews_per_app": 0.28,
    #   "rejection_stage_distribution": {"applied": 60, "interview": 30, "offer": 10},
    #   "longest_process_days": 45,
    #   "fastest_offer_days": 8,
    # }

    # ── Industry breakdown ────────────────────────────────────────────────
    industry_breakdown: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment='{"fintech": {"applied": 15, "interviewed": 5, "offers": 1}, ...}',
    )

    # ── Writing style profile ─────────────────────────────────────────────
    writing_style: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment="Extracted writing style from outgoing emails for personalized outreach",
    )
    # Schema:
    # {
    #   "formality": "professional",       # casual | professional | formal
    #   "avg_sentence_length": 14.2,
    #   "avg_word_length": 5.1,
    #   "vocabulary_level": "advanced",     # basic | intermediate | advanced
    #   "tone": "confident",               # tentative | neutral | confident | assertive
    #   "greeting_style": "Hi [Name],",
    #   "closing_style": "Best regards,",
    #   "uses_emoji": false,
    #   "common_phrases": ["looking forward to", "happy to discuss", ...],
    #   "sample_sentences": ["I'd love to explore...", ...],  # 5 representative sentences
    # }

    # ── Success/failure insights ──────────────────────────────────────────
    insights: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment="AI-generated behavioral insights and recommendations",
    )
    # Schema:
    # {
    #   "strengths": ["Strong in fintech interviews", ...],
    #   "weaknesses": ["Low response rate from enterprise companies", ...],
    #   "recommendations": ["Focus on mid-stage startups where you convert best", ...],
    #   "career_trajectory": "Transitioning from consulting to tech product roles",
    # }

    def __repr__(self) -> str:
        return (
            f"<EmailIntelligence user={self.user_id} "
            f"status={self.scan_status} apps={self.applications_reconstructed}>"
        )
