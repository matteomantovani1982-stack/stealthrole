"""
app/api/routes/scout.py — StealthRole Signal Intelligence API

GET   /api/v1/scout/signals       — main engine: ranked opportunity cards from signals
GET   /api/v1/scout/history       — last 10 scout results for trend tracking
GET   /api/v1/scout/jobs          — legacy job search (Adzuna/JSearch/Serper)
GET   /api/v1/scout/config        — which sources are active
POST  /api/v1/scout/jobs/save     — save a job
GET   /api/v1/scout/jobs/saved    — list saved jobs
DEL   /api/v1/scout/jobs/saved/id — unsave a job
PATCH /api/v1/scout/hidden-market/{id}/dismiss — toggle dismiss on a hidden signal
"""
import hashlib
import re
import uuid as _uuid
from datetime import UTC, datetime, timedelta

import httpx
import structlog
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, update, delete

from app.config import settings
from app.dependencies import CurrentUserId, DB
from app.models.hidden_signal import HiddenSignal
from app.models.saved_job import SavedJob
from app.models.scout_result import ScoutResult

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/scout", tags=["Scout"])
TIMEOUT = 12.0
CACHE_TTL_MINUTES = 30


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_profile_and_prefs(db: DB, user_id: str) -> tuple[dict, dict]:
    """Load user profile + preferences."""
    import json
    from app.services.profile.profile_service import ProfileService
    svc = ProfileService(db)
    profile = await svc.get_active_profile(user_id)
    if not profile:
        return {}, {}

    # Preferences are stored on the profile.preferences JSONB field
    prefs = profile.preferences or {}
    if isinstance(prefs, str):
        try:
            prefs = json.loads(prefs)
        except Exception:
            prefs = {}

    # Fallback: check global_context for legacy preference storage
    if not prefs:
        try:
            ctx = json.loads(profile.global_context or "{}")
            prefs = ctx.get("preferences", ctx.get("__preferences", {}))
        except Exception:
            pass

    profile_dict = {
        "headline": profile.headline or "",
        "global_context": profile.global_context or "",
    }
    return profile_dict, prefs


# ── Signal Intelligence endpoint ──────────────────────────────────────────────

