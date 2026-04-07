"""
app/services/scout/hidden_market.py

Hidden Market Intelligence Engine.

Detects companies likely hiring BEFORE jobs are posted by analysing:
  1. Adzuna employer posting frequency (surge detection)
  2. News classification via Claude Haiku (funding, leadership, expansion)

Each detected signal is stored in the hidden_signals table and returned
to the dashboard / OpportunityRadar / WhatsApp alerts.
"""

import hashlib
import json
import re
from collections import Counter
from datetime import UTC, datetime, timedelta

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.hidden_signal import HiddenSignal

logger = structlog.get_logger(__name__)

TIMEOUT = 12.0
# Cache: don't re-scan if last scan < 30 min ago
SCAN_COOLDOWN_MINUTES = 30


class HiddenMarketService:
    """
    Detects hidden market signals and persists them to the database.

    Usage:
        svc = HiddenMarketService(db)
        signals = await svc.detect_signals(user_id)
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def detect_signals(self, user_id: str) -> list[HiddenSignal]:
        """
        Main entry point. Returns existing fresh signals or runs a new scan.
        """
        # Check for fresh signals (< 30 min old)
        cutoff = datetime.now(UTC) - timedelta(minutes=SCAN_COOLDOWN_MINUTES)
        q = (
            select(HiddenSignal)
            .where(
                HiddenSignal.user_id == user_id,
                HiddenSignal.created_at >= cutoff,
            )
            .order_by(HiddenSignal.created_at.desc())
            .limit(20)
        )
        cached = (await self.db.execute(q)).scalars().all()
        if cached:
            logger.info("hidden_market_cache_hit", user_id=user_id, count=len(cached))
            return list(cached)

        # Load user preferences for targeted scanning
        prefs = await self._load_user_prefs(user_id)

        # Run detection
        new_signals = await self._run_detection(user_id, prefs)

        logger.info("hidden_market_scan_complete", user_id=user_id, new_signals=len(new_signals))
        return new_signals

    async def _load_user_prefs(self, user_id: str) -> dict:
        """Load user's candidate profile preferences."""
        from app.services.profile.profile_service import ProfileService
        svc = ProfileService(self.db)
        profile = await svc.get_active_profile(user_id)
        if not profile:
            return {"regions": ["UAE"], "sectors": ["tech"], "roles": ["Director"]}

        prefs = profile.preferences or {}
        if not prefs and profile.global_context:
            try:
                ctx = json.loads(profile.global_context)
                prefs = ctx.get("__preferences", {})
            except (json.JSONDecodeError, TypeError):
                pass

        return {
            "regions": prefs.get("regions", ["UAE"]),
            "sectors": prefs.get("sectors", ["tech", "fintech"]),
            "roles": prefs.get("roles", ["Director", "VP"]),
        }

    async def _run_detection(self, user_id: str, prefs: dict) -> list[HiddenSignal]:
        """Run all detection sources and persist results."""
        import asyncio

        all_raw_signals = []

        # Source 1: Adzuna employer surge detection
        loop = asyncio.get_running_loop()
        adzuna_signals = await loop.run_in_executor(
            None, _detect_adzuna_surges, prefs
        )
        all_raw_signals.extend(adzuna_signals)

        # Source 2: News-based signal classification (Serper + Claude Haiku)
        news_signals = await loop.run_in_executor(
            None, _detect_news_signals, prefs
        )
        all_raw_signals.extend(news_signals)

        # Source 3: Crunchbase (verified funding + leadership)
        crunchbase_signals = await loop.run_in_executor(
            None, _detect_crunchbase_signals, prefs
        )
        all_raw_signals.extend(crunchbase_signals)

        # Source 4: MAGNiTT (MENA startup funding)
        magnitt_signals = await loop.run_in_executor(
            None, _detect_magnitt_signals, prefs
        )
        all_raw_signals.extend(magnitt_signals)

        if not all_raw_signals:
            logger.info("hidden_market_no_signals", user_id=user_id)
            return []

        # Deduplicate by company+signal_type
        seen = set()
        unique = []
        for sig in all_raw_signals:
            key = f"{sig['company'].lower().strip()}:{sig['signal_type']}"
            if key not in seen:
                seen.add(key)
                unique.append(sig)

        # Classify with Claude Haiku if API key available
        if settings.anthropic_api_key and unique:
            enriched = await loop.run_in_executor(
                None, _enrich_with_claude, unique, prefs
            )
            unique = enriched

        # Persist to database
        new_signals = []
        for sig in unique[:20]:  # Cap at 20 per scan
            # Build structured signal_data for enrichment
            signal_data = {}
            for key in ("funding_amount_usd", "funding_round_type", "lead_investors",
                        "person_name", "person_title", "location", "sector"):
                if key in sig:
                    signal_data[key] = sig[key]

            hs = HiddenSignal(
                user_id=user_id,
                company_name=sig["company"][:255],
                signal_type=sig["signal_type"],
                confidence=sig.get("confidence", 0.5),
                likely_roles=sig.get("likely_roles", []),
                reasoning=sig.get("reasoning", ""),
                source_url=sig.get("source_url", ""),
                source_name=sig.get("source_name", ""),
                signal_data=signal_data if signal_data else None,
                evidence_tier=sig.get("evidence_tier", "medium"),
                provider=sig.get("provider", sig.get("source_name", "").lower() or None),
            )
            self.db.add(hs)
            new_signals.append(hs)

        try:
            await self.db.commit()
            # Refresh to get IDs and timestamps
            for sig in new_signals:
                await self.db.refresh(sig)
        except Exception as e:
            logger.error("hidden_market_persist_failed", error=str(e))
            await self.db.rollback()
            return []

        return new_signals


