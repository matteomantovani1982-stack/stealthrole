"""
app/models/calendar_event.py

Synced calendar events from Google Calendar / Outlook.

Only interview-related events are stored (filtered during sync).
Linked to an Application when a match is found.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class CalendarEvent(Base, UUIDMixin, TimestampMixin):
    """A synced calendar event detected as interview-related."""
    __tablename__ = "calendar_events"

    # ── Owner ─────────────────────────────────────────────────────────────
    user_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    email_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("email_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Calendar access uses the same OAuth as email",
    )

    # ── Event data ────────────────────────────────────────────────────────
    provider_event_id: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Google Calendar eventId or Outlook event id — for dedup",
    )
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    end_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    location: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Meeting link or physical location",
    )
    organizer_email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    attendees: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Comma-separated attendee emails",
    )

    # ── Extracted data ────────────────────────────────────────────────────
    detected_company: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Company name extracted from event title/organizer",
    )
    detected_role: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Role extracted from event title/description",
    )
    interview_round: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Detected round: phone_screen | round_1 | round_2 | technical | onsite | final",
    )

    # ── Link to Application tracker ───────────────────────────────────────
    application_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    is_dismissed: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
        server_default="false",
    )

    def __repr__(self) -> str:
        return (
            f"<CalendarEvent id={self.id} "
            f"title={self.title!r} company={self.detected_company}>"
        )
