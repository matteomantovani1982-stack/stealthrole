"""
app/services/radar/types.py

Data types for OpportunityRadar.

Evidence tiers control what users see by default:
  strong      — show prominently (posted job + growth signal, or authoritative funding news)
  medium      — show with context (single verifiable signal, or 5+ job postings from employer)
  weak        — show in "exploring" section (single low-authority signal, or 3 postings that could be backfills)
  speculative — hidden by default (role inferred from signal type alone, no supporting evidence)
"""

from dataclasses import dataclass, field


# ── Seniority taxonomy ───────────────────────────────────────────────────────
# Maps keywords found in role titles → canonical seniority level (0-5)
# Used for checking whether opportunity seniority matches user seniority.

SENIORITY_LEVELS = {
    # Level 5 — C-suite / top executive
    "ceo": 5, "coo": 5, "cfo": 5, "cto": 5, "cmo": 5, "cio": 5, "cpo": 5,
    "chief": 5, "founder": 5, "co-founder": 5, "president": 5,
    "managing partner": 5, "managing director": 5, "general manager": 5,
    "group head": 5, "group ceo": 5, "group coo": 5,
    # Level 4 — VP / SVP / Senior Director (MENA: country head often = VP)
    "svp": 4, "senior vice president": 4, "evp": 4,
    "vp": 4, "vice president": 4,
    "senior director": 4, "executive director": 4,
    "country head": 4, "regional head": 4, "regional director": 4,
    # Level 3 — Director / Head
    "director": 3, "head": 3, "country manager": 3, "regional manager": 3,
    "principal": 3, "partner": 3,
    "associate director": 3,
    # Level 2 — Senior Manager / Lead
    "senior manager": 2, "lead": 2, "team lead": 2, "staff": 2,
    "senior consultant": 2, "senior specialist": 2,
    "assistant director": 2, "deputy director": 2,
    # Level 1 — Manager
    "manager": 1, "supervisor": 1, "coordinator": 1,
    "assistant manager": 1,
    # Level 0 — Individual contributor
    "analyst": 0, "specialist": 0, "engineer": 0,
    "developer": 0, "designer": 0, "consultant": 0,
    "associate": 0, "officer": 0, "executive": 0,
}


def detect_seniority(role_title: str | None) -> int | None:
    """Return seniority level (0-5) from a role title, or None if undetectable."""
    if not role_title:
        return None
    t = role_title.lower().strip()
    # Check longest keys first to match "senior manager" before "manager"
    # Use word-boundary matching to avoid "engineer" matching inside "engineering"
    import re
    for keyword in sorted(SENIORITY_LEVELS.keys(), key=len, reverse=True):
        if re.search(r'\b' + re.escape(keyword) + r'\b', t):
            return SENIORITY_LEVELS[keyword]
    return None


# ── Functional domain taxonomy ───────────────────────────────────────────────
# Groups role keywords into functional domains so "VP Sales" doesn't match "VP Engineering".

DOMAIN_MAP = {
    "engineering": ["engineering", "software", "developer", "devops", "platform", "infrastructure",
                    "backend", "frontend", "full stack", "sre", "data engineer", "ml engineer", "cto"],
    "product": ["product", "ux", "design", "research", "cpo"],
    "commercial": ["sales", "commercial", "revenue", "business development", "bd", "partnerships",
                   "account", "gtm", "go to market", "cro"],
    "operations": ["operations", "coo", "general manager", "gm", "supply chain", "logistics",
                   "procurement", "facilities"],
    "finance": ["finance", "cfo", "accounting", "treasury", "investor relations", "controller",
                "financial planning"],
    "marketing": ["marketing", "cmo", "growth", "brand", "communications", "pr", "content",
                  "demand gen", "digital marketing"],
    "people": ["hr", "human resources", "people", "talent", "recruiting", "chro",
               "organizational development"],
    "strategy": ["strategy", "corporate development", "m&a", "chief of staff", "transformation",
                 "consulting"],
    "legal": ["legal", "compliance", "regulatory", "governance", "general counsel"],
    "technology": ["cto", "cio", "it", "information technology", "security", "cybersecurity",
                   "cloud", "ai", "machine learning", "data science"],
    "executive": ["ceo", "founder", "co-founder", "president", "managing director",
                  "country manager", "regional director"],
}