@router.get("/signals")
async def get_signals(
    current_user_id: CurrentUserId,
    db: DB,
    region: str = Query(default=""),
    sectors: str = Query(default=""),   # comma-separated
    roles: str = Query(default=""),     # comma-separated
) -> dict:
    """
    Main StealthRole intelligence endpoint.
    Runs the signal engine: detects market signals, scores fit with Claude,
    returns ranked OpportunityCards.
    Runs in a thread pool to avoid blocking the async event loop.
    """
    import asyncio
    from functools import partial
    from app.services.scout.signal_engine import run_signal_engine

    profile_dict, prefs = await _get_profile_and_prefs(db, current_user_id)

    # Override prefs with explicit query params if provided
    if region:
        prefs["regions"] = [region]
    if sectors:
        prefs["sectors"] = sectors.split(",")
    if roles:
        prefs["roles"] = roles.split(",")

    # Ensure sensible defaults
    if not prefs.get("regions"):
        prefs["regions"] = ["UAE"]

    # Derive roles from profile headline/seniority if not explicitly set
    if not prefs.get("roles"):
        level = prefs.get("level", [])
        # Keep it simple — max 3 short role keywords for clean Serper queries
        if any("C-Suite" in l for l in level):
            prefs["roles"] = ["CEO", "COO", "CFO"]
        elif any("VP" in l for l in level):
            prefs["roles"] = ["VP", "Director"]
        elif any("Director" in l for l in level):
            prefs["roles"] = ["Director", "Head of"]
        else:
            # Extract from headline
            headline = profile_dict.get("headline", "")
            if headline:
                prefs["roles"] = [headline.split("|")[0].strip()[:20]]
            else:
                prefs["roles"] = ["CEO", "COO", "Director"]

    if not prefs.get("sectors"):
        prefs["sectors"] = ["tech", "fintech", "ecommerce"]

    # Simplify region for search — use short name, not "Global / Remote"
    regions = prefs.get("regions", ["UAE"])
    clean_regions = []
    for r in regions:
        if "global" in r.lower() or "remote" in r.lower():
            clean_regions.append("MENA")
        else:
            clean_regions.append(r)
    prefs["regions"] = clean_regions

    # ── Check cache: return fresh result if < 30 min old ────────────────
    cache_cutoff = datetime.now(UTC) - timedelta(minutes=CACHE_TTL_MINUTES)
    cached_q = (
        select(ScoutResult)
        .where(
            ScoutResult.user_id == current_user_id,
            ScoutResult.is_stale == False,  # noqa: E712
            ScoutResult.created_at >= cache_cutoff,
        )
        .order_by(ScoutResult.created_at.desc())
        .limit(1)
    )
    cached_row = (await db.execute(cached_q)).scalar_one_or_none()
    if cached_row is not None:
        logger.info("scout_cache_hit", user_id=current_user_id, age_s=(datetime.now(UTC) - cached_row.created_at).seconds)
        # Detect if cached data is from mock/demo by checking scored_by
        is_demo = cached_row.scored_by in ("mock", "demo", "")
        return {
            "opportunities": cached_row.opportunities,
            "live_openings": cached_row.live_openings,
            "signals_detected": cached_row.signals_detected,
            "sources_searched": cached_row.sources_searched,
            "is_demo": is_demo,
            "engine_version": "3.0",
            "scored_by": cached_row.scored_by,
            "cached": True,
        }

    # ── Run synchronous signal engine in thread pool ────────────────────
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        partial(run_signal_engine, preferences=prefs, user_profile=profile_dict, max_results=20)
    )

    # ── Persist result & mark previous rows stale ───────────────────────
    try:
        await db.execute(
            update(ScoutResult)
            .where(ScoutResult.user_id == current_user_id, ScoutResult.is_stale == False)  # noqa: E712
            .values(is_stale=True)
        )
        new_row = ScoutResult(
            user_id=current_user_id,
            opportunities=result.get("opportunities", []),
            live_openings=result.get("live_openings", []),
            signals_detected=result.get("signals_detected", 0),
            sources_searched=result.get("sources_searched", 0),
            scored_by=result.get("scored_by", ""),
            regions=prefs.get("regions", []),
            roles=prefs.get("roles", []),
            sectors=prefs.get("sectors", []),
            is_stale=False,
        )
        db.add(new_row)
        await db.commit()
        logger.info("scout_result_saved", user_id=current_user_id, signals=result.get("signals_detected", 0))
    except Exception as e:
        logger.warning("scout_result_save_failed", error=str(e))
        await db.rollback()

    return result


# ── History endpoint ──────────────────────────────────────────────────────

@router.get("/history")
async def get_scout_history(
    current_user_id: CurrentUserId,
    db: DB,
    limit: int = Query(default=10, ge=1, le=50),
) -> dict:
    """Return the last N scout results for this user (for trend tracking)."""
    q = (
        select(ScoutResult)
        .where(ScoutResult.user_id == current_user_id)
        .order_by(ScoutResult.created_at.desc())
        .limit(limit)
    )
    rows = (await db.execute(q)).scalars().all()
    return {
        "history": [
            {
                "id": str(row.id),
                "created_at": row.created_at.isoformat(),
                "signals_detected": row.signals_detected,
                "sources_searched": row.sources_searched,
                "scored_by": row.scored_by,
                "regions": row.regions,
                "roles": row.roles,
                "sectors": row.sectors,
                "is_stale": row.is_stale,
                "opportunities_count": len(row.opportunities) if row.opportunities else 0,
                "live_openings_count": len(row.live_openings) if row.live_openings else 0,
            }
            for row in rows
        ],
        "total": len(rows),
    }


# ── Legacy job search endpoint ────────────────────────────────────────────────

REGION_TO_ADZUNA = {
    "UAE":("ae","Dubai"),"KSA":("sa","Riyadh"),"Qatar":("qa","Doha"),
    "Kuwait":("kw","Kuwait City"),"Bahrain":("bh","Manama"),"Oman":("om","Muscat"),
    "Egypt":("eg","Cairo"),"UK":("gb","London"),"EU":("de","Berlin"),
    "US":("us","New York"),"Canada":("ca","Toronto"),"Global":("gb","London"),
}
REGION_TO_JSEARCH = {
    "UAE":"Dubai, UAE","KSA":"Riyadh, Saudi Arabia","Qatar":"Doha, Qatar",
    "Kuwait":"Kuwait City, Kuwait","Bahrain":"Manama, Bahrain","Oman":"Muscat, Oman",
    "Egypt":"Cairo, Egypt","UK":"London, UK","EU":"Europe","US":"United States",
    "Canada":"Canada","Global":"",
}
SOURCE_COLORS = {
    "LinkedIn":"#0a66c2","Indeed":"#2164f3","Glassdoor":"#0caa41",
    "Bayt":"#e84b37","GulfTalent":"#1a4e8c","NaukriGulf":"#4a90d9",
    "Monster":"#6a0dad","Adzuna":"#d63384","Web":"#555",
}

