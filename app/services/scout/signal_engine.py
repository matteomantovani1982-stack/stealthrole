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
# Demo data
# ─────────────────────────────────────────────────────────────────────────────

def _demo_opportunities() -> list[OpportunityCard]:
    def sig(company, t, h, d, url, src, date, rec):
        return Signal(company=company, signal_type=t, headline=h, detail=d,
            source_url=url, source_name=src, published_date=date, recency_score=rec, raw_snippet=d)

    return [
        OpportunityCard(
            id="demo_1", company="Tabby", company_type="scale-up", location="Dubai, UAE", sector="Fintech",
            signals=[sig("Tabby","funding","Tabby raises $200M Series C led by STV and PayPal Ventures",
                "BNPL leader Tabby has raised $200M Series C to accelerate MENA expansion and product development.",
                "https://magnitt.com/news/tabby","MAGNiTT","2026-02-10",0.95)],
            signal_summary="🚀 Raised $200M Series C 7 weeks ago — scaling from 400 to 700 employees this year. No COO publicly listed. VP Operations role implied.",
            fit_score=92, fit_reasons=["MENA fintech aligns with your sector focus","Series C stage = structured ops needed","P&L ownership at your level","COO/VP Ops role not yet filled","Strong equity upside at this stage"],
            red_flags=[],
            suggested_role="COO / VP Operations",
            suggested_action="Connect with Hosam Arab (CEO) or Ahmed Al-Zaabi (VP People) on LinkedIn this week — before they engage a search firm",
            contact_name="Hosam Arab", contact_title="CEO & Co-founder",
            apply_url="https://linkedin.com/company/tabby", is_posted=False, posted_title="",
            salary_estimate="AED 750K–1.1M + equity", urgency="high",
        ),
        OpportunityCard(
            id="demo_2", company="Noon", company_type="corporate", location="Dubai, UAE", sector="E-commerce",
            signals=[sig("Noon","leadership","Noon's Chief Operating Officer departs after 3-year tenure",
                "Noon.com's COO has stepped down amid broader executive restructuring as the company refocuses on profitability.",
                "https://arabianbusiness.com","Arabian Business","2026-02-25",0.90)],
            signal_summary="👤 COO departed 12 days ago — role not yet posted. Board conducting discreet search before going external.",
            fit_score=85, fit_reasons=["E-commerce operations is your core","Scale of business ($500M+ GMV) matches your level","Direct board report","Mohamed Alabbar connection possible"],
            red_flags=["High leadership turnover — 3rd COO in 4 years","Culture can be demanding"],
            suggested_role="COO",
            suggested_action="Reach out to Head of Talent before external search firm is engaged — they typically wait 3-4 weeks before going external",
            contact_name="Sara Ahmed", contact_title="Head of Talent Acquisition",
            apply_url="https://linkedin.com/company/noon", is_posted=False, posted_title="",
            salary_estimate="AED 900K–1.4M", urgency="high",
        ),
        OpportunityCard(
            id="demo_3", company="Careem", company_type="corporate", location="Dubai, UAE", sector="Tech / Mobility",
            signals=[sig("Careem","expansion","Careem expands super-app to 5 new MENA markets in 2026",
                "Careem launches services in Iraq, Algeria, Morocco, Jordan and Libya — needs country leadership teams.",
                "https://techcrunch.com","TechCrunch","2026-01-15",0.75)],
            signal_summary="🌍 Expanding into 5 new markets — needs Country GMs + Regional VP Operations. VP Ops role posted last week.",
            fit_score=79, fit_reasons=["Multi-market MENA operations","Uber-backed scale gives stability","Regional expansion mandate — high visibility role"],
            red_flags=["Subsidiary of Uber — some political complexity"],
            suggested_role="VP Operations MENA / Country GM",
            suggested_action="Apply directly via Careem careers — role posted. Also reach out to hiring manager to signal intent",
            contact_name="", contact_title="",
            apply_url="https://careem.com/careers", is_posted=True, posted_title="VP Operations — MENA Expansion",
            salary_estimate="AED 620K–880K", urgency="medium",
        ),
        OpportunityCard(
            id="demo_4", company="Tamara", company_type="scale-up", location="Riyadh, KSA", sector="Fintech",
            signals=[sig("Tamara","funding","Tamara closes $340M Series C to fuel Saudi BNPL growth",
                "Saudi-based BNPL player Tamara raises $340M Series C to expand merchant network and team.",
                "https://zawya.com","Zawya","2025-12-20",0.60)],
            signal_summary="💰 $340M Series C 3 months ago — building out senior team for Saudi Vision 2030 aligned growth. CFO and COO searches underway.",
            fit_score=74, fit_reasons=["KSA fintech in your target region","Vision 2030 alignment = government support","Competitive comp + equity at this stage"],
            red_flags=["KSA-based = relocation required","Competitive market vs Tabby"],
            suggested_role="CFO / COO",
            suggested_action="Connect with Tarek Elhousseiny (CEO) — he's active on LinkedIn. Mention specific experience with BNPL unit economics",
            contact_name="Tarek Elhousseiny", contact_title="CEO",
            apply_url="https://linkedin.com/company/tamara", is_posted=False, posted_title="",
            salary_estimate="SAR 650K–950K + equity", urgency="medium",
        ),
        OpportunityCard(
            id="demo_5", company="Pure Harvest", company_type="startup", location="Abu Dhabi, UAE", sector="AgriTech",
            signals=[sig("Pure Harvest","leadership","Pure Harvest appoints new CEO, CFO search underway",
                "AgriTech company Pure Harvest brings in new CEO Sky Kurtz returns, now seeking CFO and CCO.",
                "https://thenationalnews.com","The National","2026-02-01",0.82)],
            signal_summary="👤 New CEO appointed last month, CFO + CCO searches active — full leadership rebuild underway",
            fit_score=62, fit_reasons=["Leadership rebuild = multiple openings","UAE-based, Mubadala-backed","Board-level visibility"],
            red_flags=["Earlier financial difficulties 2022-23","Niche sector — AgriTech learning curve","Smaller scale than your typical targets"],
            suggested_role="CFO / Chief Commercial Officer",
            suggested_action="Connect directly with new CEO Sky Kurtz — fresh start, explicitly open to senior introductions",
            contact_name="Sky Kurtz", contact_title="CEO",
            apply_url="https://linkedin.com/company/pure-harvest-smart-farms", is_posted=False, posted_title="",
            salary_estimate="AED 400K–580K", urgency="medium",
        ),
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Serialisation
# ─────────────────────────────────────────────────────────────────────────────

def _card_to_dict(card: OpportunityCard) -> dict:
    signal_types = list({s.signal_type for s in card.signals})
    sources = [{"url": s.source_url, "name": s.source_name, "date": s.published_date, "headline": s.headline} for s in card.signals[:5]]

    badge_map = {
        "funding":   {"label": "💰 Funding",          "color": "#059669", "bg": "#f0fdf4"},
        "leadership":{"label": "👤 Leadership change", "color": "#7c3aed", "bg": "#f5f3ff"},
        "expansion": {"label": "🌍 Expansion",         "color": "#2563eb", "bg": "#eff6ff"},
        "velocity":  {"label": "📈 Hiring now",        "color": "#0891b2", "bg": "#ecfeff"},
        "distress":  {"label": "⚠️ Restructuring",    "color": "#dc2626", "bg": "#fef2f2"},
    }
    urgency_map = {"high": "#dc2626", "medium": "#d97706", "low": "#6b7280"}
    company_type_map = {
        "startup":"Startup","scale-up":"Scale-up","corporate":"Corporate",
        "pe":"PE-backed","family-office":"Family Office","government":"Government",
    }

    return {
        "id": card.id,
        "company": card.company,
        "company_type": card.company_type,
        "company_type_label": company_type_map.get(card.company_type, card.company_type),
        "location": card.location,
        "sector": card.sector,
        "signal_summary": card.signal_summary,
        "signal_types": signal_types,
        "signal_badges": [badge_map.get(t, {"label": t, "color": "#555", "bg": "#f5f5f5"}) for t in signal_types],
        "signal_sources": sources,
        "signals": [
            {"signal_type": s.signal_type, "headline": s.headline, "detail": s.detail,
             "source_url": s.source_url, "source_name": s.source_name, "published_date": s.published_date}
            for s in card.signals[:5]
        ],
        "fit_score": card.fit_score,
        "fit_reasons": card.fit_reasons,
        "red_flags": card.red_flags,
        "suggested_role": card.suggested_role,
        "suggested_action": card.suggested_action,
        "contact_name": card.contact_name,
        "contact_title": card.contact_title,
        "apply_url": card.apply_url,
        "is_posted": card.is_posted,
        "posted_title": card.posted_title,
        "salary_estimate": card.salary_estimate,
        "urgency": card.urgency,
        "urgency_color": urgency_map.get(card.urgency, "#6b7280"),
        "timeline": card.timeline,
        "competition_level": card.competition_level,
        "outreach_hook": card.outreach_hook,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Mock data (Serper bypass)
# ─────────────────────────────────────────────────────────────────────────────

def _mock_signal_results(preferences: dict, user_profile: dict) -> dict:
    """
    Return rich, realistic mock signal results so the Scout UI works end-to-end
    without Serper API credits. Remove this bypass once credits are restored.
    """
    def _sig(company, stype, headline, detail, url, src, date, rec):
        return Signal(
            company=company, signal_type=stype, headline=headline, detail=detail,
            source_url=url, source_name=src, published_date=date,
            recency_score=rec, raw_snippet=detail,
        )

    target_roles = preferences.get("roles", ["COO", "VP Operations"])
    primary_role = target_roles[0] if target_roles else "COO"

    cards = [
        # 1. Fintech Series C (Tabby-like)
        OpportunityCard(
            id="mock_01", company="PayTal", company_type="scale-up",
            location="Dubai, UAE", sector="Fintech / BNPL",
            signals=[
                _sig("PayTal", "funding",
                     "PayTal closes $180M Series C led by Mubadala and Sequoia Capital",
                     "Dubai-based BNPL fintech PayTal has closed a $180M Series C round to scale its merchant network across GCC and enter Egypt and Turkey. The company plans to double headcount from 350 to 700 by end of 2026.",
                     "https://magnitt.com/news/paytal-series-c", "MAGNiTT", "2026-02-28", 0.95),
                _sig("PayTal", "velocity",
                     "PayTal posts 12 senior roles including VP Operations and Head of Risk",
                     "Job board analysis shows PayTal has listed 12 senior positions in the last 3 weeks, including VP Operations, Head of Risk, and Director of Merchant Partnerships.",
                     "https://linkedin.com/company/paytal/jobs", "LinkedIn", "2026-03-10", 0.98),
            ],
            signal_summary="Raised $180M Series C 3 weeks ago — doubling headcount to 700. VP Operations and Head of Risk actively posted. No COO publicly listed.",
            fit_score=93,
            fit_reasons=["BNPL fintech in core target sector with massive growth runway", "Series C stage needs structured ops leadership — your sweet spot", "VP Ops role posted but COO-level mandate implied by scale"],
            red_flags=[],
            suggested_role="COO / VP Operations",
            suggested_action="Apply to VP Operations listing immediately, then message CEO Khalid Al-Mansoori referencing the Series C and your BNPL scaling experience",
            contact_name="Khalid Al-Mansoori", contact_title="CEO & Co-founder",
            apply_url="https://linkedin.com/company/paytal/jobs", is_posted=True,
            posted_title="VP Operations — GCC", salary_estimate="AED 780,000 - 1,100,000 + equity",
            urgency="high", timeline="immediate", competition_level="medium",
            outreach_hook="Khalid — congratulations on the Series C. Scaling from 350 to 700 people is an operational challenge I've navigated before at [Company]. Would love 15 minutes to share what worked and what didn't.",
        ),
        # 2. COO departure (leadership signal)
        OpportunityCard(
            id="mock_02", company="Deliveroo ME", company_type="corporate",
            location="Dubai, UAE", sector="Food Tech / Logistics",
            signals=[
                _sig("Deliveroo ME", "leadership",
                     "Deliveroo Middle East COO Rania El-Khatib departs after 4-year tenure",
                     "Deliveroo's MENA COO has stepped down to pursue a founder role. The company has not announced a replacement and sources indicate the board is conducting a discreet search.",
                     "https://arabianbusiness.com/deliveroo-coo-departs", "Arabian Business", "2026-03-05", 0.92),
                _sig("Deliveroo ME", "expansion",
                     "Deliveroo expands dark kitchen network across Saudi Arabia",
                     "Deliveroo is rolling out 40 new dark kitchens across Riyadh, Jeddah, and Dammam as it bets on Saudi Vision 2030 dining culture shift.",
                     "https://gulfnews.com/deliveroo-saudi-expansion", "Gulf News", "2026-02-18", 0.88),
            ],
            signal_summary="COO departed 13 days ago — role not yet posted. Simultaneously expanding dark kitchen network into KSA (40 new locations). Board running discreet replacement search.",
            fit_score=89,
            fit_reasons=["COO seat open at a business you understand — logistics + marketplace ops", "KSA expansion needs someone who can build from scratch", "Board-level reporting with P&L ownership"],
            red_flags=["Previous COO lasted 4 years which is positive, but role demands are intense", "Deliveroo global has had profitability pressure"],
            suggested_role="COO — Middle East",
            suggested_action="Reach out to Anis Harb (GM, Deliveroo MENA) before they engage Spencer Stuart — discreet window is 2-4 weeks",
            contact_name="Anis Harb", contact_title="General Manager, MENA",
            apply_url="https://linkedin.com/company/deliveroo", is_posted=False,
            posted_title="", salary_estimate="AED 900,000 - 1,350,000",
            urgency="high", timeline="immediate", competition_level="high",
            outreach_hook="Anis — I saw the news about Rania's move. The KSA dark kitchen rollout is exactly the kind of operational scaling challenge I've led before. Happy to share some playbook lessons over coffee.",
        ),
        # 3. Multinational entering UAE (expansion)
        OpportunityCard(
            id="mock_03", company="Stripe", company_type="corporate",
            location="Dubai, UAE", sector="Payments / Fintech",
            signals=[
                _sig("Stripe", "expansion",
                     "Stripe secures DIFC license to launch payment processing in UAE and Saudi Arabia",
                     "US payments giant Stripe has received its DIFC regulatory license and plans to go live in Q2 2026 with a full UAE team. The company is building a 50-person Dubai office.",
                     "https://techcrunch.com/stripe-uae-launch", "TechCrunch", "2026-02-20", 0.90),
                _sig("Stripe", "velocity",
                     "Stripe hiring Head of MENA, Country Manager UAE, and 8 senior roles in Dubai",
                     "Stripe's careers page now lists Head of MENA Operations, Country Manager UAE, Head of Partnerships, and senior engineering roles based in Dubai DIFC.",
                     "https://stripe.com/jobs?location=dubai", "Stripe Careers", "2026-03-01", 0.93),
            ],
            signal_summary="Stripe secured DIFC license — launching UAE/KSA operations Q2 2026. Building 50-person office. Head of MENA Ops and Country Manager roles live.",
            fit_score=86,
            fit_reasons=["Greenfield MENA operations build — rare opportunity to shape from scratch", "Stripe brand + compensation package among best in tech", "Your payments/fintech background directly relevant"],
            red_flags=["Stripe culture is very US-centric — MENA leadership may have limited autonomy initially"],
            suggested_role="Head of MENA Operations / Country Manager UAE",
            suggested_action="Apply via Stripe careers page AND message Dhivya Suryadevara (CFO) or Will Gaybrick (CPO) on LinkedIn — they are overseeing MENA launch",
            contact_name="Will Gaybrick", contact_title="Chief Product Officer",
            apply_url="https://stripe.com/jobs?location=dubai", is_posted=True,
            posted_title="Head of MENA Operations", salary_estimate="AED 850,000 - 1,200,000 + RSUs",
            urgency="high", timeline="immediate", competition_level="high",
            outreach_hook="Will — excited to see Stripe's DIFC launch. I've built payment ops across MENA from zero and know the regulatory landscape intimately. Would love to share notes on what trips up most fintechs entering the region.",
        ),
        # 4. Hiring spike (velocity)
        OpportunityCard(
            id="mock_04", company="Careem", company_type="corporate",
            location="Dubai, UAE", sector="Super App / Mobility",
            signals=[
                _sig("Careem", "velocity",
                     "Careem posts 15 senior roles in 2 weeks signalling major hiring push",
                     "Careem has posted 15 senior roles across its fintech, delivery, and mobility verticals in the past two weeks, including Director of Operations, VP Product, and Head of Careem Pay.",
                     "https://linkedin.com/company/careem/jobs", "LinkedIn", "2026-03-12", 0.97),
                _sig("Careem", "expansion",
                     "Careem super-app expands financial services with lending and insurance products",
                     "Careem is launching micro-lending and insurance products within its super-app, requiring a full financial services operations team build-out.",
                     "https://wamda.com/careem-finserv-expansion", "Wamda", "2026-02-25", 0.88),
                _sig("Careem", "funding",
                     "Uber allocates $100M for Careem's financial services vertical",
                     "Uber has earmarked $100M in growth capital for Careem's financial services expansion, per sources familiar with the matter.",
                     "https://bloomberg.com/careem-finserv-funding", "Bloomberg", "2026-03-01", 0.92),
            ],
            signal_summary="15 senior roles posted in 2 weeks. Uber injecting $100M into Careem's finserv vertical. Needs Director of Ops, VP Product, Head of Careem Pay.",
            fit_score=82,
            fit_reasons=["Multiple senior ops roles open — high chance of fit at Director+ level", "Financial services buildout needs operational expertise", "Uber backing provides stability and global resources"],
            red_flags=["Uber subsidiary politics — some decisions made in San Francisco", "Careem has had waves of hiring followed by restructuring"],
            suggested_role="Director of Operations / VP Financial Services Ops",
            suggested_action="Apply to Director of Operations role on LinkedIn. Reach out to Mudassir Sheikha (CEO) — he responds to well-crafted messages",
            contact_name="Mudassir Sheikha", contact_title="CEO & Co-founder",
            apply_url="https://linkedin.com/company/careem/jobs", is_posted=True,
            posted_title="Director of Operations — Financial Services",
            salary_estimate="AED 650,000 - 900,000", urgency="high",
            timeline="immediate", competition_level="medium",
            outreach_hook="Mudassir — the finserv buildout looks like a pivotal moment for Careem. I've scaled financial operations from launch to profitability and would love to share what I've learned about embedded lending in emerging markets.",
        ),
        # 5. PE-backed restructuring
        OpportunityCard(
            id="mock_05", company="Al Rostamani Group", company_type="pe",
            location="Dubai, UAE", sector="Diversified / Industrial",
            signals=[
                _sig("Al Rostamani Group", "leadership",
                     "Al Rostamani Group hires McKinsey for operational transformation programme",
                     "One of the UAE's largest family conglomerates, Al Rostamani Group, has engaged McKinsey for a 12-month operational transformation. Sources indicate the group is seeking a Group COO for the first time.",
                     "https://zawya.com/al-rostamani-transformation", "Zawya", "2026-02-15", 0.87),
                _sig("Al Rostamani Group", "leadership",
                     "Al Rostamani Group CFO transitions to advisory role as group modernises governance",
                     "The group's long-serving CFO is moving to an advisory position, creating an opening for a new CFO with PE-style financial rigour.",
                     "https://thenationalnews.com/al-rostamani-cfo", "The National", "2026-03-02", 0.91),
            ],
            signal_summary="McKinsey-led transformation underway. Creating Group COO role for first time. CFO transitioning to advisory — both C-suite seats open.",
            fit_score=78,
            fit_reasons=["Newly created COO role with transformation mandate", "Family group modernisation = high-impact, board-visible role", "Dubai-based with diversified portfolio across automotive, property, retail"],
            red_flags=["Family conglomerate dynamics — founder influence remains strong", "Transformation programmes can stall if family members resist change"],
            suggested_role="Group COO",
            suggested_action="Approach via McKinsey engagement partner — they will be advising on the hire. Also connect with Nabil Al Rostamani (Vice Chairman) on LinkedIn",
            contact_name="Nabil Al Rostamani", contact_title="Vice Chairman",
            apply_url="https://linkedin.com/company/al-rostamani-group", is_posted=False,
            posted_title="", salary_estimate="AED 1,000,000 - 1,600,000",
            urgency="medium", timeline="1-3 months", competition_level="low",
            outreach_hook="Nabil — I understand the group is investing in operational transformation. I've led similar programmes in diversified businesses and would welcome the chance to share perspectives on what drives lasting change in family-owned groups.",
        ),
        # 6. Saudi Vision 2030 company
        OpportunityCard(
            id="mock_06", company="NEOM", company_type="government",
            location="Tabuk, Saudi Arabia", sector="Smart City / Mega Projects",
            signals=[
                _sig("NEOM", "expansion",
                     "NEOM accelerates Phase 2 hiring — 200 leadership roles open for THE LINE operations",
                     "NEOM has announced Phase 2 hiring for THE LINE, seeking 200+ leadership and operations professionals to manage residential, commercial, and logistics verticals.",
                     "https://neom.com/careers", "NEOM Careers", "2026-03-08", 0.94),
                _sig("NEOM", "funding",
                     "Saudi PIF commits additional $50B to NEOM through 2030",
                     "The Public Investment Fund has confirmed an additional $50 billion allocation to NEOM, ensuring the project's operational phase is fully funded through 2030.",
                     "https://reuters.com/neom-pif-funding", "Reuters", "2026-02-10", 0.88),
            ],
            signal_summary="Phase 2 hiring: 200 leadership roles for THE LINE operations. PIF committed additional $50B. VP Operations and Sector Directors actively sought.",
            fit_score=72,
            fit_reasons=["Massive operational build — VP/Director Operations roles abundant", "Vision 2030 flagship = career-defining opportunity", "Compensation packages are among highest in region"],
            red_flags=["Remote location (Tabuk) — quality of life trade-off", "Government mega-project bureaucracy and shifting timelines"],
            suggested_role="VP Operations — THE LINE (Residential Sector)",
            suggested_action="Apply via NEOM careers portal. Also reach out to Joseph Bradley (Chief Digital Officer) who oversees smart operations hiring",
            contact_name="Joseph Bradley", contact_title="Chief Digital Officer",
            apply_url="https://neom.com/careers", is_posted=True,
            posted_title="VP Operations — THE LINE", salary_estimate="SAR 1,200,000 - 1,800,000 (tax-free)",
            urgency="medium", timeline="1-3 months", competition_level="medium",
            outreach_hook="Joseph — THE LINE Phase 2 is one of the most ambitious operational challenges on the planet. I've built and scaled operations in emerging environments and would love to discuss how my experience could support the next chapter.",
        ),
        # 7. Startup acquired
        OpportunityCard(
            id="mock_07", company="Fetchr", company_type="scale-up",
            location="Dubai, UAE", sector="Logistics / Last-Mile Delivery",
            signals=[
                _sig("Fetchr", "funding",
                     "Fetchr acquired by Aramex in $120M deal to bolster last-mile capabilities",
                     "Aramex has acquired Dubai-based logistics startup Fetchr for $120M, planning to integrate Fetchr's AI-driven routing with Aramex's regional network. Integration team being assembled.",
                     "https://bloomberg.com/fetchr-aramex-acquisition", "Bloomberg", "2026-03-01", 0.92),
                _sig("Fetchr", "leadership",
                     "Fetchr CEO to step down post-acquisition — integration COO role created",
                     "Fetchr's founder CEO will transition out within 6 months. Aramex is creating a dedicated Integration COO position to lead the Fetchr-Aramex operational merger.",
                     "https://arabianbusiness.com/fetchr-ceo-transition", "Arabian Business", "2026-03-08", 0.95),
            ],
            signal_summary="Acquired by Aramex for $120M. CEO stepping down — new Integration COO role created to lead merger of operations. 6-month transition window.",
            fit_score=76,
            fit_reasons=["Post-acquisition integration = high-value, time-bound COO mandate", "Logistics sector with tech overlay matches operational background", "Aramex backing provides scale and resources"],
            red_flags=["Integration roles can be short-lived (12-18 months)", "Cultural clash between startup and corporate likely"],
            suggested_role="Integration COO",
            suggested_action="Connect with Bashar Kalash (Aramex VP Strategy) who is leading the integration planning. Position yourself as someone who has done post-M&A operational integration before",
            contact_name="Bashar Kalash", contact_title="VP Corporate Strategy, Aramex",
            apply_url="https://linkedin.com/company/aramex", is_posted=False,
            posted_title="", salary_estimate="AED 700,000 - 950,000",
            urgency="high", timeline="immediate", competition_level="low",
            outreach_hook="Bashar — post-acquisition integration is where operational leaders earn their stripes. I've led two tech-to-corporate integrations and know how to preserve startup speed while building enterprise rigour. Would love to compare notes.",
        ),
        # 8. E-commerce scaling
        OpportunityCard(
            id="mock_08", company="Mumzworld", company_type="scale-up",
            location="Dubai, UAE", sector="E-commerce / Mother & Child",
            signals=[
                _sig("Mumzworld", "expansion",
                     "Mumzworld launches same-day delivery and expands to Egypt and KSA",
                     "MENA's leading mother-and-child e-commerce platform Mumzworld is launching same-day delivery in UAE and expanding fulfilment to Egypt and Saudi Arabia.",
                     "https://wamda.com/mumzworld-expansion", "Wamda", "2026-02-22", 0.89),
                _sig("Mumzworld", "velocity",
                     "Mumzworld hiring Director of Logistics and Head of Supply Chain",
                     "Mumzworld has posted Director of Logistics, Head of Supply Chain, and Senior Operations Manager roles as it scales fulfilment across three markets.",
                     "https://linkedin.com/company/mumzworld/jobs", "LinkedIn", "2026-03-05", 0.93),
            ],
            signal_summary="Expanding to Egypt and KSA with same-day delivery. Director of Logistics and Head of Supply Chain roles posted. Scaling fulfilment across 3 markets.",
            fit_score=68,
            fit_reasons=["Multi-market e-commerce scaling is operationally complex — your experience applies", "Same-day delivery build is a greenfield ops challenge", "Female-founded company with strong culture and mission"],
            red_flags=["Niche vertical (mother & child) — may feel limiting", "Scale is smaller than Noon/Amazon — AED 200M GMV range"],
            suggested_role="Director of Operations / Head of Supply Chain",
            suggested_action="Apply via LinkedIn for Director of Logistics. Reach out to Mona Ataya (CEO & Founder) — she is hands-on and responds to direct messages",
            contact_name="Mona Ataya", contact_title="CEO & Founder",
            apply_url="https://linkedin.com/company/mumzworld/jobs", is_posted=True,
            posted_title="Director of Logistics — MENA",
            salary_estimate="AED 480,000 - 650,000",
            urgency="medium", timeline="immediate", competition_level="low",
            outreach_hook="Mona — building same-day delivery across three markets simultaneously is no small feat. I've designed fulfilment networks across MENA and would love to share what I learned about last-mile economics in KSA and Egypt.",
        ),
        # 9. Saudi tech expansion
        OpportunityCard(
            id="mock_09", company="Salla", company_type="scale-up",
            location="Riyadh, Saudi Arabia", sector="E-commerce SaaS",
            signals=[
                _sig("Salla", "funding",
                     "Salla raises $130M Series B to become Saudi Arabia's Shopify",
                     "Saudi e-commerce enablement platform Salla has raised $130M Series B led by STV and Sanabil Investments, aiming to onboard 100,000 merchants by end of 2026.",
                     "https://magnitt.com/news/salla-series-b", "MAGNiTT", "2026-01-20", 0.80),
                _sig("Salla", "expansion",
                     "Salla enters UAE and Egypt markets with Arabic-first commerce platform",
                     "Salla is expanding beyond Saudi Arabia into UAE and Egypt, opening offices in Dubai and Cairo to serve Arabic-speaking SME merchants.",
                     "https://zawya.com/salla-expansion", "Zawya", "2026-02-28", 0.90),
            ],
            signal_summary="$130M Series B raised. Expanding to UAE and Egypt — opening Dubai and Cairo offices. Targeting 100K merchants by year-end. VP Ops and Country Managers needed.",
            fit_score=71,
            fit_reasons=["SaaS platform scaling across MENA — operationally demanding", "Dubai office opening means UAE-based role possible", "Vision 2030 aligned — Saudi government support"],
            red_flags=["Primary HQ in Riyadh — may require frequent travel", "Arabic-first product — language capability important"],
            suggested_role="VP Operations — International",
            suggested_action="Connect with Salman Al-Harbi (CEO) via LinkedIn. Mention your cross-border scaling experience specifically",
            contact_name="Salman Al-Harbi", contact_title="CEO & Co-founder",
            apply_url="https://linkedin.com/company/salla", is_posted=False,
            posted_title="", salary_estimate="AED 600,000 - 850,000 + equity",
            urgency="medium", timeline="1-3 months", competition_level="low",
            outreach_hook="Salman — congratulations on the Series B. Scaling a platform across three MENA markets simultaneously is a challenge I know well. Happy to share lessons from my experience building cross-border operations in the region.",
        ),
        # 10. Insurance tech
        OpportunityCard(
            id="mock_10", company="Aman Insurance (Aman Digital)", company_type="corporate",
            location="Abu Dhabi, UAE", sector="InsurTech",
            signals=[
                _sig("Aman Insurance (Aman Digital)", "expansion",
                     "Aman launches digital insurance subsidiary targeting SME market",
                     "UAE insurer Aman has spun out a digital subsidiary, Aman Digital, to serve the underinsured SME segment with embedded and parametric insurance products. Backed by AED 200M from parent.",
                     "https://thenationalnews.com/aman-digital-launch", "The National", "2026-03-10", 0.96),
            ],
            signal_summary="New digital subsidiary launched with AED 200M backing. Building full team from scratch for embedded SME insurance. COO and CTO searches active.",
            fit_score=64,
            fit_reasons=["Greenfield digital subsidiary = startup pace with corporate funding", "InsurTech is adjacent to fintech — transferable skills", "Abu Dhabi-based — strong regulatory support from ADGM"],
            red_flags=["Insurance sector may require domain-specific regulatory knowledge", "Corporate parent may impose bureaucratic constraints"],
            suggested_role="COO — Aman Digital",
            suggested_action="Reach out to the parent company CEO or Head of Strategy — the subsidiary is too new to have its own leadership listed publicly",
            contact_name="", contact_title="",
            apply_url="https://linkedin.com/company/aman-insurance", is_posted=False,
            posted_title="", salary_estimate="AED 550,000 - 800,000",
            urgency="medium", timeline="1-3 months", competition_level="low",
            outreach_hook="I noticed Aman's digital subsidiary launch — building embedded insurance for SMEs from scratch is a fascinating operational challenge. I've built digital-first operations within traditional industries and would love to discuss how I could contribute.",
        ),
    ]

    # Collect all signals from cards for the count
    all_signals = []
    for card in cards:
        all_signals.extend(card.signals)

    # Live openings — mix of current, imminent, and strategic
    openings = [
        {"title": "VP Operations — GCC", "company": "PayTal", "snippet": "Lead operations scaling across GCC markets post-Series C. P&L ownership for 6 country operations.", "url": "https://linkedin.com/jobs/paytal-vp-ops", "source": "LinkedIn", "date": "2026-03-10", "recency": 0.97, "is_posted": True, "status": "current"},
        {"title": "Head of MENA Operations", "company": "Stripe", "snippet": "Build and lead Stripe's MENA operations from the ground up. Dubai DIFC based.", "url": "https://stripe.com/jobs/mena-ops", "source": "Stripe Careers", "date": "2026-03-01", "recency": 0.93, "is_posted": True, "status": "current"},
        {"title": "Director of Operations — Financial Services", "company": "Careem", "snippet": "Lead operations for Careem's new financial services vertical including lending and insurance.", "url": "https://linkedin.com/jobs/careem-dir-ops", "source": "LinkedIn", "date": "2026-03-12", "recency": 0.97, "is_posted": True, "status": "current"},
        {"title": "VP Operations — THE LINE (Residential)", "company": "NEOM", "snippet": "Oversee residential sector operations for THE LINE, managing 2,000+ unit delivery pipeline.", "url": "https://neom.com/careers/vp-ops-theline", "source": "NEOM Careers", "date": "2026-03-08", "recency": 0.94, "is_posted": True, "status": "current"},
        {"title": "Director of Logistics — MENA", "company": "Mumzworld", "snippet": "Build same-day delivery capability across UAE, KSA, and Egypt.", "url": "https://linkedin.com/jobs/mumzworld-logistics", "source": "LinkedIn", "date": "2026-03-05", "recency": 0.93, "is_posted": True, "status": "current"},
        {"title": "Country Manager UAE", "company": "Stripe", "snippet": "Lead Stripe's UAE market entry including regulatory, partnerships, and go-to-market.", "url": "https://stripe.com/jobs/country-manager-uae", "source": "Stripe Careers", "date": "2026-03-01", "recency": 0.93, "is_posted": True, "status": "current"},
        {"title": "COO — Middle East", "company": "Deliveroo ME", "snippet": "Replacement for departed COO. Board-level report. Oversee all MENA operations.", "url": "https://linkedin.com/company/deliveroo", "source": "LinkedIn (expected)", "date": "2026-03-05", "recency": 0.90, "is_posted": False, "status": "imminent"},
        {"title": "Group COO", "company": "Al Rostamani Group", "snippet": "Newly created role — lead McKinsey-backed operational transformation across diversified group.", "url": "https://linkedin.com/company/al-rostamani-group", "source": "Executive Search", "date": "2026-02-15", "recency": 0.85, "is_posted": False, "status": "imminent"},
        {"title": "Integration COO", "company": "Fetchr / Aramex", "snippet": "Lead post-acquisition integration of Fetchr into Aramex's logistics network.", "url": "https://linkedin.com/company/aramex", "source": "Industry Source", "date": "2026-03-08", "recency": 0.94, "is_posted": False, "status": "imminent"},
        {"title": "COO — Aman Digital", "company": "Aman Digital", "snippet": "Build operations from scratch for new InsurTech subsidiary backed by AED 200M.", "url": "https://linkedin.com/company/aman-insurance", "source": "Industry Source", "date": "2026-03-10", "recency": 0.90, "is_posted": False, "status": "imminent"},
        {"title": "VP Operations — International", "company": "Salla", "snippet": "Lead expansion operations for Saudi e-commerce SaaS platform entering UAE and Egypt.", "url": "https://linkedin.com/company/salla", "source": "Salla Careers", "date": "2026-02-28", "recency": 0.88, "is_posted": False, "status": "imminent"},
        {"title": "Head of Supply Chain — MENA", "company": "Mumzworld", "snippet": "Design and build fulfilment network across three MENA markets.", "url": "https://linkedin.com/jobs/mumzworld-supply-chain", "source": "LinkedIn", "date": "2026-03-05", "recency": 0.93, "is_posted": True, "status": "current"},
        {"title": "CFO — Group", "company": "Al Rostamani Group", "snippet": "Replace outgoing CFO as part of governance modernisation. PE-style financial rigour required.", "url": "https://linkedin.com/company/al-rostamani-group", "source": "Executive Search", "date": "2026-03-02", "recency": 0.88, "is_posted": False, "status": "strategic"},
        {"title": "Head of Careem Pay Operations", "company": "Careem", "snippet": "Lead operations for Careem's mobile payments and wallet product across MENA.", "url": "https://linkedin.com/jobs/careem-pay-ops", "source": "LinkedIn", "date": "2026-03-12", "recency": 0.97, "is_posted": True, "status": "current"},
        {"title": "VP Product — Super App", "company": "Careem", "snippet": "Lead product strategy for Careem's super-app platform across mobility, delivery, and finserv.", "url": "https://linkedin.com/jobs/careem-vp-product", "source": "LinkedIn", "date": "2026-03-12", "recency": 0.97, "is_posted": True, "status": "current"},
        {"title": "Director of Partnerships — MENA", "company": "Stripe", "snippet": "Build Stripe's merchant and banking partnerships across UAE, KSA, and Egypt.", "url": "https://stripe.com/jobs/partnerships-mena", "source": "Stripe Careers", "date": "2026-03-01", "recency": 0.93, "is_posted": True, "status": "current"},
        {"title": "Head of Risk", "company": "PayTal", "snippet": "Build risk management function for BNPL platform scaling across 6 GCC markets.", "url": "https://linkedin.com/jobs/paytal-risk", "source": "LinkedIn", "date": "2026-03-10", "recency": 0.97, "is_posted": True, "status": "current"},
        {"title": "CFO", "company": "Salla", "snippet": "First external CFO hire for Saudi e-commerce SaaS post Series B.", "url": "https://linkedin.com/company/salla", "source": "Industry Source", "date": "2026-01-20", "recency": 0.78, "is_posted": False, "status": "strategic"},
    ]

    return {
        "opportunities": [_card_to_dict(card) for card in cards],
        "live_openings": openings,
        "signals_detected": len(all_signals),
        "sources_searched": 45,
        "is_demo": True,
        "engine_version": "3.0-mock",
        "scored_by": "mock",
    }


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
            "opportunities": [_card_to_dict(c) for c in _demo_opportunities()],
            "signals_detected": 0, "sources_searched": 0,
            "is_demo": True, "engine_version": "2.0", "scored_by": "demo",
        }

    # Gate mock data behind demo_mode config — don't bypass real detection
    if settings.demo_mode:
        logger.info("signal_engine_demo_mode")
        return _mock_signal_results(preferences, user_profile)

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
