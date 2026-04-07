"""
app/services/scout/magnitt_provider.py

MAGNiTT API provider for MENA startup signals.

MAGNiTT is the leading startup data platform for the MENA region.
Provides authoritative data on:
  - Funding rounds (GCC, Egypt, Turkey, Pakistan)
  - Startup profiles (sector, stage, team size)
  - Investor activity in the region

API docs: https://magnitt.com/api (requires enterprise key)

Returns Signal-compatible dicts for signal_engine integration.
Gracefully returns empty list if API key not configured.
"""

from __future__ import annotations

from datetime import datetime, UTC, timedelta

import httpx
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)

MAGNITT_API = "https://api.magnitt.com/v1"
TIMEOUT = 15.0


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.magnitt_api_key}",
        "Accept": "application/json",
    }


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


# ── Funding Signals (MENA) ────────────────────────────────────────────────────

def fetch_mena_funding_signals(
    sectors: list[str],
    days_back: int = 90,
    limit: int = 15,
) -> list[dict]:
    """
    Fetch recent MENA startup funding from MAGNiTT.
    Returns Signal-compatible dicts.
    """
    if not settings.magnitt_api_key:
        return []

    signals = []
    cutoff = (datetime.now(UTC) - timedelta(days=days_back)).strftime("%Y-%m-%d")

    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            params: dict = {
                "sort": "-announced_date",
                "limit": limit,
                "date_from": cutoff,
            }
            if sectors:
                params["industry"] = ",".join(sectors[:3])

            resp = client.get(
                f"{MAGNITT_API}/funding-rounds",
                headers=_headers(),
                params=params,
            )

            if resp.status_code != 200:
                logger.warning("magnitt_funding_error", status=resp.status_code, body=resp.text[:200])
                return []

            data = resp.json()

            for round_data in data.get("data", []):
                company_name = round_data.get("startup_name", "Unknown")
                amount = round_data.get("amount")
                currency = round_data.get("currency", "USD")
                round_type = round_data.get("funding_type", "unknown")
                announced = round_data.get("announced_date", "")
                country = round_data.get("country", "")
                industry = round_data.get("industry", "")
                investors = round_data.get("investors", [])

                # Format amount
                amount_str = ""
                if amount:
                    if amount >= 1_000_000:
                        amount_str = f"${amount / 1_000_000:.0f}M"
                    elif amount >= 1_000:
                        amount_str = f"${amount / 1_000:.0f}K"
                    else:
                        amount_str = f"${amount}"

                investor_names = [inv.get("name", "") for inv in investors[:3]] if isinstance(investors, list) else []
                lead_str = ", ".join(investor_names) if investor_names else "undisclosed"

                round_display = round_type.replace("_", " ").title()
                headline = f"{company_name} ({country}) raised {amount_str}" if amount_str else f"{company_name} ({country}) closed {round_display}"
                detail = f"{round_display} round. Industry: {industry}. Investors: {lead_str}."

                signals.append({
                    "company": company_name,
                    "signal_type": "funding",
                    "headline": headline,
                    "detail": detail,
                    "source_url": f"https://magnitt.com/startups/{company_name.lower().replace(' ', '-')}",
                    "source_name": "MAGNiTT",
                    "published_date": announced,
                    "recency_score": _recency_score(announced) if announced else 0.3,
                    "raw_snippet": f"{round_display}: {amount_str} — {country} / {industry}",
                    "funding_amount_usd": amount,
                    "funding_round_type": round_type,
                    "lead_investors": investor_names,
                    "location": country,
                    "sector": industry,
                    "evidence_tier": "strong",  # MAGNiTT = authoritative for MENA
                })

    except httpx.TimeoutException:
        logger.warning("magnitt_funding_timeout")
    except Exception as e:
        logger.error("magnitt_funding_error", error=str(e))

    logger.info("magnitt_funding_done", count=len(signals))
    return signals


# ── Startup Enrichment (MENA) ─────────────────────────────────────────────────

def enrich_mena_startup(company_name: str) -> dict | None:
    """
    Look up a MENA startup on MAGNiTT for enrichment data.
    """
    if not settings.magnitt_api_key:
        return None

    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            resp = client.get(
                f"{MAGNITT_API}/startups",
                headers=_headers(),
                params={"search": company_name, "limit": 1},
            )

            if resp.status_code != 200:
                return None

            data = resp.json()
            results = data.get("data", [])
            if not results:
                return None

            startup = results[0]
            return {
                "name": startup.get("name", ""),
                "description": startup.get("description", ""),
                "country": startup.get("country", ""),
                "city": startup.get("city", ""),
                "industry": startup.get("industry", ""),
                "stage": startup.get("stage", ""),
                "team_size": startup.get("team_size", ""),
                "total_funding": startup.get("total_funding", ""),
                "founded_year": startup.get("founded_year", ""),
                "source": "magnitt",
            }

    except Exception as e:
        logger.debug("magnitt_enrich_failed", company=company_name, error=str(e))
        return None
