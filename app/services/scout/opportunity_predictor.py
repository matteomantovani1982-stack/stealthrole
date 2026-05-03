"""
app/services/scout/opportunity_predictor.py

Predictive Opportunity Engine — scans financial journals, news sources,
regulatory filings, and industry reports to predict future hiring BEFORE
companies even know they need to hire.

Intelligence layers:
  1. Financial Events → predict operational needs
  2. Regulatory Changes → predict compliance hiring
  3. Industry Shifts → predict sector-wide demand
  4. Company Lifecycle → predict stage-specific roles
  5. Competitive Moves → predict defensive hiring

Data sources (all via Serper — no additional API keys):
  - Financial journals: Bloomberg, Reuters, Financial Times, WSJ, Arabian Business
  - Tech press: TechCrunch, Wired, The Information, Sifted
  - MENA sources: Magnitt, Zawya, Gulf News Business, Arab News Economy
  - Regulatory: SEC filings, DFSA, ADGM, SAMA, CMA announcements
  - Industry: McKinsey, BCG, Bain reports, Gartner, CB Insights

Processing:
  - Detects events with hiring implications
  - Predicts WHAT role will be needed (with confidence %)
  - Predicts WHEN hiring will happen (timeline)
  - Predicts WHO the decision maker is (title + department)
  - Scores against user profile
  - Generates proactive outreach strategy
"""

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

import httpx
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)

TIMEOUT = 12.0
SERPER_NEWS_URL = "https://google.serper.dev/news"


@dataclass
class PredictedOpportunity:
    """A predicted future hiring opportunity."""
    company: str
    predicted_role: str
    confidence: float  # 0-1
    timeline: str  # "1-3 months", "3-6 months", "6-12 months"
    urgency: str  # "imminent", "likely", "possible"
    trigger_event: str  # What happened that triggers this prediction
    trigger_type: str  # funding, regulatory, expansion, competitive, lifecycle
    reasoning: str  # Why we predict this hire
    decision_maker_title: str  # Who will make the hiring decision
    recommended_action: str  # What the user should do
    source_url: str
    source_name: str
    published_date: str
    signals: list[str] = field(default_factory=list)


# ── Source queries by intelligence layer ──────────────────────────────────────

def _build_queries(region: str, sectors: list[str], roles: list[str]) -> dict[str, list[str]]:
    """Build targeted search queries for each intelligence layer."""
    sec = " ".join(sectors[:3]) if sectors else "tech fintech"
    _role_kw = " ".join(roles[:2]) if roles else "operations leadership"

    return {
        "financial_events": [
            f"raised funding hiring plans {region} {sec} 2026",
            f"IPO preparation executive team {region} 2026",
            f"revenue growth headcount expansion {region} {sec}",
            f"Series B C funding operational scaling {region}",
            f"acquisition integration team building {region} {sec}",
            f"private equity portfolio company operational improvement",
            f"profitability pressure cost optimization {region} {sec}",
        ],
        "regulatory_changes": [
            f"new regulation compliance {region} {sec} 2026",
            f"DFSA ADGM SAMA CMA new rules 2026",
            f"data protection privacy regulation {region} 2026",
            f"financial regulation fintech banking license {region}",
            f"ESG reporting mandatory {region} 2026",
            f"anti-money laundering compliance hiring {region}",
        ],
        "industry_shifts": [
            f"industry report growth forecast {region} {sec} 2026",
            f"McKinsey BCG report {region} {sec} talent demand",
            f"digital transformation spending {region} 2026",
            f"AI adoption enterprise {region} {sec} hiring",
            f"market consolidation {region} {sec} 2026",
            f"emerging technology investment {region} 2026",
        ],
        "competitive_moves": [
            f"competitor expansion {region} {sec} market entry 2026",
            f"market share battle {region} {sec} hiring war",
            f"talent acquisition war {region} {sec} 2026",
            f"poaching executives {region} {sec}",
            f"competitive response hiring {region} {sec}",
        ],
        "company_lifecycle": [
            f"startup scaling challenges {region} {sec} operations",
            f"Series A to B growth team building {region}",
            f"pre-IPO governance board executive hiring",
            f"post-merger integration leadership {region} {sec}",
            f"turnaround restructuring new leadership {region}",
            f"international expansion country manager {region}",
        ],
    }


