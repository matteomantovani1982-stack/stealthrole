"""
app/models/mutual_connection.py

Stores 2nd-degree connection data: "Person A knows Person B"
Scraped from LinkedIn profile pages by the Chrome extension.

Used by Find My Way In to build real intro paths:
  You → Your Connection (who knows target) → Target Person
"""

from sqlalchemy import String, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class MutualConnection(Base, UUIDMixin, TimestampMixin):
    """Records that a target person has mutual connections with the user's network."""
    __tablename__ = "mutual_connections"

    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # The target person (someone you're NOT directly connected to)
    target_linkedin_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    target_name: Mapped[str] = mapped_column(String(255), nullable=False)
    target_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    target_company: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    target_linkedin_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # The mutual connection (someone you ARE connected to who also knows the target)
    mutual_linkedin_id: Mapped[str] = mapped_column(String(255), nullable=False)
    mutual_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mutual_linkedin_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # How many total mutual connections exist (even if we only scraped some names)
    total_mutual_count: Mapped[int] = mapped_column(Integer, default=0)
