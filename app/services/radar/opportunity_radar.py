"""
app/services/radar/opportunity_radar.py

Main orchestrator: collect signals → normalize → dedup → score → rank.

This is the single entry point. Everything else (dashboard, WhatsApp, email)
consumes OpportunityRadar output.
"""

import structlog

from app.services.radar.adapters import adapt_scout_job, adapt_signal_card
from app.services.radar.dedup import dedup_and_merge
from app.services.radar.scorer import score_opportunity
from app.services.radar.types import RadarOpportunity

logger = structlog.get_logger(__name__)


async def run_radar(
    db,
    user_id: str,
    user_prefs: dict,
    profile_dict: dict | None = None,
    limit: int = 20,
    min_score: int = 0,
    source_filter: str = "all",
    urgency_filter: str = "all",
    include_speculative: bool = False,
) -> dict:
    """
    Run the OpportunityRadar pipeline.

    1. Collect signals from all available sources
    2. Normalize via adapters
    3. Dedup + merge
    4. Score each opportunity
    5. Rank, filter, return

    Args:
        db: async database session
        user_id: current user's ID
        user_prefs: candidate preferences dict
        profile_dict: candidate profile for fit scoring
        limit: max results
        min_score: minimum radar_score filter
        source_filter: "all" | "hidden_market" | "job_board" | "signal_engine"
        urgency_filter: "all" | "high" | "medium" | "low"

    Returns:
        dict with opportunities[], total, scoring metadata
    """
    import time
    start = time.monotonic()

    # ── 1. Collect signals ──────────────────────────────────────────────
    all_inputs = []

    # Source A: Signal Engine (cached ScoutResult)
    signal_inputs = await _load_signal_engine_results(db, user_id)
    all_inputs.extend(signal_inputs)

    # Source B: Scout Jobs (cached or live from Adzuna/JSearch)
    job_inputs = await _load_scout_jobs(db, user_id, user_prefs)
    all_inputs.extend(job_inputs)

    # Source C: Hidden Market (when table exists)
    hidden_inputs = await _load_hidden_market(db, user_id)
    all_inputs.extend(hidden_inputs)

    # Sources D & E: Email Intelligence + LinkedIn (Phase 2 stubs — return [])

    logger.info(
        "radar_signals_collected",
        user_id=user_id,
        signal_engine=len(signal_inputs),
        scout_jobs=len(job_inputs),
        hidden_market=len(hidden_inputs),
        total=len(all_inputs),
    )

    if not all_inputs:
        return {
            "opportunities": [],
            "total": 0,
            "returned": 0,
            "scoring": {
                "method": "heuristic",
                "profile_completeness": _profile_completeness(profile_dict),
                "sources_active": [],
                "sources_unavailable": ["email_intelligence", "linkedin"],
            },
            "meta": {"scored_in_ms": 0},
            "onboarding_hint": (
                "No opportunities found yet. To populate your radar: "
                "1) Upload a CV, 2) Fill in your profile preferences (target roles, sectors, regions), "
                "3) Visit the Job Scout page to trigger a market scan."
            ),
        }

    # ── 2. Dedup + Merge ────────────────────────────────────────────────
    merged = dedup_and_merge(all_inputs)

    # ── 3. Score ────────────────────────────────────────────────────────
    scored: list[RadarOpportunity] = []
    filtered_speculative = 0
    for m in merged:
        evidence_tier = m.get("evidence_tier", "medium")

        # Filter speculative by default
        if evidence_tier == "speculative" and not include_speculative:
            filtered_speculative += 1
            continue

        radar_score, breakdown, urgency, reasoning = score_opportunity(m, user_prefs)

        # Apply filters before building full object
        if radar_score < min_score:
            continue
        # Skip opportunities with near-zero fit — prevents high signal_strength
        # from pushing irrelevant opportunities into the visible list
        if user_prefs and breakdown.profile_fit < 0.15:
            filtered_speculative += 1
            continue
        if source_filter != "all" and source_filter not in m.get("source_tags", []):
            continue
        if urgency_filter != "all" and urgency != urgency_filter:
            continue

        opp = RadarOpportunity(
            id=m["id"],
            company=m["company"],
            company_normalized=m["company_normalized"],
            role=m.get("role"),
            location=m.get("location"),
            sector=m.get("sector"),
            radar_score=radar_score,
            score_breakdown=breakdown,
            sources=m["sources"],
            source_tags=m["source_tags"],
            reasoning=reasoning,
            suggested_action=_suggested_action(m, urgency),
            outreach_hook=m.get("outreach_hook", ""),
            urgency=urgency,
            evidence_tier=evidence_tier,
            fit_reasons=m.get("fit_reasons", []),
            red_flags=m.get("red_flags", []),
            first_seen_at=m.get("most_recent_date"),
        )
        scored.append(opp)

    # ── 4. Rank ─────────────────────────────────────────────────────────
    scored.sort(key=lambda o: o.radar_score, reverse=True)
    for i, opp in enumerate(scored):
        opp.rank = i + 1

    total = len(scored)
    returned = scored[:limit]

    elapsed_ms = int((time.monotonic() - start) * 1000)

    sources_active = []
    if signal_inputs:
        sources_active.append("signal_engine")
    if job_inputs:
        sources_active.append("job_board")
    if hidden_inputs:
        sources_active.append("hidden_market")

    return {
        "opportunities": [o.to_dict() for o in returned],
        "total": total,
        "returned": len(returned),
        "scoring": {
            "method": "heuristic",
            "profile_completeness": _profile_completeness(profile_dict),
            "sources_active": sources_active,
            "sources_unavailable": ["email_intelligence", "linkedin"],
        },
        "meta": {
            "scored_in_ms": elapsed_ms,
            "filtered_speculative": filtered_speculative,
        },
    }