# ── Prediction rules ─────────────────────────────────────────────────────────

# Event → predicted role + timeline + decision maker
PREDICTION_RULES = [
    # Financial events
    {"keywords": ["series a", "seed", "raised", "million", "funding"],
     "min_keywords": 2,
     "predicted_role": "Head of Operations",
     "timeline": "1-3 months",
     "urgency": "imminent",
     "decision_maker": "CEO / Founder",
     "reasoning": "Post-funding companies need operational leadership to scale. Founders typically hire a COO/Head of Ops within 3 months of closing.",
     "trigger_type": "funding"},

    {"keywords": ["series b", "series c", "growth", "scale", "expansion"],
     "min_keywords": 2,
     "predicted_role": "VP Operations / COO",
     "timeline": "1-3 months",
     "urgency": "imminent",
     "decision_maker": "CEO",
     "reasoning": "Growth-stage funding means board pressure to professionalize operations. VP/COO hire is the most common post-Series B move.",
     "trigger_type": "funding"},

    {"keywords": ["ipo", "public", "listing", "pre-ipo"],
     "min_keywords": 1,
     "predicted_role": "CFO / Chief Compliance Officer",
     "timeline": "3-6 months",
     "urgency": "likely",
     "decision_maker": "CEO / Board",
     "reasoning": "Pre-IPO companies need financial leadership for regulatory compliance, investor relations, and governance.",
     "trigger_type": "lifecycle"},

    {"keywords": ["acquisition", "acquired", "merger", "integration"],
     "min_keywords": 1,
     "predicted_role": "Integration Lead / COO",
     "timeline": "1-3 months",
     "urgency": "imminent",
     "decision_maker": "CEO / PE Partner",
     "reasoning": "Post-acquisition integration requires dedicated operational leadership. Usually hired within weeks of deal close.",
     "trigger_type": "competitive"},

    # Regulatory
    {"keywords": ["regulation", "compliance", "new rules", "mandatory"],
     "min_keywords": 2,
     "predicted_role": "Head of Compliance / GRC Lead",
     "timeline": "3-6 months",
     "urgency": "likely",
     "decision_maker": "General Counsel / CEO",
     "reasoning": "New regulations create immediate compliance hiring needs. Companies that delay face fines.",
     "trigger_type": "regulatory"},

    {"keywords": ["data protection", "privacy", "gdpr", "data law"],
     "min_keywords": 1,
     "predicted_role": "Data Protection Officer",
     "timeline": "3-6 months",
     "urgency": "likely",
     "decision_maker": "CTO / General Counsel",
     "reasoning": "Data privacy regulations require dedicated DPO role. Often a board-level mandate.",
     "trigger_type": "regulatory"},

    # Expansion
    {"keywords": ["new market", "enters", "expands to", "launches in", "new office"],
     "min_keywords": 1,
     "predicted_role": "Country Manager / Regional Director",
     "timeline": "1-3 months",
     "urgency": "imminent",
     "decision_maker": "COO / CEO",
     "reasoning": "Market entry requires local leadership. Country Manager is the first hire in a new market.",
     "trigger_type": "expansion"},

    {"keywords": ["new product", "product launch", "new service", "platform launch"],
     "min_keywords": 1,
     "predicted_role": "Head of Product / Product Director",
     "timeline": "3-6 months",
     "urgency": "likely",
     "decision_maker": "CPO / CEO",
     "reasoning": "New product lines need dedicated product leadership. Often hired 3-6 months before launch.",
     "trigger_type": "expansion"},

    # Competitive
    {"keywords": ["competitor", "market share", "losing", "aggressive", "war"],
     "min_keywords": 2,
     "predicted_role": "VP Sales / Head of Growth",
     "timeline": "1-3 months",
     "urgency": "imminent",
     "decision_maker": "CEO / CRO",
     "reasoning": "Competitive pressure forces companies to hire commercial leaders fast. Revenue defense is priority #1.",
     "trigger_type": "competitive"},

    # Technology
    {"keywords": ["digital transformation", "ai adoption", "automation", "technology investment"],
     "min_keywords": 1,
     "predicted_role": "CTO / VP Engineering / Head of Digital",
     "timeline": "3-6 months",
     "urgency": "likely",
     "decision_maker": "CEO / Board",
     "reasoning": "Digital transformation initiatives require senior technology leadership to drive execution.",
     "trigger_type": "industry_shift"},

    # Turnaround
    {"keywords": ["turnaround", "restructuring", "new leadership", "transformation"],
     "min_keywords": 1,
     "predicted_role": "Transformation Lead / COO",
     "timeline": "1-3 months",
     "urgency": "imminent",
     "decision_maker": "Board / PE Partner",
     "reasoning": "Turnaround situations create urgent leadership vacancies. Decision is usually made by the board, not existing management.",
     "trigger_type": "lifecycle"},

    # PE/VC
    {"keywords": ["private equity", "pe firm", "portfolio", "operational improvement"],
     "min_keywords": 2,
     "predicted_role": "Operating Partner / Portfolio COO",
     "timeline": "1-3 months",
     "urgency": "imminent",
     "decision_maker": "PE Managing Partner",
     "reasoning": "PE firms bring in operational leaders within 90 days of acquisition to drive value creation plan.",
     "trigger_type": "funding"},
]


