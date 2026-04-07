"""
app/services/radar/scorer.py

Heuristic scoring for OpportunityRadar.

Composite formula:
  raw_score = profile_fit(40%) + signal_strength(20%) + recency(15%)
            + competition(10%) + conviction(10%)

Hard caps:
  Domain mismatch (both detected) → profile_fit capped at 0.35
  Seniority gap ≥ 3              → profile_fit capped at 0.20
  Region mismatch (explicit pref) → profile_fit × 0.7 penalty

Evidence penalty:
  strong      → ×1.0  (no penalty)
  medium      → ×0.85
  weak        → ×0.55
  speculative → ×0.25

This means a speculative opportunity with a perfect raw score of 100
would display as 25. It cannot appear "high urgency" by accident.
"""

from datetime import datetime, UTC

from app.services.radar.types import (
    ScoreBreakdown,
    detect_seniority,
    detect_domain,
    sectors_match,
    regions_match,
)

# Evidence tier → score multiplier
_TIER_MULTIPLIER = {
    "strong": 1.0,
    "medium": 0.85,
    "weak": 0.55,
    "speculative": 0.25,
}


def score_opportunity(merged: dict, user_prefs: dict) -> tuple[int, ScoreBreakdown, str, str]:
    """
    Score a merged opportunity.

    Returns:
        (radar_score 0-100, ScoreBreakdown, urgency, evidence_tier, reasoning)
    """
    # If the opportunity already has a pre-computed fit_score (from signal engine),
    # use it as the base profile fit instead of re-computing from scratch
    pre_score = merged.get("fit_score") or merged.get("radar_score")
    if pre_score and isinstance(pre_score, (int, float)) and pre_score > 0:
        pf = min(1.0, pre_score / 100)
    else:
        pf = _profile_fit(merged, user_prefs)
    ss = _signal_strength(merged)
    rc = _recency(merged)
    cp = _competition(merged)
    cv = _conviction(merged)

    breakdown = ScoreBreakdown(
        profile_fit=round(pf, 2),
        signal_strength=round(ss, 2),
        recency=round(rc, 2),
        competition=round(cp, 2),
        conviction=round(cv, 2),
    )

    raw = pf * 40 + ss * 20 + rc * 15 + cp * 10 + cv * 10

    # Apply evidence tier penalty
    tier = merged.get("evidence_tier", "medium")
    multiplier = _TIER_MULTIPLIER.get(tier, 0.85)
    score = round(raw * multiplier)

    # Hard mismatch penalty: when fit is capped (domain or seniority mismatch),
    # prevent recency/competition from inflating the total above the mismatch threshold
    if pf <= 0.35:
        score = round(score * 0.7)

    score = max(0, min(100, score))

    # Urgency is gated by both score AND evidence tier
    # Only strong evidence can produce high urgency
    if tier in ("weak", "speculative"):
        urgency = "low"
    elif tier == "medium":
        urgency = "medium" if score >= 50 else "low"  # medium evidence caps at medium urgency
    elif score >= 75:
        urgency = "high"  # only strong evidence reaches here
    elif score >= 50:
        urgency = "medium"
    else:
        urgency = "low"

    reasoning = _build_reasoning(merged, breakdown, score, tier, user_prefs)

    return score, breakdown, urgency, reasoning


# ── Profile Fit (0-1) ────────────────────────────────────────────────────────
# Uses seniority taxonomy, functional domain matching, sector hierarchy,
# and region equivalence instead of naive substring matching.

