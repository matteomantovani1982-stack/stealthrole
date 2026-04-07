"""
app/schemas/relationship.py

Pydantic schemas for the Relationship Engine API.
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

IntroStatusType = Literal[
    "identified", "outreach_drafted", "requested",
    "introduced", "declined", "converted",
]


# ── Company map ───────────────────────────────────────────────────────────────

class CompanyPerson(BaseModel):
    connection_id: str
    name: str
    title: str | None = None
    headline: str | None = None
    linkedin_url: str | None = None
    is_recruiter: bool
    is_hiring_manager: bool
    relationship_strength: str | None = None
    rank_score: int
    intro_angle: str
    outreach_status: str | None = None
    warm_intro_id: str | None = None


class CompanyMapResponse(BaseModel):
    company: str
    total_connections: int
    recruiters: int
    hiring_managers: int
    people: list[CompanyPerson]


# ── Warm intro ────────────────────────────────────────────────────────────────

class RequestIntroRequest(BaseModel):
    connection_id: uuid.UUID
    target_company: str = Field(..., min_length=1, max_length=255)
    target_role: str | None = Field(default=None, max_length=255)
    application_id: uuid.UUID | None = None
    relationship_context: str | None = Field(default=None, max_length=500)
    custom_message: str | None = Field(default=None, max_length=2000)


class WarmIntroResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    connection_id: uuid.UUID
    application_id: uuid.UUID | None = None
    target_company: str
    target_role: str | None = None
    target_person: str | None = None
    status: str
    outreach_message: str | None = None
    response_message: str | None = None
    notes: str | None = None
    relationship_context: str | None = None
    intro_angle: str | None = None
    requested_at: datetime | None = None
    responded_at: datetime | None = None
    created_at: datetime


class UpdateIntroStatusRequest(BaseModel):
    status: IntroStatusType
    response_message: str | None = Field(default=None, max_length=5000)
    notes: str | None = Field(default=None, max_length=5000)


# ── Pipeline ──────────────────────────────────────────────────────────────────

class PipelineResponse(BaseModel):
    intros: list[WarmIntroResponse]
    total: int


class PipelineStatsResponse(BaseModel):
    total_intros: int
    by_status: dict[str, int]
    active: int
    successful: int
    conversion_rate: float