def _predict_from_article(title: str, snippet: str, url: str, source_name: str, date: str) -> PredictedOpportunity | None:
    """Apply prediction rules to a news article."""
    text = f"{title} {snippet}".lower()

    for rule in PREDICTION_RULES:
        matches = sum(1 for kw in rule["keywords"] if kw in text)
        if matches >= rule["min_keywords"]:
            company = _extract_company(title)
            if not company or len(company) < 3:
                continue

            return PredictedOpportunity(
                company=company,
                predicted_role=rule["predicted_role"],
                confidence=min(0.95, 0.5 + matches * 0.15),
                timeline=rule["timeline"],
                urgency=rule["urgency"],
                trigger_event=title[:150],
                trigger_type=rule["trigger_type"],
                reasoning=rule["reasoning"],
                decision_maker_title=rule["decision_maker"],
                recommended_action=f"Research {company}, find connections, prepare positioning for {rule['predicted_role']} role",
                source_url=url,
                source_name=source_name,
                published_date=date,
                signals=[kw for kw in rule["keywords"] if kw in text],
            )

    return None


def _extract_company(title: str) -> str | None:
    """Extract company name from article title."""
    # Common patterns: "Company raises $X", "Company announces Y", "Company to Z"
    patterns = [
        r'^([A-Z][\w\s&.-]+?)\s+(?:raises|raised|secures|closes|announces|launches|enters|expands|acquires|hires|appoints)',
        r'^([A-Z][\w\s&.-]+?)\s+(?:to |will |plans |set to)',
        r'(?:at|by)\s+([A-Z][\w\s&.-]+?)(?:\s*[,.]|\s+(?:in|for|as|after))',
    ]
    for pattern in patterns:
        m = re.search(pattern, title)
        if m:
            name = m.group(1).strip()
            if len(name) > 2 and len(name) < 50:
                return name
    # Fallback: first capitalized phrase
    m = re.match(r'^([A-Z][\w\s&.-]{2,30}?)(?:\s+[-—:|]|\s+(?:raises|announces|launches|to |will ))', title)
    if m:
        return m.group(1).strip()
    return None


def _serper_news_query(query: str, num: int = 5) -> list[dict]:
    """Query Serper News API."""
    if not settings.serper_api_key:
        return []
    try:
        resp = httpx.post(
            SERPER_NEWS_URL,
            json={"q": query, "num": num},
            headers={"X-API-KEY": settings.serper_api_key},
            timeout=TIMEOUT,
        )
        if resp.status_code == 200:
            return resp.json().get("news", [])
    except Exception as e:
        logger.debug("predictor_serper_failed", query=query[:50], error=str(e))
    return []


# ── Main prediction engine ────────────────────────────────────────────────────

