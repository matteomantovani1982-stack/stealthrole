"""
app/schemas/auto_apply.py

Pydantic schemas for the Auto-Apply Engine API.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ── Profile ───────────────────────────────────────────────────────────────────

class AutoApplyProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    location: str | None = Field(default=None, max_length=255)
    linkedin_url: str | None = Field(default=None, max_length=500)
    website_url: str | None = Field(default=None, max_length=500)
    current_company: str | None = Field(default=None, max_length=255)
    current_title: str | None = Field(default=None, max_length=255)
    standard_answers: dict | None = None
    cover_letter_template: str | None = Field(default=None, max_length=10000)


class AutoApplyProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    linkedin_url: str | None = None
    website_url: str | None = None
    current_company: str | None = None
    current_title: str | None = None
    standard_answers: dict
    cover_letter_template: str | None = None
    created_at: datetime


# ── Prepare ───────────────────────────────────────────────────────────────────

class PrepareRequest(BaseModel):
    company: str = Field(..., min_length=1, max_length=255)
    role: str = Field(..., min_length=1, max_length=255)
    apply_url: str = Field(..., min_length=1, max_length=2000)
    application_id: uuid.UUID | None = None
    job_run_id: uuid.UUID | None = None


# ── Submission ────────────────────────────────────────────────────────────────

class SubmissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company: str
    role: str
    apply_url: str
    ats_platform: str
    form_payload: dict
    cv_s3_key: str | None = None
    status: str
    error_message: str | None = None
    submitted_at: datetime | None = None
    application_id: uuid.UUID | None = None
    created_at: datetime


class ReportSubmittedRequest(BaseModel):
    submission_id: uuid.UUID


class ReportFailedRequest(BaseModel):
    submission_id: uuid.UUID
    error: str = Field(..., max_length=1000)


# ── Stats ─────────────────────────────────────────────────────────────────────

class AutoApplyStatsResponse(BaseModel):
    total: int
    submitted: int
    prepared: int
    failed: int
    by_status: dict[str, int]


class PlatformInfo(BaseModel):
    id: str
    name: str
    supported: bool
