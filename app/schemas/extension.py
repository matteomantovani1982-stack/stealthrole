"""
app/schemas/extension.py

Pydantic schemas for the Chrome Extension capture API.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# ── Request models ─────────────────────────────────────────────

class CaptureProfileRequest(BaseModel):
    """Raw LinkedIn profile data from extension."""

    linkedin_url: str
    full_name: str = ""
    headline: str = ""
    company: str = ""
    location: str = ""
    raw_html: str | None = None
    metadata: dict = Field(default_factory=dict)


class CaptureJobRequest(BaseModel):
    """Raw job posting data from extension."""

    job_url: str
    title: str = ""
    company: str = ""
    location: str = ""
    description: str = ""
    posted_date: str | None = None
    raw_html: str | None = None
    metadata: dict = Field(default_factory=dict)


class CaptureCompanyRequest(BaseModel):
    """Raw company page data from extension."""

    company_url: str
    company_name: str = ""
    industry: str = ""
    size: str = ""
    description: str = ""
    recent_posts: list[dict] = Field(
        default_factory=list,
    )
    raw_html: str | None = None
    metadata: dict = Field(default_factory=dict)


# ── Response models ────────────────────────────────────────────

class CaptureResponse(BaseModel):
    """Standard response for all capture endpoints."""

    success: bool = True
    capture_id: str = ""
    capture_type: str = ""
    signals_created: int = 0
    message: str = ""
