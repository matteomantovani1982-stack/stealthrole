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


def companies_match(a: str, b: str) -> bool:
    """Check if two company names refer to the same company."""
    na = normalize_company(a)
    nb = normalize_company(b)
    if not na or not nb:
        return False
    # Exact match after normalization
    if na == nb:
        return True
    # One contains the other (for "Amazon" matching "Amazon Web Services")
    if na in nb or nb in na:
        return True
    # First word match (handles "Careem" matching "Careem Networks")
    if na.split() and nb.split():
        # Lowered min length from 4 to 3 so "noon" (4), "kfc" (3) match
        first_a = na.split()[0]
        first_b = nb.split()[0]
        if first_a == first_b and len(first_a) >= 3:
            return True
    # Substring match on full normalized strings (for "noon" vs "noon middle east")
    if len(na) >= 3 and len(nb) >= 3:
        if na in nb or nb in na:
            return True
    return False


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


def detect_seniority(title: str) -> int:
    """Score seniority from title. Higher = more senior."""
    if not title:
        return 0
    tl = title.lower()
    if any(k in tl for k in ["ceo", "coo", "cfo", "cto", "cmo", "founder", "president", "managing director"]):
        return 100
    # "partner" needs word boundary to avoid matching "partnerships"
    is_partner = bool(re.search(r'\bpartner\b', tl)) and 'partnership' not in tl
    if is_partner or any(k in tl for k in ["vp", "vice president", "svp", "evp"]):
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

    def _ai_intro_message(
        self,
        mutual_name: str,
        target_name: str,
        target_title: str,
        company: str,
        role: str,
    ) -> str:
        """
        Generate a personalized LinkedIn message asking a mutual connection
        for an intro to a target person. Uses Claude Haiku (cheap). Cached
        in Redis for 7 days per (mutual, target, company, role) tuple.
        """
        import hashlib
        cache_key = None
        try:
            import redis
            from app.config import settings as _s
            r = redis.Redis.from_url(_s.redis_url, decode_responses=True)
            key_hash = hashlib.sha256(
                f"{mutual_name}|{target_name}|{target_title}|{company}|{role}".encode()
            ).hexdigest()[:16]
            cache_key = f"intro_msg:{key_hash}"
            cached = r.get(cache_key)
            if cached:
                return cached
        except Exception:
            r = None

        # Call Haiku (cheap, ~150 tokens)
        try:
            from app.services.llm.client import ClaudeClient
            from app.services.llm.router import LLMTask

            mutual_first = mutual_name.split()[0] if mutual_name else "there"
            target_first = target_name.split()[0] if target_name else "them"

            system_prompt = (
                "You are drafting a short, warm, professional LinkedIn message. "
                "The user is asking their mutual connection for an introduction to someone "
                "at a target company. Keep it under 80 words. Warm but professional. "
                "Be SPECIFIC: mention the target person's name and title, the company, "
                "and the specific role. Show you did your research. "
                "End with 'No pressure at all!' "
                "Do NOT use generic openers like 'Hope you're doing well' or 'I hope this message finds you well'. "
                "Do NOT include subject lines or placeholder brackets. "
                "Return ONLY the message body."
            )

            user_prompt = (
                f"Mutual connection (the person I'm writing TO): {mutual_name}\n"
                f"Target person (who I want to be introduced to): {target_name}, {target_title}, at {company}\n"
                f"Role I am pursuing: {role}\n\n"
                f"Write a personalized message from me to {mutual_first}, asking them to introduce me to "
                f"{target_first} at {company}. Mention why {target_first}'s role ({target_title}) "
                f"is relevant to my pursuit of the {role} position."
            )

            client = ClaudeClient(task=LLMTask.CLASSIFICATION, max_tokens=200)
            raw, _ = client.call_text(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.6,
            )
            message = raw.strip()
            # Strip any leading/trailing quote marks
            if message.startswith('"') and message.endswith('"'):
                message = message[1:-1]

            # Cache for 7 days
            if r and cache_key:
                try:
                    r.setex(cache_key, 7 * 86400, message)
                except Exception:
                    pass

            return message
        except Exception:
            # Fallback template
            mutual_first = mutual_name.split()[0] if mutual_name else "there"
            target_first = target_name.split()[0] if target_name else "them"
            return (
                f"Hi {mutual_first}, I saw you're connected with {target_name} "
                f"({target_title}) at {company}. I'm exploring a {role} opportunity there and think "
                f"{target_first} would be a great person to speak with. Would you be comfortable "
                f"making a quick intro? Happy to send you a short bio to forward. "
                f"No pressure at all."
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

        # Step 1: Direct contacts at target company
        # SENIORITY TIERS — ranked top to bottom:
        #   C_SUITE (4) → VP_DIRECTOR (3) → MANAGER (2) → IC (1) → RECRUITER (0)
        # Recruiters are EXCLUDED from direct contacts (Layer 1) per product spec —
        # they belong in a separate Recruiters layer, not the warm-intro funnel.
        def _seniority_tier(title: str) -> tuple[int, str]:
            t = (title or "").lower()
            if any(k in t for k in ["recruiter", "talent acquisition", "talent partner", "headhunter", "head hunter", "human resources", "people operations", "people partner", "staffing", "executive search", "search consultant", "resourcing", "recruitment"]):
                return (0, "RECRUITER")
            # "partner" needs word-boundary check to avoid matching "partnerships"
            is_partner = bool(re.search(r'\bpartner\b', t)) and 'partnership' not in t
            if is_partner or any(k in t for k in ["ceo", "coo", "cfo", "cto", "cio", "cpo", "chro", "chief", "founder", "co-founder", "president", "managing director", "managing partner", "general manager"]):
                return (4, "C_SUITE")
            if any(k in t for k in ["vp", "vice president", "head of", "svp", "evp", "group director", "regional director"]) or re.search(r'\bdirector\b', t):
                return (3, "VP_DIRECTOR")
            if re.search(r'\bmanager\b', t) or any(k in t for k in ["lead", "principal", "senior manager", "team lead", "supervisor", "department head"]):
                return (2, "MANAGER")
            return (1, "IC")

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

            # 2. Headline — try multiple extraction patterns
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

                # 2c. Direct mention of company name anywhere in headline
                #     (last resort — only if the normalized company name is long enough to avoid false matches)
                if len(norm_target) >= 5 and norm_target in normalize_company(headline):
                    # Check ORIGINAL headline (not normalized!) for "ex-" / "former" before company name
                    # normalize_company strips "Ex-" prefix, so the ex-check must use the raw text
                    hl_lower = headline.lower()
                    # Also check each segment that contains the company for former status
                    is_former = False
                    for seg in re.split(r'[|·•]', hl_lower):
                        seg_stripped = seg.strip()
                        seg_norm = normalize_company(seg_stripped)
                        if norm_target in seg_norm or seg_norm in norm_target:
                            if _is_former_company(seg_stripped):
                                is_former = True
                                break
                    if not is_former:
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
            if _conn_matches_company(c, company):
                is_visited = c.relationship_strength == "visited"
                tier_rank, tier_name = _seniority_tier(c.current_title or c.headline or "")
                first_name = (c.full_name or "there").split()[0]
                entry = {
                    "name": c.full_name,
                    "title": c.current_title or "",
                    "company": c.current_company,
                    "linkedin_url": c.linkedin_url,
                    "is_recruiter": tier_name == "RECRUITER",
                    "is_hiring_manager": tier_rank >= 3 and tier_name != "RECRUITER",
                    "seniority_tier": tier_name,
                    "_tier_rank": tier_rank,
                    "relevance_score": rank_connection(c, role),
                    "intro_angle": _suggest_intro_angle(c, role),
                    "message": _seniority_message(first_name, company, role, tier_name, c.current_title or c.headline or ""),
                    "connection_id": str(c.id),
                    "is_visited_profile": is_visited,
                }
                if is_visited:
                    entry["intro_angle"] = _suggest_cold_outreach_angle(c, company, role)
                    entry["message"] = _generate_cold_outreach(
                        c.full_name, company, role,
                        title=c.current_title, is_recruiter=(tier_name == "RECRUITER"),
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

        # Build maps for matching mutual connectors to our 1st-degree connections
        conn_by_id = {(c.linkedin_id or ""): c for c in all_conns if c.linkedin_id}
        conn_by_name: dict[str, LinkedInConnection] = {}
        conn_by_first_last: dict[str, LinkedInConnection] = {}
        for c in all_conns:
            name_lower = c.full_name.lower().strip()
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
                if connector:
                    t_name = mc.target_name or ""
                    t_title = mc.target_title or ""
                    t_company = mc.target_company or company
                    t_url = mc.target_linkedin_url or ""
                    real_paths.append({
                        "target": {
                            "name": t_name,
                            "title": t_title,
                            "company": t_company,
                            "linkedin_url": t_url,
                            "why_target": f"{t_name or 'Contact'} works at {t_company} as {t_title or 'employee'}"
                        },
                        "connector": {
                            "name": connector.full_name,
                            "title": connector.current_title or "",
                            "company": connector.current_company or "",
                            "linkedin_url": connector.linkedin_url or "",
                            "connection_id": str(connector.id),
                        },
                        "path": f"You → {connector.full_name} → {mc.target_name}",
                        "reason": f"{connector.full_name} is connected to {mc.target_name} on LinkedIn — verified mutual connection",
                        "action": f"Ask {connector.full_name.split()[0]} to introduce you to {mc.target_name} at {mc.target_company or company}",
                        "strength": "strong",
                        "verified": True,
                    })

        # Deduplicate paths by connector — normalize names aggressively
        seen_connectors = set()
        unique_paths = []
        for p in real_paths:
            # Normalize: lowercase, strip, remove middle initials, take first+last
            cname = p["connector"]["name"].lower().strip()
            parts = cname.split()
            # Use first + last name as key (ignores middle names/initials)
            if len(parts) >= 2:
                dedup_key = parts[0] + " " + parts[-1]
            else:
                dedup_key = cname
            # Also dedup by connection_id if available
            cid = p["connector"].get("connection_id", "")
            if dedup_key not in seen_connectors and (not cid or cid not in seen_connectors):
                seen_connectors.add(dedup_key)
                if cid:
                    seen_connectors.add(cid)
                unique_paths.append(p)
        real_paths = unique_paths

        # Sort by connector relevance
        def _path_rank(p):
            c = conn_by_name.get(p["connector"]["name"].lower().strip())
            return rank_connection(c, role) if c else 0
        real_paths.sort(key=_path_rank, reverse=True)

        # Filter out path targets who are already 1st-degree direct contacts
        direct_names = {d["name"].lower().strip() for d in direct}
        real_paths = [p for p in real_paths if p["target"]["name"].lower().strip() not in direct_names]

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
        # Cap at 50 to match LinkedIn's visible mutual count
        if real_paths:
            real_paths = real_paths[:50]
            # Attach a personalized intro message to ALL displayed paths
            for p in real_paths:
                target_name = p["target"]["name"] or f"your contact at {company}"
                target_title = p["target"].get("title") or "employee"
                connector_first = p["connector"]["name"].split()[0] if p["connector"]["name"] else "there"
                try:
                    msg = self._ai_intro_message(
                        mutual_name=p["connector"]["name"],
                        target_name=target_name,
                        target_title=target_title,
                        company=company,
                        role=role or "senior role",
                    )
                    # Ensure non-empty message (LLM sometimes returns empty)
                    if msg and msg.strip():
                        p["intro_message"] = msg
                    else:
                        raise ValueError("empty message")
                except Exception:
                    # Fallback to template if LLM fails or returns empty
                    target_first = target_name.split()[0] if target_name else "them"
                    p["intro_message"] = (
                        f"Hi {connector_first}, I'd love to connect with {target_name} "
                        f"({target_title}) at {company}. I know you're connected with the team "
                        f"there, and I'd be grateful if you could introduce me to the right person. "
                        f"Your insight into their culture and mission would be invaluable as I explore "
                        f"this next step. No pressure at all!"
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

        # Find real people at the company to suggest visiting their profiles
        discover_targets = []
        if not real_paths and not direct and not visited_targets:
            discover_targets = await self._find_people_to_discover(company, role)

        # No more "network brokers" fallback. Surfacing random recruiters and
        # senior people from unrelated companies confused users — they expected
        # contacts AT the target company, not generic suggestions.
        # Empty array kept for response shape backward-compat.
        network_brokers: list = []

        return {
            "company": company,
            "role": role,
            "best_path": best_path,
            "backup_paths": backup_paths,
            "verified_paths": len(real_paths),
            "discover_targets": discover_targets,
            "network_brokers": network_brokers,  # always [] — kept for response shape
            "total_connections": len(all_conns),
            "direct_contacts": direct[:50],  # 1st-degree, recruiter-free, sorted by seniority
            "total_direct": len(direct),
            "recruiter_contacts": recruiter_contacts[:25],  # separate bucket
            "total_recruiters": len(recruiter_contacts),
            "visited_targets": visited_targets[:20],
            "total_visited": len(visited_targets),
            "recommended_action": recommended,
        }

    async def _find_people_to_discover(self, company: str, role: str | None) -> list[dict]:
        """Use Serper to find real people at the target company on LinkedIn."""
        from app.config import settings
        import httpx

        if not settings.serper_api_key:
            return []

        role_str = role or "VP Director Head"
        queries = [
            f"site:linkedin.com/in {company} {role_str}",
            f"site:linkedin.com/in {company} recruiter talent acquisition",
        ]

        results = []
        seen = set()

        async with httpx.AsyncClient(timeout=8) as client:
            for q in queries:
                try:
                    resp = await client.post(
                        "https://google.serper.dev/search",
                        headers={"X-API-KEY": settings.serper_api_key, "Content-Type": "application/json"},
                        json={"q": q, "num": 5},
                    )
                    if resp.status_code != 200:
                        continue
                    for r in resp.json().get("organic", []):
                        url = r.get("link", "")
                        if "/in/" not in url or url in seen:
                            continue
                        seen.add(url)
                        title = r.get("title", "")
                        # LinkedIn titles are like "Name - Title - Company | LinkedIn"
                        parts = [p.strip() for p in title.split(" - ") if p.strip()]
                        name = parts[0] if parts else ""
                        person_title = parts[1] if len(parts) > 1 else ""
                        # Skip if it's a company page or generic
                        if not name or len(name) < 3 or "linkedin" in name.lower():
                            continue
                        results.append({
                            "name": name,
                            "title": person_title,
                            "linkedin_url": url.split("?")[0],
                            "snippet": r.get("snippet", "")[:200],
                        })
                except Exception:
                    continue

        return results[:6]

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