# ── Source loaders ───────────────────────────────────────────────────────────

async def _load_signal_engine_results(db, user_id: str) -> list:
    """Load cached OpportunityCards from ScoutResult."""
    from sqlalchemy import select
    from app.models.scout_result import ScoutResult

    q = (
        select(ScoutResult)
        .where(ScoutResult.user_id == user_id, ScoutResult.is_stale == False)  # noqa: E712
        .order_by(ScoutResult.created_at.desc())
        .limit(1)
    )
    row = (await db.execute(q)).scalar_one_or_none()
    if not row:
        return []

    inputs = []
    for card in (row.opportunities or []):
        if isinstance(card, dict):
            inputs.append(adapt_signal_card(card))
    return inputs


async def _load_scout_jobs(db, user_id: str, prefs: dict) -> list:
    """Load live job results. Uses cached ScoutResult.live_openings if available."""
    from sqlalchemy import select
    from app.models.scout_result import ScoutResult

    q = (
        select(ScoutResult)
        .where(ScoutResult.user_id == user_id, ScoutResult.is_stale == False)  # noqa: E712
        .order_by(ScoutResult.created_at.desc())
        .limit(1)
    )
    row = (await db.execute(q)).scalar_one_or_none()
    if not row:
        return []

    inputs = []
    for job in (row.live_openings or []):
        if isinstance(job, dict):
            inputs.append(adapt_scout_job(job))
    return inputs


async def _load_hidden_market(db, user_id: str) -> list:
    """Load HiddenSignal rows if the table exists."""
    try:
        from sqlalchemy import select, text
        # Check if table exists first (graceful for pre-migration state)
        result = await db.execute(
            text("SELECT to_regclass('public.hidden_signals')")
        )
        if result.scalar() is None:
            return []

        from app.models.hidden_signal import HiddenSignal
        q = (
            select(HiddenSignal)
            .where(
                HiddenSignal.user_id == user_id,
                HiddenSignal.is_dismissed == False,  # noqa: E712
            )
            .order_by(HiddenSignal.created_at.desc())
            .limit(50)
        )
        rows = (await db.execute(q)).scalars().all()
        from app.services.radar.adapters import adapt_hidden_signal
        return [adapt_hidden_signal({
            "company_name": r.company_name,
            "signal_type": r.signal_type,
            "confidence": r.confidence,
            "likely_roles": r.likely_roles,
            "reasoning": r.reasoning,
            "source_url": r.source_url,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }) for r in rows]
    except Exception as e:
        logger.warning("hidden_market_load_failed", error=str(e))
        return []


# ── Helpers ──────────────────────────────────────────────────────────────────

def _profile_completeness(profile_dict: dict | None) -> float:
    if not profile_dict:
        return 0.0
    score = 0.0
    if profile_dict.get("headline"):
        score += 0.2
    if profile_dict.get("global_context"):
        score += 0.2
    exps = profile_dict.get("experiences", [])
    if exps:
        score += min(0.4, len(exps) * 0.1)
    score += 0.1  # partial for having a profile at all
    return min(1.0, round(score, 2))


def _suggested_action(merged: dict, urgency: str) -> str:
    company = merged.get("company", "the company")
    if merged.get("has_hidden_market") and not merged.get("is_posted"):
        return f"Generate a Shadow Application for {company} — approach before the role is posted."
    if merged.get("is_posted") and urgency == "high":
        return f"Generate an Intelligence Pack and apply quickly — high-fit role at {company}."
    if merged.get("is_posted"):
        return f"Review the posting and generate an Intelligence Pack for {company}."
    return f"Monitor {company} for more signals."
