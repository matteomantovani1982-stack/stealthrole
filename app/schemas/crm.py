"""
app/schemas/crm.py

Pydantic schemas for the Follow-Up CRM module.
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

EventType = Literal[
    "applied", "recruiter_contact", "phone_screen", "interview",
    "technical", "onsite", "offer", "rejection", "withdrawal",
    "follow_up", "note",
]


# ── Timeline ──────────────────────────────────────────────────────────────────

class TimelineEventCreate(BaseModel):
    event_type: EventType
    event_date: datetime
    title: str = Field(..., min_length=1, max_length=255)
    notes: str | None = Field(default=None, max_length=5000)
    contact_person: str | None = Field(default=None, max_length=255)
    contact_email: str | None = Field(default=None, max_length=255)
    contact_role: str | None = Field(default=None, max_length=255)
    next_action: str | None = Field(default=None, max_length=500)
    next_action_date: datetime | None = None


class TimelineEventUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=5000)
    contact_person: str | None = Field(default=None, max_length=255)
    contact_email: str | None = Field(default=None, max_length=255)
    contact_role: str | None = Field(default=None, max_length=255)
    next_action: str | None = Field(default=None, max_length=500)
    next_action_date: datetime | None = None


class TimelineEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    application_id: uuid.UUID
    event_type: str
    event_date: datetime
    title: str
    notes: str | None = None
    contact_person: str | None = None
    contact_email: str | None = None
    contact_role: str | None = None
    next_action: str | None = None
    next_action_date: datetime | None = None
    follow_up_sent: bool
    source: str | None = None
    created_at: datetime


# ── Calendar events ───────────────────────────────────────────────────────────

class CalendarEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    start_time: datetime
    end_time: datetime | None = None
    location: str | None = None
    organizer_email: str | None = None
    detected_company: str | None = None
    detected_role: str | None = None
    interview_round: str | None = None
    application_id: uuid.UUID | None = None
    is_dismissed: bool
    created_at: datetime


class LinkCalendarEventRequest(BaseModel):
    application_id: uuid.UUID


# ── Follow-up ─────────────────────────────────────────────────────────────────

class FollowUpListResponse(BaseModel):
    overdue: list[TimelineEventResponse]
    upcoming: list[TimelineEventResponse]
    total_overdue: int
    total_upcoming: int


# ── Next action ───────────────────────────────────────────────────────────────

class NextActionResponse(BaseModel):
    action: str
    urgency: str
    suggested_date: str | None = None
    template: str | None = None


# ── CRM summary ──────────────────────────────────────────────────────────────

class CRMSummaryResponse(BaseModel):
    overdue_followups: int
    upcoming_followups: int
    upcoming_interviews: int
    next_interview: str | None = None
