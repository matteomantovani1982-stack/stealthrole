"""
app/services/email_integration/extractor.py

Extracts job application signals from email metadata.

Phase 1 approach: rule-based pattern matching on subject + snippet.
Phase 3 will add Claude-based extraction for higher accuracy.

Each email gets classified into:
  - detected_stage: applied | interview | offer | rejected | unknown
  - company: extracted from sender domain / subject
  - role: extracted from subject if present
  - confidence: high | medium | low
"""

from __future__ import annotations

import re
import structlog
from dataclasses import dataclass

from app.services.email_integration.providers import EmailMessage

logger = structlog.get_logger(__name__)


@dataclass
class ExtractionResult:
    detected_stage: str
    company: str | None
    role: str | None
    confidence: str  # high | medium | low


# ── Pattern definitions ───────────────────────────────────────────────────────

# Patterns ordered by specificity — first match wins

_APPLICATION_PATTERNS = [
    # Applied confirmations
    (r"thank you for (applying|your application|your interest)", "applied", "high"),
    (r"we (have |)received your application", "applied", "high"),
    (r"application (received|confirmed|submitted)", "applied", "high"),
    (r"your application for", "applied", "medium"),
    (r"successfully (applied|submitted)", "applied", "high"),

    # Interview invitations
    (r"(schedule|book|arrange|confirm).{0,30}interview", "interview", "high"),
    (r"invite you.{0,20}(interview|conversation|chat)", "interview", "high"),
    (r"like to (meet|speak|talk) with you", "interview", "high"),
    (r"next (step|stage|round)", "interview", "medium"),
    (r"mov(ed|ing) forward", "interview", "medium"),
    (r"(phone|video|technical|onsite|on-site) (screen|interview|call)", "interview", "high"),
    (r"interview (invitation|confirmation|details|scheduled)", "interview", "high"),

    # Offers
    (r"(pleased|happy|delighted|excited) to (offer|extend)", "offer", "high"),
    (r"offer (letter|of employment|package)", "offer", "high"),
    (r"job offer", "offer", "high"),
    (r"welcome to the team", "offer", "high"),
    (r"congratulations.{0,30}(offer|position|role)", "offer", "high"),

    # Rejections
    (r"unfortunately.{0,50}(not|unable|won't)", "rejected", "high"),
    (r"after careful (consideration|review)", "rejected", "medium"),
    (r"(not|won't) (be )?(moving|proceeding|advancing) forward", "rejected", "high"),
    (r"position has been filled", "rejected", "high"),
    (r"decided (to|not to) (pursue|move forward with) other", "rejected", "high"),
    (r"we (regret|are sorry) to inform", "rejected", "high"),
    (r"will not be (moving|proceeding)", "rejected", "high"),
    (r"other candidates", "rejected", "medium"),
]

# Common no-reply / ATS domains that indicate company emails
_ATS_DOMAINS = {
    "greenhouse.io", "lever.co", "workable.com", "smartrecruiters.com",
    "icims.com", "myworkdayjobs.com", "taleo.net", "jobvite.com",
    "ashbyhq.com", "bamboohr.com", "recruitee.com", "breezy.hr",
}

# Domains to ignore (newsletters, marketing, etc.)
_IGNORE_DOMAINS = {
    "linkedin.com", "indeed.com", "glassdoor.com", "noreply.google.com",
    "notifications.google.com", "mailer-daemon",
}


def extract_signal(msg: EmailMessage) -> ExtractionResult | None:
    """
    Analyze an email and extract a job application signal.
    Returns None if the email doesn't appear job-related.
    """
    text = f"{msg.subject} {msg.snippet}".lower()

    # Skip obvious non-job emails
    sender_domain = _extract_domain(msg.sender)
    if sender_domain in _IGNORE_DOMAINS:
        return None

    # Match against patterns
    for pattern, stage, confidence in _APPLICATION_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            company = _extract_company(msg.sender, msg.subject)
            role = _extract_role(msg.subject, msg.snippet)

            return ExtractionResult(
                detected_stage=stage,
                company=company,
                role=role,
                confidence=confidence,
            )

    return None


def _extract_domain(sender: str) -> str:
    """Extract domain from email sender string."""
    # Handle "Name <email@domain.com>" format
    match = re.search(r"@([\w.-]+)", sender)
    if match:
        return match.group(1).lower()
    return ""


def _extract_company(sender: str, subject: str) -> str | None:
    """
    Best-effort company name extraction.
    Strategy: use sender display name, then domain name.
    """
    # Try sender display name (before <email>)
    display_match = re.match(r"^([^<]+)", sender)
    if display_match:
        display = display_match.group(1).strip()
        # Clean common prefixes
        for prefix in ("Talent Team at ", "Recruiting at ", "Careers at ", "HR at "):
            if display.lower().startswith(prefix.lower()):
                return display[len(prefix):].strip()
        # If it's not just an email address, use it
        if "@" not in display and len(display) > 2:
            return display.strip('" ')

    # Fallback: extract from "at {Company}" or "@ {Company}" in subject
    at_match = re.search(r"(?:at|@)\s+([A-Z][\w\s&.'-]+?)(?:\s*[-–|]|\s*$)", subject)
    if at_match:
        return at_match.group(1).strip()

    # Last resort: capitalize the domain name
    domain = _extract_domain(sender)
    if domain and domain not in _ATS_DOMAINS:
        # Remove TLD and capitalize
        company = domain.split(".")[0]
        if len(company) > 2:
            return company.capitalize()

    return None


def _extract_role(subject: str, snippet: str) -> str | None:
    """
    Best-effort role title extraction from subject line.
    Looks for common patterns: "for {Role}", "{Role} position", etc.
    """
    text = subject

    # "Application for Senior Engineer" / "for the role of ..."
    role_match = re.search(
        r"(?:for|regarding|re:)\s+(?:the\s+)?(?:role\s+of\s+|position\s+of\s+)?([A-Z][\w\s/&-]{3,50}?)(?:\s+(?:at|@|position|role|–|-|\||$))",
        text,
        re.IGNORECASE,
    )
    if role_match:
        role = role_match.group(1).strip()
        if len(role) > 3:
            return role

    # "{Role} - Application" / "{Role} | Interview"
    pipe_match = re.search(
        r"^([A-Z][\w\s/&-]{3,50}?)\s*[-–|]\s*(?:application|interview|offer|update)",
        text,
        re.IGNORECASE,
    )
    if pipe_match:
        return pipe_match.group(1).strip()

    return None