def _profile_fit(merged: dict, prefs: dict) -> float:
    """
    Structured profile fit scoring. 0-1.

    Hard caps applied after scoring:
      - Domain mismatch (both detected): cap at 0.35
      - Seniority gap ≥ 3: cap at 0.20
      - Region mismatch (user has explicit region pref): multiply by 0.7
      - Missing data: 0 credit (not partial)
    """
    if not prefs:
        pre = merged.get("fit_score_precomputed")
        return (pre / 100.0) if pre else 0.15  # very low default when no prefs

    score = 0.0
    opp_role = merged.get("role") or ""
    domain_mismatch = False
    seniority_gap = 0
    region_mismatch = False

    # ── 1. Functional domain match (0.30) ────────────────────────────────
    opp_domain = detect_domain(opp_role)
    user_domains = set()
    for r in prefs.get("roles", []):
        d = detect_domain(r)
        if d:
            user_domains.add(d)

    if opp_domain and user_domains:
        if opp_domain in user_domains:
            score += 0.30
        elif opp_domain == "executive" or "executive" in user_domains:
            score += 0.20  # executive matches broadly
        else:
            domain_mismatch = True  # hard penalty applied below
    # Missing domain: 0 credit (was 0.10)

    # ── 2. Seniority match (0.25) ────────────────────────────────────────
    opp_level = detect_seniority(opp_role)
    user_levels = []
    for r in prefs.get("roles", []):
        lv = detect_seniority(r)
        if lv is not None:
            user_levels.append(lv)
    for s in prefs.get("level", prefs.get("seniority", [])):
        lv = detect_seniority(s)
        if lv is not None:
            user_levels.append(lv)

    if opp_level is not None and user_levels:
        target_level = max(user_levels)
        seniority_gap = abs(opp_level - target_level)
        if seniority_gap == 0:
            score += 0.25
        elif seniority_gap == 1:
            score += 0.15
        elif seniority_gap == 2:
            score += 0.05
        # gap >= 3 → 0 credit + hard cap applied below
    # Missing seniority: 0 credit (was 0.08)

    # ── 3. Sector match (0.20) ───────────────────────────────────────────
    target_sectors = prefs.get("sectors", [])
    opp_sector = merged.get("sector") or ""
    if sectors_match(target_sectors, opp_sector):
        score += 0.20
    # Missing/mismatched sector: 0 credit (was 0.05)

    # ── 4. Region match (0.15) ───────────────────────────────────────────
    target_regions = prefs.get("regions", [])
    opp_location = merged.get("location") or ""
    if target_regions and opp_location:
        if regions_match(target_regions, opp_location):
            score += 0.15
        else:
            region_mismatch = True  # penalty applied below
    # Missing location: 0 credit (was 0.05)

    # ── 5. Company stage fit (0.10) ──────────────────────────────────────
    target_types = [t.lower() for t in prefs.get("companyType", prefs.get("company_type", []))]
    if target_types:
        detail = ""
        sources = merged.get("sources", [])
        if sources:
            src = sources[0]
            detail = (src.headline if hasattr(src, "headline") else "").lower()
        for tt in target_types:
            if tt in detail:
                score += 0.10
                break
        # Can't determine: 0 credit (was 0.03)
    # No preference: 0 credit (was 0.05)

    # ── Apply hard caps ──────────────────────────────────────────────────
    if domain_mismatch:
        score = min(score, 0.35)

    if seniority_gap >= 3:
        score = min(score, 0.20)

    if region_mismatch:
        score *= 0.7

    return min(1.0, max(0.0, score))


# ── Signal Strength (0-1) ────────────────────────────────────────────────────

def _signal_strength(merged: dict) -> float:
    """Quality of evidence. 0-1."""
    tier = merged.get("evidence_tier", "medium")

    # Signal strength is primarily driven by evidence tier
    base = {"strong": 0.9, "medium": 0.65, "weak": 0.4, "speculative": 0.2}.get(tier, 0.5)

    # Boost for multi-source
    if merged.get("has_hidden_market") and merged.get("has_job_board"):
        base = max(base, 1.0)
    elif merged.get("is_posted") and merged.get("salary"):
        base = max(base, 0.9)

    return min(1.0, base)


# ── Recency (0-1) ────────────────────────────────────────────────────────────

def _recency(merged: dict) -> float:
    """How fresh. 0-1. Linear decay over 60 days."""
    date_str = merged.get("most_recent_date")
    if not date_str:
        return 0.3

    try:
        if isinstance(date_str, str):
            dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
        else:
            dt = date_str
        days = (datetime.now() - dt).days
        return max(0.0, 1.0 - days / 60.0)
    except (ValueError, TypeError):
        return 0.3


# ── Competition (0-1) ────────────────────────────────────────────────────────

