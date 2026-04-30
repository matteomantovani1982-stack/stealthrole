"""
app/services/linkedin/relationship_engine.py

Relationship Engine — finds warm paths to target companies through LinkedIn.

Key capabilities:
  1. Normalized company matching (fuzzy, alias-aware)
  2. Direct contact detection + ranking by functional relevance
  3. Warm path detection (You → Connection → Target Company)
  4. Intro message generation with context
  5. Pipeline tracking
"""

import re
import unicodedata
import uuid
from datetime import UTC, datetime
from collections import defaultdict

import structlog
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.models.linkedin_connection import LinkedInConnection
from app.models.warm_intro import WarmIntro, IntroStatus

logger = structlog.get_logger(__name__)


# ── Company normalization ─────────────────────────────────────────────────────

# Common alias map: alias → canonical name
COMPANY_ALIASES = {
    "aws": "amazon",
    "amazon web services": "amazon",
    "amazon.com": "amazon",
    "meta platforms": "meta",
    "facebook": "meta",
    "fb": "meta",
    "alphabet": "google",
    "google cloud": "google",
    "google llc": "google",
    "microsoft corporation": "microsoft",
    "msft": "microsoft",
    "tcts": "tata communications",
    "tata communications (tcts)": "tata communications",
    "mckinsey & company": "mckinsey",
    "mckinsey and company": "mckinsey",
    "mck": "mckinsey",
    "bcg": "boston consulting group",
    "bain & company": "bain",
    "bain and company": "bain",
    "pwc": "pricewaterhousecoopers",
    "pricewaterhousecoopers": "pwc",
    "ey": "ernst & young",
    "ernst young": "ernst & young",
    "jpmorgan": "jp morgan",
    "j.p. morgan": "jp morgan",
    "jpmc": "jp morgan",
    "deloitte consulting": "deloitte",
    # Oliver Wyman + parent group
    "ow": "oliver wyman",
    "oliver wyman group": "oliver wyman",
    "marsh mclennan": "marsh & mclennan",
    "mmc": "marsh & mclennan",
    # Accenture / strategy houses
    "acn": "accenture",
    "accenture strategy": "accenture",
    # Roland Berger
    "rb": "roland berger",
    "roland berger strategy consultants": "roland berger",
    # Kearney
    "at kearney": "kearney",
    "a.t. kearney": "kearney",
    # LEK
    "lek consulting": "lek",
    "l.e.k. consulting": "lek",
    "l.e.k.": "lek",
    # Strategy&
    "strategy&": "strategy and",
    "strategy &": "strategy and",
    # UAE banks
    "mashreq": "mashreq bank",
    "mashreq bank psc": "mashreq bank",
    "mashreqbank": "mashreq bank",
    "mashreq neo": "mashreq bank",
    "mashreq global": "mashreq bank",
    "mashreq capital": "mashreq bank",
    "mashreq al islami": "mashreq bank",
    "mashreq securities": "mashreq bank",
}

# Suffixes to strip
COMPANY_SUFFIXES = [
    "inc", "inc.", "ltd", "ltd.", "llc", "llp", "plc", "corp", "corp.",
    "corporation", "company", "co", "co.", "group", "holdings", "international",
    "pvt", "private", "limited", "gmbh", "sa", "s.a.", "ag", "psc", "pjsc", "fzc", "fze", "fzco",
]


def _is_former_company(name: str) -> bool:
    """Check if a company field indicates a former/past employer."""
    n = name.lower().strip()
    return bool(re.match(r'^(ex[\s\-]|former[\s\-]|previously[\s\-]|prev[\s\-]|fka[\s\-])', n))