# ── Source 1: Adzuna Employer Surge Detection ────────────────────────────────

def _detect_adzuna_surges(prefs: dict) -> list[dict]:
    """
    Detect companies with unusual posting volume on Adzuna.

    Strategy: Search for jobs in user's target regions/roles, count
    postings per employer. Companies with 3+ recent postings = hiring surge.
    """
    if not settings.adzuna_app_id or not settings.adzuna_app_key:
        return []

    from app.api.routes.scout import REGION_TO_ADZUNA

    signals = []
    regions = prefs.get("regions", ["UAE"])
    roles = prefs.get("roles", ["Director"])
    keywords = " ".join(roles[:2])

    for region in regions[:2]:  # Cap at 2 regions to conserve API calls
        rc, city = REGION_TO_ADZUNA.get(region, ("gb", region))
        try:
            r = httpx.get(
                f"https://api.adzuna.com/v1/api/jobs/{rc}/search/1",
                params={
                    "app_id": settings.adzuna_app_id,
                    "app_key": settings.adzuna_app_key,
                    "what": keywords,
                    "where": city,
                    "results_per_page": 50,
                    "content-type": "application/json",
                    "sort_by": "date",
                },
                timeout=TIMEOUT,
            )
            r.raise_for_status()
            results = r.json().get("results", [])

            # Count postings per company
            company_counts: Counter = Counter()
            company_data: dict[str, list[dict]] = {}
            for item in results:
                company_name = (item.get("company", {}).get("display_name", "") or "").strip()
                if not company_name or len(company_name) < 3:
                    continue
                company_counts[company_name] += 1
                company_data.setdefault(company_name, []).append(item)

            # Companies with 3+ postings = hiring surge
            for company, count in company_counts.most_common(10):
                if count >= 3:
                    sample_titles = [
                        item.get("title", "")[:80]
                        for item in company_data[company][:5]
                    ]
                    signals.append({
                        "company": company,
                        "signal_type": "hiring_surge",
                        "confidence": min(0.9, 0.5 + count * 0.1),
                        "likely_roles": sample_titles[:3],
                        "reasoning": (
                            f"{company} has {count} open positions in {region}. "
                            f"Recent roles: {', '.join(sample_titles[:3])}. "
                            f"High posting volume suggests active expansion."
                        ),
                        "source_url": f"https://www.adzuna.co.{rc}/search?q={company.replace(' ', '+')}",
                        "source_name": "adzuna",
                    })

            logger.info("adzuna_surge_scan", region=region, companies_with_surge=len([c for c, n in company_counts.items() if n >= 3]))

        except Exception as e:
            logger.warning("adzuna_surge_scan_failed", region=region, error=str(e))

    return signals


# ── Source 2: News-Based Signal Detection ────────────────────────────────────

SIGNAL_KEYWORDS = {
    "funding": [
        "raises", "raised", "funding", "series a", "series b", "series c",
        "seed round", "investment", "backed", "venture", "million", "billion",
    ],
    "leadership": [
        "appoints", "appointed", "names", "joins as", "promoted", "steps down",
        "resigns", "new ceo", "new coo", "new cfo", "new cto",
    ],
    "expansion": [
        "expands", "expansion", "launches", "enters", "new market", "opens office",
        "new office", "partnership", "joint venture",
    ],
    "product_launch": [
        "launches product", "new product", "announces platform", "releases",
        "unveils", "introduces",
    ],
}


