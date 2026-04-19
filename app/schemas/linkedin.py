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
    skipped: int = 0
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


# ── Feature 2: Messages sync (conversation-centric) ───────────────────────────

class MessageEntry(BaseModel):
    """One message inside a conversation thread."""
    sender: Literal["me", "them"]
    text: str = Field(..., max_length=10000)
    sent_at: str | None = None
    is_mine: bool = False


class ConversationPayload(BaseModel):
    """Full conversation thread from the extension's Voyager API call."""
    conversation_urn: str = Field(..., max_length=255)
    contact_name: str | None = Field(default=None, max_length=255)
    contact_linkedin_id: str | None = Field(default=None, max_length=255)
    contact_linkedin_url: str | None = Field(default=None, max_length=500)
    contact_title: str | None = Field(default=None, max_length=255)
    contact_company: str | None = Field(default=None, max_length=255)
    messages: list[MessageEntry] = Field(..., max_length=2000)
    last_message_at: str | None = None
    last_sender: Literal["me", "them"] | None = None
    is_unread: bool = False


class MessagesSyncRequest(BaseModel):
    """Extension pushes a batch of full conversation threads at once."""
    conversations: list[ConversationPayload] = Field(..., max_length=100)


class MessagesSyncResponse(BaseModel):
    created: int
    updated: int
    total_processed: int
    total_messages: int
    classification_enabled: bool


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


# ── Extension v2: Job + Company ingest ───────────────────────────────────────

class JobCaptureInput(BaseModel):
    """Structured job data scraped from a LinkedIn job detail page."""
    title: str = Field(..., max_length=500)
    company: str = Field(default="", max_length=255)
    company_linkedin_url: str | None = Field(default=None, max_length=500)
    location: str = Field(default="", max_length=255)
    description: str = Field(default="", max_length=10000)
    salary: str = Field(default="", max_length=255)
    employment_type: str = Field(default="", max_length=100)
    seniority_level: str = Field(default="", max_length=100)
    industry: str = Field(default="", max_length=255)
    job_function: str = Field(default="", max_length=255)
    posted_at: str = Field(default="", max_length=100)
    applicant_count: str = Field(default="", max_length=100)
    linkedin_job_id: str = Field(default="", max_length=50)
    linkedin_url: str = Field(default="", max_length=2000)


class IngestJobRequest(BaseModel):
    job: JobCaptureInput
    source_url: str = Field(default="", max_length=2000)


class IngestJobResponse(BaseModel):
    saved: bool
    job_id: str | None = None
    already_existed: bool = False


class IngestJobsBulkRequest(BaseModel):
    """Batch of job summaries from a search results page."""
    jobs: list[JobCaptureInput] = Field(..., max_length=100)


class IngestJobsBulkResponse(BaseModel):
    saved: int
    skipped: int


class CompanyCaptureInput(BaseModel):
    """Structured company data from a LinkedIn company page."""
    name: str = Field(..., max_length=255)
    linkedin_url: str = Field(default="", max_length=500)
    tagline: str = Field(default="", max_length=500)
    industry: str = Field(default="", max_length=255)
    headcount: str = Field(default="", max_length=100)
    specialties: str = Field(default="", max_length=1000)
    website: str = Field(default="", max_length=500)
    headquarters: str = Field(default="", max_length=255)
    founded: str = Field(default="", max_length=50)
    type: str = Field(default="", max_length=100)
    about: str = Field(default="", max_length=3000)


class IngestCompanyRequest(BaseModel):
    company: CompanyCaptureInput
    source_url: str = Field(default="", max_length=2000)


class IngestCompanyResponse(BaseModel):
    saved: bool
    company_name: str
    connections_here: int = 0
    signals_count: int = 0
