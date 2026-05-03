"""
app/schemas/insights.py

Pydantic schemas for the Value / ROI Engine API.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SignalEffectivenessItem(BaseModel):
    """Success rate for one signal type."""

    signal_type: str = ""
    total_signals: int = 0
    positive_outcomes: int = 0
    hires: int = 0
    success_rate: float = 0.0
    hire_rate: float = 0.0


class ActionEffectivenessItem(BaseModel):
    """Success rate for one action type."""

    action_type: str = ""
    total_generated: int = 0
    sent: int = 0
    responded: int = 0
    dismissed: int = 0
    response_rate: float = 0.0
    execution_rate: float = 0.0


class PathPerformanceItem(BaseModel):
    """Success rate for one outreach path."""

    path: str = ""
    success_rate: float = 0.0
    sample_count: int = 0


class TimingInsights(BaseModel):
    """Average timing metrics."""

    avg_hours_to_send: float | None = None
    avg_hours_to_respond: float | None = None


class InsightSummary(BaseModel):
    """High-level summary of value metrics."""

    total_signals_tracked: int = 0
    total_positive_outcomes: int = 0
    total_hires: int = 0
    overall_success_rate: float = 0.0
    total_actions_generated: int = 0
    total_responses: int = 0
    best_signal_type: str | None = None
    best_path: str | None = None


class RecommendationItem(BaseModel):
    """A single actionable recommendation."""

    type: str = ""
    title: str = ""
    detail: str = ""
    priority: str = "medium"


class InsightsResponse(BaseModel):
    """Response from GET /insights — full value dashboard."""

    user_id: str = ""
    computed_at: str = ""
    signal_effectiveness: list[SignalEffectivenessItem] = (
        Field(default_factory=list)
    )
    action_effectiveness: list[ActionEffectivenessItem] = (
        Field(default_factory=list)
    )
    path_performance: list[PathPerformanceItem] = (
        Field(default_factory=list)
    )
    timing: TimingInsights = Field(
        default_factory=TimingInsights,
    )
    summary: InsightSummary = Field(
        default_factory=InsightSummary,
    )
    recommendations: list[RecommendationItem] = (
        Field(default_factory=list)
    )
