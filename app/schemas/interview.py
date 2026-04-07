"""
app/schemas/interview.py

Pydantic schemas for Interview Coach + Compensation API.
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RoundType = Literal[
    "phone_screen", "technical", "behavioral", "case_study",
    "onsite", "panel", "final", "hiring_manager",
]
Outcome = Literal["passed", "failed", "pending", "unknown"]


class InterviewRoundCreate(BaseModel):
    round_type: RoundType
    scheduled_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, ge=5, le=480)
    interviewer_name: str | None = Field(default=None, max_length=255)
    interviewer_title: str | None = Field(default=None, max_length=255)
    interviewer_linkedin: str | None = Field(default=None, max_length=500)
    prep_notes: str | None = Field(default=None, max_length=5000)
    focus_areas: list[str] | None = None


class InterviewRoundUpdate(BaseModel):
    scheduled_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, ge=5, le=480)
    interviewer_name: str | None = Field(default=None, max_length=255)
    interviewer_title: str | None = Field(default=None, max_length=255)
    interviewer_linkedin: str | None = Field(default=None, max_length=500)
    prep_notes: str | None = Field(default=None, max_length=5000)
    focus_areas: list[str] | None = None
    debrief: str | None = Field(default=None, max_length=5000)
    questions_asked: list[str] | None = None
    confidence_rating: int | None = Field(default=None, ge=1, le=5)
    outcome: Outcome | None = None


class InterviewRoundResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    application_id: uuid.UUID
    round_number: int
    round_type: str
    scheduled_at: datetime | None = None
    duration_minutes: int | None = None
    interviewer_name: str | None = None
    interviewer_title: str | None = None
    interviewer_linkedin: str | None = None
    prep_notes: str | None = None
    focus_areas: dict | None = None
    debrief: str | None = None
    questions_asked: dict | None = None
    confidence_rating: int | None = None
    outcome: str | None = None
    created_at: datetime


class PrepGuideResponse(BaseModel):
    round_type: str
    round_number: int
    interviewer: str | None = None
    interviewer_title: str | None = None
    focus: list[str] = []
    tips: list[str] = []
    common_questions: list[str] = []
    user_prep_notes: str | None = None
    user_focus_areas: dict | None = None


class NegotiationGuideResponse(BaseModel):
    company: str
    role: str
    talking_points: list[str]
    counter_offer_strategy: str
    things_to_negotiate: list[str]
    benchmark: dict | None = None


class CompensationBenchmarkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role_title: str
    region: str
    seniority_level: str | None = None
    currency: str
    p25: int | None = None
    p50: int | None = None
    p75: int | None = None
    p90: int | None = None
    total_comp_p50: int | None = None
    source: str | None = None


class InterviewStatsResponse(BaseModel):
    total_rounds: int
    by_outcome: dict[str, int]
    by_type: dict[str, int]
    pass_rate: float | None = None