def predict_opportunities(
    preferences: dict,
    user_profile: dict,
    max_results: int = 20,
) -> dict:
    """
    Scan financial journals, news, and industry sources to predict
    future hiring opportunities before they're posted.

    Returns predicted opportunities ranked by confidence + fit.
    """
    regions = preferences.get("regions", ["UAE"])
    sectors = preferences.get("sectors", [])
    roles = preferences.get("roles", [])
    region = regions[0] if regions else "UAE Dubai"

    logger.info("predictor_start", region=region, sectors=sectors)

    if not settings.serper_api_key:
        logger.warning("predictor_no_serper_key")
        return {"predictions": [], "sources_scanned": 0, "is_demo": True}

    queries = _build_queries(region, sectors, roles)

    # Fetch all sources in parallel
    all_articles = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {}
        for layer, layer_queries in queries.items():
            for q in layer_queries:
                futures[executor.submit(_serper_news_query, q, 5)] = layer

        for future in as_completed(futures):
            try:
                articles = future.result()
                all_articles.extend(articles)
            except Exception:
                pass

    logger.info("predictor_articles_fetched", count=len(all_articles))

    # If no articles found (Serper out of credits), return intelligent predictions
    # based on known MENA market signals
    if not all_articles:
        return _fallback_predictions(region, sectors, roles, max_results)

    # Deduplicate by URL
    seen_urls = set()
    unique_articles = []
    for a in all_articles:
        url = a.get("link", "")
        if url not in seen_urls:
            seen_urls.add(url)
            unique_articles.append(a)

    # Apply prediction rules
    predictions: list[PredictedOpportunity] = []
    for article in unique_articles:
        pred = _predict_from_article(
            title=article.get("title", ""),
            snippet=article.get("snippet", ""),
            url=article.get("link", ""),
            source_name=article.get("source", ""),
            date=article.get("date", ""),
        )
        if pred:
            predictions.append(pred)

    # Deduplicate by company (keep highest confidence per company)
    by_company: dict[str, PredictedOpportunity] = {}
    for pred in predictions:
        key = pred.company.lower().strip()
        if key not in by_company or pred.confidence > by_company[key].confidence:
            by_company[key] = pred

    # Sort by confidence descending
    sorted_preds = sorted(by_company.values(), key=lambda p: p.confidence, reverse=True)[:max_results]

    logger.info("predictor_complete", predictions=len(sorted_preds), articles_scanned=len(unique_articles))

    return {
        "predictions": [
            {
                "company": p.company,
                "predicted_role": p.predicted_role,
                "confidence": round(p.confidence * 100),
                "timeline": p.timeline,
                "urgency": p.urgency,
                "trigger_event": p.trigger_event,
                "trigger_type": p.trigger_type,
                "reasoning": p.reasoning,
                "decision_maker": p.decision_maker_title,
                "recommended_action": p.recommended_action,
                "source_url": p.source_url,
                "source_name": p.source_name,
                "published_date": p.published_date,
                "signals": p.signals,
            }
            for p in sorted_preds
        ],
        "sources_scanned": len(unique_articles),
        "layers_queried": list(queries.keys()),
        "is_demo": False,
    }


def _fallback_predictions(
    region: str,
    sectors: list[str],
    roles: list[str],
    max_results: int,
) -> dict:
    """Return empty predictions when Serper is unavailable."""
    logger.warning("predictor_fallback_no_serper")
    return {
        "predictions": [],
        "sources_scanned": 0,
        "layers_queried": [],
        "is_demo": True,
        "empty_reason": (
            "Predicted opportunities require market scanning "
            "to be active."
        ),
    }


# ── Interpretation-based prediction (Phase 4) ───────────────────────

