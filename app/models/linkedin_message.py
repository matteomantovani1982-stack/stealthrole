"""
app/models/linkedin_message.py

Conversation-centric LinkedIn message thread captured by the browser extension.
Distinct from the flat `linkedin_conversations` table (which stores individual
messages as rows) — this model stores the full thread as one row with messages
embedded as JSONB, matching Feature 2 of the extension rebuild spec.

Classification/AI-draft columns are populated by a Celery task that's
currently gated by the ENABLE_LINKEDIN_MSG_CLASSIFY env var (default: off)
to avoid burning LLM credits during early testing.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class LinkedInMessage(Base, UUIDMixin, TimestampMixin):
    """One LinkedIn conversation thread with all messages embedded."""
    __tablename__ = "linkedin_messages"

    user_id: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True,
    )

    # LinkedIn's conversation URN, e.g. "urn:li:fsd_conversation:2-abc123"
    # Unique per user — we dedupe incoming sync payloads against this.
    conversation_urn: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True,
    )

    # ── Contact identification ─────────────────────────────────────────────
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_linkedin_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True,
    )
    contact_linkedin_url: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
    )
    contact_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_company: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True,
    )

    # ── Message body ───────────────────────────────────────────────────────
    # JSONB array of {sender, text, sent_at, is_mine} objects.
    # Full conversation history for the thread.
    messages: Mapped[list] = mapped_column(JSONB, nullable=False)
    message_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
    )

    # ── Thread state ───────────────────────────────────────────────────────
    last_message_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True,
    )
    last_sender: Mapped[str | None] = mapped_column(
        String(10), nullable=True,
        comment="me | them — who sent the most recent message",
    )
    is_unread: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false",
    )
    days_since_reply: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        comment="Days since the last inbound message that we haven't replied to",
    )

    # ── Classification (Haiku, currently gated behind feature flag) ────────
    is_job_related: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True,
        comment="NULL = not yet classified. True = show in /inbox default filter.",
    )
    classification: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
        comment="recruiter | opportunity | networking | interview | other",
    )
    stage: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
        comment="initial | replied | interviewing | offer | rejected",
    )
    ai_draft_reply: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Haiku-generated suggested reply — user edits before sending",
    )
    classification_confidence: Mapped[float | None] = mapped_column(
        Float, nullable=True,
    )
    classified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    def __repr__(self) -> str:
        return (
            f"<LinkedInMessage id={self.id} "
            f"contact={self.contact_name!r} msgs={self.message_count}>"
        )
