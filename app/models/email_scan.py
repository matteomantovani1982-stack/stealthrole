"""
app/models/email_scan.py

Extracted application signal from a scanned email.

Each EmailScan represents one job-related signal found in an email:
  - Application confirmation ("Thank you for applying...")
  - Interview invite ("We'd like to schedule...")
  - Rejection ("After careful consideration...")
  - Offer ("We're pleased to offer...")

Signals can be auto-linked to Application tracker entries,
or presented to the user for manual confirmation.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class DetectedStage(StrEnum):
    """Stage inferred from the email content."""
    APPLIED = "applied"
    INTERVIEW = "interview"
    OFFER = "offer"
    REJECTED = "rejected"
    UNKNOWN = "unknown"


class ScanConfidence(StrEnum):
    """How confident we are in the extraction."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EmailScan(Base, UUIDMixin, TimestampMixin):
    """
    One application signal extracted from an email.
    May be linked to an Application record or awaiting user confirmation.
    """
    __tablename__ = "email_scans"

    # ── Source ────────────────────────────────────────────────────────────
    email_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("email_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    message_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Provider message ID (Gmail msg id / Graph message id) for dedup",
    )

    # ── Email metadata ────────────────────────────────────────────────────
    email_from: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Sender address",
    )
    email_subject: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
        comment="Email subject line",
    )
    email_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="When the email was sent",
    )
    email_snippet: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="First ~200 chars of email body for context",
    )

    # ── Extracted data ────────────────────────────────────────────────────
    company: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Company name extracted from email",
    )
    role: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Role title extracted from email",
    )
    detected_stage: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=DetectedStage.UNKNOWN,
        comment="Inferred application stage: applied | interview | offer | rejected | unknown",
    )
    confidence: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ScanConfidence.MEDIUM,
        comment="Extraction confidence: high | medium | low",
    )

    # ── Link to Application tracker ───────────────────────────────────────
    application_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Linked Application record (null = unlinked / pending user review)",
    )
    is_dismissed: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
        server_default="false",
        comment="User dismissed this signal (false positive)",
    )

    def __repr__(self) -> str:
        return (
            f"<EmailScan id={self.id} "
            f"company={self.company!r} "
            f"stage={self.detected_stage}>"
        )