def _adzuna(keywords: str, location: str) -> list[dict]:
    if not settings.adzuna_app_id or not settings.adzuna_app_key:
        return []
    rc, city = REGION_TO_ADZUNA.get(location, ("gb", location))
    try:
        r = httpx.get(f"https://api.adzuna.com/v1/api/jobs/{rc}/search/1",
            params={"app_id":settings.adzuna_app_id,"app_key":settings.adzuna_app_key,
                    "what":keywords,"where":city,"results_per_page":10,"content-type":"application/json"},
            timeout=TIMEOUT)
        r.raise_for_status()
        jobs = []
        for item in r.json().get("results",[]):
            sal_min = item.get("salary_min"); sal_max = item.get("salary_max")
            sal = f"${int(sal_min):,}–${int(sal_max):,}" if sal_min and sal_max else ""
            jobs.append({
                "id": hashlib.md5(item.get("redirect_url","").encode()).hexdigest(),
                "title": item.get("title","")[:120],
                "company": item.get("company",{}).get("display_name","")[:80],
                "location": item.get("location",{}).get("display_name","")[:80],
                "snippet": item.get("description","")[:400],
                "url": item.get("redirect_url",""),
                "source":"Adzuna","salary":sal,
                "posted_date": item.get("created","")[:10],
                "source_color": SOURCE_COLORS["Adzuna"],
            })
        return jobs
    except Exception as e:
        logger.warning("adzuna_failed", error=str(e))
        return []

def _jsearch(keywords: str, location: str) -> list[dict]:
    if not settings.jsearch_api_key:
        return []
    loc = REGION_TO_JSEARCH.get(location, location)
    try:
        r = httpx.get("https://jsearch.p.rapidapi.com/search",
            headers={"X-RapidAPI-Key":settings.jsearch_api_key,"X-RapidAPI-Host":"jsearch.p.rapidapi.com"},
            params={"query":f"{keywords} {loc}","page":"1","num_pages":"1","date_posted":"month"},
            timeout=TIMEOUT)
        r.raise_for_status()
        jobs = []
        for item in r.json().get("data",[]):
            link = item.get("job_apply_link","")
            src = "LinkedIn" if "linkedin" in link.lower() else "Glassdoor" if "glassdoor" in link.lower() else "Indeed"
            sal_min = item.get("job_min_salary"); sal_max = item.get("job_max_salary")
            sal = f"${int(sal_min):,}–${int(sal_max):,} {item.get('job_salary_period','')}" if sal_min and sal_max else ""
            jobs.append({
                "id": item.get("job_id", hashlib.md5(link.encode()).hexdigest()),
                "title": item.get("job_title","")[:120],
                "company": item.get("employer_name","")[:80],
                "location": ", ".join(p for p in [item.get("job_city",""),item.get("job_country","")] if p)[:80],
                "snippet": item.get("job_description","")[:400],
                "url": link or item.get("job_google_link",""),
                "source":src,"salary":sal,
                "posted_date": item.get("job_posted_at_datetime_utc","")[:10],
                "source_color": SOURCE_COLORS.get(src,"#555"),
                "is_remote": item.get("job_is_remote",False),
            })
        return jobs
    except Exception as e:
        logger.warning("jsearch_failed", error=str(e))
        return []

