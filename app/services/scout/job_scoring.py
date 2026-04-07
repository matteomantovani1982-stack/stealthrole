"""
app/services/scout/job_scoring.py

Job Scout 2.0 — enhanced job scoring with salary extraction,
freshness scoring, and source quality ranking.

Extends existing scout results with richer data.
Rule-based — zero LLM cost.
"""

import re
from datetime import datetime, UTC, timedelta

import structlog

logger = structlog.get_logger(__name__)


# ── Salary extraction ─────────────────────────────────────────────────────────

_SALARY_PATTERNS = [
    # "$120,000 - $150,000"
    (r'\$\s*([\d,]+)\s*[-–—]\s*\$\s*([\d,]+)', "USD"),
    # "120k - 150k" / "120K-150K"
    (r'(\d{2,3})[kK]\s*[-–—]\s*(\d{2,3})[kK]', "USD_K"),
    # "AED 30,000 - 40,000"
    (r'AED\s*([\d,]+)\s*[-–—]\s*(?:AED\s*)?([\d,]+)', "AED"),
    # "SAR 25000 - 35000"
    (r'SAR\s*([\d,]+)\s*[-–—]\s*(?:SAR\s*)?([\d,]+)', "SAR"),
    # "£80,000 - £120,000"
    (r'[£]\s*([\d,]+)\s*[-–—]\s*[£]?\s*([\d,]+)', "GBP"),
    # "€70,000 - €90,000"
    (r'[€]\s*([\d,]+)\s*[-–—]\s*[€]?\s*([\d,]+)', "EUR"),
]

_PERIOD_PATTERNS = [
    (r'per\s*(?:year|annum|yr|pa)', "annual"),
    (r'per\s*month', "monthly"),
    (r'per\s*hour', "hourly"),
    (r'/\s*(?:yr|year|annum)', "annual"),
    (r'/\s*mo(?:nth)?', "monthly"),
    (r'/\s*hr', "hourly"),
]


def extract_salary(text: str) -> dict | None:
    """
    Extract salary range from job posting text.
    Returns {min, max, currency, period} or None.
    """
    if not text:
        return None

    for pattern, currency_hint in _SALARY_PATTERNS:
        match = re.search(pattern, text)
        if match:
            low_str = match.group(1).replace(",", "")
            high_str = match.group(2).replace(",", "")

            try:
                low = int(low_str)
                high = int(high_str)
            except ValueError:
                continue

            # Handle K suffix
            if currency_hint == "USD_K":
                low *= 1000
                high *= 1000
                currency_hint = "USD"

            # Detect period
            period = "annual"
            for p_pattern, p_name in _PERIOD_PATTERNS:
                if re.search(p_pattern, text, re.IGNORECASE):
                    period = p_name
                    break

            # Sanity check
            if low > high:
                low, high = high, low
            if low < 100 and period == "annual":
                continue  # Probably not a salary

            return {
                "min": low,
                "max": high,
                "currency": currency_hint,
                "period": period,
                "display": f"{currency_hint} {low:,} - {high:,} {period}",
            }

    return None


# ── Freshness scoring ─────────────────────────────────────────────────────────

def freshness_score(posted_date: str | None) -> dict:
    """
    Score how fresh a job posting is.
    Returns {score: 0-100, label: str, days_ago: int}.
    """
    if not posted_date:
        return {"score": 30, "label": "Unknown", "days_ago": None}

    try:
        dt = datetime.fromisoformat(posted_date.replace("Z", "+00:00"))
        days = (datetime.now(UTC) - dt).days
    except Exception:
        return {"score": 30, "label": "Unknown", "days_ago": None}

    if days <= 1:
        return {"score": 100, "label": "Just posted", "days_ago": days}
    if days <= 3:
        return {"score": 90, "label": "Very fresh", "days_ago": days}
    if days <= 7:
        return {"score": 75, "label": "This week", "days_ago": days}
    if days <= 14:
        return {"score": 55, "label": "Last 2 weeks", "days_ago": days}
    if days <= 30:
        return {"score": 35, "label": "This month", "days_ago": days}
    if days <= 60:
        return {"score": 15, "label": "Stale", "days_ago": days}
    return {"score": 5, "label": "Very old", "days_ago": days}


# ── Source quality ranking ────────────────────────────────────────────────────

_SOURCE_QUALITY = {
    # Direct company sources
    "company_careers": 100,
    "greenhouse": 95,
    "lever": 95,
    "workable": 90,
    "ashby": 90,

    # Major job boards
    "linkedin": 85,
    "indeed": 75,
    "glassdoor": 75,

    # Regional
    "bayt": 70,
    "gulftalent": 70,
    "naukrigulf": 65,

    # Aggregators
    "adzuna": 60,
    "jsearch": 55,
    "google": 50,

    # Generic/unknown
    "serper": 40,
    "other": 30,
}


def source_quality_score(source: str | None) -> int:
    """Score the quality/reliability of a job source (0-100)."""
    if not source:
        return 30
    return _SOURCE_QUALITY.get(source.lower(), 30)


# ── Combined job scoring ──────────────────────────────────────────────────────

def score_job(job: dict) -> dict:
    """
    Enrich a job listing with salary, freshness, and source quality.
    Adds fields to the job dict (non-destructive).
    """
    text = f"{job.get('title', '')} {job.get('snippet', '')} {job.get('description', '')}"

    salary = extract_salary(text)
    fresh = freshness_score(job.get("posted_date"))
    source_q = source_quality_score(job.get("source"))

    # Composite relevance score
    composite = round(
        fresh["score"] * 0.4
        + source_q * 0.3
        + (70 if salary else 30) * 0.3  # Having salary info is a positive signal
    )

    return {
        **job,
        "salary_extracted": salary,
        "freshness": fresh,
        "source_quality": source_q,
        "relevance_score": composite,
    }


def rank_jobs(jobs: list[dict]) -> list[dict]:
    """Score and rank a list of jobs by composite relevance."""
    scored = [score_job(j) for j in jobs]
    scored.sort(key=lambda j: j.get("relevance_score", 0), reverse=True)
    return scored