def _detect_news_signals(prefs: dict) -> list[dict]:
    """
    Search news via Serper for hiring signals in target sectors/regions.
    Falls back gracefully if Serper is unavailable.
    """
    if not settings.serper_api_key:
        # Fallback: return empty (Serper out of credits)
        return []

    regions = prefs.get("regions", ["UAE"])
    sectors = prefs.get("sectors", ["tech"])
    region_str = " ".join(regions[:2])
    sector_str = " ".join(sectors[:2])

    queries = [
        f"startup funding {region_str} {sector_str} 2026",
        f"company expansion {region_str} new office 2026",
        f"CEO CTO appointed {region_str} {sector_str} 2026",
        f"product launch {region_str} {sector_str} 2026",
    ]

    signals = []
    seen_urls = set()

    for query in queries:
        try:
            r = httpx.post(
                "https://google.serper.dev/news",
                headers={
                    "X-API-KEY": settings.serper_api_key,
                    "Content-Type": "application/json",
                },
                json={"q": query, "num": 8},
                timeout=TIMEOUT,
            )
            r.raise_for_status()
            news_items = r.json().get("news", [])

            for item in news_items:
                url = item.get("link", "")
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                title = item.get("title", "")
                snippet = item.get("snippet", "")
                text = f"{title} {snippet}".lower()

                # Classify signal type
                signal_type = _classify_text(text)
                if not signal_type:
                    continue

                # Extract company name from title
                company = _extract_company(title)
                if not company or len(company) < 3:
                    continue

                signals.append({
                    "company": company,
                    "signal_type": signal_type,
                    "confidence": 0.6,  # Will be refined by Claude
                    "likely_roles": [],  # Will be filled by Claude
                    "reasoning": snippet[:500],
                    "source_url": url,
                    "source_name": _source_label(url),
                })

        except Exception as e:
            logger.warning("serper_news_signal_failed", query=query[:60], error=str(e))

    return signals


def _classify_text(text: str) -> str | None:
    """Classify text into signal type using keyword matching."""
    for signal_type, keywords in SIGNAL_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return signal_type
    return None


def _extract_company(title: str) -> str:
    """Extract company name from a news title."""
    for sep in [" raises ", " appoints ", " acquires ", " launches ", " expands ",
                " names ", " secures ", " closes ", " announces "]:
        if sep in title.lower():
            return title.split(sep, 1)[0].strip()[:80]
    # Fallback: take first part before common separators
    for sep in [" - ", " | ", " — ", ": "]:
        if sep in title:
            return title.split(sep, 1)[0].strip()[:80]
    return ""


def _source_label(url: str) -> str:
    """Map URL to a human-readable source name."""
    labels = {
        "techcrunch": "TechCrunch", "bloomberg": "Bloomberg",
        "reuters": "Reuters", "linkedin": "LinkedIn",
        "crunchbase": "Crunchbase", "magnitt": "MAGNiTT",
        "wamda": "Wamda", "zawya": "Zawya",
        "arabianbusiness": "Arabian Business", "forbes": "Forbes",
    }
    for key, label in labels.items():
        if key in url.lower():
            return label
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc.replace("www.", "").split(".")[0].capitalize()
    except Exception:
        return "Web"


# ── Claude Haiku Enrichment ──────────────────────────────────────────────────

CLASSIFY_SYSTEM = """You are a senior executive recruiter analysing market signals.

For each company signal, answer EACH question with specific evidence from the signal text.
If there is no evidence, write "NO EVIDENCE" — do not guess.

For each signal determine:

1. WHAT does this company do? (sector, product, stage — based on signal text only)
2. WHY would they hire? (what specific business problem does this signal create?)
3. WHAT role specifically? (one PRIMARY role title — not "various roles")
   - The role must be logically connected to the signal.
   - Funding → likely needs to scale a team (which team depends on what they do)
   - Leadership departure → likely needs a replacement (for THAT specific function)
   - Expansion → likely needs regional leadership (for THAT market)
   - Do NOT suggest roles unrelated to the signal.
4. WHY NOW? (what's the timeline? Is this imminent or speculative?)
5. WHAT EVIDENCE supports this role inference? (quote signal text or write "PATTERN ONLY")
6. CONFIDENCE: Rate as one of:
   - strong (0.8-1.0): signal explicitly mentions hiring, or the role is a direct logical consequence
   - medium (0.5-0.7): strong inference but no explicit hiring mention
   - weak (0.3-0.4): plausible but could mean many things
   - speculative (0.1-0.2): pure guess based on signal type pattern alone

CRITICAL: If evidence is "PATTERN ONLY", confidence MUST be weak or speculative.
Do NOT present speculative role inferences as strong opportunities.

Return ONLY a JSON array:
[
  {
    "company": "CompanyName",
    "signal_type": "funding",
    "confidence": 0.6,
    "likely_roles": ["VP Engineering"],
    "reasoning": "Why this company: [sector/context]. Why this role: [specific connection to signal]. Evidence: [quote or PATTERN ONLY].",
    "evidence_basis": "direct|inference|pattern_only"
  }
]

RETURN ONLY JSON. No preamble."""


