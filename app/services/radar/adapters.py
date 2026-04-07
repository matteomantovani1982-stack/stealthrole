"""
app/services/radar/adapters.py

Source adapters — normalize raw data from each source into RadarInput.

Each adapter:
  1. Converts source-specific data into RadarInput
  2. Assigns an evidence_tier (strong/medium/weak/speculative)

Evidence tier rules:
  strong      — posted job with salary, OR signal from authoritative source with explicit hiring mention
  medium      — posted job without salary, OR verifiable signal (funding with amount, named exec change)
  weak        — single low-authority source, or hiring surge of only 3 postings
  speculative — role inferred from signal type alone with no evidence the company needs THIS role
"""

from app.services.radar.types import RadarInput

# Sources considered authoritative for signal classification
_AUTHORITATIVE_SOURCES = {
    "techcrunch", "bloomberg", "reuters", "ft.com", "wsj",
    "crunchbase", "magnitt", "linkedin", "forbes", "wamda",
}


def _is_authoritative(url: str) -> bool:
    url_lower = url.lower()
    return any(s in url_lower for s in _AUTHORITATIVE_SOURCES)


def adapt_signal_card(card: dict) -> RadarInput:
    """Adapt an OpportunityCard from the existing signal engine."""
    signals = card.get("signals", [])
    signal_type = signals[0].get("signal_type", "unknown") if signals else "unknown"
    is_posted = card.get("is_posted", False)
    fit_score = card.get("fit_score", 50)

    # Evidence tier for signal engine cards
    if is_posted and fit_score >= 70:
        tier = "strong"
    elif is_posted or (len(signals) >= 2 and fit_score >= 50):
        tier = "medium"
    elif fit_score >= 40:
        tier = "weak"
    else:
        tier = "speculative"

    return RadarInput(
        company=card.get("company", ""),
        role=card.get("suggested_role") or card.get("posted_title"),
        location=card.get("location"),
        sector=card.get("sector"),
        source_type="signal_engine",
        signal_type=signal_type,
        headline=card.get("signal_summary", ""),
        detail="",
        source_url=card.get("apply_url", ""),
        confidence=fit_score / 100.0,
        detected_at=None,
        salary=card.get("salary_estimate"),
        is_posted=is_posted,
        evidence_tier=tier,
        fit_score_precomputed=fit_score,
        fit_reasons=card.get("fit_reasons", []),
        red_flags=card.get("red_flags", []),
        outreach_hook=card.get("outreach_hook", ""),
    )


def adapt_scout_job(job: dict) -> RadarInput:
    """Adapt a job from Adzuna/JSearch/Serper scout results."""
    has_salary = bool(job.get("salary"))
    has_description = len(job.get("snippet", "")) > 100

    # Posted jobs are inherently strong evidence — the role exists
    if has_salary and has_description:
        tier = "strong"
    elif has_salary or has_description:
        tier = "medium"  # real job, just less detail
    else:
        tier = "medium"  # still a real posting

    return RadarInput(
        company=job.get("company", ""),
        role=job.get("title", ""),
        location=job.get("location"),
        sector=None,
        source_type="job_board",
        signal_type="posted_job",
        headline=job.get("title", ""),
        detail=job.get("snippet", ""),
        source_url=job.get("url", ""),
        confidence=1.0,
        detected_at=job.get("posted_date"),
        salary=job.get("salary"),
        is_posted=True,
        evidence_tier=tier,
        platform=job.get("source"),
    )


def adapt_hidden_signal(signal: dict) -> RadarInput:
    """
    Adapt a HiddenSignal row.

    Evidence tier depends on:
    - Whether likely_roles were Claude-enriched (not empty) vs guessed
    - Signal confidence from the detection engine
    - Whether source is authoritative
    """
    likely_roles = signal.get("likely_roles", [])
    confidence = signal.get("confidence", 0.5)
    source_url = signal.get("source_url", "")
    reasoning = signal.get("reasoning", "")
    evidence_basis = signal.get("evidence_basis", "")

    # Determine evidence tier
    has_roles = bool(likely_roles)
    authoritative = _is_authoritative(source_url)
    has_reasoning = len(reasoning) > 50
    provider = signal.get("provider", "")
    stored_tier = signal.get("evidence_tier", "")

    # Direct API providers (Crunchbase, MAGNiTT) → trust their evidence tier
    if stored_tier == "strong" and provider in ("crunchbase", "magnitt"):
        tier = "strong"
    # Pattern-only evidence is always speculative regardless of confidence
    elif evidence_basis == "pattern_only":
        tier = "speculative"
    elif not has_roles:
        tier = "speculative"
    elif has_roles and confidence >= 0.7 and (authoritative or has_reasoning):
        tier = "medium"
    elif has_roles and confidence >= 0.5:
        tier = "weak"
    else:
        tier = "weak"

    # Extract location/sector from signal_data if available
    signal_data = signal.get("signal_data") or {}

    return RadarInput(
        company=signal.get("company_name", ""),
        role=likely_roles[0] if likely_roles else None,
        location=signal_data.get("location"),
        sector=signal_data.get("sector"),
        source_type="hidden_market",
        signal_type=signal.get("signal_type", ""),
        headline=f"{signal.get('company_name', '')}: {signal.get('signal_type', '')}",
        detail=reasoning,
        source_url=source_url,
        confidence=confidence,
        detected_at=signal.get("created_at"),
        salary=None,
        is_posted=False,
        evidence_tier=tier,
    )


# Phase 2 stubs
def adapt_email_signal(event: dict) -> RadarInput:
    """Stub for Email Intelligence adapter (Phase 2)."""
    return RadarInput(company="", source_type="email_intelligence", evidence_tier="speculative")


def adapt_linkedin_signal(signal: dict) -> RadarInput:
    """
    Adapt a LinkedIn connection signal into RadarInput.
    Signal comes from a connection at a target company who is a recruiter
    or hiring manager — indicates the company is actively hiring.
    """
    company = signal.get("current_company", "")
    title = signal.get("current_title", "")
    is_recruiter = signal.get("is_recruiter", False)
    name = signal.get("full_name", "")

    if not company:
        return RadarInput(company="", source_type="linkedin", evidence_tier="speculative")

    # Recruiter at a company = medium evidence (they exist but no posted role)
    # Hiring manager = weak evidence (they might be hiring for their team)
    tier = "medium" if is_recruiter else "weak"
    headline = f"{name} ({title}) at {company}" if name else f"{title} at {company}"

    return RadarInput(
        company=company,
        role=None,
        location=None,
        sector=None,
        source_type="linkedin",
        signal_type="network_connection",
        headline=headline,
        detail=f"You know {name} at {company} — warm intro possible",
        source_url=signal.get("linkedin_url", ""),
        confidence=0.6 if is_recruiter else 0.3,
        is_posted=False,
        evidence_tier=tier,
    )
