"""
app/models/application.py

Standalone application tracker for the Kanban board.

Unlike JobRun (which is tied to the CV tailoring pipeline), an Application
is a lightweight record the user creates manually to track where they've
applied, what stage they're at, and through which channel.

Stage flow:
  applied → interview → offer  (happy path)
       ↘      ↘         ↘
        → → rejected → → →     (at any point)
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class ApplicationStage(StrEnum):
    """Kanban columns for the application tracker."""
    WATCHING = "watching"
    APPLIED = "applied"
    INTERVIEW = "interview"
    OFFER = "offer"
    REJECTED = "rejected"


class Application(Base, UUIDMixin, TimestampMixin):
    """
    One tracked job application.

    Designed for manual entry now; auto-fill from email/LinkedIn comes later.
    Links optionally to a JobRun if the user also generated an Intelligence Pack.
    """
    __tablename__ = "applications"

    # ── Owner ──────────────────────────────────────────────────────────────
    user_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="User who owns this application",
    )

    # ── Core fields (shown on each Kanban card) ───────────────────────────
    company: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Company name",
    )
    role: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Job title / role applied for",
    )
    date_applied: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="When the application was submitted",
    )
    source_channel: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="How the user found/applied: linkedin, indeed, referral, company_site, other",
    )

    # ── Kanban stage ──────────────────────────────────────────────────────
    stage: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=ApplicationStage.APPLIED,
        server_default=ApplicationStage.APPLIED,
        index=True,
        comment="Kanban column: applied | interview | offer | rejected",
    )

    # ── Optional detail fields ────────────────────────────────────────────
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Free-form user notes",
    )
    url: Mapped[str | None] = mapped_column(
        String(2000),
        nullable=True,
        comment="Link to the job posting",
    )
    salary: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Salary info (free-text for flexibility)",
    )
    contact_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Recruiter or hiring manager name",
    )
    contact_email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Recruiter or hiring manager email",
    )

    # ── Stage timestamps ──────────────────────────────────────────────────
    interview_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When moved to interview stage",
    )
    offer_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When moved to offer stage",
    )
    rejected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When moved to rejected stage",
    )

    # ── Optional link to JobRun ───────────────────────────────────────────
    job_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("job_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Optional link to a JobRun Intelligence Pack",
    )

    def __repr__(self) -> str:
        return (
            f"<Application id={self.id} "
            f"company={self.company!r} "
            f"role={self.role!r} "
            f"stage={self.stage}>"
        )
