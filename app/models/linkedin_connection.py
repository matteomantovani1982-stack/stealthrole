"""
app/models/linkedin_connection.py

LinkedIn connection imported via browser extension.

The extension scrapes the user's LinkedIn connections page and pushes
structured data to the backend. We detect recruiters, match connections
to target companies, and surface warm intros in the Relationship Engine.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class LinkedInConnection(Base, UUIDMixin, TimestampMixin):
    """One LinkedIn connection belonging to a user."""
    __tablename__ = "linkedin_connections"

    user_id: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True,
    )

    # ── Profile data (from extension scrape) ──────────────────────────────
    linkedin_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        comment="LinkedIn member URN or vanity URL slug",
    )
    linkedin_url: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
    )
    full_name: Mapped[str] = mapped_column(
        String(255), nullable=False,
    )
    headline: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
        comment="LinkedIn headline text",
    )
    current_title: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
    )
    current_company: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
    )
    location: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
    )
    profile_image_url: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
    )
    connected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="When the LinkedIn connection was established",
    )

    # ── Classification ────────────────────────────────────────────────────
    is_recruiter: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false",
        comment="Detected as recruiter/talent/HR based on title keywords",
    )
    is_hiring_manager: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false",
        comment="Detected as potential hiring manager (Director+)",
    )
    relationship_strength: Mapped[str | None] = mapped_column(
        String(20), nullable=True,
        comment="strong | medium | weak — based on interaction signals",
    )
    tags: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment='User or auto-assigned tags: ["recruiter", "fintech", "warm_intro"]',
    )

    # ── Company matching ──────────────────────────────────────────────────
    matched_application_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="SET NULL"),
        nullable=True, index=True,
        comment="Linked to an application at the same company",
    )

    def __repr__(self) -> str:
        return (
            f"<LinkedInConnection id={self.id} "
            f"name={self.full_name!r} company={self.current_company}>"
        )