def detect_domain(role_title: str | None) -> str | None:
    """Return the functional domain of a role title, or None."""
    if not role_title:
        return None
    import re
    t = role_title.lower().strip()
    # Check longer keywords first for more specific matches
    for domain, keywords in DOMAIN_MAP.items():
        for kw in sorted(keywords, key=len, reverse=True):
            if re.search(r'\b' + re.escape(kw) + r'\b', t):
                return domain
    return None


# ── Sector hierarchy ─────────────────────────────────────────────────────────
# Parent sectors contain children. "fintech" should match target "financial services".

SECTOR_HIERARCHY = {
    "technology": ["tech", "saas", "software", "cloud", "ai", "cybersecurity", "data",
                   "platform", "devtools", "infrastructure"],
    "financial services": ["fintech", "banking", "insurance", "payments", "crypto", "blockchain",
                           "wealth management", "investment", "lending", "neobank"],
    "ecommerce": ["ecommerce", "e-commerce", "marketplace", "retail tech", "d2c", "retail"],
    "healthcare": ["healthtech", "medtech", "biotech", "pharma", "digital health", "wellness"],
    "energy": ["oil", "gas", "renewables", "solar", "cleantech", "utilities", "energy tech"],
    "real estate": ["proptech", "real estate", "construction", "property"],
    "logistics": ["logistics", "supply chain", "shipping", "freight", "mobility",
                  "transportation", "ride-hailing", "last mile", "delivery"],
    "food": ["foodtech", "food delivery", "restaurant tech", "agritech", "agriculture"],
    "education": ["edtech", "education", "training", "e-learning"],
    "consulting": ["consulting", "advisory", "professional services", "management consulting"],
    "government": ["government", "public sector", "defense", "military"],
    "media": ["media", "entertainment", "gaming", "streaming", "content", "adtech", "advertising"],
    "travel": ["travel", "tourism", "hospitality", "hotels", "traveltech"],
}


def sectors_match(target_sectors: list[str], opportunity_sector: str | None) -> bool:
    """Check if opportunity sector matches any target sector, including hierarchy.

    Tokenizes compound sectors like "SaaS Platform" into individual tokens
    and checks each against the hierarchy.
    """
    if not target_sectors or not opportunity_sector:
        return False
    import re
    # Tokenize the opportunity sector on common delimiters
    opp_tokens = [t.strip().lower() for t in re.split(r'[,/\-—&]|\s+', opportunity_sector) if t.strip()]
    opp_full = opportunity_sector.lower().strip()

    for ts in target_sectors:
        ts_lower = ts.lower().strip()
        # Direct match on full string
        if ts_lower == opp_full or ts_lower in opp_full or opp_full in ts_lower:
            return True
        # Check each token
        for token in opp_tokens:
            if ts_lower == token or ts_lower in token or token in ts_lower:
                return True
        # Hierarchy match: check if target and any opp token share a parent
        ts_parent = _find_sector_parent(ts_lower)
        if ts_parent:
            if _find_sector_parent(opp_full) == ts_parent:
                return True
            for token in opp_tokens:
                if _find_sector_parent(token) == ts_parent:
                    return True
    return False


def _find_sector_parent(sector: str) -> str | None:
    """Find the parent sector group for a given sector name."""
    for parent, children in SECTOR_HIERARCHY.items():
        if sector == parent:
            return parent
        for child in children:
            # Exact match or sector starts/ends with child
            if sector == child:
                return parent
            # "fintech" should match child "fintech", not child "tech"
            # Only allow containment if child is the FULL sector or a clear prefix/suffix
            if len(child) >= 5 and (sector.startswith(child) or sector.endswith(child)):
                return parent
    return None