def _serper_jobs(keywords: str, location: str) -> list[dict]:
    if not settings.serper_api_key:
        return []
    import httpx as _httpx
    try:
        seen, jobs = set(), []
        for query in [
            f"{keywords} jobs {location} site:linkedin.com/jobs",
            f"{keywords} jobs {location} site:bayt.com OR site:gulftalent.com",
            f"{keywords} hiring {location} 2026",
        ]:
            r = _httpx.post("https://google.serper.dev/search",
                headers={"X-API-KEY":settings.serper_api_key,"Content-Type":"application/json"},
                json={"q":query,"num":5}, timeout=TIMEOUT)
            r.raise_for_status()
            for item in r.json().get("organic",[]):
                url = item.get("link","")
                if not url or url in seen: continue
                seen.add(url)
                title = item.get("title",""); company = ""
                for sep in [" at "," - "," | "," @ "]:
                    if sep in title:
                        parts = title.split(sep,1); title = parts[0].strip(); company = parts[1].strip(); break
                src = next((s for s,d in [("LinkedIn","linkedin"),("Bayt","bayt"),("GulfTalent","gulftalent"),
                    ("Glassdoor","glassdoor"),("Indeed","indeed"),("NaukriGulf","naukrigulf")] if d in url), "Web")
                jobs.append({"id":hashlib.md5(url.encode()).hexdigest(),"title":title[:120],
                    "company":company[:80],"location":location,"snippet":item.get("snippet","")[:400],
                    "url":url,"source":src,"salary":"","posted_date":"",
                    "source_color":SOURCE_COLORS.get(src,"#555")})
        return jobs
    except Exception as e:
        logger.warning("serper_jobs_failed", error=str(e))
        return []

def _demo_jobs() -> list[dict]:
    return [
        {"id":"d1","title":"COO","company":"Series B Tech Company","location":"Dubai, UAE","snippet":"","url":"https://linkedin.com/jobs","source":"LinkedIn","salary":"AED 600K–900K","posted_date":"2026-03-01","source_color":"#0a66c2","is_remote":False,"requirements":["P&L","C-suite","Series B","MENA","equity"]},
        {"id":"d2","title":"VP Commercial","company":"GCC SaaS Scale-up","location":"Riyadh, KSA","snippet":"","url":"https://bayt.com","source":"Bayt","salary":"SAR 500K–700K","posted_date":"2026-03-03","source_color":"#e84b37","is_remote":False,"requirements":["GTM","revenue","KSA","SaaS"]},
        {"id":"d3","title":"General Manager","company":"PE-backed Portfolio Co.","location":"Abu Dhabi, UAE","snippet":"","url":"https://gulftalent.com","source":"GulfTalent","salary":"AED 720K+","posted_date":"2026-02-28","source_color":"#1a4e8c","is_remote":False,"requirements":["P&L","PE","board","UAE"]},
    ]


@router.get("/jobs")
async def scout_jobs(
    current_user_id: CurrentUserId, db: DB,
    keywords: str = Query(default=""),
    location: str = Query(default=""),
) -> dict:
    profile_dict, prefs = await _get_profile_and_prefs(db, current_user_id)

    if not keywords:
        roles = prefs.get("roles",[])
        seniority = prefs.get("seniority",[])
        keywords = " ".join((roles[:2]+seniority[:1])) or "senior director manager"
    if not location:
        location = (prefs.get("regions") or ["UAE"])[0]

    seen, all_jobs = set(), []
    def add(jobs):
        for j in jobs:
            if j.get("id","") not in seen:
                seen.add(j["id"]); all_jobs.append(j)

    add(_adzuna(keywords, location))
    add(_jsearch(keywords, location))
    if len(all_jobs) < 8:
        add(_serper_jobs(keywords, location))
    if not all_jobs:
        all_jobs = _demo_jobs()
        return {"jobs":all_jobs,"total":len(all_jobs),"query":keywords,"location":location,"is_demo":True,"sources_used":["demo"]}

    sources_used = list({j["source"] for j in all_jobs})
    return {"jobs":all_jobs[:24],"total":len(all_jobs),"query":keywords,"location":location,"is_demo":False,"sources_used":sources_used}


# ── Hidden Market endpoint ────────────────────────────────────────────────────

