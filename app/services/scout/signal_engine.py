"""
app/services/scout/signal_engine.py

StealthRole Signal Intelligence Engine
=======================================

Instead of searching for "jobs", we detect SIGNALS that indicate
a company is about to hire at senior level — before the job is posted.

Signal types:
  FUNDING     — raised capital → headcount growth imminent
  LEADERSHIP  — C-suite departure/arrival → replacement or restructure
  EXPANSION   — new market/product/M&A → team building needed
  VELOCITY    — spike in open roles → active growth phase
  DISTRESS    — layoffs/restructure → avoid or contrarian opportunity

Each signal is:
  - Detected from multiple web/news sources via Serper
  - Scored for recency and relevance
  - Fed to Claude which synthesises fit score, suggested role, contact, action
  - Returned as ranked OpportunityCards
"""

import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)

TIMEOUT = 12.0
SERPER_URL = "https://google.serper.dev/search"
SERPER_NEWS_URL = "https://google.serper.dev/news"


# ─────────────────────────────────────────────────────────────────────────────
# Data models
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Signal:
    company: str
    signal_type: str        # funding | leadership | expansion | velocity | distress
    headline: str
    detail: str
    source_url: str
    source_name: str
    published_date: str
    recency_score: float    # 0-1, 1=today
    raw_snippet: str


@dataclass
class OpportunityCard:
    id: str
    company: str
    company_type: str
    location: str
    sector: str
    signals: list[Signal]
    signal_summary: str
    fit_score: int
    fit_reasons: list[str]
    red_flags: list[str]
    suggested_role: str
    suggested_action: str
    contact_name: str
    contact_title: str
    apply_url: str
    is_posted: bool
    posted_title: str
    salary_estimate: str
    urgency: str            # high | medium | low
    timeline: str = ""          # immediate|1-3 months|3-6 months
    competition_level: str = "" # low|medium|high
    outreach_hook: str = ""     # ready-to-use LinkedIn opening line


# ─────────────────────────────────────────────────────────────────────────────
# Serper helpers
# ─────────────────────────────────────────────────────────────────────────────

