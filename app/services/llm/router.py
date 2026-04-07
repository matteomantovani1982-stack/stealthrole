"""
app/services/llm/router.py

Central model routing for LLM tasks.

Routes each task type to the cheapest model that can handle it.
Goal: reduce LLM costs ~80-90% without changing product behavior.

Model tiers:
  Haiku  ($0.80/$4 per M tokens)  — classification, tagging, scoring
  Sonnet ($3/$15 per M tokens)    — reasoning, generation, strategy
  Opus   ($15/$75 per M tokens)   — deep analysis (future use only)

Usage:
  from app.services.llm.router import get_model_for_task, LLMTask

  client = ClaudeClient(task=LLMTask.CLASSIFICATION)
  # or
  model = get_model_for_task(LLMTask.SCORING)
"""

from enum import StrEnum

import structlog

from app.config import settings

logger = structlog.get_logger(__name__)


# ── Model IDs ─────────────────────────────────────────────────────────────────

HAIKU = "claude-haiku-4-5-20251001"
SONNET = "claude-sonnet-4-6"
OPUS = "claude-opus-4-6"


# ── Task taxonomy ─────────────────────────────────────────────────────────────

class LLMTask(StrEnum):
    """All LLM task types in StealthRole, mapped to model tiers."""

    # ── Haiku tier: classification, tagging, scoring ──────────────────────
    CLASSIFICATION = "classification"       # seniority, sector, geography
    SCORING = "scoring"                     # opportunity scoring, CV quality
    SIGNAL_ENRICHMENT = "signal_enrichment" # hidden market signal classification
    SIGNAL_SCORING = "signal_scoring"       # opportunity card scoring
    CV_QUALITY = "cv_quality"               # fast CV quality score (0-100)
    CV_BEST_PRACTICES = "cv_best_practices" # CV feedback suggestions
    JD_EXTRACTION = "jd_extraction"         # extract JD from webpage
    PROFILE_IMPORT = "profile_import"       # parse CV/LinkedIn into profile
    NEWS_TAGGING = "news_tagging"           # classify company news

    # ── Sonnet tier: reasoning, generation, strategy ──────────────────────
    EDIT_PLAN = "edit_plan"                 # CV tailoring edit plan
    POSITIONING = "positioning"             # positioning strategy
    REPORT_PACK = "report_pack"             # company intel + strategy
    SHADOW_HYPOTHESIS = "shadow_hypothesis" # shadow application hiring theory
    STRATEGY_MEMO = "strategy_memo"         # shadow strategy memo
    OUTREACH = "outreach"                   # outreach message generation
    CV_BUILD = "cv_build"                   # generate CV from scratch
    OPPORTUNITY_REASONING = "opportunity_reasoning"  # explain why opportunity fits

    # ── Opus tier: deep analysis (future) ─────────────────────────────────
    DEEP_ANALYSIS = "deep_analysis"         # multi-document, long-context
    CAREER_INTELLIGENCE = "career_intelligence"  # behavioral pattern analysis


# ── Task → Model mapping ─────────────────────────────────────────────────────

_TASK_MODEL_MAP: dict[str, str] = {
    # Haiku tier
    LLMTask.CLASSIFICATION: HAIKU,
    LLMTask.SCORING: HAIKU,
    LLMTask.SIGNAL_ENRICHMENT: HAIKU,
    LLMTask.SIGNAL_SCORING: HAIKU,
    LLMTask.CV_QUALITY: HAIKU,
    LLMTask.CV_BEST_PRACTICES: HAIKU,
    LLMTask.JD_EXTRACTION: HAIKU,
    LLMTask.PROFILE_IMPORT: HAIKU,
    LLMTask.NEWS_TAGGING: HAIKU,

    # Sonnet tier
    LLMTask.EDIT_PLAN: SONNET,
    LLMTask.POSITIONING: SONNET,
    LLMTask.REPORT_PACK: SONNET,
    LLMTask.SHADOW_HYPOTHESIS: SONNET,
    LLMTask.STRATEGY_MEMO: SONNET,
    LLMTask.OUTREACH: SONNET,
    LLMTask.CV_BUILD: SONNET,
    LLMTask.OPPORTUNITY_REASONING: SONNET,

    # Opus tier
    LLMTask.DEEP_ANALYSIS: OPUS,
    LLMTask.CAREER_INTELLIGENCE: OPUS,
}

# Fallback chain: if a model fails, try the next tier up
_FALLBACK_CHAIN = {
    HAIKU: SONNET,
    SONNET: OPUS,
    OPUS: None,  # no fallback from Opus
}


def get_model_for_task(task: str | LLMTask) -> str:
    """
    Resolve the optimal model for a given task type.
    Falls back to settings.claude_model if task is unknown.
    """
    model = _TASK_MODEL_MAP.get(str(task))
    if model:
        return model

    logger.warning("llm_router_unknown_task", task=task, fallback=settings.claude_model)
    return settings.claude_model


def get_fallback_model(current_model: str) -> str | None:
    """Get the next model in the fallback chain, or None if at top."""
    return _FALLBACK_CHAIN.get(current_model)


def get_task_tier(task: str | LLMTask) -> str:
    """Return the tier name for a task: haiku, sonnet, or opus."""
    model = get_model_for_task(task)
    if model == HAIKU:
        return "haiku"
    elif model == SONNET:
        return "sonnet"
    elif model == OPUS:
        return "opus"
    return "unknown"
