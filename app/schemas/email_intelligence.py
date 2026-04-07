"""
app/schemas/email_intelligence.py

Pydantic schemas for Email Intelligence API.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EmailIntelligenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    scan_status: str
    scan_started_at: datetime | None = None
    scan_completed_at: datetime | None = None
    scan_period_years: int
    total_emails_scanned: int
    job_emails_found: int
    applications_reconstructed: int
    error_message: str | None = None
    reconstructed_timeline: list | None = None
    patterns: dict | None = None
    industry_breakdown: dict | None = None
    insights: dict | None = None
    writing_style: dict | None = None
    created_at: datetime
    updated_at: datetime


class PatternsResponse(BaseModel):
    avg_response_days: float | None = None
    response_rate_pct: float = 0
    best_day_to_apply: str | None = None
    best_time_to_apply: str | None = None
    avg_interviews_per_app: float = 0
    rejection_stage_distribution: dict | None = None
    longest_process_days: int | None = None
    fastest_offer_days: int | None = None
    total_companies_applied: int = 0
    total_responses: int = 0


class InsightsResponse(BaseModel):
    strengths: list[str] = []
    weaknesses: list[str] = []
    recommendations: list[str] = []
    career_trajectory: str = ""


class ScanTriggerResponse(BaseModel):
    message: str
    task_id: str | None = None
    scan_status: str