# ── Region equivalence ───────────────────────────────────────────────────────

REGION_GROUPS = {
    "gcc": ["uae", "dubai", "abu dhabi", "ksa", "saudi", "riyadh", "jeddah",
            "qatar", "doha", "bahrain", "manama", "kuwait", "oman", "muscat"],
    "mena": ["gcc", "uae", "dubai", "ksa", "saudi", "egypt", "cairo",
             "jordan", "amman", "lebanon", "beirut", "morocco", "tunisia"],
    "global": [],
    "remote": [],
}

# City → country mapping. When user says "UAE", match any UAE city.
# When user says "Dubai", match only "Dubai" (direct containment handles this).
CITY_TO_COUNTRY = {
    "dubai": "uae", "abu dhabi": "uae", "sharjah": "uae", "ajman": "uae",
    "riyadh": "ksa", "jeddah": "ksa", "dammam": "ksa", "neom": "ksa",
    "doha": "qatar", "manama": "bahrain", "muscat": "oman",
    "kuwait city": "kuwait",
    "cairo": "egypt", "alexandria": "egypt",
    "amman": "jordan", "beirut": "lebanon",
    "casablanca": "morocco", "tunis": "tunisia",
    "london": "uk", "manchester": "uk", "edinburgh": "uk",
    "new york": "us", "san francisco": "us", "austin": "us", "boston": "us",
    "toronto": "canada", "vancouver": "canada",
    "berlin": "germany", "munich": "germany",
    "paris": "france", "amsterdam": "netherlands",
    "singapore": "singapore", "hong kong": "hong kong",
    "mumbai": "india", "bangalore": "india", "delhi": "india",
}


def _resolve_country(location: str) -> str | None:
    """Resolve a location string to a country code using city→country map."""
    loc = location.lower().strip()
    # Check direct city match
    for city, country in CITY_TO_COUNTRY.items():
        if city in loc:
            return country
    return None


def regions_match(target_regions: list[str], opportunity_location: str | None) -> bool:
    """Check if opportunity location matches any target region.

    Resolution order:
    1. Global/remote → match everything
    2. Direct containment (e.g., "UAE" in "Dubai, UAE")
    3. City→country resolution (e.g., user="UAE", loc="Dubai" → Dubai is in UAE → match)
    4. Group expansion ONLY for group names (GCC, MENA)
    """
    if not target_regions or not opportunity_location:
        return False
    loc = opportunity_location.lower().strip()
    loc_country = _resolve_country(loc)  # e.g., "riyadh, saudi arabia" → "ksa"

    for tr in target_regions:
        tr_lower = tr.lower().strip()

        # Global/remote matches everything
        if tr_lower in ("global", "remote") or loc in ("global", "remote"):
            return True

        # Direct containment (require min 3 chars to avoid "uk" in "dubai")
        if len(tr_lower) >= 3 and (tr_lower in loc or loc in tr_lower):
            return True

        # Exact short match
        if len(tr_lower) < 3 and tr_lower == loc:
            return True

        # City→country resolution: user says "UAE", location is "Dubai"
        # Dubai resolves to "uae" → matches user target "uae"
        if loc_country and tr_lower == loc_country:
            return True

        # Also check: user says "Dubai" (a city), location is "UAE"
        # Resolve user target as city → country, check if that country appears in loc
        tr_country = _resolve_country(tr_lower)
        if tr_country and tr_country in loc:
            return True

        # Group expansion: ONLY for group names (gcc, mena)
        _GROUP_NAMES = {"gcc", "mena"}
        if tr_lower in _GROUP_NAMES:
            members = REGION_GROUPS.get(tr_lower, [])
            # Check direct membership
            if any(m in loc for m in members if len(m) >= 3):
                return True
            # Check resolved country membership
            if loc_country and loc_country in members:
                return True

    return False