@router.get("/hidden-market")
async def get_hidden_market(
    current_user_id: CurrentUserId,
    db: DB,
) -> dict:
    """
    Detect hidden market signals: companies likely hiring before jobs are posted.
    Sources: Adzuna employer surge detection + news-based classification.
    """
    from app.services.scout.hidden_market import HiddenMarketService

    svc = HiddenMarketService(db)
    signals = await svc.detect_signals(current_user_id)

    return {
        "signals": [
            {
                "id": str(sig.id),
                "company_name": sig.company_name,
                "signal_type": sig.signal_type,
                "confidence": sig.confidence,
                "likely_roles": sig.likely_roles,
                "reasoning": sig.reasoning,
                "source_url": sig.source_url,
                "source_name": sig.source_name,
                "is_dismissed": sig.is_dismissed,
                "created_at": sig.created_at.isoformat() if sig.created_at else None,
            }
            for sig in signals
        ],
        "total": len(signals),
    }


@router.patch("/hidden-market/{signal_id}/dismiss")
async def dismiss_hidden_signal(
    signal_id: _uuid.UUID,
    current_user_id: CurrentUserId,
    db: DB,
) -> dict:
    """Toggle dismiss state for a hidden market signal."""
    q = select(HiddenSignal).where(
        HiddenSignal.id == signal_id,
        HiddenSignal.user_id == current_user_id,
    )
    signal = (await db.execute(q)).scalar_one_or_none()
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found.")

    signal.is_dismissed = not signal.is_dismissed
    await db.flush()
    await db.commit()

    return {
        "id": str(signal.id),
        "is_dismissed": signal.is_dismissed,
    }


# ── Saved Jobs endpoints ──────────────────────────────────────────────────

class SaveJobRequest(BaseModel):
    source: str = Field(..., max_length=50)
    external_id: str = Field(..., max_length=255)
    title: str = Field(..., max_length=500)
    company: str = Field("", max_length=255)
    location: str = Field("", max_length=255)
    url: str = Field("", max_length=2000)
    salary_min: int | None = None
    salary_max: int | None = None
    metadata: dict = Field(default_factory=dict)


def _job_to_dict(job: SavedJob) -> dict:
    return {
        "id": str(job.id),
        "source": job.source,
        "external_id": job.external_id,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "salary_min": job.salary_min,
        "salary_max": job.salary_max,
        "url": job.url,
        "metadata": job.metadata_,
        "saved_at": job.saved_at.isoformat() if job.saved_at else None,
        "created_at": job.created_at.isoformat() if job.created_at else None,
    }


@router.post("/jobs/save", status_code=201)
async def save_job(
    body: SaveJobRequest,
    current_user_id: CurrentUserId,
    db: DB,
) -> dict:
    """Save a job from scout results."""
    # Check for duplicate
    q = select(SavedJob).where(
        SavedJob.user_id == current_user_id,
        SavedJob.source == body.source,
        SavedJob.external_id == body.external_id,
    )
    existing = (await db.execute(q)).scalar_one_or_none()
    if existing:
        return _job_to_dict(existing)

    job = SavedJob(
        user_id=current_user_id,
        source=body.source,
        external_id=body.external_id,
        title=body.title,
        company=body.company,
        location=body.location,
        url=body.url,
        salary_min=body.salary_min,
        salary_max=body.salary_max,
        metadata_=body.metadata,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return _job_to_dict(job)


@router.get("/jobs/saved")
async def list_saved_jobs(
    current_user_id: CurrentUserId,
    db: DB,
) -> dict:
    """List all saved jobs for the current user."""
    q = (
        select(SavedJob)
        .where(SavedJob.user_id == current_user_id)
        .order_by(SavedJob.saved_at.desc())
    )
    rows = (await db.execute(q)).scalars().all()
    return {
        "saved_jobs": [_job_to_dict(j) for j in rows],
        "total": len(rows),
    }


@router.delete("/jobs/saved/{saved_job_id}", status_code=200)
async def unsave_job(
    saved_job_id: _uuid.UUID,
    current_user_id: CurrentUserId,
    db: DB,
) -> dict:
    """Remove a saved job."""
    q = select(SavedJob).where(
        SavedJob.id == saved_job_id,
        SavedJob.user_id == current_user_id,
    )
    job = (await db.execute(q)).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Saved job not found.")
    await db.delete(job)
    await db.commit()
    return {"deleted": True, "id": str(saved_job_id)}


@router.get("/config")
async def scout_config(current_user_id: CurrentUserId) -> dict:
    return {
        "adzuna": bool(settings.adzuna_app_id and settings.adzuna_app_key),
        "jsearch": bool(settings.jsearch_api_key),
        "serper": bool(settings.serper_api_key),
        "claude": bool(settings.anthropic_api_key),
        "signal_engine": bool(settings.serper_api_key),
        "demo_mode": not any([settings.adzuna_app_id, settings.jsearch_api_key, settings.serper_api_key]),
        "predictor": bool(settings.serper_api_key),
    }


# ── Predictive Opportunity Engine ─────────────────────────────────────────────

@router.get(
    "/predictions",
    summary="Predict future hiring opportunities from news + financial signals",
    tags=["Scout"],
)
async def get_predictions(
    current_user_id: CurrentUserId,
    db: DB,
    limit: int = 20,
) -> dict:
    """
    Scans financial journals, regulatory filings, and industry reports
    to predict companies that WILL hire before they post the job.
    """
    from app.services.scout.opportunity_predictor import predict_opportunities
    from app.services.profile.profile_service import ProfileService

    # Load user preferences
    svc = ProfileService(db)
    profile = await svc.get_active_profile_orm(current_user_id)
    prefs = {}
    if profile and profile.preferences:
        prefs = profile.preferences
    elif profile and profile.global_context:
        import json
        try:
            ctx = json.loads(profile.global_context)
            prefs = {"sectors": ctx.get("sectors", []), "roles": ctx.get("roles", [])}
        except Exception:
            pass

    profile_dict = profile.to_prompt_dict() if profile else {}

    # Run predictor in thread pool (blocking IO)
    import asyncio
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        lambda: predict_opportunities(prefs, profile_dict, max_results=limit),
    )

    return result