def normalize_text(text: str) -> str:
    """Lowercase + strip punctuation + collapse whitespace.

    Used by the Way In discovery pipeline for token matching against
    candidate titles, snippets, and search queries.
    """
    if not text:
        return ""
    n = text.lower()
    n = re.sub(r"[^\w\s&]", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    return n


def normalize_company(name: str) -> str:
    """Normalize company name for matching."""
    if not name:
        return ""
    n = name.lower().strip()
    # Strip "Ex-" / "Former" prefix (so "Ex-Oliver Wyman" → "oliver wyman")
    n = re.sub(r'^(ex[\s\-]|former[\s\-]|previously[\s\-]|prev[\s\-]|fka[\s\-])', '', n).strip()
    # Remove content in parentheses
    n = re.sub(r'\([^)]*\)', '', n).strip()
    # Remove punctuation except &
    n = re.sub(r'[^\w\s&]', ' ', n).strip()
    # Remove common suffixes
    words = n.split()
    words = [w for w in words if w not in COMPANY_SUFFIXES]
    n = " ".join(words).strip()
    # Check alias map
    if n in COMPANY_ALIASES:
        n = COMPANY_ALIASES[n]
    return n


def strip_linkedin_display_noise(text: str) -> str:
    """Remove bidi / invisible chars LinkedIn embeds around display names (e.g. RTL marks)."""
    if not text:
        return ""
    s = unicodedata.normalize("NFKC", text)
    for ch in (
        "\u200e",
        "\u200f",
        "\u202a",
        "\u202b",
        "\u202c",
        "\u202d",
        "\u202e",
        "\u2066",
        "\u2067",
        "\u2068",
        "\u2069",
        "\ufeff",
    ):
        s = s.replace(ch, "")
    return s.strip()


def normalize_person_name(name: str) -> str:
    """Strip credentials and parentheticals for mutual / connector name matching."""
    n = strip_linkedin_display_noise(name or "")
    n = n.lower().strip()
    if not n:
        return ""
    n = re.sub(
        r",?\s*(?:mba|phd|pmp|cfa|cpa|md|pe|esq|jr\.?|sr\.?|ii|iii|iv)\.?\s*$",
        "",
        n,
        flags=re.IGNORECASE,
    ).strip()
    n = re.sub(r"\([^)]*\)", "", n).strip()
    n = re.sub(r"\s+", " ", n)
    return n


def linkedin_profile_slug_from_url(url: str) -> str:
    """Public /in/{slug} segment, lowercased (matches across www / country TLD)."""
    if not url or "/in/" not in url.lower():
        return ""
    part = url.lower().split("/in/", 1)[-1]
    return part.split("?")[0].strip("/")


def match_connector_from_mutual(
    mc,
    conn_by_id: dict[str, LinkedInConnection],
    conn_by_name: dict[str, LinkedInConnection],
    conn_by_first_last: dict[str, LinkedInConnection],
    conn_by_slug: dict[str, LinkedInConnection],
) -> LinkedInConnection | None:
    """Resolve mutual's connector name/id to one of the user's 1st-degree connections."""
    mid = (getattr(mc, "mutual_linkedin_id", None) or "").strip()
    mname = normalize_person_name(getattr(mc, "mutual_name", None) or "")
    if mid and mid in conn_by_id:
        return conn_by_id[mid]
    if mid:
        key = mid.lower()
        if key in conn_by_slug:
            return conn_by_slug[key]
    if mname and mname in conn_by_name:
        return conn_by_name[mname]
    if mname:
        parts = mname.split()
        if len(parts) >= 2:
            fl_key = f"{parts[0]} {parts[-1]}"
            if fl_key in conn_by_first_last:
                return conn_by_first_last[fl_key]
        slug = re.sub(r"[^a-z0-9]", "-", mname).strip("-")
        if slug:
            if slug in conn_by_slug:
                return conn_by_slug[slug]
            if slug in conn_by_first_last:
                return conn_by_first_last[slug]
    if mname and len(mname) >= 4:
        for stored_name, conn in conn_by_name.items():
            if stored_name.startswith(mname) or mname.startswith(stored_name):
                if abs(len(stored_name) - len(mname)) < 15:
                    return conn
    return None


def companies_match(a: str, b: str) -> bool:
    """Check if two company names refer to the same company."""
    na = normalize_company(a)
    nb = normalize_company(b)
    if not na or not nb:
        return False
    # Exact match after normalization
    if na == nb:
        return True
    # Containment: one contains the other (e.g. "Amazon" in "Amazon Web Services")
    # MUST require the shorter string to be at least 5 chars to avoid
    # false positives like "bank" matching "Mashreq Bank"
    shorter, longer = (na, nb) if len(na) <= len(nb) else (nb, na)
    if len(shorter) >= 5 and shorter in longer:
        return True
    # First-word fallback is useful for real brand prefixes, but can create
    # bad matches for generic words like "digital", "professional", etc.
    # Keep this strict to avoid false positives in path-in.
    if na.split() and nb.split():
        first_a = na.split()[0]
        first_b = nb.split()[0]
        generic_first_words = {
            "digital", "professional", "bank", "group", "capital", "global",
            "international", "solutions", "services", "technology",
            "technologies", "consulting", "management", "partners",
        }
        if first_a == first_b and len(first_a) >= 5 and first_a not in generic_first_words:
            # Only allow first-word fallback when at least one side is effectively
            # a single-brand token (e.g., "careem" vs "careem networks").
            if len(na.split()) == 1 or len(nb.split()) == 1:
                return True
    return False


def _wayin_headline_bucket(title_norm: str, company_hint_norm: str) -> str:
    """LinkedIn-style fields only (title line + parsed employer). Excludes snippet."""
    return f"{title_norm} {company_hint_norm}".strip()


def _wayin_company_tokens_in_text(company_tokens: list[str], text: str) -> int:
    if not text or not company_tokens:
        return 0
    return sum(
        1 for t in company_tokens
        if re.search(rf"\b{re.escape(t)}\b", text)
    )


def _wayin_snippet_suggests_past_only_employer(
    title_norm: str,
    company_hint_norm: str,
    snippet_norm: str,
    company_norm: str,
) -> bool:
    """Drop Serp rows where the target company appears as a *past* job in the snippet but not in the headline."""
    if not company_norm or not snippet_norm or company_norm not in snippet_norm:
        return False
    headline = _wayin_headline_bucket(title_norm, company_hint_norm)
    if company_norm in headline:
        return False
    past_re = re.compile(
        r"\b(?:ex[\s\-]|former|previously|past\s|alumni|alumnus|"
        r"used\s+to\s+work|worked\s+at|left\s+)\b",
        re.I,
    )
    return past_re.search(snippet_norm) is not None


# ── Functional relevance ──────────────────────────────────────────────────────

ROLE_DOMAINS = {
    "engineering": ["engineer", "developer", "cto", "vp engineering", "tech lead", "architect", "devops", "sre", "software"],
    "product": ["product", "pm", "product manager", "vp product", "head of product"],
    "strategy": ["strategy", "operations", "chief of staff", "coo", "business development", "biz dev", "transformation"],
    "commercial": ["sales", "growth", "marketing", "cmo", "revenue", "commercial", "partnerships", "bd"],
    "finance": ["finance", "cfo", "controller", "treasury", "investor relations", "fp&a"],
    "hr": ["hr", "people", "talent", "recruiter", "recruiting", "human resources", "people operations"],
    "design": ["design", "ux", "ui", "creative", "head of design"],
    "data": ["data", "analytics", "ml", "machine learning", "ai", "data science"],
    "executive": ["ceo", "founder", "co-founder", "president", "managing director", "general manager", "country manager"],
}


def detect_domain(title: str) -> str:
    """Detect functional domain from a job title."""
    if not title:
        return "general"
    tl = title.lower()
    for domain, keywords in ROLE_DOMAINS.items():
        if any(kw in tl for kw in keywords):
            return domain
    return "general"


def seniority_tier(title: str) -> tuple[int, str]:
    """Classify a title into a seniority tier used by the Way In ranker.

    Returns (rank, label) where rank is 0..4:
        0 RECRUITER, 1 IC, 2 MANAGER, 3 VP_DIRECTOR, 4 C_SUITE
    Order of checks matters — VP/Director must come before C_SUITE
    because "Vice President" contains "president".
    """
    t = (title or "").lower()
    # Recruiter / talent / HR
    if any(k in t for k in [
        "recruiter", "talent acquisition", "talent partner", "headhunter",
        "head hunter", "human resources", "people operations", "people partner",
        "staffing", "executive search", "search consultant", "resourcing",
        "recruitment",
    ]):
        return (0, "RECRUITER")
    # "Managing Director/Partner" / GM are C-suite-equivalent.
    if any(k in t for k in ["managing director", "managing partner", "general manager"]):
        return (4, "C_SUITE")
    # VP / SVP / EVP / Director / Head of (must come before plain C_SUITE check
    # because "Vice President" contains "president").
    if (
        any(k in t for k in ["vice president", "vp ", "svp", "evp"])
        or t.startswith("vp")
        or any(k in t for k in ["head of", "group director", "regional director"])
        or re.search(r"\bdirector\b", t)
    ):
        return (3, "VP_DIRECTOR")
    is_partner = bool(re.search(r"\bpartner\b", t)) and "partnership" not in t
    if (
        is_partner
        or any(re.search(r"\b" + k + r"\b", t) for k in ["ceo", "coo", "cfo", "cto", "cio", "cpo", "chro"])
        or any(k in t for k in ["chief", "founder", "co-founder", "president"])
    ):
        return (4, "C_SUITE")
    if re.search(r"\bmanager\b", t) or any(k in t for k in [
        "lead", "principal", "senior manager", "team lead", "supervisor", "department head",
    ]):
        return (2, "MANAGER")
    return (1, "IC")


def detect_seniority(title: str) -> int:
    """Score seniority from title. Higher = more senior."""
    if not title:
        return 0
    tl = title.lower()
    # "Managing Director" MUST come before both VP and general director checks
    if "managing director" in tl:
        return 100
    # VP check MUST come before "president" — "Vice President" contains "president"
    if any(k in tl for k in ["vice president", "svp", "evp"]) or re.search(r'\bvp\b', tl):
        return 80
    # C-suite: use word boundaries for short abbreviations to avoid
    # "cto" matching "director", "coo" matching "scooter", etc.
    if any(re.search(r'\b' + k + r'\b', tl) for k in ["ceo", "coo", "cfo", "cto", "cmo"]):
        return 100
    if any(k in tl for k in ["founder", "president", "chief"]):
        return 100
    # "partner" needs word boundary to avoid matching "partnerships"
    is_partner = bool(re.search(r'\bpartner\b', tl)) and 'partnership' not in tl
    if is_partner:
        return 80
    if any(k in tl for k in ["director", "head of"]):
        return 70
    if any(k in tl for k in ["senior manager", "principal"]):
        return 55
    if any(k in tl for k in ["manager", "lead", "team lead"]):
        return 45
    if any(k in tl for k in ["senior", "sr."]):
        return 35
    return 20


# ── Connection ranking ────────────────────────────────────────────────────────

def rank_connection(conn: LinkedInConnection, target_role: str | None = None) -> int:
    """Score a connection for intro value. Considers role, seniority, recruiter status."""
    score = 0
    title = conn.current_title or ""

    # Recruiter boost
    if conn.is_recruiter or detect_domain(title) == "hr":
        score += 100

    # Hiring manager boost
    if conn.is_hiring_manager:
        score += 80

    # Seniority
    score += detect_seniority(title)

    # Functional relevance to target role
    if target_role:
        target_domain = detect_domain(target_role)
        conn_domain = detect_domain(title)
        if target_domain == conn_domain and target_domain != "general":
            score += 40  # Same function = very relevant

    # Relationship strength
    if conn.relationship_strength == "strong":
        score += 30
    elif conn.relationship_strength == "medium":
        score += 10

    return score


def _generate_intro_message(
    connection_name: str,
    target_company: str,
    target_role: str | None,
    relationship_context: str | None,
    is_recruiter: bool,
    connection_title: str | None = None,
    connection_seniority: int = 50,
) -> str:
    first_name = connection_name.split()[0] if connection_name else "there"
    role_mention = f" the {target_role} role" if target_role else " opportunities"

    # Recruiter/HR — be direct about the role
    if is_recruiter:
        if relationship_context:
            return (
                f"Hi {first_name}, {relationship_context} — I wanted to reach out. "
                f"I'm actively exploring{role_mention} at {target_company} and I'd love to learn about "
                f"the hiring process and what the team is looking for. Would you have 10 minutes this week?"
            )
        return (
            f"Hi {first_name}, I see you're handling talent at {target_company}. "
            f"I'm very interested in{role_mention} and believe my background is a strong fit. "
            f"Would you be open to a quick conversation about the role and what the ideal candidate looks like?"
        )

    # Senior / C-suite — lead with strategic value, not job-seeking
    if connection_seniority >= 70:
        if relationship_context:
            return (
                f"Hi {first_name}, {relationship_context}. "
                f"I've been following {target_company}'s trajectory closely and I'd welcome your perspective "
                f"on where the business is headed. Would you be open to a 15-minute call? "
                f"I have some thoughts on the operational challenges at this stage that might be useful."
            )
        return (
            f"Hi {first_name}, I noticed your work at {target_company} — impressive growth. "
            f"I'm exploring how my operational experience could contribute to what you're building. "
            f"Rather than a formal ask, I'd love to exchange perspectives over coffee or a quick call."
        )

    # Same-function peer — ask about team dynamics and culture
    if connection_title and target_role:
        conn_domain = detect_domain(connection_title)
        role_domain = detect_domain(target_role)
        if conn_domain and conn_domain == role_domain:
            if relationship_context:
                return (
                    f"Hi {first_name}, {relationship_context}. "
                    f"I'm looking at{role_mention} at {target_company} and since you're in the same function, "
                    f"I'd really value your take on the team dynamics, culture, and what day-to-day looks like. "
                    f"Would you be open to a quick chat?"
                )
            return (
                f"Hi {first_name}, I'm exploring{role_mention} at {target_company}. "
                f"As someone in a similar function there, your perspective on the team and culture "
                f"would be incredibly valuable. Would 10 minutes work sometime this week?"
            )

    # General connection — warm but specific
    if relationship_context:
        return (
            f"Hi {first_name}, hope you're well! {relationship_context} — I wanted to reach out. "
            f"I'm exploring{role_mention} at {target_company} and would love to hear about your "
            f"experience there. Even a brief perspective on the culture and team would help a lot."
        )
    return (
        f"Hi {first_name}, I'm exploring{role_mention} at {target_company} "
        f"and I see you're connected to the team. I'd appreciate any insights you could share about "
        f"the company culture and what they value in leaders. Would a quick call work?"
    )


def _suggest_cold_outreach_angle(conn: LinkedInConnection, company: str, target_role: str | None) -> str:
    """Suggest an angle for cold outreach to someone you're NOT connected to."""
    title = conn.current_title or "employee"
    seniority = detect_seniority(title)

    if conn.is_recruiter or detect_domain(title) == "hr":
        return f"{conn.full_name} handles talent/recruiting at {company} — reach out about the {target_role or 'role'} directly"

    if seniority >= 70:
        return f"{conn.full_name} is {title} at {company} — senior enough to influence hiring. Lead with value: mention a specific insight about their business"

    if target_role and detect_domain(target_role) == detect_domain(title):
        return f"{conn.full_name} is {title} — same function as your target role. Ask about team structure and what they look for in candidates"

    return f"{conn.full_name} is {title} at {company} — connect with a specific, personalized reason tied to their work"


def _generate_cold_outreach(
    name: str, company: str, role: str | None,
    title: str | None = None, is_recruiter: bool = False,
) -> str:
    """Generate a cold outreach message for someone you're NOT connected to.
    Varies by their seniority and function."""
    first = name.split()[0] if name else "there"
    seniority = detect_seniority(title or "") if title else 50

    if is_recruiter or (title and detect_domain(title or "") == "hr"):
        return (
            f"Hi {first}, I came across your profile at {company} and I'm very interested in "
            f"{'the ' + role + ' opportunity' if role else 'senior opportunities there'}. "
            f"My background in operations leadership across MENA may be relevant — "
            f"would you be open to a brief conversation about what you're looking for?"
        )

    if seniority >= 70:
        # Senior leader — lead with business insight, not job ask
        return (
            f"Hi {first}, I've been following {company}'s recent moves with interest. "
            f"{'The ' + role + ' mandate' if role else 'The strategic direction'} resonates "
            f"with challenges I've navigated before. I'd welcome the chance to exchange perspectives — "
            f"no ask, just a conversation between peers."
        )

    if seniority >= 50:
        # Mid-level — ask about team and culture
        return (
            f"Hi {first}, I'm researching {company} and your experience as "
            f"{title or 'part of the team'} caught my eye. "
            f"{'I am exploring ' + role + ' and' if role else 'I'} would love to hear your take on "
            f"the team culture and what it's like to work there. Quick 10-min call?"
        )

    # More junior — friendly, casual
    return (
        f"Hi {first}, I'm exploring opportunities at {company} "
        f"{'in the ' + role + ' area ' if role else ''}and I'd love to learn more about "
        f"what the company culture is like from someone on the ground. Open to a quick chat?"
    )


def _suggest_intro_angle(conn: LinkedInConnection, target_role: str | None) -> str:
    title = conn.current_title or "employee"
    company = conn.current_company or "the company"

    if conn.is_recruiter or detect_domain(title) == "hr":
        return f"{conn.full_name} is a recruiter/HR at {company} — direct path to open roles and hiring pipeline"

    if conn.is_hiring_manager or detect_seniority(title) >= 70:
        return f"{conn.full_name} is {title} at {company} — likely a decision maker or peer to the hiring manager"

    if target_role and detect_domain(target_role) == detect_domain(title):
        return f"{conn.full_name} is {title} — same function as your target role, strong referral potential"

    return f"{conn.full_name} works at {company} as {title} — insider perspective and potential referral"


# ── Relationship Engine ───────────────────────────────────────────────────────

class RelationshipEngine:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._company_intel_cache: dict[str, str] = {}

    def _resolve_target_company(self, company: str, role: str | None, all_conns: list[LinkedInConnection]) -> str:
        """
        Resolve placeholder/undisclosed company labels to a concrete company when
        the role string contains a real brand (e.g., "Revolut — GM MENA").
        """
        raw_company = (company or "").strip()
        company_lower = raw_company.lower()
        if not any(k in company_lower for k in ["undisclosed", "confidential", "stealth", "unknown"]):
            return raw_company

        role_str = (role or "").strip()
        if not role_str:
            return raw_company

        # Common title patterns:
        #   "<Company> — <Role>"
        #   "<Role details> | <Company> — <Role>"
        candidates: list[str] = []
        if "—" in role_str:
            candidates.append(role_str.split("—", 1)[0].strip())
        if " - " in role_str:
            candidates.append(role_str.split(" - ", 1)[0].strip())
        for seg in re.split(r"[|•]", role_str):
            s = seg.strip()
            if not s:
                continue
            if "—" in s:
                candidates.append(s.split("—", 1)[0].strip())
            elif " - " in s:
                candidates.append(s.split(" - ", 1)[0].strip())
            else:
                candidates.append(s)

        def _is_plausible_company_name(name: str) -> bool:
            n = normalize_company(name)
            if not n:
                return False
            banned = {
                "digital", "banking", "expansion", "licensed", "company",
                "name", "undisclosed", "target", "role", "mena", "uae",
            }
            tokens = [t for t in n.split() if t]
            if not tokens:
                return False
            if all(t in banned for t in tokens):
                return False
            return True

        for left_candidate in candidates:
            if not left_candidate or not _is_plausible_company_name(left_candidate):
                continue
            # Verify it looks real against imported network companies when possible.
            conn_match_count = 0
            for c in all_conns:
                if c.current_company and companies_match(c.current_company, left_candidate):
                    conn_match_count += 1
                    if conn_match_count >= 1:
                        return left_candidate
            # If no connection match exists, still prefer explicit company-looking string.
            norm = normalize_company(left_candidate)
            if len(norm.split()) <= 4 and "digital banking expansion" not in norm:
                return left_candidate

        return raw_company

    # ── Company intel gathering ──────────────────────────────────────────

    def _gather_company_intel(self, company: str) -> str:
        """
        Gather quick signals about a company via Serper: recent news,
        funding, growth, strategic moves. Returns a short summary string
        for use as icebreaker context in messages. Cached per company
        within this request and in Redis for 24h.
        """
        if company in self._company_intel_cache:
            return self._company_intel_cache[company]

        # Skip intel generation for placeholder/undisclosed company labels.
        # Pulling web intel for these names causes misleading fabricated context.
        company_l = (company or "").lower()
        if any(k in company_l for k in ["undisclosed", "confidential", "stealth", "unknown"]):
            self._company_intel_cache[company] = ""
            return ""

        # Check Redis cache first
        import hashlib
        cache_key = f"company_intel:{hashlib.sha256(company.lower().encode()).hexdigest()[:12]}"
        try:
            import redis
            from app.config import settings as _s
            r = redis.Redis.from_url(_s.redis_url, decode_responses=True)
            cached = r.get(cache_key)
            if cached:
                self._company_intel_cache[company] = cached
                return cached
        except Exception:
            r = None

        # Gather via Serper
        intel_lines = []
        try:
            from app.config import settings
            if not settings.serper_api_key:
                return ""
            import httpx
            client = httpx.Client(timeout=6)
            queries = [
                f"{company} recent news 2026",
                f"{company} expansion growth hiring 2026",
            ]
            seen_snippets = set()
            for q in queries:
                try:
                    resp = client.post(
                        "https://google.serper.dev/search",
                        headers={"X-API-KEY": settings.serper_api_key, "Content-Type": "application/json"},
                        json={"q": q, "num": 3},
                    )
                    if resp.status_code == 200:
                        for r_item in resp.json().get("organic", []):
                            snippet = r_item.get("snippet", "").strip()
                            if snippet and snippet not in seen_snippets:
                                seen_snippets.add(snippet)
                                intel_lines.append(snippet)
                except Exception:
                    continue
            client.close()
        except Exception:
            pass

        intel = " | ".join(intel_lines[:4]) if intel_lines else ""
        self._company_intel_cache[company] = intel

        # Cache in Redis for 24h
        if r and intel:
            try:
                r.setex(cache_key, 86400, intel)
            except Exception:
                pass

        return intel

    # ── Personalized message generation ──────────────────────────────────

    def _craft_message(
        self,
        recipient_name: str,
        recipient_title: str,
        recipient_headline: str,
        company: str,
        role: str | None,
        company_intel: str,
        message_type: str = "direct",  # "direct" | "intro_request"
        # For intro_request only:
        connector_name: str = "",
    ) -> str:
        """
        Generate a hyper-personalized LinkedIn message using Claude.
        message_type:
          - "direct": You're messaging someone AT the target company
          - "intro_request": You're asking your connection to intro you to someone
        """
        import hashlib
        cache_key = None
        try:
            import redis
            from app.config import settings as _s
            r = redis.Redis.from_url(_s.redis_url, decode_responses=True)
            key_hash = hashlib.sha256(
                f"{message_type}|{recipient_name}|{recipient_title}|{company}|{role}|{connector_name}".encode()
            ).hexdigest()[:16]
            cache_key = f"msg:{key_hash}"
            cached = r.get(cache_key)
            if cached and str(cached).strip():
                return str(cached).strip()
        except Exception:
            r = None

        try:
            from app.services.llm.client import ClaudeClient
            from app.services.llm.router import LLMTask

            first_name = recipient_name.split()[0] if recipient_name else "there"

            if message_type == "intro_request":
                # Asking YOUR connection to introduce you to someone at the company
                system_prompt = (
                    "You write LinkedIn DMs that get replies. The user will paste this into LinkedIn.\n"
                    "- You are writing TO your 1st-degree connection (the recipient). "
                    "You want a warm intro TO a specific person they know at the same company.\n"
                    "- Open with something SPECIFIC about the recipient — role, headline, or shared context. "
                    "Never 'Hope you're well.'\n"
                    "- Name the person you want to meet and why (role you're pursuing at that company, "
                    "what insight would help — hiring, team, culture, process).\n"
                    "- One clear ask: intro. Offer a 1–2 sentence blurb they can forward.\n"
                    "- Under 70 words. No fluff, no buzzwords. Do not invent facts not in the prompt.\n"
                    "- End with: No pressure at all!\n"
                    "- Return ONLY the message body. No subject line, no brackets, no placeholders."
                )
                user_prompt = (
                    f"Write a message to {recipient_name} ({recipient_title}).\n"
                    f"Their LinkedIn headline: {recipient_headline or 'not provided'}\n"
                    f"Please ask them to introduce me to: {connector_name} (at {company}).\n"
                    f"The role I'm pursuing there: {role or 'a senior role'}\n"
                    f"Optional company news (use only if it fits naturally; otherwise skip): "
                    f"{company_intel or 'none'}\n\n"
                    f"Sound like a real peer asking a favour — written only for {first_name}."
                )
            else:
                # Direct message to someone AT the target company
                system_prompt = (
                    "You write LinkedIn DMs that get replies. The user will paste this into LinkedIn.\n"
                    "- They are pursuing a specific job/opportunity at the recipient's company.\n"
                    "- Open with something SPECIFIC — role, headline, or one concrete detail. "
                    "Never 'Hope you're well' or 'I came across your profile.'\n"
                    "- Tie the ask to how THEY can help you get an edge: hiring for that role, "
                    "team priorities, culture fit, or who else to speak with.\n"
                    "- One clear ask (short call, one question, or brief guidance).\n"
                    "- Under 70 words. Confident, peer-to-peer. Not needy.\n"
                    "- Do not invent employer facts; if company intel is missing, stay with role + company only.\n"
                    "- Return ONLY the message body. No subject line, no brackets, no placeholders."
                )
                user_prompt = (
                    f"Write a message to {recipient_name}.\n"
                    f"Their title: {recipient_title}\n"
                    f"Their LinkedIn headline: {recipient_headline or 'not provided'}\n"
                    f"They work at: {company}\n"
                    f"Role I'm pursuing there: {role or 'a senior role'}\n"
                    f"Optional company intel (icebreaker — use only if accurate): "
                    f"{company_intel or 'none'}\n\n"
                    f"Make it feel written only for {first_name} — relevant to their job at {company} "
                    f"and my goal of landing the role."
                )

            client = ClaudeClient(task=LLMTask.CLASSIFICATION, max_tokens=280)
            raw, _ = client.call_text(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.55,
            )
            message = raw.strip()
            if message.startswith('"') and message.endswith('"'):
                message = message[1:-1]
            message = message.strip()
            if not message:
                raise ValueError("empty_llm_message")

            # Cache for 7 days
            if r and cache_key and message:
                try:
                    r.setex(cache_key, 7 * 86400, message)
                except Exception:
                    pass

            return message
        except Exception as e:
            logger.warning("craft_message_failed", error=str(e), type=message_type)
            # Fallback — still better than fully generic
            first = recipient_name.split()[0] if recipient_name else "there"
            if message_type == "intro_request":
                return (
                    f"Hi {first}, I noticed you're connected with {connector_name} at {company}. "
                    f"I'm exploring a {role or 'senior role'} there and {connector_name.split()[0] if connector_name else 'they'} "
                    f"would be a great person to get perspective from. "
                    f"Would you be open to a quick intro? Happy to send a blurb you can forward. "
                    f"No pressure at all!"
                )
            return (
                f"Hi {first}, your work as {recipient_title} at {company} caught my attention. "
                f"I'm exploring a {role or 'senior role'} opportunity there and your perspective "
                f"on the team would be invaluable. Quick 15-min call this week? "
                f"Happy to share context on what I bring to the table."
            )

    def _ai_intro_message(
        self,
        mutual_name: str,
        target_name: str,
        target_title: str,
        company: str,
        role: str,
        company_intel: str = "",
        mutual_headline: str = "",
        mutual_title: str = "",
    ) -> str:
        """
        Generate a personalized LinkedIn message asking a mutual connection
        for an intro to a target person. Delegates to _craft_message.
        """
        return self._craft_message(
            recipient_name=mutual_name,
            recipient_title=mutual_title or "",
            recipient_headline=mutual_headline,
            company=company,
            role=role,
            company_intel=company_intel,
            message_type="intro_request",
            connector_name=f"{target_name} ({target_title})",
        )

    async def _get_all_connections(self, user_id: str) -> list[LinkedInConnection]:
        """Load all connections for a user."""
        result = await self.db.execute(
            select(LinkedInConnection).where(
                LinkedInConnection.user_id == user_id,
            )
        )
        return list(result.scalars().all())

    # ── Company relationship map ──────────────────────────────────────────

    async def get_company_map(
        self, user_id: str, company: str
    ) -> dict:
        """Find all connections at a target company using normalized matching."""
        all_conns = await self._get_all_connections(user_id)

        # Find direct connections using normalized matching (exclude former employees)
        direct = [c for c in all_conns if c.current_company and companies_match(c.current_company, company) and not _is_former_company(c.current_company)]

        # Load existing warm intros
        conn_ids = [c.id for c in direct]
        intro_map: dict[uuid.UUID, WarmIntro] = {}
        if conn_ids:
            intro_result = await self.db.execute(
                select(WarmIntro).where(
                    WarmIntro.user_id == user_id,
                    WarmIntro.connection_id.in_(conn_ids),
                )
            )
            for intro in intro_result.scalars().all():
                intro_map[intro.connection_id] = intro

        # Rank by relevance
        ranked = sorted(direct, key=lambda c: rank_connection(c), reverse=True)

        people = []
        for conn in ranked:
            existing_intro = intro_map.get(conn.id)
            people.append({
                "connection_id": str(conn.id),
                "name": conn.full_name,
                "title": conn.current_title,
                "company": conn.current_company,
                "headline": conn.headline,
                "linkedin_url": conn.linkedin_url,
                "is_recruiter": conn.is_recruiter or detect_domain(conn.current_title or "") == "hr",
                "is_hiring_manager": conn.is_hiring_manager or detect_seniority(conn.current_title or "") >= 70,
                "domain": detect_domain(conn.current_title or ""),
                "seniority": detect_seniority(conn.current_title or ""),
                "rank_score": rank_connection(conn),
                "intro_angle": _suggest_intro_angle(conn, None),
                "outreach_status": existing_intro.status if existing_intro else None,
                "warm_intro_id": str(existing_intro.id) if existing_intro else None,
            })

        return {
            "company": company,
            "total_connections": len(people),
            "recruiters": sum(1 for p in people if p["is_recruiter"]),
            "hiring_managers": sum(1 for p in people if p["is_hiring_manager"]),
            "people": people,
        }

    # ── Find Way In (the killer feature) ──────────────────────────────────

    async def find_way_in(
        self, user_id: str, company: str, role: str | None = None
    ) -> dict:
        """
        Find the best path into a target company.
        Uses Claude to identify target person + best connector from your network.
        """
        all_conns = await self._get_all_connections(user_id)
        company = self._resolve_target_company(company, role, all_conns)
        company_lower = (company or "").lower()
        undisclosed_company = any(k in company_lower for k in ["undisclosed", "confidential", "stealth", "unknown"])

        # Gather company intel for message personalization (cached, fast)
        company_intel = self._gather_company_intel(company)

        # Step 1: Direct contacts at target company
        # SENIORITY TIERS — ranked top to bottom:
        #   C_SUITE (4) → VP_DIRECTOR (3) → MANAGER (2) → IC (1) → RECRUITER (0)
        # Recruiters are EXCLUDED from direct contacts (Layer 1) per product spec —
        # they belong in a separate Recruiters layer, not the warm-intro funnel.
        def _seniority_tier(title: str) -> tuple[int, str]:
            return seniority_tier(title)

        def _seniority_message(first_name: str, company: str, role: str | None, tier: str, contact_title: str = "") -> str:
            role_str = role or "senior role"
            if tier in ("C_SUITE", "VP_DIRECTOR"):
                return (
                    f"Hi {first_name}, I'd love to connect with someone at {company} "
                    f"for a {role_str} opportunity there. "
                    f"I know you're connected with the team, and I'd be grateful if you could "
                    f"introduce me to the right person. "
                    f"Your insight into their culture and mission would be invaluable "
                    f"as I explore this next step. No pressure at all!"
                )
            if tier == "MANAGER":
                return (
                    f"Hi {first_name}, I'm exploring a {role_str} opportunity at {company} "
                    f"and as someone in the team there, your perspective would be incredibly valuable. "
                    f"I'd love to hear about the culture and what the team looks for. "
                    f"Would you have 15 minutes for a quick chat this week?"
                )
            return (
                f"Hi {first_name}, I'm exploring a {role_str} opportunity at {company} "
                f"and would love to get an insider's view on the team and culture. "
                f"Any perspective you could share would help a lot. "
                f"Would you be open to a quick 15-minute chat? Happy to return the favour anytime."
            )

        def _conn_matches_company(c: LinkedInConnection, company: str) -> bool:
            """Check if a connection currently works at the target company.
            Uses multiple strategies: current_company, headline parsing,
            current_title, and pipe-separated headline segments.
            Excludes former employees (Ex-, Former prefix)."""
            norm_target = normalize_company(company)
            if not norm_target:
                return False

            # 1. Primary: current_company field
            if c.current_company:
                if _is_former_company(c.current_company):
                    return False
                if companies_match(c.current_company, company):
                    # Double-check headline for "Ex-" / "Former" — LinkedIn sometimes
                    # stores company name without the prefix in current_company field
                    # while the headline clearly says "Ex-Company"
                    headline = c.headline or ""
                    if headline:
                        hl_lower = headline.lower()
                        for seg in re.split(r'[|·•,]', hl_lower):
                            seg_stripped = seg.strip()
                            seg_norm = normalize_company(seg_stripped)
                            if norm_target in seg_norm or seg_norm in norm_target:
                                if _is_former_company(seg_stripped):
                                    return False
                    return True

            # 2. Headline — try explicit current-employer patterns only
            headline = c.headline or ""
            if headline:
                hl = headline.lower()
                # Skip if entire headline starts with "ex-" or "former"
                if _is_former_company(hl):
                    return False

                # 2a. "... at Company" or "... @ Company"
                at_match = re.search(r'\bat\s+(.+?)(?:\s*[|·•,]|$)', hl)
                if at_match:
                    hl_company = at_match.group(1).strip()
                    if not _is_former_company(hl_company) and companies_match(hl_company, company):
                        return True

                # 2b. Split by | · • , and check each segment
                #     Handles "Strategy Consultant | Oliver Wyman" or "Oliver Wyman · Dubai"
                segments = re.split(r'[|·•]', headline)
                for seg in segments:
                    seg = seg.strip()
                    if not seg or len(seg) < 2:
                        continue
                    if _is_former_company(seg):
                        continue
                    # Strip common prefixes like "at" "working at"
                    cleaned = re.sub(r'^(?:at|working at|@)\s+', '', seg, flags=re.IGNORECASE).strip()
                    if companies_match(cleaned, company):
                        return True

            # 3. current_title — sometimes contains "Title at Company"
            title = c.current_title or ""
            if title:
                title_at = re.search(r'\bat\s+(.+?)(?:\s*[|·•,]|$)', title.lower())
                if title_at:
                    t_company = title_at.group(1).strip()
                    if not _is_former_company(t_company) and companies_match(t_company, company):
                        return True

            return False

        direct = []
        recruiter_contacts = []
        visited_targets = []
        for c in all_conns:
            # For undisclosed/confidential targets, never force-match direct company contacts.
            if (not undisclosed_company) and _conn_matches_company(c, company):
                is_visited = c.relationship_strength == "visited"
                tier_rank, tier_name = _seniority_tier(c.current_title or c.headline or "")
                # Generate personalized message using LLM + company intel
                msg = self._craft_message(
                    recipient_name=c.full_name,
                    recipient_title=c.current_title or "",
                    recipient_headline=c.headline or "",
                    company=company,
                    role=role,
                    company_intel=company_intel,
                    message_type="direct",
                )
                entry = {
                    "name": c.full_name,
                    "title": c.current_title or "",
                    "company": c.current_company,
                    "linkedin_url": c.linkedin_url,
                    "headline": c.headline or "",
                    "is_recruiter": tier_name == "RECRUITER",
                    "is_hiring_manager": tier_rank >= 3 and tier_name != "RECRUITER",
                    "seniority_tier": tier_name,
                    "_tier_rank": tier_rank,
                    "relevance_score": rank_connection(c, role),
                    "intro_angle": _suggest_intro_angle(c, role),
                    "message": msg,
                    "connection_id": str(c.id),
                    "is_visited_profile": is_visited,
                }
                if is_visited:
                    entry["intro_angle"] = _suggest_cold_outreach_angle(c, company, role)
                    entry["message"] = self._craft_message(
                        recipient_name=c.full_name,
                        recipient_title=c.current_title or "",
                        recipient_headline=c.headline or "",
                        company=company,
                        role=role,
                        company_intel=company_intel,
                        message_type="direct",
                    )
                    visited_targets.append(entry)
                elif tier_name == "RECRUITER":
                    # Recruiters get their own bucket — NOT shown in Layer 1 direct contacts
                    recruiter_contacts.append(entry)
                else:
                    direct.append(entry)
        # Sort by seniority tier (C_SUITE first), then by relevance score within tier
        direct.sort(key=lambda x: (-x["_tier_rank"], -x["relevance_score"]))
        recruiter_contacts.sort(key=lambda x: -x["relevance_score"])
        visited_targets.sort(key=lambda x: x["relevance_score"], reverse=True)
        # Strip internal sort key from response payload
        for d in direct:
            d.pop("_tier_rank", None)
        for d in recruiter_contacts:
            d.pop("_tier_rank", None)

        # Step 2: Check REAL 2nd-degree paths from mutual connection data
        from app.models.mutual_connection import MutualConnection
        real_paths = []

        # Find mutual connections where target works at the target company
        mutual_results = await self.db.execute(
            select(MutualConnection).where(
                MutualConnection.user_id == user_id,
            )
        )
        all_mutuals = list(mutual_results.scalars().all())

        # Build maps for matching mutual connectors to our 1st-degree connections.
        # Skip rows where full_name is None/empty — these come from a buggy
        # extension scrape and would crash .lower().split()/etc. downstream.
        conn_by_id = {(c.linkedin_id or ""): c for c in all_conns if c.linkedin_id}
        conn_by_name: dict[str, LinkedInConnection] = {}
        conn_by_first_last: dict[str, LinkedInConnection] = {}
        for c in all_conns:
            if not c.full_name:
                continue
            name_lower = c.full_name.lower().strip()
            if not name_lower:
                continue
            conn_by_name[name_lower] = c
            # Also index by slug form (extension stores fake IDs as "first-last")
            slug = re.sub(r'[^a-z0-9]', '-', name_lower).strip('-')
            conn_by_first_last[slug] = c
            # Index by first+last only (handles middle names/initials)
            parts = name_lower.split()
            if len(parts) >= 2:
                fl_key = parts[0] + " " + parts[-1]
                if fl_key not in conn_by_first_last:
                    conn_by_first_last[fl_key] = c

        def _normalize_name(name: str) -> str:
            """Strip suffixes like MBA, PhD, PMP, etc. and normalize."""
            n = name.lower().strip()
            # Remove common credential suffixes
            n = re.sub(r',?\s*(?:mba|phd|pmp|cfa|cpa|md|pe|esq|jr\.?|sr\.?|ii|iii|iv)\.?\s*$', '', n, flags=re.IGNORECASE).strip()
            # Remove content in parentheses
            n = re.sub(r'\([^)]*\)', '', n).strip()
            # Collapse whitespace
            n = re.sub(r'\s+', ' ', n)
            return n

        def _find_connector(mc) -> LinkedInConnection | None:
            """Match a mutual connection to a 1st-degree connection. Uses fuzzy matching."""
            mid = (mc.mutual_linkedin_id or "").strip()
            mname = _normalize_name(mc.mutual_name or "")
            # 1. Direct linkedin_id match (most reliable)
            if mid and mid in conn_by_id:
                return conn_by_id[mid]
            # 2. Exact full name match
            if mname and mname in conn_by_name:
                return conn_by_name[mname]
            # 3. First+last name match (ignores middle names/initials)
            if mname:
                parts = mname.split()
                if len(parts) >= 2:
                    fl_key = parts[0] + " " + parts[-1]
                    if fl_key in conn_by_first_last:
                        return conn_by_first_last[fl_key]
            # 4. Slug match (extension sometimes stores fake IDs as "first-last")
            if mname:
                slug = re.sub(r'[^a-z0-9]', '-', mname).strip('-')
                if slug in conn_by_first_last:
                    return conn_by_first_last[slug]
            # 5. Substring match — if one name contains the other (handles "John Smith, MBA" vs "John Smith")
            if mname and len(mname) >= 4:
                for stored_name, conn in conn_by_name.items():
                    if stored_name.startswith(mname) or mname.startswith(stored_name):
                        if abs(len(stored_name) - len(mname)) < 15:  # guard against very short names matching long ones
                            return conn
            return None

        # Build set of visited target linkedin_ids so we can also match mutuals for them
        visited_target_ids = set()
        for c in all_conns:
            if c.relationship_strength == "visited" and c.linkedin_id:
                if _conn_matches_company(c, company):
                    visited_target_ids.add(c.linkedin_id)

        for mc in all_mutuals:
            # Match by target company OR by target being a visited profile for this application
            company_matches = mc.target_company and companies_match(mc.target_company, company)
            target_is_visited = mc.target_linkedin_id in visited_target_ids
            if company_matches or target_is_visited:
                # Find the mutual connector in our 1st-degree connections
                connector = _find_connector(mc)
                if connector and connector.full_name:
                    t_name = mc.target_name or ""
                    t_title = mc.target_title or ""
                    t_company = mc.target_company or company
                    t_url = mc.target_linkedin_url or ""
                    connector_full_name = (connector.full_name or "").strip()
                    connector_first = connector_full_name.split()[0] if connector_full_name else "your contact"
                    real_paths.append({
                        "target": {
                            "name": t_name,
                            "title": t_title,
                            "company": t_company,
                            "linkedin_url": t_url,
                            "why_target": f"{t_name or 'Contact'} works at {t_company} as {t_title or 'employee'}"
                        },
                        "connector": {
                            "name": connector_full_name,
                            "title": connector.current_title or "",
                            "company": connector.current_company or "",
                            "linkedin_url": connector.linkedin_url or "",
                            "connection_id": str(connector.id),
                        },
                        "path": f"You → {connector_full_name} → {t_name or 'contact'}",
                        "reason": f"{connector_full_name} is connected to {t_name or 'this person'} on LinkedIn — verified mutual connection",
                        "action": f"Ask {connector_first} to introduce you to {t_name or 'them'} at {t_company}",
                        "strength": "strong",
                        "verified": True,
                    })

        # Deduplicate paths by connector — normalize names aggressively.
        # Defensive .get(... "") in case any field is missing.
        seen_connectors = set()
        unique_paths = []
        for p in real_paths:
            cname = (p.get("connector", {}).get("name") or "").lower().strip()
            if not cname:
                continue
            parts = cname.split()
            dedup_key = (parts[0] + " " + parts[-1]) if len(parts) >= 2 else cname
            cid = p.get("connector", {}).get("connection_id") or ""
            if dedup_key not in seen_connectors and (not cid or cid not in seen_connectors):
                seen_connectors.add(dedup_key)
                if cid:
                    seen_connectors.add(cid)
                unique_paths.append(p)
        real_paths = unique_paths

        def _path_rank(p):
            n = (p.get("connector", {}).get("name") or "").lower().strip()
            c = conn_by_name.get(n) if n else None
            return rank_connection(c, role) if c else 0
        real_paths.sort(key=_path_rank, reverse=True)

        # Filter out path targets who are already 1st-degree direct contacts.
        direct_names = {(d.get("name") or "").lower().strip() for d in direct if d.get("name")}
        real_paths = [
            p for p in real_paths
            if (p.get("target", {}).get("name") or "").lower().strip() not in direct_names
        ]

        # Step 3: Build candidate connectors for AI-suggested paths (fallback)
        target_domain = detect_domain(role) if role else "general"
        candidates = []
        for c in all_conns:
            if c.current_company and companies_match(c.current_company, company):
                continue
            title = c.current_title or ""
            is_rec = c.is_recruiter or detect_domain(title) == "hr"
            same_func = target_domain != "general" and detect_domain(title) == target_domain
            senior = detect_seniority(title) >= 60
            if is_rec or same_func or senior:
                candidates.append(c)

        # Step 4: Use Claude for AI paths only if no real paths found
        best_path = None
        backup_paths = []

        # ONLY use verified paths — no AI guessing
        # Filter out paths with no target person info — these produce garbage LLM messages
        real_paths = [p for p in real_paths if p["target"].get("name") and p["target"]["name"].strip()]
        # Cap at 50 to match LinkedIn's visible mutual count
        if real_paths:
            real_paths = real_paths[:50]
            # Attach a personalized intro message to ALL displayed paths
            for p in real_paths:
                target_name = p["target"]["name"]
                target_title = p["target"].get("title") or "employee"
                connector_name = p["connector"]["name"]
                # Look up connector's headline for personalization
                connector_headline = ""
                connector_obj = conn_by_name.get(connector_name.lower().strip())
                if connector_obj:
                    connector_headline = connector_obj.headline or ""
                try:
                    msg = self._ai_intro_message(
                        mutual_name=connector_name,
                        target_name=target_name,
                        target_title=target_title,
                        company=company,
                        role=role or "senior role",
                        company_intel=company_intel,
                        mutual_headline=connector_headline,
                        mutual_title=p["connector"].get("title") or "",
                    )
                    if msg and msg.strip():
                        p["intro_message"] = msg
                    else:
                        raise ValueError("empty message")
                except Exception:
                    connector_first = connector_name.split()[0] if connector_name else "there"
                    p["intro_message"] = (
                        f"Hi {connector_first}, I noticed you're connected with {target_name} "
                        f"({target_title}) at {company}. I'm exploring a {role or 'senior role'} "
                        f"there and {target_name.split()[0]}'s perspective would be really valuable. "
                        f"Would you be open to a quick intro? Happy to send a blurb you can forward. "
                        f"No pressure at all!"
                    )
            best_path = real_paths[0]
            backup_paths = real_paths[1:]

        # Recommended action
        if real_paths:
            rp = real_paths[0]
            target_display = rp['target']['name'] or f"your contact at {company}"
            recommended = f"Ask {rp['connector']['name']} to introduce you to {target_display} at {company} — they're connected on LinkedIn"
        elif direct:
            best = direct[0]
            recommended = f"Message {best['name']} ({best['title']}) directly at {company}"
        elif visited_targets:
            best_v = visited_targets[0]
            recommended = f"Reach out to {best_v['name']} ({best_v['title']}) at {company} — you've researched their profile. Lead with a specific insight about {company}."
        else:
            recommended = f"No verified paths yet. Use the StealthRole extension: search LinkedIn for people at {company}, visit their profiles, and the extension will map your connections automatically."

        # ALWAYS find key people at the target company — the core value prop.
        # Cross-reference with user's connections to show degree + path.
        discover_targets = await self._find_key_people(company, role, all_conns, company_intel)
        discovery_yielded_real_people = len(discover_targets) > 0

        # Honest fallback: top up with REAL 1st-degree contacts at the target
        # company (never synthetic stub names). Keeps the panel useful when
        # web search returns fewer than 3.
        if len(discover_targets) < 3:
            seen_dt = {
                f"{(d.get('name') or '').lower().strip()}|{((d.get('linkedin_url') or '').rstrip('/').lower())}"
                for d in discover_targets
            }
            fallback_pool = (direct or []) + (recruiter_contacts or []) + (visited_targets or [])
            for c in fallback_pool:
                if not (c.get("name") or "").strip():
                    continue
                key = f"{(c.get('name') or '').lower().strip()}|{((c.get('linkedin_url') or '').rstrip('/').lower())}"
                if key in seen_dt:
                    continue
                seen_dt.add(key)
                is_vis = bool(c.get("is_visited_profile"))
                # Visited profiles are scraped targets — not labeled 1st/2nd; real network rows are 1st.
                fb_degree = None if is_vis else "1st"
                discover_targets.append({
                    "name": c.get("name", ""),
                    "title": c.get("title", ""),
                    "linkedin_url": c.get("linkedin_url"),
                    "snippet": c.get("headline", ""),
                    "degree": fb_degree,
                    "connection_path": None,
                    "message": c.get("message", ""),
                    "why_relevant": self._explain_relevance(c.get("title", ""), role, company),
                })
                if len(discover_targets) >= 5:
                    break
        discover_targets = discover_targets[:5]

        # Discovery metadata for the frontend so it can show a clear empty state
        # (instead of silently rendering nothing) when discovery genuinely fails.
        from app.config import settings as _wayin_settings
        if undisclosed_company:
            discovery_reason = "undisclosed_company"
        elif not _wayin_settings.serper_api_key:
            discovery_reason = "no_search_api_key"
        elif discovery_yielded_real_people:
            discovery_reason = "ok"
        elif discover_targets:
            discovery_reason = "fallback_network_only"
        else:
            discovery_reason = "no_results"
        discovery_meta = {
            "reason": discovery_reason,
            "returned": len(discover_targets),
            "from_search": discovery_yielded_real_people,
        }

        # No more "network brokers" fallback. Surfacing random recruiters and
        # senior people from unrelated companies confused users — they expected
        # contacts AT the target company, not generic suggestions.
        # Empty array kept for response shape backward-compat.
        network_brokers: list = []

        # ── DEBUG: find connections that mention the company but didn't match ──
        matched_ids = {d.get("connection_id") for d in direct}
        matched_ids |= {d.get("connection_id") for d in recruiter_contacts}
        matched_ids |= {d.get("connection_id") for d in visited_targets}
        # Filter out generic industry words that cause massive false positives in near-miss search
        _generic_words = {"bank", "group", "capital", "global", "international", "consulting",
                          "services", "solutions", "technology", "digital", "management", "partners",
                          "financial", "investment", "advisory", "holdings", "ventures", "systems"}
        company_words = [w for w in normalize_company(company).split() if len(w) >= 4 and w not in _generic_words]
        near_misses = []
        for c in all_conns:
            cid = str(c.id)
            if cid in matched_ids:
                continue
            haystack = " ".join([
                c.current_company or "",
                c.headline or "",
                c.current_title or "",
                c.full_name or "",
            ]).lower()
            if any(w in haystack for w in company_words):
                near_misses.append({
                    "name": c.full_name,
                    "current_company": c.current_company,
                    "headline": (c.headline or "")[:120],
                    "current_title": c.current_title,
                    "relationship_strength": c.relationship_strength,
                    "linkedin_id": c.linkedin_id,
                    "_why_excluded": "did not pass _conn_matches_company()",
                })

        return {
            "company": company,
            "role": role,
            "best_path": best_path,
            "backup_paths": backup_paths,
            "verified_paths": len(real_paths),
            "discover_targets": discover_targets,
            "discovery_meta": discovery_meta,
            "network_brokers": network_brokers,  # always [] — kept for response shape
            "total_connections": len(all_conns),
            "direct_contacts": direct[:50],  # 1st-degree, recruiter-free, sorted by seniority
            "total_direct": len(direct),
            "recruiter_contacts": recruiter_contacts[:25],  # separate bucket
            "total_recruiters": len(recruiter_contacts),
            "visited_targets": visited_targets[:20],
            "total_visited": len(visited_targets),
            "recommended_action": recommended,
            # Internal debug fields intentionally omitted from API response.
        }

    # ── Way In core pipeline (5 stages) ──────────────────────────────────
    #
    # Discovery → Normalize → Rank → Network overlay → Messages
    #
    # Each stage is a small, testable helper. structlog events at every
    # stage make accept/reject decisions visible in production.
    #
    # No fake stub names are ever returned. If discovery yields no real
    # people, this method returns [] and the caller surfaces the reason.

    REGION_TOKENS_POOL = (
        "uae", "dubai", "abu dhabi", "ksa", "saudi", "riyadh", "jeddah",
        "qatar", "doha", "bahrain", "oman", "kuwait",
        "gcc", "mena", "middle east",
    )
    GENERIC_COMPANY_TOKENS = {
        "global", "group", "capital", "digital", "services", "solutions",
        "professional", "bank", "international", "holdings", "ventures",
        "consulting", "management", "partners", "advisory", "financial",
        "technology", "technologies", "systems", "company",
    }
    GENERIC_ROLE_TOKENS = {
        "manager", "director", "head", "chief", "officer", "practice",
        "senior", "lead", "vice", "president",
    }

    def _wayin_tokens(self, company: str, role: str | None) -> tuple[list[str], list[str], list[str]]:
        """Build (company_tokens, role_tokens, region_tokens) used by the ranker."""
        company_tokens = [
            t for t in normalize_company(company).split()
            if len(t) >= 4 and t not in self.GENERIC_COMPANY_TOKENS
        ]
        role_tokens = [
            t for t in normalize_text(role or "").split()
            if len(t) >= 4 and t not in self.GENERIC_ROLE_TOKENS
        ]
        target_text = normalize_text(f"{company} {role or ''}")
        region_tokens = [r for r in self.REGION_TOKENS_POOL if r in target_text]
        return company_tokens, role_tokens, region_tokens

    async def _find_key_people(
        self, company: str, role: str | None,
        all_conns: list[LinkedInConnection],
        company_intel: str,
    ) -> list[dict]:
        """Way In pipeline. Returns 0–5 ranked people with degree + message.

        Returns [] when discovery yields nothing real. Never returns
        synthetic stub names like "Recruiter — <company>".
        """
        logger.info(
            "wayin_pipeline_start",
            company=company, role=role, n_connections=len(all_conns),
        )

        # Stage A — DISCOVER raw candidates
        raw = await self._wayin_discover(company, role)
        if not raw:
            logger.info("wayin_pipeline_no_raw", company=company, role=role)
            return []

        # Stage B — NORMALIZE
        normalized = [self._wayin_normalize(c) for c in raw]

        # Stage C — RANK
        ranked = self._wayin_rank(normalized, company, role)
        if not ranked:
            logger.info("wayin_pipeline_no_ranked", company=company, role=role, raw=len(raw))
            return []

        # Stage D — CROSS-REFERENCE with user's network
        overlaid = await self._wayin_overlay_network(ranked, all_conns, company)

        # Stage E — GENERATE messages and finalize
        return self._wayin_finalize(overlaid, company, role, company_intel)

    # ── Stage A: DISCOVER ────────────────────────────────────────────────

    async def _wayin_discover(self, company: str, role: str | None) -> list[dict]:
        """Discover raw candidate profiles via Serper LinkedIn search.

        Skips discovery cleanly when the target is undisclosed or the
        Serper API key is missing — does NOT return synthetic stubs.
        """
        from app.config import settings
        import httpx

        if not (company and company.strip()):
            logger.info("wayin_discover_skip_no_company")
            return []
        company_lower = company.lower()
        if any(k in company_lower for k in ["undisclosed", "confidential", "stealth", "unknown"]):
            logger.info("wayin_discover_skip_undisclosed", company=company)
            return []
        if not settings.serper_api_key:
            logger.warning("wayin_discover_skip_no_serper_key", company=company)
            return []

        role_str = role or "VP Director Head"
        queries = [
            f'site:linkedin.com/in "{company}" {role_str}',
            f'site:linkedin.com/in "{company}" recruiter talent acquisition',
            f'site:linkedin.com/in "{company}" head director vp',
            f'site:linkedin.com/in "{company}" people operations human resources',
        ]
        logger.info("wayin_discover_queries", company=company, queries=queries)

        seen: set[str] = set()
        raw: list[dict] = []
        async with httpx.AsyncClient(timeout=8) as client:
            for q in queries:
                try:
                    resp = await client.post(
                        "https://google.serper.dev/search",
                        headers={
                            "X-API-KEY": settings.serper_api_key,
                            "Content-Type": "application/json",
                        },
                        json={"q": q, "num": 8},
                    )
                except Exception as e:
                    logger.warning("wayin_serper_request_failed", query=q, error=str(e))
                    continue
                if resp.status_code != 200:
                    logger.warning("wayin_serper_non_200", query=q, status=resp.status_code)
                    continue
                for item in resp.json().get("organic", []) or []:
                    record = self._wayin_parse_serper_item(item, q)
                    if not record:
                        continue
                    key = (record.get("linkedin_url") or "").lower()
                    if key in seen:
                        continue
                    seen.add(key)
                    raw.append(record)

        logger.info("wayin_discover_raw", company=company, raw_count=len(raw))
        return raw

    def _wayin_parse_serper_item(self, item: dict, source_query: str) -> dict | None:
        """Parse one Serper organic result into a candidate record. Pure."""
        url = (item.get("link") or "").strip()
        if "/in/" not in url:
            return None
        title_raw = item.get("title", "") or ""
        snippet_raw = item.get("snippet", "") or ""
        parts = [p.strip() for p in title_raw.split(" - ") if p.strip()]
        name = parts[0] if parts else ""
        person_title = parts[1] if len(parts) > 1 else ""
        if person_title:
            person_title = re.sub(r"\s*\|?\s*LinkedIn\s*$", "", person_title).strip()
        if not name or len(name) < 3 or "linkedin" in name.lower():
            return None
        company_hint = ""
        if len(parts) >= 3:
            company_hint = re.sub(r"\s*\|?\s*LinkedIn\s*$", "", parts[2]).strip()
        return {
            "name": name,
            "title": person_title,
            "company_hint": company_hint,
            "linkedin_url": url.split("?")[0],
            "snippet": snippet_raw[:240],
            "_source_query": source_query,
        }

    # ── Stage B: NORMALIZE ───────────────────────────────────────────────

    def _wayin_normalize(self, candidate: dict) -> dict:
        """Add normalized text fields used by the ranker. Pure."""
        title = candidate.get("title", "")
        snippet = candidate.get("snippet", "")
        company_hint = candidate.get("company_hint", "")
        candidate["title_norm"] = normalize_text(title)
        candidate["snippet_norm"] = normalize_text(snippet)
        candidate["company_hint_norm"] = normalize_company(company_hint)
        candidate["function"] = detect_domain(title)
        candidate["seniority_score"] = detect_seniority(title)
        candidate["seniority_label"] = seniority_tier(title)[1]
        candidate["combined_text"] = " ".join([
            candidate["title_norm"], candidate["snippet_norm"], candidate["company_hint_norm"],
        ]).strip()
        return candidate

    # ── Stage C: RANK ────────────────────────────────────────────────────

    def _wayin_rank(
        self, candidates: list[dict], company: str, role: str | None,
    ) -> list[dict]:
        """Score each candidate, drop irrelevant ones, sort high → low. Pure.

        Hard rejections:
          - company doesn't match (no 2+ token hits AND no parsed company hint match)
          - candidate is neither hiring-relevant nor sufficiently senior
          - region required (role mentions a region) but candidate is non-recruiter IC
            without that region
        """
        company_tokens, role_tokens, region_tokens = self._wayin_tokens(company, role)
        role_function = detect_domain(role or "")
        company_norm = normalize_company(company)

        scored: list[dict] = []
        for c in candidates:
            text = c.get("combined_text", "")
            title = c.get("title", "")
            title_norm = c.get("title_norm", "")
            company_hint = c.get("company_hint_norm", "")
            snippet_norm = c.get("snippet_norm", "")
            headline = _wayin_headline_bucket(title_norm, company_hint)

            if _wayin_snippet_suggests_past_only_employer(
                title_norm, company_hint, snippet_norm, company_norm,
            ):
                logger.info(
                    "wayin_rank_rejected",
                    name=c.get("name", ""), title=title,
                    reason="past_employer_snippet_only",
                    company=company,
                )
                continue

            # ── Company match score ──
            # Require evidence in the LinkedIn *headline* fields (title + employer hint),
            # not Google snippet alone — snippets often mention a company for talks, press, ex-roles.
            company_match_score = 0
            company_pass = False
            if company_hint and companies_match(company_hint, company):
                company_match_score = 100
                company_pass = True
            elif company_norm and title_norm and company_norm in title_norm:
                company_match_score = 80
                company_pass = True
            elif company_tokens:
                hits_h = _wayin_company_tokens_in_text(company_tokens, headline)
                if len(company_tokens) >= 2:
                    if hits_h >= 2:
                        company_match_score = 60
                        company_pass = True
                elif hits_h >= 1:
                    company_match_score = 60
                    company_pass = True
            if not company_pass:
                logger.info(
                    "wayin_rank_rejected",
                    name=c.get("name", ""), title=title,
                    reason="company_mismatch",
                    company=company, company_hint=company_hint,
                )
                continue

            # ── Recruiter / hiring-influence signals ──
            is_recruiter = bool(re.search(
                r"\b(recruit|recruiter|recruiting|recruitment|talent acquisition|"
                r"talent partner|headhunter|head hunter|human resources|hr partner|"
                r"people operations|people partner|staffing|executive search|"
                r"search consultant|resourcing)\b",
                text,
            ))
            is_hiring_authority = bool(re.search(
                r"\b(hiring manager|head of|chief|vice president|svp|evp|"
                r"managing director|country manager|general manager|business unit head)\b",
                text,
            )) or re.search(r"\bvp\b", text) is not None or re.search(r"\bdirector\b", text) is not None

            recruiter_score = 60 if is_recruiter else 0
            hiring_score = 40 if (is_hiring_authority and not is_recruiter) else 0

            # ── Function / role-token relevance ──
            role_score = 0
            person_function = c.get("function", "general")
            if role_function != "general" and person_function == role_function:
                role_score += 30
            if role_tokens and any(re.search(rf"\b{re.escape(t)}\b", text) for t in role_tokens):
                role_score += 20

            # ── Seniority ──
            seniority_norm = int(c.get("seniority_score", 0) or 0)
            seniority_score = seniority_norm * 0.4

            # ── Region match (only matters when role/company implies a region) ──
            if region_tokens:
                region_match = any(rt in text for rt in region_tokens)
            else:
                region_match = True
            region_score = 15 if (region_tokens and region_match) else (0 if not region_tokens else 0)

            # ── Hard rejects ──
            if not is_recruiter and not is_hiring_authority and seniority_norm < 45:
                logger.info(
                    "wayin_rank_rejected",
                    name=c.get("name", ""), title=title,
                    reason="not_hiring_relevant",
                    seniority=seniority_norm,
                )
                continue
            if region_tokens and not region_match and not is_recruiter and seniority_norm < 70:
                logger.info(
                    "wayin_rank_rejected",
                    name=c.get("name", ""), title=title,
                    reason="region_mismatch",
                    region_tokens=region_tokens,
                )
                continue

            score = (
                company_match_score
                + recruiter_score
                + hiring_score
                + role_score
                + seniority_score
                + region_score
            )
            components = {
                "company_match": company_match_score,
                "recruiter": recruiter_score,
                "hiring": hiring_score,
                "role": role_score,
                "seniority": seniority_score,
                "region": region_score,
            }
            c["_rank_score"] = round(score, 2)
            c["_rank_components"] = components
            c["_is_recruiter"] = is_recruiter
            c["_is_hiring_authority"] = is_hiring_authority
            scored.append(c)
            logger.info(
                "wayin_rank_accepted",
                name=c.get("name", ""), title=title,
                score=c["_rank_score"], components=components,
            )

        scored.sort(key=lambda x: x["_rank_score"], reverse=True)
        return scored

    # ── Stage D: CROSS-REFERENCE network ─────────────────────────────────

    async def _wayin_overlay_network(
        self,
        ranked: list[dict],
        all_conns: list[LinkedInConnection],
        company: str,
    ) -> list[dict]:
        """Annotate each candidate with degree (1st / 2nd only) and connector path.

        Reads MutualConnection records to find verified 2nd-degree paths.
        Never invents a connector — everyone else stays unlabeled (degree None).
        """
        from app.models.mutual_connection import MutualConnection

        conn_by_id: dict[str, LinkedInConnection] = {}
        conn_by_name: dict[str, LinkedInConnection] = {}
        conn_by_url: dict[str, LinkedInConnection] = {}
        conn_by_first_last: dict[str, LinkedInConnection] = {}
        # Slug keys from real /in/{vanity} URLs only — used for 1st-degree identity.
        conn_profile_slug: dict[str, LinkedInConnection] = {}
        # URL slug + name-derived keys — used to resolve mutual → connector only.
        conn_by_slug: dict[str, LinkedInConnection] = {}

        for c in all_conns:
            lid = (getattr(c, "linkedin_id", None) or "").strip()
            if lid:
                conn_by_id[lid] = c
            if c.linkedin_url:
                u = c.linkedin_url.rstrip("/").lower()
                conn_by_url[u] = c
                slug = linkedin_profile_slug_from_url(c.linkedin_url)
                if slug:
                    conn_by_slug[slug] = c
                    conn_profile_slug[slug] = c
            fn = strip_linkedin_display_noise((c.full_name or "").strip())
            if not fn:
                continue
            name_lower = fn.lower().strip()
            conn_by_name[name_lower] = c
            parts = name_lower.split()
            if len(parts) >= 2:
                fl = f"{parts[0]} {parts[-1]}"
                if fl not in conn_by_first_last:
                    conn_by_first_last[fl] = c
            hy_slug = re.sub(r"[^a-z0-9]", "-", name_lower).strip("-")
            if hy_slug:
                conn_by_slug.setdefault(hy_slug, c)

        def _trusted_first_degree_network_row(c: LinkedInConnection | None) -> bool:
            """Extension marks profile visits: strong/medium=real network, weak=2nd, discovered=3rd, visited=unknown."""
            if c is None:
                return False
            rs = (getattr(c, "relationship_strength", None) or "").strip().lower()
            if rs in ("weak", "discovered", "visited"):
                return False
            return True

        mutual_by_target_url: dict[str, list] = defaultdict(list)
        mutual_by_target_slug: dict[str, list] = defaultdict(list)
        mutual_by_target_name: dict[str, list] = defaultdict(list)
        user_id = all_conns[0].user_id if all_conns else None
        if user_id:
            mutual_results = await self.db.execute(
                select(MutualConnection).where(MutualConnection.user_id == user_id)
            )
            for mc in mutual_results.scalars().all():
                if mc.target_linkedin_url:
                    u = mc.target_linkedin_url.rstrip("/").lower()
                    mutual_by_target_url[u].append(mc)
                    ts = linkedin_profile_slug_from_url(mc.target_linkedin_url)
                    if ts:
                        mutual_by_target_slug[ts].append(mc)
                if mc.target_name:
                    tl = strip_linkedin_display_noise(mc.target_name).lower().strip()
                    mutual_by_target_name[tl].append(mc)
                    tnorm = normalize_person_name(mc.target_name)
                    if tnorm and tnorm != tl:
                        mutual_by_target_name[tnorm].append(mc)
                    parts = tl.split()
                    if len(parts) >= 2:
                        mutual_by_target_name[f"{parts[0]} {parts[-1]}"].append(mc)

        for c in ranked:
            url_key = (c.get("linkedin_url") or "").rstrip("/").lower()
            slug_key = linkedin_profile_slug_from_url(url_key) if url_key else ""
            raw_display_name = strip_linkedin_display_noise(c.get("name") or "")
            name_key = raw_display_name.lower().strip()
            norm_name = normalize_person_name(raw_display_name)
            parts = name_key.split()
            fl_key = f"{parts[0]} {parts[-1]}" if len(parts) >= 2 else ""

            # 1st degree ONLY when the discovered profile URL/slug matches a synced
            # connection. Name-only matches cause false 1sts (same name, wrong person).
            direct_conn = None
            if slug_key or (url_key and "/in/" in url_key):
                direct_conn = conn_by_url.get(url_key) or (
                    conn_profile_slug.get(slug_key) if slug_key else None
                )
            else:
                direct_conn = (
                    conn_by_name.get(name_key)
                    or (conn_by_first_last.get(fl_key) if fl_key else None)
                )
            if direct_conn and not _trusted_first_degree_network_row(direct_conn):
                direct_conn = None
            degree = None
            connection_path = None
            degree_bonus = 0

            if direct_conn:
                degree = "1st"
                # A direct connection at the target company is the most
                # actionable contact possible — it must rank above unlabeled
                # candidates even when they have a slightly stronger
                # function/seniority signal.
                degree_bonus = 50
            else:
                bucket_lists: list = []
                if url_key:
                    bucket_lists.append(mutual_by_target_url.get(url_key, []))
                if slug_key:
                    bucket_lists.append(mutual_by_target_slug.get(slug_key, []))
                if name_key:
                    bucket_lists.append(mutual_by_target_name.get(name_key, []))
                if norm_name and norm_name != name_key:
                    bucket_lists.append(mutual_by_target_name.get(norm_name, []))
                if fl_key:
                    bucket_lists.append(mutual_by_target_name.get(fl_key, []))

                seen_mutual: set[tuple] = set()
                mutuals: list = []
                for lst in bucket_lists:
                    for mc in lst:
                        mk = (
                            getattr(mc, "target_linkedin_id", None),
                            (getattr(mc, "mutual_linkedin_id", None) or "").lower(),
                            (getattr(mc, "mutual_name", None) or "").lower(),
                        )
                        if mk in seen_mutual:
                            continue
                        seen_mutual.add(mk)
                        mutuals.append(mc)

                for mc in mutuals:
                    connector = match_connector_from_mutual(
                        mc, conn_by_id, conn_by_name, conn_by_first_last, conn_by_slug,
                    )
                    if connector:
                        degree = "2nd"
                        connection_path = {
                            "connector_name": connector.full_name,
                            "connector_title": connector.current_title or "",
                            "connector_url": connector.linkedin_url or "",
                            "connector_id": str(connector.id),
                            "connector_headline": (connector.headline or ""),
                        }
                        degree_bonus = 25
                        break

            c["degree"] = degree
            c["connection_path"] = connection_path
            c["_direct_conn"] = direct_conn
            c["_rank_score"] = round(c.get("_rank_score", 0) + degree_bonus, 2)
            if "_rank_components" in c:
                c["_rank_components"]["degree"] = degree_bonus
            logger.info(
                "wayin_overlay",
                name=c.get("name", ""), degree=degree,
                connector=(connection_path or {}).get("connector_name"),
                final_score=c.get("_rank_score"),
            )

        ranked.sort(key=lambda x: x.get("_rank_score", 0), reverse=True)
        return ranked

    # ── Stage E: GENERATE messages + finalize ────────────────────────────

    def _wayin_finalize(
        self,
        overlaid: list[dict],
        company: str,
        role: str | None,
        company_intel: str,
    ) -> list[dict]:
        """Build messages (1st direct, 2nd intro request) and cap at 5.

        Drops any candidate without a real name (no empty target names).
        Every 1st and every 2nd with a connector gets a non-empty LinkedIn draft
        (LLM via _craft_message, or the same fallbacks if the model/cache fails).
        Unlabeled targets get no auto message.
        """
        out: list[dict] = []
        seen: set[str] = set()
        for c in overlaid:
            name = (c.get("name") or "").strip()
            if not name:
                continue
            key = f"{name.lower()}|{(c.get('linkedin_url') or '').rstrip('/').lower()}"
            if key in seen:
                continue
            seen.add(key)

            raw_deg = c.get("degree")
            degree = raw_deg if raw_deg in ("1st", "2nd") else None
            connection_path = c.get("connection_path")
            message = ""
            if degree == "1st":
                message = self._craft_message(
                    recipient_name=name,
                    recipient_title=c.get("title", ""),
                    recipient_headline=c.get("snippet", ""),
                    company=company,
                    role=role,
                    company_intel=company_intel,
                    message_type="direct",
                )
            elif degree == "2nd" and connection_path:
                message = self._craft_message(
                    recipient_name=connection_path.get("connector_name", ""),
                    recipient_title=connection_path.get("connector_title", ""),
                    recipient_headline=connection_path.get("connector_headline") or "",
                    company=company,
                    role=role,
                    company_intel=company_intel,
                    message_type="intro_request",
                    connector_name=f"{name} ({c.get('title','')})",
                )
            # Unlabeled: no message — strict.

            if degree in ("1st", "2nd") and not (message or "").strip():
                logger.warning(
                    "wayin_finalize_empty_message",
                    degree=degree, name=name,
                )
                if degree == "2nd" and connection_path:
                    cn = connection_path.get("connector_name", "") or "there"
                    cfirst = cn.split()[0] if cn else "there"
                    tgt_first = name.split()[0] if name else "them"
                    tt = (c.get("title") or "").strip() or "there"
                    message = (
                        f"Hi {cfirst}, I noticed you're connected with {name} ({tt}) at {company}. "
                        f"I'm exploring a {role or 'senior role'} there and {tgt_first}'s "
                        f"perspective would be really valuable. "
                        f"Would you be open to a quick intro? Happy to send a blurb you can forward. "
                        f"No pressure at all!"
                    )
                elif degree == "1st":
                    rt = c.get("title", "") or "the team"
                    first = name.split()[0] if name else "there"
                    message = (
                        f"Hi {first}, your work as {rt} at {company} caught my attention. "
                        f"I'm exploring a {role or 'senior role'} opportunity there and your perspective "
                        f"on the team would be invaluable. Could I ask for 15 minutes this week? "
                        f"Happy to share what I bring to the table."
                    )

            out.append({
                "name": name,
                "title": c.get("title", ""),
                "linkedin_url": c.get("linkedin_url"),
                "snippet": c.get("snippet", ""),
                "degree": degree,
                "connection_path": connection_path if degree == "2nd" else None,
                "message": message,
                "why_relevant": self._explain_relevance(c.get("title", ""), role, company),
                "rank_score": c.get("_rank_score", 0),
                "rank_components": c.get("_rank_components", {}),
            })
            if len(out) >= 5:
                break
        logger.info(
            "wayin_pipeline_done",
            company=company, role=role, returned=len(out),
        )
        return out

    def _explain_relevance(self, person_title: str, target_role: str | None, company: str) -> str:
        """Short explanation of why this person is worth talking to."""
        title_lower = (person_title or "").lower()
        role_lower = (target_role or "").lower()

        if any(k in title_lower for k in ["recruiter", "talent", "hiring", "people operations", "hr "]):
            return f"Handles hiring at {company} — direct path to open roles"
        if detect_seniority(person_title) >= 80:
            return f"Senior leader at {company} — can influence hiring decisions"
        if detect_seniority(person_title) >= 60:
            return f"Director-level at {company} — likely involved in hiring for this area"
        if target_role and detect_domain(role_lower) == detect_domain(title_lower) and detect_domain(title_lower) != "general":
            return f"Same function as your target role — strong referral potential"
        return f"Works at {company} — insider perspective on team and culture"

    async def _find_people_to_discover(self, company: str, role: str | None) -> list[dict]:
        """Legacy wrapper — delegates to _find_key_people."""
        return []

    async def _claude_find_paths(
        self, company: str, role: str | None,
        direct: list[dict], candidates: list[LinkedInConnection],
    ) -> list[dict]:
        """Use Claude to identify target people and build real paths."""
        import json as _json
        from app.services.llm.client import ClaudeClient
        from app.services.llm.router import LLMTask

        # Build connector list for Claude
        connector_lines = []
        for c in candidates[:40]:
            connector_lines.append(
                f"  {c.full_name} | {c.current_title or 'N/A'} | {c.current_company or 'N/A'}"
            )

        direct_lines = []
        for d in direct[:10]:
            direct_lines.append(f"  {d['name']} | {d['title']} | {d['company']}")

        client = ClaudeClient(task=LLMTask.REPORT_PACK)

        system = "You are a career networking strategist. You build specific intro paths from a person's LinkedIn network to reach hiring decision makers. Return only valid JSON."

        prompt = f"""TARGET: {role or 'Senior role'} at {company}

DIRECT CONNECTIONS AT {company.upper()} ({len(direct)}):
{chr(10).join(direct_lines) if direct_lines else '  None'}

MY NETWORK - POTENTIAL CONNECTORS ({len(connector_lines)}):
{chr(10).join(connector_lines) if connector_lines else '  None'}

Build 1-3 specific intro paths to reach a hiring decision maker at {company} for the {role or 'target'} role.

For each path you MUST:
1. Name a specific TARGET PERSON (YY) — the person at {company} who would hire for this role (use a realistic title like "VP of Strategy" or "Head of Talent Acquisition"). If I have direct connections, use their real names.
2. Name the CONNECTOR (XX) — the specific person from my network who is best positioned to reach YY
3. Explain WHY XX can reach YY — shared industry, similar seniority, recruiter in same space, etc.

Return JSON array:
[
  {{
    "target": {{
      "name": "<specific name if known from direct contacts, or realistic title like 'Head of Strategy at {company}'>",
      "title": "<title>",
      "why_target": "<why this person is the right target for the {role or 'target'} role>"
    }},
    "connector": {{
      "name": "<exact name from my network list>",
      "title": "<their title>",
      "company": "<their company>"
    }},
    "path": "You → <connector name> → <target name/title>",
    "reason": "<specific reason why this connector can reach the target — NOT generic>",
    "action": "<exact action to take — 'Ask [Name] for an intro to [Target] because [reason]'>",
    "strength": "<strong/medium/weak>"
  }}
]

RULES:
- Use REAL names from the lists above — do NOT invent connector names
- If I have direct contacts at {company}, the path is "You → [direct contact]" (no intermediary needed)
- For indirect paths, the connector MUST be someone from my network list
- reason must be SPECIFIC, not "may know" or "could help"
- If the connector is a recruiter, say "recruiter in [industry] who hires for similar roles"
- If the connector is in the same function, say "works in [function] at [company] — peer network overlaps with {company}"
- Return ONLY valid JSON array"""

        try:
            response, _meta = client.call_text(system, prompt)
            text = response.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            paths = _json.loads(text)
            if isinstance(paths, list):
                return paths
            return []
        except Exception as e:
            logger.error("claude_path_parse_failed", error=str(e))
            return []

    # ── Request intro ─────────────────────────────────────────────────────

    async def request_intro(
        self,
        user_id: str,
        connection_id: uuid.UUID,
        target_company: str,
        target_role: str | None = None,
        application_id: uuid.UUID | None = None,
        relationship_context: str | None = None,
        custom_message: str | None = None,
    ) -> WarmIntro:
        result = await self.db.execute(
            select(LinkedInConnection).where(
                LinkedInConnection.id == connection_id,
                LinkedInConnection.user_id == user_id,
            )
        )
        conn = result.scalar_one_or_none()
        if not conn:
            raise ValueError("Connection not found")

        existing = await self.db.execute(
            select(WarmIntro).where(
                WarmIntro.connection_id == connection_id,
                WarmIntro.application_id == application_id,
                WarmIntro.user_id == user_id,
            )
        )
        intro = existing.scalar_one_or_none()

        message = custom_message or _generate_intro_message(
            connection_name=conn.full_name,
            target_company=target_company,
            target_role=target_role,
            relationship_context=relationship_context,
            is_recruiter=conn.is_recruiter,
            connection_title=conn.current_title,
            connection_seniority=detect_seniority(conn.current_title or ""),
        )
        angle = _suggest_intro_angle(conn, target_role)

        if intro:
            intro.outreach_message = message
            intro.relationship_context = relationship_context
            intro.intro_angle = angle
            intro.target_role = target_role
            if intro.status == IntroStatus.IDENTIFIED:
                intro.status = IntroStatus.OUTREACH_DRAFTED
        else:
            intro = WarmIntro(
                user_id=user_id,
                connection_id=connection_id,
                application_id=application_id,
                target_company=target_company,
                target_role=target_role,
                status=IntroStatus.OUTREACH_DRAFTED,
                outreach_message=message,
                relationship_context=relationship_context,
                intro_angle=angle,
            )
            self.db.add(intro)

        await self.db.flush()
        await self.db.commit()
        await self.db.refresh(intro)
        return intro

    # ── Pipeline management ───────────────────────────────────────────────

    async def update_status(self, user_id: str, intro_id: uuid.UUID, new_status: str, response_message: str | None = None, notes: str | None = None) -> WarmIntro | None:
        result = await self.db.execute(select(WarmIntro).where(WarmIntro.id == intro_id, WarmIntro.user_id == user_id))
        intro = result.scalar_one_or_none()
        if not intro:
            return None
        now = datetime.now(UTC)
        intro.status = new_status
        if new_status == IntroStatus.REQUESTED and not intro.requested_at:
            intro.requested_at = now
        if new_status in (IntroStatus.INTRODUCED, IntroStatus.DECLINED) and not intro.responded_at:
            intro.responded_at = now
        if response_message is not None:
            intro.response_message = response_message
        if notes is not None:
            intro.notes = notes
        await self.db.flush()
        await self.db.commit()
        await self.db.refresh(intro)
        return intro

    async def get_pipeline(self, user_id: str, status_filter: str | None = None) -> list[WarmIntro]:
        query = select(WarmIntro).where(WarmIntro.user_id == user_id)
        if status_filter:
            query = query.where(WarmIntro.status == status_filter)
        result = await self.db.execute(query.order_by(WarmIntro.updated_at.desc()))
        return list(result.scalars().all())

    async def get_pipeline_stats(self, user_id: str) -> dict:
        result = await self.db.execute(
            select(WarmIntro.status, func.count()).where(WarmIntro.user_id == user_id).group_by(WarmIntro.status)
        )
        by_status = {row[0]: row[1] for row in result.all()}
        total = sum(by_status.values())
        return {
            "total_intros": total,
            "by_status": by_status,
            "active": by_status.get("requested", 0) + by_status.get("outreach_drafted", 0),
            "successful": by_status.get("introduced", 0) + by_status.get("converted", 0),
            "conversion_rate": round((by_status.get("introduced", 0) + by_status.get("converted", 0)) / total * 100, 1) if total > 0 else 0.0,
        }

    async def auto_identify_intros(self, user_id: str, application_id: uuid.UUID) -> list[WarmIntro]:
        app_result = await self.db.execute(select(Application).where(Application.id == application_id, Application.user_id == user_id))
        app = app_result.scalar_one_or_none()
        if not app:
            return []

        all_conns = await self._get_all_connections(user_id)
        matches = [c for c in all_conns if c.current_company and companies_match(c.current_company, app.company) and not _is_former_company(c.current_company)]

        created = []
        for conn in matches:
            existing = await self.db.execute(select(WarmIntro).where(WarmIntro.connection_id == conn.id, WarmIntro.application_id == application_id))
            if existing.scalar_one_or_none():
                continue
            intro = WarmIntro(
                user_id=user_id, connection_id=conn.id, application_id=application_id,
                target_company=app.company, target_role=app.role,
                status=IntroStatus.IDENTIFIED, intro_angle=_suggest_intro_angle(conn, app.role),
            )
            self.db.add(intro)
            created.append(intro)

        if created:
            await self.db.flush()
            await self.db.commit()
            for intro in created:
                await self.db.refresh(intro)
        return created