async def predict_from_interpretations(
    db,  # AsyncSession
    user_id: str,
    preferences: dict,
    user_profile: dict,
    max_results: int = 20,
) -> dict | None:
    """Build predictions from existing SignalInterpretation records.

    Returns a predictions dict (same shape as
    ``predict_opportunities``) when interpretations exist, or
    ``None`` to signal the caller to fall back to the legacy
    article-based predictor.

    Parameters
    ----------
    db : AsyncSession
    user_id : str
    preferences : dict
        User's target roles / sectors / regions.
    user_profile : dict
        Profile dict for fit context.
    max_results : int
    """
    from datetime import datetime as dt
    from datetime import timedelta, timezone

    from sqlalchemy import select

    from app.models.hidden_signal import HiddenSignal
    from app.models.signal_interpretation import (
        SignalInterpretation,
    )

    # Fetch recent interpretations (last 24 h) with company names
    cutoff = dt.now(timezone.utc) - timedelta(hours=24)
    q = (
        select(
            SignalInterpretation,
            HiddenSignal.company_name,
            HiddenSignal.source_url,
            HiddenSignal.source_name,
        )
        .join(
            HiddenSignal,
            HiddenSignal.id == SignalInterpretation.signal_id,
        )
        .where(
            SignalInterpretation.user_id == user_id,
            SignalInterpretation.created_at >= cutoff,
        )
        .order_by(
            SignalInterpretation.interpretation_confidence.desc(),
        )
        .limit(50)
    )
    rows = (await db.execute(q)).all()

    if not rows:
        return None  # fall back to legacy

    predictions = _interpretations_to_predictions(rows)

    # Deduplicate by company — keep highest confidence
    by_company: dict[str, dict] = {}
    for pred in predictions:
        key = pred["company"].lower().strip()
        if (
            key not in by_company
            or pred["confidence"] > by_company[key]["confidence"]
        ):
            by_company[key] = pred

    sorted_preds = sorted(
        by_company.values(),
        key=lambda p: p["confidence"],
        reverse=True,
    )[:max_results]

    logger.info(
        "predictor_from_interpretations",
        user_id=user_id,
        interpretations=len(rows),
        predictions=len(sorted_preds),
    )

    return {
        "predictions": sorted_preds,
        "sources_scanned": len(rows),
        "layers_queried": ["signal_interpretation"],
        "is_demo": False,
        "engine": "interpretation",
    }


def _interpretations_to_predictions(
    rows: list[tuple],
) -> list[dict]:
    """Convert (SignalInterpretation, company, url, source) tuples
    into prediction dicts."""
    results: list[dict] = []

    for row in rows:
        interp = row[0]
        company_name = row[1] or "Unknown"
        source_url = row[2] or ""
        source_name = row[3] or "signal_interpretation"

        roles = interp.predicted_roles or []
        if not roles:
            continue

        # Pick the highest-confidence predicted role
        best_role = max(
            roles, key=lambda r: r.get("confidence", 0),
        )
        role_title = best_role.get("role", "Senior Role")
        raw_timeline = best_role.get("timeline", "3_6_months")
        urgency = best_role.get("urgency", "likely")
        role_conf = best_role.get("confidence", 0.5)

        # Combine interpretation + role confidence
        interp_conf = interp.interpretation_confidence or 0.5
        combined = (interp_conf * 0.6) + (role_conf * 0.4)

        # Structured reasoning
        reasoning = (
            f"{interp.business_change} "
            f"{interp.org_impact} "
            f"{interp.hiring_reason}"
        )

        # Format timeline
        timeline = _format_timeline(raw_timeline)

        # Action with hiring owner context
        owner = interp.hiring_owner_title or "hiring manager"
        action = (
            f"Research {company_name}, identify the "
            f"{owner}, and position yourself for the "
            f"{role_title} role"
        )

        results.append({
            "company": company_name,
            "predicted_role": role_title,
            "confidence": round(combined * 100),
            "timeline": timeline,
            "urgency": urgency,
            "trigger_event": interp.business_change[:150],
            "trigger_type": interp.trigger_type,
            "reasoning": reasoning[:500],
            "decision_maker": interp.hiring_owner_title or "",
            "recommended_action": action,
            "source_url": source_url,
            "source_name": source_name,
            "published_date": "",
            "signals": [interp.trigger_type],
            "rule_id": interp.rule_id,
            "interpretation_id": str(interp.id),
        })

    return results


_TIMELINE_MAP = {
    "immediate": "immediate",
    "1_3_months": "1-3 months",
    "3_6_months": "3-6 months",
    "6_12_months": "6-12 months",
}


def _format_timeline(raw: str) -> str:
    """Normalise timeline codes for display."""
    return _TIMELINE_MAP.get(raw, raw.replace("_", " "))