def _competition(merged: dict) -> float:
    """Inverse of expected applicant volume. 0-1."""
    tier = merged.get("evidence_tier", "medium")
    if merged.get("has_hidden_market") and not merged.get("is_posted"):
        # Only give low-competition credit for strong/medium signals
        # Speculative/weak signals have UNKNOWN competition, not low
        if tier in ("strong", "medium"):
            return 0.9
        return 0.5  # unknown competition for weak/speculative

    date_str = merged.get("most_recent_date")
    if date_str:
        try:
            if isinstance(date_str, str):
                dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
            else:
                dt = date_str
            days = (datetime.now() - dt).days
            if days < 3:
                return 0.8
            elif days < 7:
                return 0.6
            elif days < 14:
                return 0.4
            else:
                return 0.2
        except (ValueError, TypeError):
            pass
    return 0.5


# ── Conviction (0-1) ─────────────────────────────────────────────────────────

def _conviction(merged: dict) -> float:
    """How many independent sources confirm. 0-1."""
    n = merged.get("num_sources", 1)
    if n >= 3:
        return 1.0
    if n == 2:
        return 0.75

    for s in merged.get("sources", []):
        url = s.source_url if hasattr(s, "source_url") else ""
        if any(auth in url.lower() for auth in ["techcrunch", "bloomberg", "linkedin", "reuters", "ft.com"]):
            return 0.6
    return 0.4


# ── Structured Reasoning ─────────────────────────────────────────────────────