def _serper(query: str, num: int = 10) -> list[dict]:
    if not settings.serper_api_key:
        return []
    try:
        r = httpx.post(SERPER_URL,
            headers={"X-API-KEY": settings.serper_api_key, "Content-Type": "application/json"},
            json={"q": query, "num": num}, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json().get("organic", [])
    except Exception as e:
        logger.warning("serper_error", q=query[:60], err=str(e))
        return []


def _serper_news(query: str, num: int = 10) -> list[dict]:
    if not settings.serper_api_key:
        return []
    try:
        r = httpx.post(SERPER_NEWS_URL,
            headers={"X-API-KEY": settings.serper_api_key, "Content-Type": "application/json"},
            json={"q": query, "num": num}, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json().get("news", [])
    except Exception as e:
        logger.warning("serper_news_error", q=query[:60], err=str(e))
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Signal keywords
# ─────────────────────────────────────────────────────────────────────────────

FUNDING_KW = ["raises","raised","funding","series a","series b","series c","seed round",
    "investment","backed","venture","growth capital","pe investment","private equity",
    "acquired","merger","million","billion","تمويل","مليون"]

LEADERSHIP_KW = ["appoints","appointed","names","joins as","promoted","steps down","resigns",
    "departed","new ceo","new coo","new cfo","new cto","chief executive","chief operating",
    "vice president","managing director","general manager","head of","country manager","leaves","exit"]

EXPANSION_KW = ["expands","expansion","launches","enters","new market","opens office",
    "new office","hiring","doubling","growing team","new product","partnership",
    "joint venture","uae","dubai","saudi","riyadh","gcc","mena","middle east"]

DISTRESS_KW = ["layoffs","laid off","restructuring","downsizing","cuts jobs","bankruptcy",
    "losses","revenue decline","struggling","investigation","fine","lawsuit"]

# ── NEW: Pain, Structural, Market signal keywords ─────────────────────────────

PAIN_KW = ["missed earnings","poor performance","regulatory fine","compliance issue",
    "pr crisis","product failure","product recall","security breach","data breach",
    "layoff at competitor","executive departed","key departure","glassdoor","employee reviews",
    "workplace culture","toxic","burnout","turnover","whistleblower"]

STRUCTURAL_KW = ["spin-off","carve-out","rebrand","strategic pivot","pivot to",
    "digital transformation","reorganization","restructure","demerger",
    "esg commitment","sustainability initiative","new regulation","regulatory change",
    "compliance requirement","name change","new brand"]

MARKET_KW = ["competitor raised","competitor funding","industry report","sector growth",
    "government policy","government contract","enterprise contract","awarded contract",
    "market opportunity","emerging market","industry trend","regulatory tailwind",
    "sector report","market analysis","industry forecast"]

MA_KW = ["acquisition","acquired","merger","acquires","takeover","buy-out","buyout",
    "joint venture","strategic investment","minority stake","majority stake"]

BOARD_KW = ["board of directors","board member","board seat","joins board",
    "pe firm","vc firm","takes control","new chairman","advisory board"]


def _classify(text: str) -> str:
    t = text.lower()
    if any(k in t for k in FUNDING_KW):    return "funding"
    if any(k in t for k in MA_KW):         return "ma_activity"
    if any(k in t for k in LEADERSHIP_KW): return "leadership"
    if any(k in t for k in BOARD_KW):      return "board_change"
    if any(k in t for k in EXPANSION_KW):  return "expansion"
    if any(k in t for k in PAIN_KW):       return "pain_signal"
    if any(k in t for k in STRUCTURAL_KW): return "structural"
    if any(k in t for k in MARKET_KW):     return "market_signal"
    if any(k in t for k in DISTRESS_KW):   return "distress"
    return "velocity"


def _company_from_title(title: str) -> str:
    for sep in [" raises "," appoints "," acquires "," launches "," expands "," names "," secures "," closes "]:
        if sep in title.lower():
            return title.split(sep, 1)[0].strip()[:60]
    return ""


def _date_from(r: dict) -> str:
    return str(r.get("date") or r.get("publishedDate") or "")[:10]


def _recency(date_str: str) -> float:
    if not date_str:
        return 0.3
    try:
        dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
        days = (datetime.now() - dt).days
        return max(0.0, 1.0 - days / 180.0)
    except:
        return 0.3


def _source_label(url: str) -> str:
    labels = {"techcrunch":"TechCrunch","magnitt":"MAGNiTT","wamda":"Wamda","zawya":"Zawya",
        "arabianbusiness":"Arabian Business","bloomberg":"Bloomberg","reuters":"Reuters",
        "linkedin":"LinkedIn","glassdoor":"Glassdoor","crunchbase":"Crunchbase",
        "thenationalnews":"The National","khaleejtimes":"Khaleej Times",
        "gulfnews":"Gulf News","forbes":"Forbes","ft.com":"FT","wsj":"WSJ"}
    for k, v in labels.items():
        if k in url.lower():
            return v
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc.replace("www.","").split(".")[0].capitalize()
    except:
        return "Web"


# ─────────────────────────────────────────────────────────────────────────────
# Signal fetchers
# ─────────────────────────────────────────────────────────────────────────────

def _funding_signals(region: str, sectors: list[str], roles: list[str]) -> list[Signal]:
    sec = " ".join(sectors[:3]) if sectors else "tech fintech ecommerce"
    queries = [
        f"startup raises funding {region} 2025 2026 {sec}",
        f"series A B C funding {region} {sec} million",
        f"MENA funding round 2026 {sec}",
        f"private equity investment {region} 2026",
        f"venture capital {region} 2026 portfolio company",
        f"{region} startup acquisition 2026 {sec}",
        f"IPO preparation {region} {sec} 2026",
        f"growth equity {region} expansion capital 2026",
    ]
    signals, seen = [], set()
    for q in queries:
        for r in _serper_news(q, 8):
            url = r.get("link","")
            if url in seen: continue
            seen.add(url)
            text = f"{r.get('title','')} {r.get('snippet','')}"
            if not any(k in text.lower() for k in FUNDING_KW): continue
            company = _company_from_title(r.get("title",""))
            if not company or len(company) < 3: continue
            signals.append(Signal(
                company=company, signal_type="funding",
                headline=r.get("title","")[:120], detail=r.get("snippet","")[:400],
                source_url=url, source_name=_source_label(url),
                published_date=_date_from(r), recency_score=_recency(_date_from(r)),
                raw_snippet=r.get("snippet",""),
            ))
    return signals


def _leadership_signals(region: str, sectors: list[str]) -> list[Signal]:
    queries = [
        f"CEO COO CFO appointed {region} 2025 2026",
        f"chief executive steps down {region} startup scaleup",
        f"new managing director general manager {region} 2026",
        f"VP director appointed {region} {' '.join(sectors[:2]) if sectors else 'tech'}",
        f"C-suite departure resignation {region} 2025 2026",
        f"new country manager {region} 2026",
        f"hiring CEO COO CFO {region} executive search 2026",
        f"board of directors appointment {region} 2026",
        f"interim CEO COO {region} {' '.join(sectors[:2]) if sectors else 'tech'}",
    ]
    signals, seen = [], set()
    for q in queries:
        for r in _serper_news(q, 8):
            url = r.get("link","")
            if url in seen: continue
            seen.add(url)
            text = f"{r.get('title','')} {r.get('snippet','')}"
            if not any(k in text.lower() for k in LEADERSHIP_KW): continue
            company = _company_from_title(r.get("title",""))
            if not company or len(company) < 3: continue
            signals.append(Signal(
                company=company, signal_type="leadership",
                headline=r.get("title","")[:120], detail=r.get("snippet","")[:400],
                source_url=url, source_name=_source_label(url),
                published_date=_date_from(r), recency_score=_recency(_date_from(r)),
                raw_snippet=r.get("snippet",""),
            ))
    return signals


def _expansion_signals(region: str, sectors: list[str]) -> list[Signal]:
    queries = [
        f"company expands {region} new office 2025 2026",
        f"international company launches {region} operations",
        f"enters UAE Dubai market 2026",
        f"MENA expansion strategy 2026",
        f"regional hub {region} headquarters 2026",
        f"company opens {region} office hiring leadership",
        f"company {region} license approval regulatory 2026",
        f"free zone company registration {region} 2026",
        f"multinational opens {region} hiring team 2026",
    ]
    signals, seen = [], set()
    for q in queries:
        for r in _serper_news(q, 6):
            url = r.get("link","")
            if url in seen: continue
            seen.add(url)
            text = f"{r.get('title','')} {r.get('snippet','')}"
            if not any(k in text.lower() for k in EXPANSION_KW): continue
            company = _company_from_title(r.get("title",""))
            if not company or len(company) < 3: continue
            signals.append(Signal(
                company=company, signal_type="expansion",
                headline=r.get("title","")[:120], detail=r.get("snippet","")[:400],
                source_url=url, source_name=_source_label(url),
                published_date=_date_from(r), recency_score=_recency(_date_from(r)),
                raw_snippet=r.get("snippet",""),
            ))
    return signals


def _velocity_signals(roles: list[str], region: str, sectors: list[str]) -> list[Signal]:
    """Detect hiring spikes from multiple job boards and news sources."""
    role_str = " ".join(roles[:3]) if roles else "CEO COO Director"
    sec = " ".join(sectors[:2]) if sectors else "tech"
    JOB_SOURCES = ["bayt.com", "gulftalent.com", "indeed.com", "greenhouse.io", "lever.co",
                   "workday.com", "jobs.", "careers.", "naukrigulf.com", "monster.com", "linkedin.com"]
    queries = [
        f"senior executive hiring {region} {sec} 2026",
        f"{role_str} open position {region}",
        f"executive vacancy {region} 2026",
        f"site:bayt.com {role_str} {region}",
        f"site:gulftalent.com {role_str}",
        f"site:linkedin.com/jobs {role_str} {region}",
    ]
    signals, seen = [], set()
    for q in queries:
        for r in _serper(q, 8):
            url = r.get("link","")
            if url in seen: continue
            # Accept any job board or company careers page — not just LinkedIn
            is_job_source = any(x in url for x in JOB_SOURCES)
            is_careers = "career" in url or "job" in url or "recruit" in url
            if not (is_job_source or is_careers): continue
            seen.add(url)
            company = _company_from_title(r.get("title",""))
            if not company or len(company) < 3: continue
            signals.append(Signal(
                company=company, signal_type="velocity",
                headline=r.get("title","")[:120], detail=r.get("snippet","")[:400],
                source_url=url, source_name=_source_label(url),
                published_date=_date_from(r), recency_score=0.85,
                raw_snippet=r.get("snippet",""),
            ))
    return signals


def _live_job_openings(roles: list[str], region: str, sectors: list[str]) -> list[dict]:
    """
    Fetch CURRENT posted job openings — actual vacancies, not signals.
    Returns raw search results with is_posted=True marker.
    Sources: Bayt, GulfTalent, Indeed, LinkedIn Jobs, Naukrigulf, company career pages.
    """
    if not settings.serper_api_key:
        return []

    role_str = " ".join(roles[:3]) if roles else "CEO COO Director"
    sec = " ".join(sectors[:2]) if sectors else ""
    region_q = region or "UAE"

    queries = [
        f"{role_str} job vacancy {region_q} {sec}",
        f"senior executive open role {region_q} 2026",
        f"site:bayt.com {role_str} {region_q}",
        f"site:gulftalent.com {role_str}",
        f"site:indeed.com {role_str} {region_q}",
        f"site:linkedin.com/jobs {role_str} {region_q}",
    ]

    results, seen = [], set()
    for q in queries:
        for r in _serper(q, 8):
            url = r.get("link","")
            if url in seen: continue
            seen.add(url)
            title = r.get("title","")
            snippet = r.get("snippet","")
            if not title: continue
            results.append({
                "title": title[:120],
                "company": _company_from_title(title),
                "snippet": snippet[:400],
                "url": url,
                "source": _source_label(url),
                "date": _date_from(r),
                "recency": _recency(_date_from(r)),
                "is_posted": True,
            })

    # Also fetch news about companies actively hiring
    news_q = f"hiring expanding leadership team {region_q} {sec} 2026"
    for item in _serper_news(news_q, 10):
        url = item.get("link","")
        if url in seen: continue
        seen.add(url)
        title = item.get("title","")
        if any(k in title.lower() for k in ["layoff","cut","retrench","downsize"]): continue
        results.append({
            "title": title[:120],
            "company": _company_from_title(title),
            "snippet": item.get("snippet","")[:400],
            "url": url,
            "source": _source_label(url),
            "date": _date_from(item),
            "recency": _recency(_date_from(item)),
            "is_posted": False,  # It's a news signal, not a direct job posting
        })

    logger.info("live_jobs_fetched", count=len(results))
    return results[:30]


# ─────────────────────────────────────────────────────────────────────────────
# Claude scoring
# ─────────────────────────────────────────────────────────────────────────────

def _score_with_claude(signals: list[Signal], user_profile: dict, preferences: dict) -> list[OpportunityCard]:
    if not settings.anthropic_api_key or not signals:
        return _score_heuristic(signals, preferences)

    by_company: dict[str, list[Signal]] = {}
    for sig in signals:
        key = sig.company.lower().strip()
        by_company.setdefault(key, []).append(sig)

    signal_text = ""
    for company, sigs in list(by_company.items())[:12]:
        signal_text += f"\n## {company}\n"
        for s in sigs[:4]:
            signal_text += f"- [{s.signal_type.upper()}] {s.headline} ({s.published_date or 'recent'}) — {s.source_name}\n"
            if s.detail:
                signal_text += f"  {s.detail[:200]}\n"

    profile_summary = json.dumps({
        "headline": user_profile.get("headline",""),
        "background": (user_profile.get("global_context","") or "")[:600],
        "target_roles": preferences.get("roles",[]),
        "target_regions": preferences.get("regions",[]),
        "target_sectors": preferences.get("sectors",[]),
        "seniority": preferences.get("seniority",[]),
        "company_types": preferences.get("companyType",[]),
        "company_stages": preferences.get("stage",[]),
        "min_salary_aed": preferences.get("salaryMin",""),
    }, indent=2)

    prompt = f"""DEEP ANALYSIS REQUIRED. You are not just matching keywords — you are reading the market like a senior headhunter with 20 years in MENA.

For each company signal, think about:
- What EXACTLY does this signal mean for hiring? Not "they might hire" — WHICH specific roles will they need and WHY
- Timeline: when will the role materialise? (immediately / 1-3 months / 3-6 months)
- Competition: how many other candidates are likely chasing this? Is there an advantage to moving now?
- Inside angle: what would a candidate say in an outreach message that shows they understand what this company is going through?

For fit scoring, be BRUTALLY honest:
- 90+ = almost perfect match, would get an interview tomorrow
- 75-89 = strong match, worth pursuing aggressively
- 60-74 = decent match, worth exploring
- 45-59 = stretch but possible with the right angle
- Below 45 = don't waste their time, skip it

You are a top-tier executive search consultant — think Korn Ferry or Spencer Stuart — analysing live market signals to identify hidden senior career opportunities for a specific professional.

USER PROFILE:
{profile_summary}

LIVE MARKET SIGNALS:
{signal_text}

Your task: For each company, determine:
1. What does this signal specifically mean for hiring? Be precise.
   - Funding → how much raised, what stage, what headcount growth is implied
   - Leadership departure → which role is now open or needs backfilling
   - Expansion → which new roles are needed in which markets
   - High velocity → which specific roles are actively open

2. Fit score (0-100) based on:
   - Does the company stage match the user's experience?
   - Does the sector match their target?
   - Is the implied role in their wheelhouse?
   - Is the location right?
   - Are there red flags that would make this a bad move?

3. Specific action the user should take NOW — not generic advice.
   Name a specific person to contact if you can infer it from context.
   Say whether to apply, reach out cold, or wait.

4. Urgency:
   - high: signal < 45 days AND fit_score > 70
   - medium: signal 45-90 days OR fit_score 50-70
   - low: signal > 90 days OR fit_score < 50

Only return companies with fit_score >= 45.
Sort by urgency (high first), then fit_score descending.
Maximum 10 results. Keep ALL field values concise (1-2 sentences max).
fit_reasons: max 3 items. red_flags: max 2 items.

CRITICAL: Return ONLY a valid JSON array. No text before or after. No markdown fences:
[
  {{
    "company": "Exact company name",
    "company_type": "startup|scale-up|corporate|pe|family-office|government",
    "location": "City, Country",
    "sector": "Sector name",
    "signal_summary": "Precise 1-2 sentence explanation of what happened and why it creates an opportunity",
    "fit_score": 85,
    "fit_reasons": ["Specific reason 1", "Specific reason 2", "Specific reason 3"],
    "red_flags": ["Specific concern if any"],
    "suggested_role": "Specific role title",
    "suggested_action": "Specific action — who to contact, how, why now",
    "contact_name": "Name if inferable from signal context",
    "contact_title": "Their title",
    "apply_url": "Direct URL to job or company LinkedIn page",
    "is_posted": false,
    "posted_title": "Actual job title if posted",
    "salary_estimate": "AED XXX–XXX or USD XXX–XXX",
    "urgency": "high|medium|low",
    "timeline": "immediate|1-3 months|3-6 months — when the role will likely materialise",
    "competition_level": "low|medium|high — how many candidates are likely pursuing this",
    "outreach_hook": "The specific opening line for a LinkedIn message that shows deep understanding"
  }}
]"""

    try:
        from app.services.llm.client import ClaudeClient
        from app.services.llm.router import LLMTask
        client = ClaudeClient(task=LLMTask.SIGNAL_SCORING, max_tokens=6000)
        raw, _result = client.call_text(
            system_prompt="You are a senior recruiter scoring market signals.",
            user_prompt=prompt,
            temperature=0.2,
        )
        raw = raw.strip()
        raw = re.sub(r'^```json\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)
        # Extract just the JSON array — ignore any trailing text
        bracket_start = raw.find('[')
        if bracket_start == -1:
            raise ValueError("No JSON array found in response")
        # Find the matching closing bracket
        depth = 0
        bracket_end = -1
        for i in range(bracket_start, len(raw)):
            if raw[i] == '[': depth += 1
            elif raw[i] == ']': depth -= 1
            if depth == 0:
                bracket_end = i + 1
                break
        if bracket_end == -1:
            # Truncated — try to fix by closing open objects/arrays
            raw_fixed = raw[bracket_start:].rstrip()
            # Close any open strings, objects, arrays
            if raw_fixed.count('"') % 2 == 1:
                raw_fixed += '"'
            while raw_fixed.count('{') > raw_fixed.count('}'):
                raw_fixed += '}'
            while raw_fixed.count('[') > raw_fixed.count(']'):
                raw_fixed += ']'
            data = json.loads(raw_fixed)
        else:
            data = json.loads(raw[bracket_start:bracket_end])

        cards = []
        for i, item in enumerate(data[:20]):
            ckey = item.get("company","").lower()
            matched = by_company.get(ckey, [])
            if not matched:
                for k, sigs in by_company.items():
                    if ckey[:8] in k or k[:8] in ckey:
                        matched = sigs; break

            cards.append(OpportunityCard(
                id=hashlib.md5(f"{item.get('company','')}_{i}".encode()).hexdigest()[:12],
                company=item.get("company","Unknown"),
                company_type=item.get("company_type","startup"),
                location=item.get("location",""),
                sector=item.get("sector",""),
                signals=matched,
                signal_summary=item.get("signal_summary",""),
                fit_score=int(item.get("fit_score",50)),
                fit_reasons=item.get("fit_reasons",[]),
                red_flags=item.get("red_flags",[]),
                suggested_role=item.get("suggested_role",""),
                suggested_action=item.get("suggested_action",""),
                contact_name=item.get("contact_name",""),
                contact_title=item.get("contact_title",""),
                apply_url=item.get("apply_url",""),
                is_posted=item.get("is_posted",False),
                posted_title=item.get("posted_title",""),
                salary_estimate=item.get("salary_estimate",""),
                urgency=item.get("urgency","medium"),
                timeline=item.get("timeline",""),
                competition_level=item.get("competition_level",""),
                outreach_hook=item.get("outreach_hook",""),
            ))
        logger.info("claude_scored", count=len(cards))
        return cards
    except Exception as e:
        logger.warning("claude_score_failed", error=str(e))
        return _score_heuristic(signals, preferences)


def _score_heuristic(signals: list[Signal], preferences: dict) -> list[OpportunityCard]:
    by_company: dict[str, list[Signal]] = {}
    for sig in signals:
        by_company.setdefault(sig.company.lower(), []).append(sig)

    cards = []
    for _, sigs in by_company.items():
        if not sigs[0].company or len(sigs[0].company) < 3: continue
        types = {s.signal_type for s in sigs}
        best = max(sigs, key=lambda s: s.recency_score)

        score = 50
        reasons = []
        if "funding"    in types: score += 20; reasons.append("Recent funding — headcount growth expected")
        if "leadership" in types: score += 25; reasons.append("Leadership change — role likely open")
        if "expansion"  in types: score += 15; reasons.append("Market expansion — local leadership needed")
        score = min(score, 90)

        urgency = "high" if best.recency_score > 0.8 else "medium" if best.recency_score > 0.4 else "low"
        type_emoji = {"funding":"💰","leadership":"👤","expansion":"🌍","velocity":"📈","distress":"⚠️"}
        summary = " · ".join(type_emoji.get(t,t) + " " + t.capitalize() for t in types)
        summary += f" — {best.headline[:80]}"

        cards.append(OpportunityCard(
            id=hashlib.md5(sigs[0].company.encode()).hexdigest()[:12],
            company=sigs[0].company, company_type="startup",
            location="", sector="",
            signals=sigs, signal_summary=summary,
            fit_score=score, fit_reasons=reasons, red_flags=[],
            suggested_role=(preferences.get("roles") or ["Senior Executive"])[0],
            suggested_action="Research and reach out via LinkedIn",
            contact_name="", contact_title="",
            apply_url=best.source_url,
            is_posted=best.signal_type=="velocity", posted_title="",
            salary_estimate="", urgency=urgency,
            timeline="1-3 months" if best.recency_score > 0.7 else "3-6 months",
            competition_level="medium",
            outreach_hook=f"I noticed {sigs[0].company} recently made headlines — I'd love to discuss how my background could support your next phase of growth.",
        ))

    cards.sort(key=lambda c: (-{"high":3,"medium":2,"low":1}.get(c.urgency,1), -c.fit_score))
    return cards[:20]


# ─────────────────────────────────────────────────────────────────────────────
# NEW: Pain, Structural, Market signal fetchers (all via Serper, no new APIs)
# ─────────────────────────────────────────────────────────────────────────────

def _pain_signals(region: str, sectors: list[str]) -> list[Signal]:
    """Detect pain signals: missed earnings, PR crises, regulatory issues, Glassdoor spikes."""
    sec = " ".join(sectors[:3]) if sectors else "tech"
    queries = [
        f"{region} company regulatory fine compliance 2026 {sec}",
        f"{region} company crisis PR issue 2026 {sec}",
        f"{region} company layoffs competitor {sec} 2026",
        f"glassdoor reviews {region} company culture issues {sec}",
        f"{region} company missed earnings revenue decline 2026",
    ]
    signals, seen = [], set()
    for q in queries:
        for r in _serper_news(q, 5):
            url = r.get("link", "")
            if url in seen: continue
            seen.add(url)
            text = f"{r.get('title', '')} {r.get('snippet', '')}"
            if not any(k in text.lower() for k in PAIN_KW): continue
            company = _company_from_title(r.get("title", ""))
            if not company or len(company) < 3: continue
            signals.append(Signal(
                company=company, signal_type="pain_signal",
                headline=r.get("title", "")[:120], detail=r.get("snippet", "")[:400],
                source_url=url, source_name=_source_label(url),
                published_date=_date_from(r), recency_score=_recency(_date_from(r)),
                raw_snippet=r.get("snippet", ""),
            ))
    return signals


def _structural_signals(region: str, sectors: list[str]) -> list[Signal]:
    """Detect structural signals: spin-offs, rebrands, digital transformation, ESG."""
    sec = " ".join(sectors[:3]) if sectors else "tech"
    queries = [
        f"{region} company rebrand strategic pivot 2026 {sec}",
        f"{region} spin-off carve-out demerger 2026",
        f"{region} digital transformation initiative 2026 {sec}",
        f"{region} ESG sustainability commitment 2026 {sec}",
        f"new regulation regulatory change {region} {sec} 2026",
    ]
    signals, seen = [], set()
    for q in queries:
        for r in _serper_news(q, 5):
            url = r.get("link", "")
            if url in seen: continue
            seen.add(url)
            text = f"{r.get('title', '')} {r.get('snippet', '')}"
            if not any(k in text.lower() for k in STRUCTURAL_KW): continue
            company = _company_from_title(r.get("title", ""))
            if not company or len(company) < 3: continue
            signals.append(Signal(
                company=company, signal_type="structural",
                headline=r.get("title", "")[:120], detail=r.get("snippet", "")[:400],
                source_url=url, source_name=_source_label(url),
                published_date=_date_from(r), recency_score=_recency(_date_from(r)),
                raw_snippet=r.get("snippet", ""),
            ))
    return signals


def _market_signals(region: str, sectors: list[str]) -> list[Signal]:
    """Detect market signals: competitor funding, govt contracts, industry reports."""
    sec = " ".join(sectors[:3]) if sectors else "tech"
    queries = [
        f"competitor raised funding {region} {sec} 2026",
        f"government contract awarded {region} 2026 {sec}",
        f"industry report sector growth {region} {sec} 2026",
        f"government policy change {region} {sec} 2026",
        f"enterprise contract announced {region} {sec} 2026",
    ]
    signals, seen = [], set()
    for q in queries:
        for r in _serper_news(q, 5):
            url = r.get("link", "")
            if url in seen: continue
            seen.add(url)
            text = f"{r.get('title', '')} {r.get('snippet', '')}"
            if not any(k in text.lower() for k in MARKET_KW): continue
            company = _company_from_title(r.get("title", ""))
            if not company or len(company) < 3: continue
            signals.append(Signal(
                company=company, signal_type="market_signal",
                headline=r.get("title", "")[:120], detail=r.get("snippet", "")[:400],
                source_url=url, source_name=_source_label(url),
                published_date=_date_from(r), recency_score=_recency(_date_from(r)),
                raw_snippet=r.get("snippet", ""),
            ))
    return signals


def _ma_signals(region: str, sectors: list[str]) -> list[Signal]:
    """Detect M&A activity: acquisitions, mergers, takeovers."""
    sec = " ".join(sectors[:3]) if sectors else "tech"
    queries = [
        f"{region} acquisition merger 2026 {sec}",
        f"{region} company acquires buyout 2026",
        f"M&A deal {region} {sec} 2026",
    ]
    signals, seen = [], set()
    for q in queries:
        for r in _serper_news(q, 5):
            url = r.get("link", "")
            if url in seen: continue
            seen.add(url)
            text = f"{r.get('title', '')} {r.get('snippet', '')}"
            if not any(k in text.lower() for k in MA_KW): continue
            company = _company_from_title(r.get("title", ""))
            if not company or len(company) < 3: continue
            signals.append(Signal(
                company=company, signal_type="ma_activity",
                headline=r.get("title", "")[:120], detail=r.get("snippet", "")[:400],
                source_url=url, source_name=_source_label(url),
                published_date=_date_from(r), recency_score=_recency(_date_from(r)),
                raw_snippet=r.get("snippet", ""),
            ))
    return signals


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2: Direct API providers (Crunchbase + MAGNiTT)
# ─────────────────────────────────────────────────────────────────────────────

def _crunchbase_signals(region: str, sectors: list[str], roles: list[str]) -> list[Signal]:
    """Fetch signals from Crunchbase API and convert to Signal objects."""
    from app.services.scout.crunchbase_provider import fetch_funding_signals, fetch_leadership_signals

    signals = []

    # Funding
    for raw in fetch_funding_signals(region=region, sectors=sectors, roles=roles):
        signals.append(Signal(
            company=raw["company"],
            signal_type=raw["signal_type"],
            headline=raw["headline"],
            detail=raw["detail"],
            source_url=raw["source_url"],
            source_name=raw["source_name"],
            published_date=raw["published_date"],
            recency_score=raw["recency_score"],
            raw_snippet=raw["raw_snippet"],
        ))

    # Leadership
    for raw in fetch_leadership_signals(region=region, sectors=sectors):
        signals.append(Signal(
            company=raw["company"],
            signal_type=raw["signal_type"],
            headline=raw["headline"],
            detail=raw["detail"],
            source_url=raw["source_url"],
            source_name=raw["source_name"],
            published_date=raw["published_date"],
            recency_score=raw["recency_score"],
            raw_snippet=raw["raw_snippet"],
        ))

    return signals


def _magnitt_signals(sectors: list[str]) -> list[Signal]:
    """Fetch MENA startup signals from MAGNiTT and convert to Signal objects."""
    from app.services.scout.magnitt_provider import fetch_mena_funding_signals

    signals = []
    for raw in fetch_mena_funding_signals(sectors=sectors):
        signals.append(Signal(
            company=raw["company"],
            signal_type=raw["signal_type"],
            headline=raw["headline"],
            detail=raw["detail"],
            source_url=raw["source_url"],
            source_name=raw["source_name"],
            published_date=raw["published_date"],
            recency_score=raw["recency_score"],
            raw_snippet=raw["raw_snippet"],
        ))
    return signals


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────

def run_signal_engine(preferences: dict, user_profile: dict, max_results: int = 20) -> dict:
    regions  = preferences.get("regions",  ["UAE"])
    sectors  = preferences.get("sectors",  [])
    roles    = preferences.get("roles",    [])
    region   = regions[0] if regions else "UAE Dubai"

    logger.info("signal_engine_start", region=region, sectors=sectors, roles=roles)

    logger.info("signal_engine_config",
        has_serper=bool(settings.serper_api_key),
        has_anthropic=bool(settings.anthropic_api_key),
        serper_key_prefix=settings.serper_api_key[:8] if settings.serper_api_key else "MISSING",
    )

    if not settings.serper_api_key:
        logger.warning("signal_engine_no_serper_key")
        return {
            "opportunities": [],
            "live_openings": [],
            "signals_detected": 0, "sources_searched": 0,
            "is_demo": True, "engine_version": "3.0", "scored_by": "none",
            "empty_reason": "Signal scanning requires API configuration. Contact support if this persists.",
        }

    # Gather all signals + live openings in PARALLEL (cuts scan time ~60s → ~15s)
    all_signals: list[Signal] = []
    live_openings: list[dict] = []

    with ThreadPoolExecutor(max_workers=12) as executor:
        futures = {
            executor.submit(_funding_signals, region, sectors, roles): "funding",
            executor.submit(_leadership_signals, region, sectors): "leadership",
            executor.submit(_expansion_signals, region, sectors): "expansion",
            executor.submit(_velocity_signals, roles, region, sectors): "velocity",
            executor.submit(_live_job_openings, roles, region, sectors): "live_openings",
            # NEW: Pain, Structural, Market, M&A signals
            executor.submit(_pain_signals, region, sectors): "pain",
            executor.submit(_structural_signals, region, sectors): "structural",
            executor.submit(_market_signals, region, sectors): "market",
            executor.submit(_ma_signals, region, sectors): "ma",
            # Phase 2: Direct API providers (Crunchbase + MAGNiTT)
            executor.submit(_crunchbase_signals, region, sectors, roles): "crunchbase",
            executor.submit(_magnitt_signals, sectors): "magnitt",
        }
        for future in as_completed(futures):
            label = futures[future]
            try:
                result = future.result()
                if label == "live_openings":
                    live_openings = result
                else:
                    all_signals.extend(result)
                logger.info(f"{label}_done", count=len(result))
            except Exception as e:
                logger.warning(f"{label}_failed", error=str(e))

    # Deduplicate signals (improved: normalise company names, fuzzy match, keep strongest per type)
    def _normalise_company(name: str) -> str:
        """Strip suffixes and normalise whitespace for dedup comparison."""
        n = name.lower().strip()
        for suffix in [" inc", " inc.", " ltd", " ltd.", " llc", " llp",
                       " corp", " corp.", " co.", " plc", " pjsc",
                       " limited", " corporation", " group", " holdings"]:
            if n.endswith(suffix):
                n = n[: -len(suffix)].rstrip(" ,.")
        return re.sub(r"\s+", " ", n).strip()

    def _company_match(a: str, b: str) -> bool:
        """Fuzzy company match: exact normalised OR first-10-chars overlap."""
        na, nb = _normalise_company(a), _normalise_company(b)
        if na == nb:
            return True
        if len(na) >= 10 and len(nb) >= 10 and na[:10] == nb[:10]:
            return True
        return False

    # Build canonical company buckets
    company_buckets: dict[str, list[Signal]] = {}
    canonical_names: dict[str, str] = {}  # normalised prefix -> canonical key

    for sig in all_signals:
        norm = _normalise_company(sig.company)
        # Find existing bucket via fuzzy match
        matched_key = None
        for existing_key in canonical_names:
            if _company_match(sig.company, existing_key):
                matched_key = canonical_names[existing_key]
                break
        if matched_key is None:
            matched_key = norm
            canonical_names[norm] = norm
            company_buckets[norm] = []
        company_buckets[matched_key].append(sig)

    # Signal stacking: count distinct signal types per company
    # More signals = higher confidence that company is about to hire
    company_signal_stacks: dict[str, dict] = {}
    for _key, sigs in company_buckets.items():
        by_type: dict[str, list[Signal]] = {}
        for s in sigs:
            by_type.setdefault(s.signal_type, []).append(s)

        signal_types = list(by_type.keys())
        stack_count = len(signal_types)

        # Build stack summary for this company
        company_name = sigs[0].company if sigs else _key
        company_signal_stacks[_key] = {
            "company": company_name,
            "signal_count": stack_count,
            "signal_types": signal_types,
            "stack_summary": " + ".join(
                t.replace("_", " ").title() for t in signal_types
            ),
            # Confidence boost: 1 signal = 1.0x, 2 = 1.3x, 3 = 1.6x, 4+ = 2.0x
            "confidence_multiplier": min(2.0, 1.0 + (stack_count - 1) * 0.3),
        }

    # Keep strongest signal per type, attach stacking data
    unique = []
    for _key, sigs in company_buckets.items():
        by_type: dict[str, list[Signal]] = {}
        for s in sigs:
            by_type.setdefault(s.signal_type, []).append(s)
        stack = company_signal_stacks.get(_key, {})
        for _stype, type_sigs in by_type.items():
            best = max(type_sigs, key=lambda s: (s.recency_score, len(s.detail)))
            # Boost recency by stack multiplier
            best.recency_score = min(1.0, best.recency_score * stack.get("confidence_multiplier", 1.0))
            # Add stack info to the signal detail
            if stack.get("signal_count", 0) > 1:
                best.raw_snippet = f"[{stack['signal_count']} signals stacked: {stack['stack_summary']}] {best.raw_snippet}"
            unique.append(best)

    logger.info("unique_signals", count=len(unique), stacked_companies=sum(1 for s in company_signal_stacks.values() if s["signal_count"] > 1))

    cards = _score_with_claude(unique, user_profile, preferences)
    scored_by = "claude" if settings.anthropic_api_key else "heuristic"

    # Classify openings by urgency: posted=green, recent news signal=yellow
    classified_openings = []
    for job in live_openings:
        rec = job.get("recency", 0.5)
        if job.get("is_posted"):
            status = "current"       # green — live posted vacancy
        elif rec > 0.7:
            status = "imminent"      # yellow — very recent signal, hiring likely
        else:
            status = "strategic"     # red/grey — longer-horizon signal
        classified_openings.append({**job, "status": status})

    # If no real signals were detected, the engine effectively produced nothing
    # Flag as demo so users don't see "0 results" labeled as real intelligence
    has_real_data = len(cards) > 0 or len(classified_openings) > 0

    return {
        "opportunities": [_card_to_dict(c) for c in cards[:max_results]],
        "live_openings": classified_openings[:20],
        "signals_detected": len(unique),
        "sources_searched": len(all_signals),
        "is_demo": not has_real_data,
        "engine_version": "3.0",
        "scored_by": scored_by,
    }
