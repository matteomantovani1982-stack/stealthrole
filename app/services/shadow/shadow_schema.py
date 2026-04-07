"""
app/services/shadow/shadow_schema.py

Pydantic schemas for Shadow Application request/response.
"""

from pydantic import BaseModel, Field


class ShadowGenerateRequest(BaseModel):
    """Input for POST /api/v1/shadow/generate."""
    company: str = Field(..., min_length=1, max_length=255)
    signal_type: str = Field(..., min_length=1, max_length=50)
    likely_roles: list[str] = Field(default_factory=list)
    signal_context: str | None = None
    radar_opportunity_id: str | None = None
    radar_score: int | None = None
    hidden_signal_id: str | None = None
    tone: str = Field(default="confident", pattern=r"^(confident|formal|casual)$")


class OutreachMessages(BaseModel):
    linkedin_note: str
    cold_email: str
    follow_up: str


class ShadowPack(BaseModel):
    hypothesis_role: str
    hiring_hypothesis: str
    strategy_memo: str
    outreach: OutreachMessages
    confidence: float
    reasoning: str


class ShadowGenerateResponse(BaseModel):
    id: str
    status: str
    company: str
    hypothesis_role: str | None = None
    message: str = "Shadow application generation started"


class ShadowDetailResponse(BaseModel):
    id: str
    company: str
    signal_type: str
    signal_context: str | None
    radar_score: int | None
    status: str
    hypothesis_role: str | None
    hiring_hypothesis: str | None
    strategy_memo: str | None
    outreach_linkedin: str | None
    outreach_email: str | None
    outreach_followup: str | None
    tailored_cv_download_url: str | None
    confidence: float | None
    reasoning: str | None
    pipeline_stage: str | None
    pipeline_notes: str | None = None
    created_at: str