# ── Current Vacancies (actual job listings from job boards) ──────────────────

@router.get("/vacancies", summary="Search job boards for current vacancies matching profile")
async def current_vacancies(
    db: DB,
    user_id: CurrentUserId,
    limit: int = Query(default=30, le=50),
) -> dict:
    """Search LinkedIn, Bayt, Indeed, Monster, GulfTalent for actual open positions."""
    profile, prefs = await _get_profile_and_prefs(db, user_id)
    roles = prefs.get("roles", ["CEO", "COO", "VP Operations"])
    sectors = prefs.get("sectors", ["Technology"])
    regions = prefs.get("regions", ["UAE"])

    if not settings.serper_api_key:
        return {"vacancies": [], "total": 0, "sources_searched": 0}

    role_str = " ".join(roles[:3])
    sector_str = " ".join(sectors[:2]) if sectors else ""
    region = regions[0] if regions else "UAE"

    # Search actual job boards — use specific job post URLs, not search pages
    queries = [
        f"site:linkedin.com/jobs/view {role_str} {region}",
        f"site:bayt.com/en/jobs {role_str} {region}",
        f"site:indeed.com/viewjob {role_str} {region}",
        f"site:gulftalent.com/jobs {role_str}",
        f"site:linkedin.com/jobs/view COO OR 'VP Operations' OR 'Head of Strategy' {region}",
        f"{role_str} hiring {region} {sector_str} 2026",
        f"'General Manager' OR 'Country Manager' OR 'Managing Director' hiring {region} {sector_str}",
        f"site:greenhouse.io OR site:lever.co {role_str} {region}",
    ]

    JOB_SOURCES = ["linkedin.com", "bayt.com", "indeed.com", "gulftalent.com", "monster.com",
                    "glassdoor.com", "naukrigulf.com", "greenhouse.io", "lever.co", "workday.com",
                    "careers.", "jobs.", "recruit"]

    all_results = []
    seen_urls = set()

    async with httpx.AsyncClient(timeout=10) as client:
        for query in queries:
            try:
                resp = await client.post(
                    "https://google.serper.dev/search",
                    headers={"X-API-KEY": settings.serper_api_key, "Content-Type": "application/json"},
                    json={"q": query, "num": 10},
                )
                if resp.status_code != 200:
                    continue
                data = resp.json()
                for r in data.get("organic", []):
                    url = r.get("link", "")
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)
                    title = r.get("title", "")
                    snippet = r.get("snippet", "")
                    if not title:
                        continue

                    # Only include actual job listings, not articles
                    is_job = any(s in url.lower() for s in JOB_SOURCES)
                    title_lower = title.lower()
                    has_job_keyword = any(k in title_lower for k in ["job", "hiring", "position", "vacancy", "career", "apply", "role", "opening"])
                    if not is_job and not has_job_keyword:
                        continue

                    # Skip articles/guides/aggregator pages
                    if any(skip in title_lower for skip in ["how to", "guide", "top 10", "best companies", "salary guide", "interview tips", "jobs in", "search results", "latest jobs", "job openings in"]):
                        continue

                    # Skip LinkedIn search/aggregate pages (not actual job posts)
                    if "linkedin.com/jobs/search" in url.lower():
                        continue
                    if re.search(r'\d+\s+\w+\s+jobs?\s+in\s+', title_lower):
                        continue

                    # Detect source
                    source = "Web"
                    for s, label in [("linkedin", "LinkedIn"), ("bayt", "Bayt"), ("indeed", "Indeed"),
                                     ("gulftalent", "GulfTalent"), ("monster", "Monster"), ("glassdoor", "Glassdoor"),
                                     ("naukrigulf", "NaukriGulf"), ("greenhouse", "Greenhouse"), ("lever.co", "Lever"),
                                     ("workday", "Workday")]:
                        if s in url.lower():
                            source = label
                            break

                    # Extract company and role from title
                    SITE_NAMES = {"linkedin", "indeed", "bayt", "glassdoor", "gulftalent", "monster",
                                  "naukrigulf", "greenhouse", "lever", "workday", "jobs", "careers"}
                    LOCATION_WORDS = {"dubai", "abu dhabi", "united arab emirates", "uae", "riyadh",
                                      "saudi arabia", "ksa", "doha", "qatar", "bahrain", "muscat",
                                      "oman", "kuwait", "cairo", "egypt", "london", "remote", "hybrid",
                                      "on-site", "onsite", "full-time", "part-time", "contract"}
                    company = ""
                    role_extracted = ""

                    # LinkedIn format: "Role - Company - Location - LinkedIn"
                    # or "Company hiring Role in Location"
                    hiring_match = re.match(r'^(.+?)\s+hiring\s+(.+?)(?:\s+in\s+.+)?$', title, re.IGNORECASE) if 'hiring' in title.lower() else None
                    if hiring_match:
                        company = hiring_match.group(1).strip()[:50]
                        role_extracted = hiring_match.group(2).strip()[:80]
                    else:
                        for sep in [" at ", " - ", " | ", " — "]:
                            if sep in title:
                                parts = [p.strip() for p in title.split(sep)]
                                # Filter out site names AND locations
                                clean_parts = []
                                for p in parts:
                                    pl = p.lower().strip()
                                    is_site = pl.split(".")[0].split(" ")[0] in SITE_NAMES
                                    is_location = any(loc in pl for loc in LOCATION_WORDS)
                                    is_short = len(p) <= 1
                                    if not is_site and not is_location and not is_short:
                                        clean_parts.append(p)
                                if len(clean_parts) >= 2:
                                    role_extracted = clean_parts[0][:80]
                                    company = clean_parts[1][:50]
                                elif len(clean_parts) == 1:
                                    role_extracted = clean_parts[0][:80]
                                break

                    # Try to extract company from snippet if not found in title
                    if not company and snippet:
                        # Snippets often start with "Company name is looking for..." or "At Company, we..."
                        snippet_match = re.match(r'^(?:At\s+)?([A-Z][A-Za-z\s&]+?)(?:\s+is\s+|\s+are\s+|\,\s+we|\s+—|\s+-)', snippet)
                        if snippet_match:
                            company = snippet_match.group(1).strip()[:50]

                    # Skip if no company could be extracted
                    if not company or company.lower() in ("company", "unknown", "n/a", ""):
                        continue
                    # Skip stale results (date string containing year before current)
                    date_str = r.get("date", "")
                    if date_str and ("2024" in date_str or "2023" in date_str):
                        continue

                    all_results.append({
                        "title": title[:150],
                        "role": role_extracted or title[:80],
                        "company": company,
                        "description": snippet[:300],
                        "url": url,
                        "source": source,
                        "date": date_str,
                    })
            except Exception:
                continue

    # Sort by source priority
    source_priority = {"LinkedIn": 1, "Bayt": 2, "Indeed": 3, "GulfTalent": 4, "Glassdoor": 5}
    all_results.sort(key=lambda x: source_priority.get(x["source"], 10))

    return {
        "vacancies": all_results[:limit],
        "total": len(all_results),
        "sources_searched": len(queries),
    }


