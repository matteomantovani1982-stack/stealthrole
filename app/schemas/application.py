"""
app/schemas/application.py

Pydantic schemas for the Application Tracker API.
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SourceChannel = Literal[
    "linkedin", "indeed", "glassdoor", "referral",
    "company_site", "recruiter", "job_board", "other",
]
Stage = Literal["watching", "applied", "interview", "offer", "rejected"]


# ── Request schemas ──────────────────────────────────────────────────────────

class ApplicationCreate(BaseModel):
    """POST /api/v1/applications"""
    company: str = Field(..., min_length=1, max_length=255)
    role: str = Field(..., min_length=1, max_length=255)
    date_applied: datetime
    source_channel: SourceChannel
    stage: Stage = "applied"
    notes: str | None = Field(default=None, max_length=5000)
    url: str | None = Field(default=None, max_length=2000)
    salary: str | None = Field(default=None, max_length=255)
    contact_name: str | None = Field(default=None, max_length=255)
    contact_email: str | None = Field(default=None, max_length=255)
    job_run_id: uuid.UUID | None = None


class ApplicationUpdate(BaseModel):
    """PATCH /api/v1/applications/{id}"""
    company: str | None = Field(default=None, min_length=1, max_length=255)
    role: str | None = Field(default=None, min_length=1, max_length=255)
    date_applied: datetime | None = None
    source_channel: SourceChannel | None = None
    stage: Stage | None = None
    notes: str | None = Field(default=None, max_length=5000)
    url: str | None = Field(default=None, max_length=2000)
    salary: str | None = Field(default=None, max_length=255)
    contact_name: str | None = Field(default=None, max_length=255)
    contact_email: str | None = Field(default=None, max_length=255)
    job_run_id: uuid.UUID | None = None


class ApplicationStageUpdate(BaseModel):
    """PATCH /api/v1/applications/{id}/stage — lightweight drag-and-drop."""
    stage: Stage


# ── Response schemas ─────────────────────────────────────────────────────────

class ApplicationResponse(BaseModel):
    """Full application detail."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company: str
    role: str
    date_applied: datetime
    source_channel: str
    stage: str
    notes: str | None = None
    url: str | None = None
    salary: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    interview_at: datetime | None = None
    offer_at: datetime | None = None
    rejected_at: datetime | None = None
    job_run_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime


class ApplicationListItem(BaseModel):
    """Card-level data for the Kanban board."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company: str
    role: str
    date_applied: datetime
    source_channel: str
    stage: str
    notes: str | None = None
    job_run_id: uuid.UUID | None = None
    created_at: datetime


class BoardColumn(BaseModel):
    """One Kanban column with its cards."""
    stage: str
    count: int
    applications: list[ApplicationListItem]


class BoardResponse(BaseModel):
    """Full Kanban board: all four columns."""
    columns: list[BoardColumn]
    total: int


# ── Analytics schemas ────────────────────────────────────────────────────────

class StageConversion(BaseModel):
    stage: str
    count: int
    rate: float = Field(description="Percentage of total applications in this stage")


class SourcePerformance(BaseModel):
    source: str
    total: int
    interviews: int
    offers: int
    interview_rate: float


class ApplicationAnalytics(BaseModel):
    total_applications: int
    by_stage: list[StageConversion]
    avg_days_to_interview: float | None = Field(
        default=None,
        description="Average calendar days from application to first interview",
    )
    best_source_channel: str | None = Field(
        default=None,
        description="Source channel with the highest interview conversion rate",
    )
    source_performance: list[SourcePerformance]