@dataclass
class RadarInput:
    """Normalized input from any signal source."""
    company: str
    role: str | None = None
    location: str | None = None
    sector: str | None = None
    source_type: str = ""          # hidden_market | job_board | signal_engine
    signal_type: str = ""          # funding | leadership | expansion | posted_job | velocity
    headline: str = ""
    detail: str = ""
    source_url: str = ""
    confidence: float = 0.5
    detected_at: str | None = None
    salary: str | None = None
    is_posted: bool = False
    platform: str | None = None    # linkedin | adzuna | jsearch
    evidence_tier: str = "medium"  # strong | medium | weak | speculative
    # Pre-computed fields from signal engine
    fit_score_precomputed: int | None = None
    fit_reasons: list[str] = field(default_factory=list)
    red_flags: list[str] = field(default_factory=list)
    outreach_hook: str = ""


@dataclass
class ScoreBreakdown:
    """Detailed scoring breakdown for a radar opportunity."""
    profile_fit: float = 0.0       # 0-1
    signal_strength: float = 0.0   # 0-1
    recency: float = 0.0           # 0-1
    competition: float = 0.0       # 0-1
    conviction: float = 0.0        # 0-1


@dataclass
class RadarSource:
    """One piece of evidence for an opportunity."""
    type: str                      # hidden_market | job_board | signal_engine
    signal_type: str = ""
    headline: str = ""
    source_url: str = ""
    detected_at: str | None = None
    platform: str | None = None
    salary: str | None = None

    def to_dict(self) -> dict:
        d = {"type": self.type, "signal_type": self.signal_type, "headline": self.headline}
        if self.source_url:
            d["source_url"] = self.source_url
        if self.detected_at:
            d["detected_at"] = self.detected_at
        if self.platform:
            d["platform"] = self.platform
        if self.salary:
            d["salary"] = self.salary
        return d


@dataclass
class RadarOpportunity:
    """A single ranked opportunity in the radar output."""
    id: str
    rank: int = 0
    company: str = ""
    company_normalized: str = ""
    role: str | None = None
    location: str | None = None
    sector: str | None = None
    radar_score: int = 0
    score_breakdown: ScoreBreakdown = field(default_factory=ScoreBreakdown)
    sources: list[RadarSource] = field(default_factory=list)
    source_tags: list[str] = field(default_factory=list)
    reasoning: str = ""
    suggested_action: str = ""
    outreach_hook: str = ""
    urgency: str = "medium"        # high | medium | low
    evidence_tier: str = "medium"  # strong | medium | weak | speculative
    timeline: str = ""
    fit_reasons: list[str] = field(default_factory=list)
    red_flags: list[str] = field(default_factory=list)
    actions: dict = field(default_factory=lambda: {
        "can_generate_pack": True,
        "can_generate_shadow": True,
        "can_generate_outreach": True,
        "can_save": True,
        "pack_job_run_id": None,
        "shadow_app_id": None,
    })
    first_seen_at: str | None = None
    is_saved: bool = False
    is_dismissed: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "rank": self.rank,
            "company": self.company,
            "company_normalized": self.company_normalized,
            "role": self.role,
            "location": self.location,
            "sector": self.sector,
            "radar_score": self.radar_score,
            "score_breakdown": {
                "profile_fit": self.score_breakdown.profile_fit,
                "signal_strength": self.score_breakdown.signal_strength,
                "recency": self.score_breakdown.recency,
                "competition": self.score_breakdown.competition,
                "conviction": self.score_breakdown.conviction,
            },
            "sources": [s.to_dict() for s in self.sources],
            "source_tags": self.source_tags,
            "reasoning": self.reasoning,
            "suggested_action": self.suggested_action,
            "outreach_hook": self.outreach_hook,
            "urgency": self.urgency,
            "evidence_tier": self.evidence_tier,
            "timeline": self.timeline,
            "fit_reasons": self.fit_reasons,
            "red_flags": self.red_flags,
            "actions": self.actions,
            "first_seen_at": self.first_seen_at,
            "is_saved": self.is_saved,
            "is_dismissed": self.is_dismissed,
        }
