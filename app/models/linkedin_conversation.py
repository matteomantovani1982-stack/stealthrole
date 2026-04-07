"""
app/models/linkedin_conversation.py

LinkedIn conversation/message thread captured by the browser extension.

Tracks message exchanges with recruiters and contacts.
Links to a connection and optionally to an application.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class LinkedInConversation(Base, UUIDMixin, TimestampMixin):
    """One message in a LinkedIn conversation thread."""
    __tablename__ = "linkedin_conversations"

    user_id: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True,
    )

    # ── Link to connection ────────────────────────────────────────────────
    connection_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("linkedin_connections.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    # ── Message data ──────────────────────────────────────────────────────
    thread_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        comment="LinkedIn conversation thread ID for grouping",
    )
    direction: Mapped[str] = mapped_column(
        String(10), nullable=False,
        comment="inbound | outbound",
    )
    sender_name: Mapped[str] = mapped_column(
        String(255), nullable=False,
    )
    message_text: Mapped[str] = mapped_column(
        Text, nullable=False,
    )
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )

    # ── Link to application ───────────────────────────────────────────────
    application_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="SET NULL"),
        nullable=True, index=True,
        comment="Linked to an application if conversation is job-related",
    )

    def __repr__(self) -> str:
        return (
            f"<LinkedInConversation id={self.id} "
            f"direction={self.direction} sender={self.sender_name!r}>"
        )
