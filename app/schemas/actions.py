"""
app/schemas/actions.py

Pydantic request/response schemas for the Action Engine API.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# ── Response models ──────────────────────────────────────────────────


class ActionItem(BaseModel):
    """A single action recommendation."""

    id: str = ""
    action_type: str = ""
    status: str = "generated"
    target_name: str = ""
    target_title: str = ""
    target_company: str = ""
    reason: str = ""
    message_subject: str | None = None
    message_body: str = ""
    timing_label: str = "this_week"
    confidence: float = 0.0
    priority: int = 50
    decision_score: float | None = None
    channel_metadata: dict = Field(default_factory=dict)
    is_user_edited: bool = False
    created_at: str | None = None
    expires_at: str | None = None


class ActionsListResponse(BaseModel):
    """Response from GET /actions."""

    actions: list[ActionItem] = Field(default_factory=list)
    total: int = 0


class TopActionsResponse(BaseModel):
    """Response from GET /actions/top — prioritised actionable items."""

    actions: list[ActionItem] = Field(default_factory=list)
    total: int = 0
    active_signals: int = 0


class ActionGenerateResponse(BaseModel):
    """Response from POST /actions/generate."""

    actions_created: int = 0
    signal_id: str = ""
    action_types: list[str] = Field(default_factory=list)


class ActionTransitionResponse(BaseModel):
    """Response from PATCH /actions/{id}/{transition}."""

    id: str = ""
    status: str = ""
    previous_status: str = ""
    success: bool = True


class ActionExecuteResponse(BaseModel):
    """Response from POST /actions/{id}/execute."""

    success: bool = False
    channel: str = ""
    mock: bool = True
    message: str = ""
    action_id: str = ""


# ── Request models ───────────────────────────────────────────────────


class ActionGenerateRequest(BaseModel):
    """Request body for POST /actions/generate."""

    signal_id: str
    profile_fit: float = 0.50
    access_strength: float = 0.50


class ActionUpdateMessageRequest(BaseModel):
    """Request body for PATCH /actions/{id}/message."""

    message_subject: str | None = None
    message_body: str | None = None
