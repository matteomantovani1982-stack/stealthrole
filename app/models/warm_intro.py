"""
app/models/warm_intro.py

Tracks the outreach pipeline for warm introductions.

Flow:
  identified → outreach_drafted → requested → introduced → converted
                                      ↘ declined

Each WarmIntro links a LinkedIn connection to an application,
tracking the intro request lifecycle.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class IntroStatus(StrEnum):
    IDENTIFIED = "identified"           # Connection found at target company
    OUTREACH_DRAFTED = "outreach_drafted"  # Intro request message generated
    REQUESTED = "requested"             # Message sent to connection
    INTRODUCED = "introduced"           # Connection made the intro
    DECLINED = "declined"               # Connection declined or no response
    CONVERTED = "converted"             # Intro led to interview/progress


class WarmIntro(Base, UUIDMixin, TimestampMixin):
    """One warm introduction attempt via a LinkedIn connection."""
    __tablename__ = "warm_intros"

    user_id: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True,
    )

    # ── Who ───────────────────────────────────────────────────────────────
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("linkedin_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="The connection being asked for an intro",
    )
    application_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="The application this intro is for",
    )

    # ── Target ────────────────────────────────────────────────────────────
    target_company: Mapped[str] = mapped_column(
        String(255), nullable=False,
    )
    target_role: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
    )
    target_person: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        comment="Specific person at the company to be introduced to (if known)",
    )

    # ── Pipeline ──────────────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(30), nullable=False,
        default=IntroStatus.IDENTIFIED,
        server_default=IntroStatus.IDENTIFIED,
        index=True,
    )

    # ── Outreach content ──────────────────────────────────────────────────
    outreach_message: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="The generated or user-edited intro request message",
    )
    response_message: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Connection's response (if any)",
    )
    notes: Mapped[str | None] = mapped_column(
        Text, nullable=True,
    )

    # ── Timestamps ────────────────────────────────────────────────────────
    requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # ── Relationship context ──────────────────────────────────────────────
    relationship_context: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
        comment="How user knows this connection: ex-colleague, alumni, mutual contact, etc.",
    )
    intro_angle: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
        comment="Why this person is the right intro path",
    )

    def __repr__(self) -> str:
        return (
            f"<WarmIntro id={self.id} "
            f"company={self.target_company} status={self.status}>"
        )
