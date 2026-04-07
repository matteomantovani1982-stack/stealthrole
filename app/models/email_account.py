"""
app/models/email_account.py

Connected email account for inbound scanning.

A user can connect Gmail and/or Outlook accounts via OAuth.
Tokens are encrypted at rest (Fernet).

Sync flow:
  1. User initiates OAuth → callback stores tokens
  2. Celery beat triggers periodic sync (every 30 min)
  3. Sync fetches new emails → extracts job application signals
  4. Signals create/update Application tracker entries
"""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class EmailProvider(StrEnum):
    GMAIL = "gmail"
    OUTLOOK = "outlook"


class SyncStatus(StrEnum):
    IDLE = "idle"
    SYNCING = "syncing"
    FAILED = "failed"


class EmailAccount(Base, UUIDMixin, TimestampMixin):
    """
    A connected email account (Gmail or Outlook).
    OAuth tokens stored encrypted — never in plaintext.
    """
    __tablename__ = "email_accounts"

    user_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="User who connected this account",
    )
    provider: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="gmail | outlook",
    )
    email_address: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="The connected email address",
    )

    # ── OAuth tokens (encrypted with Fernet) ──────────────────────────────
    access_token_encrypted: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Fernet-encrypted OAuth access token",
    )
    refresh_token_encrypted: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Fernet-encrypted OAuth refresh token",
    )
    token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the access token expires",
    )

    # ── Sync state ────────────────────────────────────────────────────────
    sync_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=SyncStatus.IDLE,
        server_default=SyncStatus.IDLE,
        comment="idle | syncing | failed",
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last successful sync timestamp",
    )
    last_sync_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Error message from last failed sync",
    )
    # History ID / delta token for incremental sync
    sync_cursor: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Gmail historyId or Graph deltaLink for incremental sync",
    )
    total_scanned: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Total emails scanned across all syncs",
    )
    total_signals: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Total application signals extracted",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        comment="False = disconnected, skip during sync",
    )
    calendar_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="Whether this account also has calendar read access",
    )

    def __repr__(self) -> str:
        return (
            f"<EmailAccount id={self.id} "
            f"provider={self.provider} "
            f"email={self.email_address}>"
        )
