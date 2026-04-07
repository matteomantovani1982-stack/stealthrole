"""
app/services/scout/crunchbase_provider.py

Crunchbase API provider for the Hidden Market Engine.

Fetches verified signal data:
  - Recent funding rounds (amount, date, lead investor, stage)
  - Leadership changes (people moving in/out of C-suite)
  - Company info (description, location, employee count, status)

Crunchbase Basic API: https://data.crunchbase.com/docs
Rate limit: 200 calls/minute on Basic plan.

Returns Signal objects compatible with signal_engine.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, UTC, timedelta

import httpx
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)

CRUNCHBASE_API = "https://api.crunchbase.com/api/v4"
TIMEOUT = 15.0


@dataclass
class FundingRound:
    """Structured funding round from Crunchbase."""
    company: str
    amount_usd: int | None
    currency: str
    round_type: str         # seed, series_a, series_b, etc.
    announced_on: str
    lead_investors: list[str]
    num_investors: int
    source_url: str


@dataclass
class LeadershipChange:
    """Structured leadership change from Crunchbase."""
    company: str
    person_name: str
    title: str
    started_on: str | None
    ended_on: str | None
    is_current: bool
    source_url: str


def _headers() -> dict:
    return {"X-cb-user-key": settings.crunchbase_api_key}


def _recency_score(date_str: str) -> float:
    """Calculate recency score (0-1) from a date string."""
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        days_ago = (datetime.now(UTC) - dt).days
        if days_ago <= 7:
            return 1.0
        elif days_ago <= 30:
            return 0.8
        elif days_ago <= 90:
            return 0.5
        elif days_ago <= 180:
            return 0.3
        return 0.1
    except Exception:
        return 0.3


# ── Funding Signals ───────────────────────────────────────────────────────────

def fetch_funding_signals(
    region: str,
    sectors: list[str],
    roles: list[str],
    days_back: int = 90,
    limit: int = 10,
) -> list[dict]:
    """
    Fetch recent funding rounds from Crunchbase.
    Returns Signal-compatible dicts for signal_engine integration.
    """
    if not settings.crunchbase_api_key:
        return []

    signals = []
    cutoff = (datetime.now(UTC) - timedelta(days=days_back)).strftime("%Y-%m-%d")

    # Build search query for funded companies in target region/sectors
    query_parts = [region]
    if sectors:
        query_parts.extend(sectors[:3])

    try:
        # Search for organizations with recent funding
        with httpx.Client(timeout=TIMEOUT) as client:
            resp = client.post(
                f"{CRUNCHBASE_API}/searches/funding_rounds",
                headers=_headers(),
                json={
                    "field_ids": [
                        "identifier", "funded_organization_identifier",
                        "money_raised", "announced_on", "investment_type",
                        "lead_investor_identifiers", "num_investors",
                    ],
                    "query": [
                        {
                            "type": "predicate",
                            "field_id": "announced_on",
                            "operator_id": "gte",
                            "values": [cutoff],
                        },
                    ],
                    "order": [
                        {"field_id": "announced_on", "sort": "desc"},
                    ],
                    "limit": limit,
                },
            )

            if resp.status_code != 200:
                logger.warning("crunchbase_funding_error", status=resp.status_code, body=resp.text[:200])
                return []

            data = resp.json()

            for entity in data.get("entities", []):
                props = entity.get("properties", {})
                org = props.get("funded_organization_identifier", {})
                company_name = org.get("value", "Unknown")
                permalink = org.get("permalink", "")

                amount = props.get("money_raised", {}).get("value")
                currency = props.get("money_raised", {}).get("currency", "USD")
                round_type = props.get("investment_type", "unknown")
                announced = props.get("announced_on", "")

                lead_investors = [
                    inv.get("value", "")
                    for inv in props.get("lead_investor_identifiers", [])
                ]

                # Format amount for display
                amount_str = ""
                if amount:
                    if amount >= 1_000_000_000:
                        amount_str = f"${amount / 1_000_000_000:.1f}B"
                    elif amount >= 1_000_000:
                        amount_str = f"${amount / 1_000_000:.0f}M"
                    else:
                        amount_str = f"${amount / 1_000:.0f}K"

                round_display = round_type.replace("_", " ").title()
                lead_str = ", ".join(lead_investors[:2]) if lead_investors else "undisclosed investors"

                headline = f"{company_name} raised {amount_str} ({round_display})" if amount_str else f"{company_name} completed {round_display} round"
                detail = f"Led by {lead_str}. Announced {announced}."

                source_url = f"https://www.crunchbase.com/funding_round/{permalink}" if permalink else ""

                signals.append({
                    "company": company_name,
                    "signal_type": "funding",
                    "headline": headline,
                    "detail": detail,
                    "source_url": source_url,
                    "source_name": "Crunchbase",
                    "published_date": announced,
                    "recency_score": _recency_score(announced) if announced else 0.3,
                    "raw_snippet": f"{round_display}: {amount_str} from {lead_str}",
                    # Extra structured data for enrichment
                    "funding_amount_usd": amount,
                    "funding_round_type": round_type,
                    "lead_investors": lead_investors,
                    "evidence_tier": "strong",  # Crunchbase = authoritative
                })

    except httpx.TimeoutException:
        logger.warning("crunchbase_funding_timeout")
    except Exception as e:
        logger.error("crunchbase_funding_error", error=str(e))

    logger.info("crunchbase_funding_done", count=len(signals))
    return signals


# ── Leadership Signals ────────────────────────────────────────────────────────

def fetch_leadership_signals(
    region: str,
    sectors: list[str],
    days_back: int = 90,
    limit: int = 10,
) -> list[dict]:
    """
    Fetch recent C-suite changes from Crunchbase people search.
    Returns Signal-compatible dicts.
    """
    if not settings.crunchbase_api_key:
        return []

    signals = []
    cutoff = (datetime.now(UTC) - timedelta(days=days_back)).strftime("%Y-%m-%d")

    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            # Search for people with recent job changes at C-suite level
            resp = client.post(
                f"{CRUNCHBASE_API}/searches/people",
                headers=_headers(),
                json={
                    "field_ids": [
                        "identifier", "first_name", "last_name",
                        "primary_job_title", "primary_organization",
                    ],
                    "query": [
                        {
                            "type": "predicate",
                            "field_id": "primary_job_title",
                            "operator_id": "contains",
                            "values": ["Chief", "CEO", "COO", "CTO", "CFO", "VP", "Head of"],
                        },
                    ],
                    "order": [
                        {"field_id": "updated_at", "sort": "desc"},
                    ],
                    "limit": limit,
                },
            )

            if resp.status_code != 200:
                logger.warning("crunchbase_leadership_error", status=resp.status_code)
                return []

            data = resp.json()

            for entity in data.get("entities", []):
                props = entity.get("properties", {})
                first = props.get("first_name", "")
                last = props.get("last_name", "")
                person_name = f"{first} {last}".strip()
                title = props.get("primary_job_title", "")
                org = props.get("primary_organization", {})
                company_name = org.get("value", "Unknown")
                permalink = org.get("permalink", "")

                headline = f"{person_name} appointed {title} at {company_name}"
                detail = f"Leadership change detected via Crunchbase."
                source_url = f"https://www.crunchbase.com/organization/{permalink}" if permalink else ""

                signals.append({
                    "company": company_name,
                    "signal_type": "leadership",
                    "headline": headline,
                    "detail": detail,
                    "source_url": source_url,
                    "source_name": "Crunchbase",
                    "published_date": "",
                    "recency_score": 0.7,  # Recent by definition (sorted by updated_at)
                    "raw_snippet": f"{person_name}: {title} at {company_name}",
                    "person_name": person_name,
                    "person_title": title,
                    "evidence_tier": "strong",
                })

    except httpx.TimeoutException:
        logger.warning("crunchbase_leadership_timeout")
    except Exception as e:
        logger.error("crunchbase_leadership_error", error=str(e))

    logger.info("crunchbase_leadership_done", count=len(signals))
    return signals


# ── Company Enrichment ────────────────────────────────────────────────────────

def enrich_company(company_name: str) -> dict | None:
    """
    Look up a company on Crunchbase and return enrichment data.
    Used to upgrade evidence tier for signals from other sources.
    """
    if not settings.crunchbase_api_key:
        return None

    try:
        # Slugify company name for permalink lookup
        slug = company_name.lower().strip().replace(" ", "-")

        with httpx.Client(timeout=TIMEOUT) as client:
            resp = client.get(
                f"{CRUNCHBASE_API}/entities/organizations/{slug}",
                headers=_headers(),
                params={
                    "field_ids": "short_description,location_identifiers,num_employees_enum,funding_total,last_funding_type,founded_on,categories",
                },
            )

            if resp.status_code != 200:
                return None

            data = resp.json()
            props = data.get("properties", {})

            return {
                "description": props.get("short_description", ""),
                "location": ", ".join(
                    loc.get("value", "") for loc in props.get("location_identifiers", [])
                ),
                "employee_range": props.get("num_employees_enum", ""),
                "total_funding_usd": props.get("funding_total", {}).get("value"),
                "last_funding_type": props.get("last_funding_type", ""),
                "founded_on": props.get("founded_on", ""),
                "categories": [c.get("value", "") for c in props.get("categories", [])],
                "source": "crunchbase",
            }

    except Exception as e:
        logger.debug("crunchbase_enrich_failed", company=company_name, error=str(e))
        return None
