"""
app/schemas/scout.py

Pydantic response schemas for the Scout API.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── Signal Intelligence ───────────────────────────────────────────────────────

class OpportunityCard(BaseModel):
    """A single scored opportunity returned by the signal engine."""
    company: str = ""
    role: str = ""
    score: float = 0
    signal_type: str = ""
    reasoning: str = ""
    source: str = ""
    url: str = ""
    location: str = ""
    sector: str = ""
    evidence_tier: str = ""


class SignalsResponse(BaseModel):
    """Response from GET /scout/signals."""
    opportunities: list[dict] = Field(default_factory=list)
    live_openings: list[dict] = Field(default_factory=list)
    signals_detected: int = 0
    sources_searched: int = 0
    is_demo: bool = False
    engine_version: str = ""
    scored_by: str = ""
    cached: bool = False


# ── History ───────────────────────────────────────────────────────────────────

class ScoutHistoryItem(BaseModel):
    id: str
    created_at: str
    signals_detected: int = 0
    sources_searched: int = 0
    scored_by: str = ""
    regions: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)
    sectors: list[str] = Field(default_factory=list)
    is_stale: bool = False
    opportunities_count: int = 0
    live_openings_count: int = 0


class ScoutHistoryResponse(BaseModel):
    history: list[ScoutHistoryItem] = Field(default_factory=list)
    total: int = 0


# ── Legacy Jobs ───────────────────────────────────────────────────────────────

class ScoutJobItem(BaseModel):
    id: str
    title: str
    company: str = ""
    location: str = ""
    snippet: str = ""
    url: str = ""
    source: str = ""
    salary: str = ""
    posted_date: str = ""
    source_color: str = ""
    is_remote: bool = False
    requirements: list[str] = Field(default_factory=list)


class ScoutJobsResponse(BaseModel):
    jobs: list[dict] = Field(default_factory=list)
    total: int = 0
    query: str = ""
    location: str = ""
    is_demo: bool = False
    sources_used: list[str] = Field(default_factory=list)


# ── Hidden Market ─────────────────────────────────────────────────────────────

class HiddenSignalItem(BaseModel):
    id: str
    company_name: str
    signal_type: str = ""
    confidence: float = 0
    likely_roles: list[str] = Field(default_factory=list)
    reasoning: str = ""
    source_url: str | None = None
    source_name: str | None = None
    is_dismissed: bool = False
    created_at: str | None = None


class HiddenMarketResponse(BaseModel):
    signals: list[HiddenSignalItem] = Field(default_factory=list)
    total: int = 0


class DismissSignalResponse(BaseModel):
    id: str
    is_dismissed: bool


# ── Saved Jobs ────────────────────────────────────────────────────────────────

class SavedJobItem(BaseModel):
    id: str
    source: str
    external_id: str
    title: str
    company: str = ""
    location: str = ""
    salary_min: int | None = None
    salary_max: int | None = None
    url: str = ""
    metadata: dict = Field(default_factory=dict)
    saved_at: str | None = None
    created_at: str | None = None


class SavedJobsResponse(BaseModel):
    saved_jobs: list[SavedJobItem] = Field(default_factory=list)
    total: int = 0


# ── Predictions ───────────────────────────────────────────────────────────────

class PredictionsResponse(BaseModel):
    predictions: list[dict] = Field(default_factory=list)
    total: int = 0
    sources_searched: int = 0


# ── Vacancies ─────────────────────────────────────────────────────────────────

class VacancyItem(BaseModel):
    title: str
    role: str = ""
    company: str = ""
    description: str = ""
    url: str = ""
    source: str = ""
    date: str = ""
    match_score: int = 50


class VacanciesResponse(BaseModel):
    vacancies: list[dict] = Field(default_factory=list)
    total: int = 0
    sources_searched: int = 0


# ── Freelance ─────────────────────────────────────────────────────────────────

class FreelanceResponse(BaseModel):
    freelance: list[dict] = Field(default_factory=list)
    total: int = 0
    sources_searched: int = 0
