"""
app/schemas/linkedin.py

Pydantic schemas for LinkedIn integration API.
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# ── Extension ingest ──────────────────────────────────────────────────────────

class LinkedInConnectionInput(BaseModel):
    """One connection from the browser extension."""
    linkedin_id: str | None = None
    linkedin_url: str | None = None
    full_name: str = Field(..., min_length=1, max_length=255)
    headline: str | None = Field(default=None, max_length=500)
    current_title: str | None = Field(default=None, max_length=255)
    current_company: str | None = Field(default=None, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    profile_image_url: str | None = None
    connected_at: str | None = None


class IngestConnectionsRequest(BaseModel):
    """Bulk push from the browser extension."""
    connections: list[LinkedInConnectionInput] = Field(..., max_length=500)


class IngestConnectionsResponse(BaseModel):
    created: int
    updated: int
    total_processed: int
    recruiters_detected: int
    applications_matched: int


class LinkedInMessageInput(BaseModel):
    """One message from the browser extension."""
    thread_id: str | None = None
    linkedin_id: str | None = None
    direction: Literal["inbound", "outbound"] = "inbound"
    sender_name: str = Field(..., max_length=255)
    message_text: str = Field(..., max_length=10000)
    sent_at: str | None = None


class IngestConversationsRequest(BaseModel):
    messages: list[LinkedInMessageInput] = Field(..., max_length=200)


# ── Response schemas ──────────────────────────────────────────────────────────

class ConnectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    linkedin_id: str | None = None
    linkedin_url: str | None = None
    full_name: str
    headline: str | None = None
    current_title: str | None = None
    current_company: str | None = None
    location: str | None = None
    is_recruiter: bool
    is_hiring_manager: bool
    relationship_strength: str | None = None
    tags: dict | None = None
    matched_application_id: uuid.UUID | None = None
    created_at: datetime


class ConnectionListResponse(BaseModel):
    connections: list[ConnectionResponse]
    total: int


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    connection_id: uuid.UUID | None = None
    thread_id: str | None = None
    direction: str
    sender_name: str
    message_text: str
    sent_at: datetime
    application_id: uuid.UUID | None = None
    created_at: datetime


class LinkThreadRequest(BaseModel):
    thread_id: str
    application_id: uuid.UUID


class LinkedInStatsResponse(BaseModel):
    total_connections: int
    recruiters: int
    unique_companies: int
