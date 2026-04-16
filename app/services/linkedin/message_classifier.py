"""
app/services/linkedin/message_classifier.py

Classifies a synced LinkedIn conversation as recruiter / opportunity /
networking / interview / other, determines the stage, and generates a
suggested reply via Claude Haiku.

Gated behind the `enable_linkedin_msg_classify` feature flag so we don't
burn LLM credits until Feature 3 (/inbox) is ready to display the output.

When disabled:
- `classify_and_draft()` returns None immediately (no-op)
- Row is still inserted by the endpoint with classification fields NULL
- A cheap heuristic `is_job_related` flag is set based on keyword matching
  so the /inbox default filter has something to work with even without AI

When enabled (flag flipped later):
- Calls Haiku with the full thread
- Returns structured classification + draft reply
- Endpoint writes them to the row
"""

from __future__ import annotations

import re
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)


# Keywords that bias a message toward "job-related". Generous set — we'd
# rather include a non-job message than miss a recruiter reaching out.
_JOB_KEYWORDS = [
    # Recruiter / role / opportunity
    "recruit", "hiring", "opportunity", "role ", "position", "job ",
    "candidate", "interview", "cv", "resume", "cover letter",
    "offer", "salary", "compensation", "benefits", "onboarding",
    "remote", "relocate", "start date",
    # Process stages
    "screen", "phone call", "chat", "next steps", "hr",
    "applied", "application", "shortlist", "rejected",
    # Company/team indicators
    "our team", "our company", "joining us", "join our",
    "growing team", "open role", "open position", "open positions",
    # Schedule/interview
    "available", "calendar", "schedule a call", "book a time",
    # Compensation/offer
    "package", "equity", "base salary", "ctc",
]

_RECRUITER_TITLES = [
    "recruiter", "talent", "talent acquisition", "ta ",
    "sourcer", "headhunter", "executive search", "hiring manager",
    "people", "hr ", "human resources",
]


def heuristic_is_job_related(
    *,
    contact_title: str | None,
    contact_company: str | None,
    messages: list[dict],
    known_recruiter: bool = False,
) -> bool:
    """
    Cheap non-LLM heuristic for the `is_job_related` flag.
    Errs on the side of inclusion — we'd rather have a false positive
    than drop a recruiter message.
    """
    if known_recruiter:
        return True

    title_l = (contact_title or "").lower()
    if any(k in title_l for k in _RECRUITER_TITLES):
        return True

    # Concatenate all message text and scan for keywords
    all_text = " ".join(m.get("text", "") for m in messages).lower()
    if any(k in all_text for k in _JOB_KEYWORDS):
        return True

    return False


async def classify_and_draft(
    *,
    contact_name: str | None,
    contact_title: str | None,
    contact_company: str | None,
    messages: list[dict],
) -> dict | None:
    """
    Classify the thread and generate a suggested reply via Haiku.
    Returns None when the feature flag is disabled (default).
    Returns {classification, stage, ai_draft_reply, confidence} when enabled.
    """
    if not settings.enable_linkedin_msg_classify:
        logger.debug("linkedin_msg_classify_disabled", contact=contact_name)
        return None

    # When enabled, this is where we'd call Haiku. Deferred to Feature 3
    # because we need the /inbox UI first to validate the output format.
    # Stub for now so flipping the flag doesn't break anything.
    logger.info(
        "linkedin_msg_classify_enabled_stub",
        contact=contact_name,
        message="classification flag is on but implementation is deferred to Feature 3",
    )
    return None
