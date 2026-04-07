"""
app/schemas/email_integration.py

Pydantic schemas for Email Integration API.
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Provider = Literal["gmail", "outlook"]


# ── OAuth flow ───────────────────────────────────────────────────────────────

class EmailConnectRequest(BaseModel):
    """Initiate OAuth connection."""
    provider: Provider


class EmailConnectResponse(BaseModel):
    """Returns the OAuth authorization URL to redirect the user to."""
    auth_url: str
    provider: str


class EmailCallbackRequest(BaseModel):
    """OAuth callback after user grants access."""
    provider: Provider
    code: str
    state: str | None = None


# ── Account schemas ──────────────────────────────────────────────────────────

class EmailAccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider: str
    email_address: str
    sync_status: str
    last_synced_at: datetime | None = None
    last_sync_error: str | None = None
    total_scanned: int
    total_signals: int
    is_active: bool
    created_at: datetime


class EmailAccountList(BaseModel):
    accounts: list[EmailAccountResponse]
    total: int


# ── Scan schemas ─────────────────────────────────────────────────────────────

class EmailScanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email_from: str
    email_subject: str
    email_date: datetime
    email_snippet: str | None = None
    company: str | None = None
    role: str | None = None
    detected_stage: str
    confidence: str
    application_id: uuid.UUID | None = None
    is_dismissed: bool
    created_at: datetime


class EmailScanList(BaseModel):
    scans: list[EmailScanResponse]
    total: int
    unlinked: int = Field(description="Scans not yet linked to an application")


class LinkScanRequest(BaseModel):
    """Link a scan to an existing application, or create a new one."""
    application_id: uuid.UUID | None = Field(
        default=None,
        description="Existing application to link to. If null, creates a new Application.",
    )


class DismissScanRequest(BaseModel):
    """Mark a scan as a false positive."""
    is_dismissed: bool = True


# ── Sync trigger ─────────────────────────────────────────────────────────────

class SyncResponse(BaseModel):
    message: str
    account_id: uuid.UUID
    task_id: str | None = None
