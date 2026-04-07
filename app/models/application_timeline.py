"""
app/models/application_timeline.py

Timeline events for the Application Tracker CRM.

Every meaningful interaction is recorded:
  - applied, recruiter_contact, phone_screen, interview_round_1/2/3,
    technical, onsite, offer, rejection, withdrawal, follow_up, note

Each event can have a contact person and a next-action date
for the follow-up reminder system.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class ApplicationTimeline(Base, UUIDMixin, TimestampMixin):
    """One event in an application's timeline."""
    __tablename__ = "application_timeline"

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Event data ────────────────────────────────────────────────────────
    event_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="applied | recruiter_contact | phone_screen | interview | technical | onsite | offer | rejection | withdrawal | follow_up | note",
    )
    event_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="When this event occurred or is scheduled",
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # ── Contact tracking ──────────────────────────────────────────────────
    contact_person: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Recruiter, hiring manager, interviewer name",
    )
    contact_email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    contact_role: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Their title at the company",
    )

    # ── Follow-up ─────────────────────────────────────────────────────────
    next_action: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Suggested or user-entered next step",
    )
    next_action_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When to follow up — drives the reminder system",
    )
    follow_up_sent: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
        server_default="false",
        comment="Whether the reminder was already sent",
    )

    # ── Source linking ────────────────────────────────────────────────────
    source: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="manual | email | calendar | linkedin",
    )
    source_ref: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="External reference: email message_id, calendar event_id, etc.",
    )

    def __repr__(self) -> str:
        return (
            f"<ApplicationTimeline id={self.id} "
            f"type={self.event_type} app={self.application_id}>"
        )