# ── Freelance opportunities ──────────────────────────────────────────────────

@router.get("/freelance", summary="Find freelance/contract opportunities matching profile")
async def freelance_opportunities(
    db: DB,
    user_id: CurrentUserId,
    limit: int = Query(default=20, le=30),
) -> dict:
    """Search freelance platforms for relevant gigs using Serper."""
    profile, prefs = await _get_profile_and_prefs(db, user_id)
    roles = prefs.get("roles", ["CEO", "COO", "Strategy Consultant"])
    sectors = prefs.get("sectors", ["Technology"])
    skills = profile.get("skills", [])[:10]

    role_str = " OR ".join(roles[:5])
    sector_str = " ".join(sectors[:2]) if sectors else ""

    if not settings.serper_api_key:
        return {"freelance": [], "total": 0, "sources_searched": 0}

    # Use Serper Jobs API for actual job listings, not web search
    role_queries = roles[:5]
    all_results = []
    seen_titles = set()

    async with httpx.AsyncClient(timeout=12) as client:
        # Serper Jobs API — returns actual job listings
        for role in role_queries:
            for query_mod in [
                f"freelance {role} remote",
                f"contract {role}",
                f"fractional {role}",
                f"consulting {role} {sector_str}",
            ]:
                try:
                    resp = await client.post(
                        "https://google.serper.dev/search",
                        headers={"X-API-KEY": settings.serper_api_key, "Content-Type": "application/json"},
                        json={"q": query_mod, "num": 5, "type": "search"},
                    )
                    if resp.status_code != 200:
                        continue
                    data = resp.json()
                    for r in data.get("organic", []):
                        url = r.get("link", "")
                        title = r.get("title", "")
                        snippet = r.get("snippet", "")
                        if not title:
                            continue
                        # Skip "best of" list articles
                        title_lower = title.lower()
                        if any(skip in title_lower for skip in ["best freelance", "top 10", "top 11", "best fractional", "how to hire", "how to find", "guide to", "what is a"]):
                            continue
                        # Dedup by title similarity
                        title_key = title_lower[:50]
                        if title_key in seen_titles:
                            continue
                        seen_titles.add(title_key)

                        # Detect source
                        source = "Web"
                        for p, label in [("upwork", "Upwork"), ("toptal", "Toptal"), ("freelancer.com", "Freelancer"), ("flexjobs", "FlexJobs"), ("contra.com", "Contra"), ("linkedin", "LinkedIn"), ("indeed", "Indeed"), ("fiverr", "Fiverr"), ("guru.com", "Guru"), ("peopleperhour", "PeoplePerHour")]:
                            if p in url.lower():
                                source = label
                                break

                        all_results.append({
                            "title": title[:120],
                            "description": snippet[:300],
                            "url": url,
                            "source": source,
                            "type": "freelance",
                            "date": r.get("date", ""),
                        })
                except Exception:
                    continue

    # Sort: known platforms first, then by recency
    platform_priority = {"Upwork": 1, "Toptal": 2, "LinkedIn": 3, "FlexJobs": 4, "Indeed": 5, "Contra": 6, "Freelancer": 7}
    all_results.sort(key=lambda x: platform_priority.get(x["source"], 10))

    # Also add platform links at the end
    platform_links = [
        {"name": "Toptal", "url": "https://www.toptal.com", "description": "Top 3% freelance talent — premium consulting & fractional exec roles"},
        {"name": "Upwork", "url": "https://www.upwork.com", "description": "Largest freelance marketplace — strategy, ops, consulting projects"},
        {"name": "FlexJobs", "url": "https://www.flexjobs.com", "description": "Vetted remote & flexible jobs — including contract/freelance exec roles"},
        {"name": "Contra", "url": "https://contra.com", "description": "Commission-free freelance platform — modern independent work"},
        {"name": "LinkedIn", "url": "https://www.linkedin.com/jobs", "description": "Filter by 'Contract' or 'Temporary' for freelance opportunities"},
        {"name": "Freelancer.com", "url": "https://www.freelancer.com", "description": "Project-based work across strategy, operations, and consulting"},
    ]

    return {
        "freelance": all_results[:limit],
        "total": len(all_results),
        "sources_searched": len(role_queries) * 4,
        "platform_links": platform_links,
    }
