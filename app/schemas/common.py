"""
app/schemas/common.py

Shared response schemas used across multiple route files.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class MessageResponse(BaseModel):
    """Generic success message response."""
    message: str


class DeletedResponse(BaseModel):
    """Response for delete operations."""
    deleted: bool = True
    id: str = ""


class CountResponse(BaseModel):
    """Response with a single count."""
    count: int = 0


# ── Dashboard ─────────────────────────────────────────────────────────────────

class DashboardSummaryResponse(BaseModel):
    profile_strength: dict = Field(default_factory=dict)
    top_opportunities: list = Field(default_factory=list)
    radar_opportunities: list = Field(default_factory=list)
    recent_applications: list[dict] = Field(default_factory=list)
    recent_shadow_applications: list[dict] = Field(default_factory=list)
    shadow_count: int = 0
    total_applications: int = 0
    total_shadow_applications: int = 0
    credit_balance: int = 0
    radar_total: int = 0
    profile_completeness: float = 0.0
    sources_active: list[str] = Field(default_factory=list)


# ── Referral ──────────────────────────────────────────────────────────────────

class ReferralStatsResponse(BaseModel):
    referral_code: str = ""
    referral_url: str = ""
    referral_count: int = 0
    credits_earned: int = 0


class ReferralApplyResponse(BaseModel):
    message: str = ""
    referred_by: str = ""


# ── Profile Strength ──────────────────────────────────────────────────────────

class ProfileStrengthResponse(BaseModel):
    score: float = 0
    max: float = 100
    breakdown: list | dict = Field(default_factory=list)
    next_action: str = ""


# ── Quickstart ────────────────────────────────────────────────────────────────

class QuickstartResponse(BaseModel):
    cv_id: str = ""
    cv_status: str = ""
    profile_id: str = ""
    profile_status: str = ""
    experiences_added: int = 0
    headline: str = ""
    extracted: dict = Field(default_factory=dict)


# ── Jobs ──────────────────────────────────────────────────────────────────────

class StageUpdateResponse(BaseModel):
    id: str
    pipeline_stage: str
    pipeline_notes: str | None = None


class TimelineEvent(BaseModel):
    id: str
    event_type: str
    title: str
    detail: str = ""
    created_at: str | None = None


class TimelineResponse(BaseModel):
    events: list[TimelineEvent] = Field(default_factory=list)
    total: int = 0


# ── Shadow Applications ──────────────────────────────────────────────────────

class ShadowApplicationItem(BaseModel):
    id: str
    company: str = ""
    signal_type: str = ""
    hypothesis_role: str = ""
    radar_score: float = 0
    confidence: float = 0
    status: str = ""
    pipeline_stage: str = ""
    created_at: str = ""


class ShadowListResponse(BaseModel):
    shadow_applications: list[ShadowApplicationItem] = Field(default_factory=list)
    total: int = 0


# ── Outreach ──────────────────────────────────────────────────────────────────

class OutreachResponse(BaseModel):
    company: str = ""
    role: str = ""
    tone: str = ""
    linkedin_note: str = ""
    cold_email: str = ""
    follow_up: str = ""


# ── Email Intelligence ────────────────────────────────────────────────────────

class EmailTimelineResponse(BaseModel):
    timeline: list = Field(default_factory=list)
    total: int = 0
    applications_reconstructed: int = 0


# ── Opportunities ─────────────────────────────────────────────────────────────

class OpportunityRadarResponse(BaseModel):
    opportunities: list = Field(default_factory=list)
    total: int = 0
    returned: int = 0
    meta: dict = Field(default_factory=dict)
