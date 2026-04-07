"""
app/services/radar/dedup.py

Normalize company/role names and merge multi-source opportunities.
"""

import re
import uuid
from collections import defaultdict

from app.services.radar.types import RadarInput, RadarSource


# Role title normalization aliases
_ROLE_ALIASES = {
    "vp of": "vp",
    "vice president of": "vp",
    "vice president": "vp",
    "sr.": "senior",
    "sr ": "senior ",
    "head of": "head",
    "director of": "director",
}


def _normalize_company(name: str) -> str:
    """Normalize company name for dedup grouping."""
    n = name.lower().strip()
    # Remove common suffixes
    for suffix in [" inc", " inc.", " ltd", " ltd.", " llc", " corp", " corp.", " co.", " co"]:
        if n.endswith(suffix):
            n = n[:-len(suffix)]
    return re.sub(r"[^a-z0-9]", "", n)


def _normalize_role(title: str | None) -> str:
    """Normalize role title for dedup grouping."""
    if not title:
        return ""
    t = title.lower().strip()
    for old, new in _ROLE_ALIASES.items():
        t = t.replace(old, new)
    return re.sub(r"[^a-z0-9 ]", "", t).strip()


def dedup_and_merge(inputs: list[RadarInput]) -> list[dict]:
    """
    Group RadarInputs by (company, role), merge sources.

    Returns list of merged opportunity dicts with:
      - company, role, location, sector (from best source)
      - sources[] (all evidence)
      - merged metadata
    """
    groups: dict[str, list[RadarInput]] = defaultdict(list)

    for inp in inputs:
        if not inp.company:
            continue
        company_key = _normalize_company(inp.company)
        role_key = _normalize_role(inp.role)
        key = f"{company_key}::{role_key}"
        groups[key].append(inp)

    merged = []
    for key, items in groups.items():
        # Pick best source for display fields
        best = max(items, key=lambda x: x.confidence)

        sources = []
        source_tags = set()
        has_hidden_market = False
        has_job_board = False

        for item in items:
            source_tags.add(item.source_type)
            if item.source_type == "hidden_market":
                has_hidden_market = True
            if item.source_type == "job_board":
                has_job_board = True
            sources.append(RadarSource(
                type=item.source_type,
                signal_type=item.signal_type,
                headline=item.headline,
                source_url=item.source_url,
                detected_at=item.detected_at,
                platform=item.platform,
                salary=item.salary,
            ))

        # Merge salary — prefer explicit
        salary = None
        for item in items:
            if item.salary:
                salary = item.salary
                break

        # Collect all fit reasons and red flags
        fit_reasons = []
        red_flags = []
        outreach_hook = ""
        for item in items:
            fit_reasons.extend(item.fit_reasons)
            red_flags.extend(item.red_flags)
            if item.outreach_hook and not outreach_hook:
                outreach_hook = item.outreach_hook

        # Determine most recent detection
        detected_dates = [i.detected_at for i in items if i.detected_at]
        most_recent = max(detected_dates) if detected_dates else None

        # Evidence tier: take the strongest tier across all sources
        # (strong > medium > weak > speculative)
        _TIER_RANK = {"strong": 3, "medium": 2, "weak": 1, "speculative": 0}
        _RANK_TIER = {v: k for k, v in _TIER_RANK.items()}
        best_tier_rank = max(_TIER_RANK.get(i.evidence_tier, 0) for i in items)
        # Boost: if hidden_market + job_board both present, promote to strong
        if has_hidden_market and has_job_board:
            best_tier_rank = max(best_tier_rank, 3)
        evidence_tier = _RANK_TIER.get(best_tier_rank, "weak")

        merged.append({
            "id": str(uuid.uuid4()),
            "company": best.company,
            "company_normalized": _normalize_company(best.company),
            "role": best.role,
            "location": best.location or next((i.location for i in items if i.location), None),
            "sector": best.sector or next((i.sector for i in items if i.sector), None),
            "sources": sources,
            "source_tags": sorted(source_tags),
            "salary": salary,
            "most_recent_date": most_recent,
            "num_sources": len(items),
            "has_hidden_market": has_hidden_market,
            "has_job_board": has_job_board,
            "max_confidence": max(i.confidence for i in items),
            "is_posted": any(i.is_posted for i in items),
            "evidence_tier": evidence_tier,
            "fit_score_precomputed": next((i.fit_score_precomputed for i in items if i.fit_score_precomputed), None),
            "fit_reasons": list(dict.fromkeys(fit_reasons)),  # deduplicate preserving order
            "red_flags": list(dict.fromkeys(red_flags)),
            "outreach_hook": outreach_hook,
        })

    return merged
