"""
app/models/auto_apply.py

Auto-Apply Engine models.

AutoApplyProfile: stored user field mappings for ATS form filling.
AutoApplySubmission: tracks each auto-apply attempt and its outcome.

Flow:
  1. User triggers auto-apply from dashboard or WhatsApp
  2. Backend generates form payload from profile + CV + JD
  3. Browser extension fills the ATS form
  4. Extension reports back success/failure
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class ATSPlatform(StrEnum):
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    WORKABLE = "workable"
    ASHBY = "ashby"
    ICIMS = "icims"
    WORKDAY = "workday"
    SMARTRECRUITERS = "smartrecruiters"
    OTHER = "other"


class SubmissionStatus(StrEnum):
    PREPARED = "prepared"       # Form payload generated, not yet submitted
    SUBMITTING = "submitting"   # Extension is filling the form
    SUBMITTED = "submitted"     # Extension confirmed form submitted
    FAILED = "failed"           # Form fill or submission failed
    DUPLICATE = "duplicate"     # Already applied to this job


class AutoApplyProfile(Base, UUIDMixin, TimestampMixin):
    """
    User's stored answers to common ATS form fields.
    Pre-filled once, reused across all applications.
    """
    __tablename__ = "auto_apply_profiles"

    user_id: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True,
    )

    # ── Standard fields (pre-filled from user profile) ────────────────────
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    website_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    current_company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    current_title: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # ── Common ATS questions (stored as JSONB for flexibility) ────────────
    # Schema: {"work_authorization": "yes", "visa_sponsorship": "no",
    #          "salary_expectation": "120000", "start_date": "immediately",
    #          "years_experience": "10", "education_level": "masters", ...}
    standard_answers: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}",
        comment="Pre-filled answers to common ATS questions",
    )

    # ── Cover letter template ─────────────────────────────────────────────
    cover_letter_template: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Default cover letter template — {company} and {role} are substituted",
    )

    def __repr__(self) -> str:
        return f"<AutoApplyProfile user_id={self.user_id}>"


class AutoApplySubmission(Base, UUIDMixin, TimestampMixin):
    """Tracks one auto-apply submission attempt."""
    __tablename__ = "auto_apply_submissions"

    user_id: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True,
    )

    # ── Links ─────────────────────────────────────────────────────────────
    application_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    job_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("job_runs.id", ondelete="SET NULL"),
        nullable=True,
        comment="Optional link to Intelligence Pack if one was generated",
    )

    # ── Target ────────────────────────────────────────────────────────────
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(255), nullable=False)
    apply_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    ats_platform: Mapped[str] = mapped_column(
        String(50), nullable=False, default=ATSPlatform.OTHER,
        comment="Detected ATS: greenhouse | lever | workable | ashby | ...",
    )

    # ── Form data ─────────────────────────────────────────────────────────
    form_payload: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}",
        comment="The form field values sent to the ATS",
    )
    cv_s3_key: Mapped[str | None] = mapped_column(
        String(1000), nullable=True,
        comment="S3 key for the CV/resume attached",
    )

    # ── Status ────────────────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(30), nullable=False,
        default=SubmissionStatus.PREPARED,
        server_default=SubmissionStatus.PREPARED,
        index=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True,
    )
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    def __repr__(self) -> str:
        return (
            f"<AutoApplySubmission id={self.id} "
            f"company={self.company!r} status={self.status}>"
        )