def _enrich_with_claude(signals: list[dict], prefs: dict) -> list[dict]:
    """Use Claude Haiku to enrich raw signals with confidence, roles, reasoning."""
    if not signals:
        return signals

    from app.services.llm.client import ClaudeClient

    # Build prompt with signal summaries
    signal_text = ""
    for i, sig in enumerate(signals[:15]):  # Cap at 15 for token efficiency
        signal_text += (
            f"\n{i+1}. {sig['company']} [{sig['signal_type']}]\n"
            f"   Source: {sig.get('source_name', 'web')}\n"
            f"   Detail: {sig.get('reasoning', '')[:200]}\n"
        )

    user_prompt = (
        f"Target roles: {', '.join(prefs.get('roles', []))}\n"
        f"Target regions: {', '.join(prefs.get('regions', []))}\n"
        f"Target sectors: {', '.join(prefs.get('sectors', []))}\n\n"
        f"SIGNALS DETECTED:\n{signal_text}\n\n"
        f"Analyse each signal. Return enriched JSON array."
    )

    try:
        from app.services.llm.router import LLMTask
        client = ClaudeClient(task=LLMTask.SIGNAL_ENRICHMENT, max_tokens=4000)
        raw_text, result = client.call_raw(
            system_prompt=CLASSIFY_SYSTEM,
            user_prompt=user_prompt,
            temperature=0.2,
        )

        # Parse JSON array from response
        text = raw_text.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```\s*$", "", text).strip()

        # Find the JSON array
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1:
            enriched = json.loads(text[start:end + 1])
        else:
            enriched = json.loads(text)

        # Merge enriched data back into signals
        enriched_map = {e["company"].lower().strip(): e for e in enriched if isinstance(e, dict)}
        for sig in signals:
            key = sig["company"].lower().strip()
            if key in enriched_map:
                e = enriched_map[key]
                evidence_basis = e.get("evidence_basis", "pattern_only")
                raw_confidence = e.get("confidence", sig.get("confidence", 0.5))

                # Enforce: pattern_only evidence MUST have weak/speculative confidence
                if evidence_basis == "pattern_only" and raw_confidence > 0.4:
                    raw_confidence = 0.3  # cap at weak

                sig["confidence"] = raw_confidence
                sig["likely_roles"] = e.get("likely_roles", sig.get("likely_roles", []))
                sig["reasoning"] = e.get("reasoning", sig.get("reasoning", ""))
                sig["evidence_basis"] = evidence_basis

        logger.info(
            "hidden_market_claude_enrichment",
            signals_enriched=len(enriched_map),
            tokens=result.input_tokens + result.output_tokens,
            cost=result.cost_usd,
        )

    except Exception as e:
        logger.warning("hidden_market_claude_enrichment_failed", error=str(e))
        # Non-fatal — return signals with original data

    return signals


# ── Source 3: Crunchbase Direct API ───────────────────────────────────────────

def _detect_crunchbase_signals(prefs: dict) -> list[dict]:
    """
    Fetch verified signals from Crunchbase API.
    Returns raw signal dicts with evidence_tier=strong.
    """
    from app.services.scout.crunchbase_provider import fetch_funding_signals, fetch_leadership_signals

    regions = prefs.get("regions", ["UAE"])
    sectors = prefs.get("sectors", [])
    roles = prefs.get("roles", [])
    region = regions[0] if regions else "UAE"

    signals = []

    for raw in fetch_funding_signals(region=region, sectors=sectors, roles=roles):
        raw["provider"] = "crunchbase"
        raw["evidence_tier"] = "strong"
        signals.append(raw)

    for raw in fetch_leadership_signals(region=region, sectors=sectors):
        raw["provider"] = "crunchbase"
        raw["evidence_tier"] = "strong"
        signals.append(raw)

    return signals


# ── Source 4: MAGNiTT (MENA Startups) ────────────────────────────────────────

def _detect_magnitt_signals(prefs: dict) -> list[dict]:
    """
    Fetch MENA startup signals from MAGNiTT.
    Returns raw signal dicts with evidence_tier=strong.
    """
    from app.services.scout.magnitt_provider import fetch_mena_funding_signals

    sectors = prefs.get("sectors", [])

    signals = []
    for raw in fetch_mena_funding_signals(sectors=sectors):
        raw["provider"] = "magnitt"
        raw["evidence_tier"] = "strong"
        signals.append(raw)

    return signals
