"""
app/schemas/quick_start.py

Pydantic schemas for the Quick Start API.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class QuickStartRequest(BaseModel):
    """Request body for POST /quick-start."""

    cv_text: str | None = None
    linkedin_url: str | None = None
    target_role: str | None = None
    target_companies: list[str] = Field(
        default_factory=list,
    )


class QuickStartSignalItem(BaseModel):
    """A scored signal in quick-start results."""

    signal_id: str = ""
    company: str = ""
    signal_type: str = ""
    confidence: float = 0.0
    decision_score: float = 0.0
    quality_gate: str = "unknown"


class QuickStartActionItem(BaseModel):
    """An action recommendation in quick-start results."""

    action_type: str = ""
    target_company: str = ""
    reason: str = ""
    timing: str = "this_week"
    confidence: float = 0.0
    message_preview: str = ""


class QuickStartSummary(BaseModel):
    """Summary of quick-start results."""

    total_signals: int = 0
    total_actions: int = 0
    top_company: str | None = None
    recommended_action: str | None = None
    target_role: str | None = None
    next_steps: list[str] = Field(default_factory=list)


class QuickStartResponse(BaseModel):
    """Response from POST /quick-start."""

    user_id: str = ""
    computed_at: str = ""
    signals: list[QuickStartSignalItem] = Field(
        default_factory=list,
    )
    actions: list[QuickStartActionItem] = Field(
        default_factory=list,
    )
    summary: QuickStartSummary = Field(
        default_factory=QuickStartSummary,
    )