def _build_reasoning(
    merged: dict,
    breakdown: ScoreBreakdown,
    score: int,
    tier: str,
    user_prefs: dict,
) -> str:
    """
    Build structured reasoning that explains WHY for each dimension.

    Format:
      Why this company: [signal]
      Why this role: [evidence]
      Why you: [fit explanation]
      Why now: [timing]
      Evidence: [tier]
    """
    company = merged.get("company", "Unknown")
    role = merged.get("role") or "unspecified role"
    parts = []

    # ── Why this company ─────────────────────────────────────────────────
    signal_types = set()
    signal_detail = ""
    for s in merged.get("sources", []):
        st = s.signal_type if hasattr(s, "signal_type") else ""
        if st and st != "posted_job":
            signal_types.add(st)
        if not signal_detail and hasattr(s, "headline") and s.headline:
            signal_detail = s.headline

    if signal_types:
        types_str = ", ".join(signal_types)
        parts.append(f"Why this company: {company} shows {types_str} signals.")
        if signal_detail and len(signal_detail) > 10:
            parts.append(f"  Signal: {signal_detail[:150]}")
    elif merged.get("is_posted"):
        parts.append(f"Why this company: {company} has an active posting for {role}.")
    else:
        parts.append(f"Why this company: {company} appeared in market scan.")

    # ── Why this role ────────────────────────────────────────────────────
    if merged.get("is_posted"):
        parts.append(f"Why this role: Posted job — the position exists and is actively being filled.")
    elif "funding" in signal_types:
        parts.append(f"Why this role: Funding typically leads to headcount growth — {role} is a likely hire at this stage.")
    elif "leadership" in signal_types:
        parts.append(f"Why this role: Leadership change often creates backfill or restructuring needs.")
    elif "expansion" in signal_types:
        parts.append(f"Why this role: Market expansion requires new regional leadership.")
    elif "hiring_surge" in signal_types:
        parts.append(f"Why this role: High posting volume suggests active team building.")
    else:
        parts.append(f"Why this role: Inferred from signal context — confidence is {tier}.")

    # ── Why you (fit) ────────────────────────────────────────────────────
    fit_parts = []
    mismatch_parts = []
    opp_domain = detect_domain(role)
    user_domains = set(detect_domain(r) for r in user_prefs.get("roles", []) if detect_domain(r))

    if opp_domain and opp_domain in user_domains:
        fit_parts.append(f"functional domain match ({opp_domain})")
    elif opp_domain and user_domains and opp_domain not in user_domains:
        mismatch_parts.append(f"domain mismatch — you target {', '.join(user_domains)}, this is {opp_domain}")

    opp_level = detect_seniority(role)
    user_target_levels = [detect_seniority(r) for r in user_prefs.get("roles", []) if detect_seniority(r) is not None]
    if opp_level is not None and user_target_levels:
        target = max(user_target_levels)
        diff = abs(opp_level - target)
        _LEVEL_NAMES = {0: "IC", 1: "Manager", 2: "Senior Manager", 3: "Director", 4: "VP", 5: "C-suite"}
        if diff == 0:
            fit_parts.append(f"seniority match ({_LEVEL_NAMES.get(opp_level, 'L'+str(opp_level))})")
        elif diff == 1:
            fit_parts.append("adjacent seniority (close enough to consider)")
        elif diff >= 2:
            opp_name = _LEVEL_NAMES.get(opp_level, f"L{opp_level}")
            tgt_name = _LEVEL_NAMES.get(target, f"L{target}")
            mismatch_parts.append(f"seniority gap — role is {opp_name}, you target {tgt_name} ({diff} levels apart)")

    # Sector
    target_sectors = user_prefs.get("sectors", [])
    opp_sector = merged.get("sector") or ""
    if target_sectors and opp_sector:
        from app.services.radar.types import sectors_match as _sm
        if _sm(target_sectors, opp_sector):
            fit_parts.append(f"sector match ({opp_sector})")
        else:
            mismatch_parts.append(f"sector mismatch — you target {', '.join(target_sectors[:3])}, this is {opp_sector}")

    # Region
    target_regions = user_prefs.get("regions", [])
    opp_location = merged.get("location") or ""
    if target_regions and opp_location:
        from app.services.radar.types import regions_match as _rm
        if _rm(target_regions, opp_location):
            fit_parts.append(f"location match ({opp_location})")
        else:
            mismatch_parts.append(f"location mismatch — you target {', '.join(target_regions[:3])}, this is in {opp_location}")

    # Check for undetectable fields — be explicit about what we couldn't assess
    if not opp_domain and user_domains and not fit_parts and not mismatch_parts:
        mismatch_parts.append(f"could not detect functional domain from role title '{role}'")
    if opp_level is None and user_target_levels and not any("seniority" in p for p in fit_parts + mismatch_parts):
        mismatch_parts.append(f"could not detect seniority level from '{role}'")

    # Assemble
    if fit_parts and not mismatch_parts:
        parts.append(f"Why you: {'; '.join(fit_parts)}.")
    elif fit_parts and mismatch_parts:
        parts.append(f"Why you: {'; '.join(fit_parts)}. However: {'; '.join(mismatch_parts)}.")
    elif mismatch_parts:
        parts.append(f"Why you: Poor fit — {'; '.join(mismatch_parts)}.")
    elif breakdown.profile_fit >= 0.5:
        parts.append("Why you: Reasonable alignment with your target profile.")
    else:
        # Build specific "what's missing" explanation
        missing = []
        if not opp_domain:
            missing.append("role domain unknown")
        if opp_level is None:
            missing.append("seniority level undetectable")
        if not merged.get("sector"):
            missing.append("sector not specified")
        if not merged.get("location"):
            missing.append("location not specified")
        if missing:
            parts.append(f"Why you: Cannot fully assess — {'; '.join(missing)}.")
        else:
            parts.append("Why you: No clear alignment with your target profile.")

    # ── Why now ──────────────────────────────────────────────────────────
    if breakdown.competition >= 0.8:
        parts.append("Why now: Low competition — early mover advantage.")
    elif breakdown.recency >= 0.8:
        parts.append("Why now: Very recent signal — act within days.")
    elif merged.get("is_posted") and breakdown.recency >= 0.6:
        parts.append("Why now: Recently posted — still early in the hiring process.")
    elif tier == "speculative":
        parts.append("Why now: Speculative — monitor for stronger signals before investing time.")
    else:
        parts.append("Why now: Moderate timing — no urgency but worth tracking.")

    # ── Evidence tier ────────────────────────────────────────────────────
    tier_labels = {
        "strong": "Strong evidence — high confidence this opportunity is real",
        "medium": "Moderate evidence — verifiable signal but role may not materialise",
        "weak": "Weak evidence — signal exists but role inference is uncertain",
        "speculative": "Speculative — based on pattern matching, not direct evidence",
    }
    parts.append(f"Evidence: {tier_labels.get(tier, tier)}.")

    return "\n".join(parts)
