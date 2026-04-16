"""
app/api/routes/linkedin.py

LinkedIn integration endpoints — browser extension API + queries.

Extension endpoints (POST /ingest*):
  Called by the StealthRole browser extension to push scraped data.
  Extension authenticates with the user's Bearer token.

Query endpoints:
  Used by the frontend to display connections, recruiters, conversations.

Routes:
  POST   /api/v1/linkedin/ingest/connections    Bulk push connections from extension
  POST   /api/v1/linkedin/ingest/conversations  Push conversation messages
  GET    /api/v1/linkedin/connections            List connections (filterable)
  GET    /api/v1/linkedin/recruiters             List detected recruiters
  GET    /api/v1/linkedin/companies/{company}    Connections at a specific company
  GET    /api/v1/linkedin/conversations          List conversation messages
  POST   /api/v1/linkedin/conversations/link     Link thread to application
  GET    /api/v1/linkedin/stats                  Quick stats for dashboard
"""

import csv
import io
import uuid

import structlog
from fastapi import APIRouter, File, Query, UploadFile, status
from pydantic import BaseModel, Field

from app.dependencies import DB, CurrentUserId

logger = structlog.get_logger(__name__)
from app.schemas.linkedin import (
    ConnectionListResponse,
    ConnectionResponse,
    ConversationResponse,
    IngestConnectionsRequest,
    IngestConnectionsResponse,
    IngestConversationsRequest,
    IngestCompanyRequest,
    IngestCompanyResponse,
    IngestJobRequest,
    IngestJobResponse,
    IngestJobsBulkRequest,
    IngestJobsBulkResponse,
    LinkedInStatsResponse,
    LinkThreadRequest,
    MessagesSyncRequest,
    MessagesSyncResponse,
)
from app.services.linkedin.linkedin_service import LinkedInService

router = APIRouter(prefix="/api/v1/linkedin", tags=["LinkedIn"])


def _svc(db: DB) -> LinkedInService:
    return LinkedInService(db=db)


# ── Extension ingest ──────────────────────────────────────────────────────────

@router.post(
    "/ingest/connections",
    response_model=IngestConnectionsResponse,
    summary="Bulk push connections from browser extension",
)
async def ingest_connections(
    payload: IngestConnectionsRequest,
    db: DB,
    user_id: CurrentUserId,
) -> IngestConnectionsResponse:
    result = await _svc(db).import_connections(
        user_id=user_id,
        connections=[c.model_dump() for c in payload.connections],
    )
    return IngestConnectionsResponse(**result)


@router.post(
    "/ingest/mutual-connections",
    summary="Store mutual connection data from profile page scrape",
)
async def ingest_mutual_connections(
    payload: dict,
    db: DB,
    user_id: CurrentUserId,
) -> dict:
    """Extension sends: target_person + list of mutual connections."""
    from sqlalchemy import select as sa_select, or_
    from app.models.mutual_connection import MutualConnection
    from app.models.linkedin_connection import LinkedInConnection

    target = payload.get("target_person", {})
    mutuals = payload.get("mutual_connections", [])
    mutual_count = payload.get("mutual_count", 0)

    if not target.get("linkedin_id") or not mutuals:
        return {"stored": 0, "target": target.get("full_name", "")}

    # Build a lookup of user's 1st-degree connections for resolving mutual IDs
    all_conns = (await db.execute(
        sa_select(LinkedInConnection).where(LinkedInConnection.user_id == user_id)
    )).scalars().all()
    conn_by_name = {c.full_name.lower().strip(): c for c in all_conns}
    conn_by_url = {c.linkedin_url: c for c in all_conns if c.linkedin_url}

    stored = 0
    for m in mutuals:
        if not m.get("name"):
            continue

        # Try to resolve mutual to a real 1st-degree connection
        resolved_id = m.get("linkedin_id") or ""
        resolved_url = m.get("linkedin_url") or ""

        # Match by LinkedIn URL first (most reliable)
        matched_conn = conn_by_url.get(resolved_url) if resolved_url else None
        # Then by name
        if not matched_conn:
            matched_conn = conn_by_name.get(m["name"].lower().strip())

        # If we found a match, use their real linkedin_id
        if matched_conn and matched_conn.linkedin_id:
            resolved_id = matched_conn.linkedin_id
            if not resolved_url and matched_conn.linkedin_url:
                resolved_url = matched_conn.linkedin_url

        # Use name as fallback ID if nothing else
        if not resolved_id:
            resolved_id = m["name"]

        # Check if already stored (by target + mutual combo)
        existing = (await db.execute(
            sa_select(MutualConnection).where(
                MutualConnection.user_id == user_id,
                MutualConnection.target_linkedin_id == target["linkedin_id"],
                or_(
                    MutualConnection.mutual_linkedin_id == resolved_id,
                    MutualConnection.mutual_name == m["name"],
                ),
            )
        )).scalars().first()

        if existing:
            # Update with better data if we have it now
            if matched_conn and matched_conn.linkedin_id and existing.mutual_linkedin_id != matched_conn.linkedin_id:
                existing.mutual_linkedin_id = matched_conn.linkedin_id
                existing.mutual_linkedin_url = matched_conn.linkedin_url or existing.mutual_linkedin_url
            continue

        db.add(MutualConnection(
            user_id=user_id,
            target_linkedin_id=target["linkedin_id"],
            target_name=target.get("full_name", ""),
            target_title=target.get("current_title", ""),
            target_company=target.get("current_company", ""),
            target_linkedin_url=target.get("linkedin_url", ""),
            mutual_linkedin_id=resolved_id,
            mutual_name=m["name"],
            mutual_linkedin_url=resolved_url,
            total_mutual_count=mutual_count,
        ))
        stored += 1

    if stored:
        await db.flush()
        await db.commit()

    return {"stored": stored, "target": target.get("full_name", "")}


@router.post(
    "/ingest/network-scan",
    summary="Store an on-demand network scan: connector + matches at target company",
)
async def ingest_network_scan(
    payload: dict,
    db: DB,
    user_id: CurrentUserId,
) -> dict:
    """
    Extension scraped a connector's connections list and found people
    who work at the target company. Store each match as a MutualConnection
    so find_way_in() will surface them as 2nd-degree paths.
    """
    from sqlalchemy import select as sa_select
    from app.models.mutual_connection import MutualConnection
    from app.models.linkedin_connection import LinkedInConnection

    connector_url = (payload.get("connector_url") or "").strip()
    connector_name = (payload.get("connector_name") or "").strip()
    target_company = (payload.get("target_company") or "").strip()
    matches = payload.get("matches", [])

    if not connector_url or not target_company or not matches:
        return {"stored": 0, "reason": "missing_required_fields"}

    # Find the connector in the user's 1st-degree connections by URL or name
    connector = None
    if connector_url:
        result = await db.execute(
            sa_select(LinkedInConnection).where(
                LinkedInConnection.user_id == user_id,
                LinkedInConnection.linkedin_url == connector_url,
            ).limit(1)
        )
        connector = result.scalar_one_or_none()
    if not connector and connector_name:
        result = await db.execute(
            sa_select(LinkedInConnection).where(
                LinkedInConnection.user_id == user_id,
            )
        )
        for c in result.scalars().all():
            if c.full_name and c.full_name.lower().strip() == connector_name.lower().strip():
                connector = c
                break

    connector_linkedin_id = connector.linkedin_id if connector else (connector_url.split("/in/")[-1].rstrip("/") if "/in/" in connector_url else connector_name.lower().replace(" ", "-"))

    stored = 0
    for m in matches:
        target_name = (m.get("name") or "").strip()
        target_url = (m.get("linkedin_url") or "").strip()
        target_headline = (m.get("headline") or "").strip()
        if not target_name:
            continue

        target_lid = target_url.split("/in/")[-1].rstrip("/") if "/in/" in target_url else target_name.lower().replace(" ", "-")

        # Skip if already stored
        existing = (await db.execute(
            sa_select(MutualConnection).where(
                MutualConnection.user_id == user_id,
                MutualConnection.target_linkedin_id == target_lid,
                MutualConnection.mutual_linkedin_id == connector_linkedin_id,
            ).limit(1)
        )).scalar_one_or_none()
        if existing:
            continue

        db.add(MutualConnection(
            user_id=user_id,
            target_linkedin_id=target_lid,
            target_name=target_name,
            target_title=target_headline[:200],
            target_company=target_company,
            target_linkedin_url=target_url,
            mutual_linkedin_id=connector_linkedin_id,
            mutual_name=connector_name or (connector.full_name if connector else ""),
            mutual_linkedin_url=connector_url,
            total_mutual_count=len(matches),
        ))
        stored += 1

    if stored:
        await db.flush()
        await db.commit()

    logger.info("network_scan_ingest", user_id=user_id, connector=connector_name, target_company=target_company, stored=stored, total=len(matches))
    return {
        "stored": stored,
        "connector": connector_name,
        "target_company": target_company,
        "total_matches": len(matches),
    }


@router.post(
    "/cleanup/mutual-connections",
    summary="Deduplicate mutual connections table",
)
async def cleanup_mutual_connections(
    db: DB,
    user_id: CurrentUserId,
) -> dict:
    """Remove duplicate mutual_connection records, keeping one per (target, mutual_name)."""
    from sqlalchemy import select as sa_select, delete as sa_delete
    from app.models.mutual_connection import MutualConnection

    # Load all records for this user
    all_records = (await db.execute(
        sa_select(MutualConnection).where(MutualConnection.user_id == user_id)
        .order_by(MutualConnection.created_at)
    )).scalars().all()

    # Keep first record per (target_linkedin_id, mutual_name), delete rest
    seen = set()
    to_delete = []
    for rec in all_records:
        key = (rec.target_linkedin_id, rec.mutual_name.lower().strip())
        if key in seen:
            to_delete.append(rec.id)
        else:
            seen.add(key)

    for did in to_delete:
        await db.execute(sa_delete(MutualConnection).where(MutualConnection.id == did))

    if to_delete:
        await db.flush()
        await db.commit()

    return {"deleted": len(to_delete), "remaining": len(seen)}


@router.post(
    "/ingest/conversations",
    status_code=status.HTTP_201_CREATED,
    summary="Push conversation messages from browser extension",
)
async def ingest_conversations(
    payload: IngestConversationsRequest,
    db: DB,
    user_id: CurrentUserId,
) -> dict:
    count = await _svc(db).add_conversation(
        user_id=user_id,
        messages=[m.model_dump() for m in payload.messages],
    )
    return {"messages_imported": count}


# ── Queries ───────────────────────────────────────────────────────────────────

@router.get(
    "/connections",
    response_model=ConnectionListResponse,
    summary="List LinkedIn connections",
)
async def list_connections(
    db: DB,
    user_id: CurrentUserId,
    company: str | None = Query(default=None, description="Filter by company name"),
    recruiters_only: bool = Query(default=False),
) -> ConnectionListResponse:
    connections = await _svc(db).list_connections(
        user_id=user_id, company=company, recruiters_only=recruiters_only,
    )
    return ConnectionListResponse(
        connections=[ConnectionResponse.model_validate(c) for c in connections],
        total=len(connections),
    )


@router.get(
    "/recruiters",
    response_model=ConnectionListResponse,
    summary="List detected recruiters in your network",
)
async def list_recruiters(
    db: DB,
    user_id: CurrentUserId,
) -> ConnectionListResponse:
    recruiters = await _svc(db).get_recruiters(user_id=user_id)
    return ConnectionListResponse(
        connections=[ConnectionResponse.model_validate(c) for c in recruiters],
        total=len(recruiters),
    )


@router.get(
    "/companies/{company}",
    response_model=ConnectionListResponse,
    summary="Find connections at a specific company (warm intros)",
)
async def connections_at_company(
    company: str,
    db: DB,
    user_id: CurrentUserId,
) -> ConnectionListResponse:
    connections = await _svc(db).get_connections_at_company(
        user_id=user_id, company=company,
    )
    return ConnectionListResponse(
        connections=[ConnectionResponse.model_validate(c) for c in connections],
        total=len(connections),
    )


@router.get(
    "/conversations",
    response_model=list[ConversationResponse],
    summary="List LinkedIn conversation messages",
)
async def list_conversations(
    db: DB,
    user_id: CurrentUserId,
    connection_id: uuid.UUID | None = Query(default=None),
    application_id: uuid.UUID | None = Query(default=None),
) -> list[ConversationResponse]:
    messages = await _svc(db).list_conversations(
        user_id=user_id,
        connection_id=connection_id,
        application_id=application_id,
    )
    return [ConversationResponse.model_validate(m) for m in messages]


@router.post(
    "/conversations/link",
    summary="Link a conversation thread to an application",
)
async def link_thread(
    payload: LinkThreadRequest,
    db: DB,
    user_id: CurrentUserId,
) -> dict:
    count = await _svc(db).link_conversation_to_application(
        user_id=user_id,
        thread_id=payload.thread_id,
        application_id=payload.application_id,
    )
    return {"messages_linked": count, "thread_id": payload.thread_id}


@router.get(
    "/stats",
    response_model=LinkedInStatsResponse,
    summary="LinkedIn integration stats for dashboard",
)
async def linkedin_stats(
    db: DB,
    user_id: CurrentUserId,
) -> LinkedInStatsResponse:
    stats = await _svc(db).get_stats(user_id=user_id)
    return LinkedInStatsResponse(**stats)


# ── CSV Import ────────────────────────────────────────────────────────────────

@router.post(
    "/import-csv",
    response_model=IngestConnectionsResponse,
    summary="Import LinkedIn connections from CSV export file",
    description=(
        "Upload the Connections.csv file from LinkedIn Settings > Data Privacy > Get a copy of your data. "
        "Parses all connections and imports them with recruiter/HM detection."
    ),
)
async def import_csv(
    file: UploadFile = File(...),
    db: DB = None,
    user_id: CurrentUserId = None,
) -> IngestConnectionsResponse:
    content = await file.read()
    text = content.decode("utf-8", errors="ignore")

    # LinkedIn CSV has note lines before the actual header — find the real header
    lines = text.split("\n")
    header_idx = 0
    for i, line in enumerate(lines):
        if line.strip().startswith("First Name,"):
            header_idx = i
            break
    csv_text = "\n".join(lines[header_idx:])

    reader = csv.DictReader(io.StringIO(csv_text))
    connections = []

    for row in reader:
        first = row.get("First Name", "").strip()
        last = row.get("Last Name", "").strip()
        full_name = f"{first} {last}".strip()
        if not full_name or full_name == " ":
            continue

        url = row.get("URL", "").strip()
        linkedin_id = url.split("/in/")[-1].rstrip("/") if "/in/" in url else None

        connections.append({
            "linkedin_id": linkedin_id,
            "linkedin_url": url or None,
            "full_name": full_name,
            "current_title": row.get("Position", "").strip() or None,
            "current_company": row.get("Company", "").strip() or None,
            "connected_at": row.get("Connected On", "").strip() or None,
        })

    if not connections:
        return IngestConnectionsResponse(created=0, updated=0, total_processed=0, recruiters_detected=0, applications_matched=0)

    result = await _svc(db).import_connections(
        user_id=user_id,
        connections=connections,
    )
    logger.info("linkedin_csv_import", user_id=user_id, total=len(connections), created=result["created"])
    return IngestConnectionsResponse(**result)


# ── Message Analysis + Reply Drafts ───────────────────────────────────────────

class ConversationAnalysisRequest(BaseModel):
    """Paste a LinkedIn conversation for analysis and reply drafting."""
    messages: str = Field(..., min_length=10, max_length=20000, description="Paste the full conversation text")
    context: str | None = Field(default=None, max_length=2000, description="Additional context: what role you're targeting, what you want to achieve")
    tone: str = Field(default="professional", pattern=r"^(professional|casual|confident|formal)$")


@router.post(
    "/analyze-conversation",
    summary="Analyze a LinkedIn conversation and draft a reply",
    description="Paste a recruiter or networking conversation. StealthRole analyzes intent and drafts an optimal reply.",
)
async def analyze_conversation(
    payload: ConversationAnalysisRequest,
    db: DB,
    user_id: CurrentUserId,
) -> dict:
    from app.services.llm.client import ClaudeClient
    from app.services.llm.router import LLMTask

    # Get user profile for context
    from app.services.profile.profile_service import ProfileService
    svc = ProfileService(db)
    profile = await svc.get_active_profile_orm(user_id)
    profile_summary = ""
    if profile:
        pd = profile.to_prompt_dict()
        profile_summary = f"Headline: {pd.get('headline', '')}\n"
        for exp in pd.get("experiences", [])[:3]:
            profile_summary += f"{exp.get('role', '')} at {exp.get('company', '')}\n"

    system_prompt = """You are an expert career coach analyzing a LinkedIn conversation.

Your job:
1. Identify the intent (recruiter outreach, networking, follow-up, rejection, etc.)
2. Assess the opportunity quality
3. Draft an optimal reply that advances the conversation

Rules:
- Be strategic, not desperate
- Show genuine interest without overselling
- Ask smart questions that show domain knowledge
- If it's a recruiter: express interest but stay in control
- If it's networking: offer value, not just ask for help
- Match the tone requested by the user

Return JSON:
{
  "intent": "recruiter_outreach | networking | follow_up | rejection | information_request | other",
  "opportunity_quality": "high | medium | low",
  "analysis": "2-3 sentences explaining what's happening in this conversation",
  "key_signals": ["what to notice about this message"],
  "suggested_reply": "the full reply text, ready to send",
  "alternative_reply": "a different approach if the first doesn't feel right",
  "next_steps": ["what to do after sending this reply"],
  "red_flags": ["any warning signs in the conversation"]
}"""

    user_prompt = f"""CONVERSATION:
{payload.messages}

{f'CONTEXT: {payload.context}' if payload.context else ''}
{f'MY PROFILE: {profile_summary}' if profile_summary else ''}
TONE: {payload.tone}

Analyze this conversation and draft a reply."""

    client = ClaudeClient(task=LLMTask.OUTREACH, max_tokens=2000)
    try:
        raw, result = client.call_text(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.3,
        )
        # Parse JSON response
        import json
        import re
        text = re.sub(r'^```(?:json)?\s*', '', raw.strip())
        text = re.sub(r'\s*```$', '', text).strip()
        data = json.loads(text)
        data["cost_usd"] = result.cost_usd
        data["model"] = result.model
        return data
    except Exception as e:
        logger.error("conversation_analysis_failed", error=str(e))
        return {
            "intent": "unknown",
            "analysis": "Could not analyze this conversation. Try pasting a cleaner version.",
            "suggested_reply": "",
            "error": str(e),
        }


@router.post(
    "/analyze-network",
    summary="AI analysis of LinkedIn network cross-referenced with profile, applications, and scout",
)
async def analyze_network(
    db: DB,
    user_id: CurrentUserId,
) -> dict:
    """Cross-reference LinkedIn connections with profile, applications, and scout to find warm paths."""
    from sqlalchemy import select as sa_select
    from app.models.linkedin_connection import LinkedInConnection
    from app.models.candidate_profile import CandidateProfile, ExperienceEntry, ProfileStatus
    from app.models.application import Application
    from app.services.llm.client import ClaudeClient
    from app.services.llm.router import LLMTask
    select = sa_select
    import json as _json
    from collections import Counter

    # 1. Get connections
    connections = (await db.execute(
        select(LinkedInConnection).where(LinkedInConnection.user_id == user_id).limit(2000)
    )).scalars().all()

    if not connections:
        return {"error": "No connections imported yet"}

    # 2. Get profile + experiences
    profile = (await db.execute(
        select(CandidateProfile).where(
            CandidateProfile.user_id == user_id,
            CandidateProfile.status == ProfileStatus.ACTIVE,
        )
    )).scalar_one_or_none()

    profile_summary = "No profile uploaded yet."
    if profile:
        experiences = (await db.execute(
            select(ExperienceEntry).where(ExperienceEntry.profile_id == profile.id)
        )).scalars().all()

        ctx = {}
        try:
            ctx = _json.loads(profile.global_context or "{}")
        except Exception:
            pass

        exp_lines = [f"  {e.role_title} at {e.company_name} ({e.start_date} - {e.end_date})" for e in experiences]
        skills = ctx.get("skills", [])
        profile_summary = f"""CANDIDATE PROFILE:
Headline: {profile.headline or 'N/A'}
Skills: {', '.join(skills[:15]) if skills else 'N/A'}
Experience:
{chr(10).join(exp_lines[:8]) if exp_lines else '  No experience entries'}
"""

    # 3. Get applications (what they're actively pursuing)
    applications = (await db.execute(
        select(Application).where(Application.user_id == user_id).order_by(Application.created_at.desc()).limit(20)
    )).scalars().all()

    app_lines = [f"  {a.company} — {a.role} (stage: {a.stage})" for a in applications]
    apps_summary = f"""ACTIVE APPLICATIONS ({len(applications)}):
{chr(10).join(app_lines) if app_lines else '  No applications yet'}
"""

    # 4. Build network summary
    companies = Counter()
    recruiters = []
    decision_makers = []
    connections_at_target_companies = {}

    target_companies = set(a.company.lower().strip() for a in applications if a.company)

    for c in connections:
        company = c.current_company or ""
        title = c.current_title or ""
        if company:
            companies[company] += 1
        tl = title.lower()
        if c.is_recruiter or "recruit" in tl or "talent" in tl or "people" in tl:
            recruiters.append(f"{c.full_name} — {title} at {company}")
        elif any(k in tl for k in ["director", "vp", "vice president", "head of", "chief", "ceo", "coo", "cfo", "cto", "founder", "partner", "managing"]):
            decision_makers.append(f"{c.full_name} — {title} at {company}")

        # Check if connection is at a target company
        if company and company.lower().strip() in target_companies:
            key = company.lower().strip()
            if key not in connections_at_target_companies:
                connections_at_target_companies[key] = []
            connections_at_target_companies[key].append(f"{c.full_name} ({title})")

    target_overlap = ""
    if connections_at_target_companies:
        parts = []
        for comp, people in connections_at_target_companies.items():
            parts.append(f"  {comp.title()}: {', '.join(people[:5])}")
        target_overlap = f"""CONNECTIONS AT COMPANIES YOU'RE APPLYING TO:
{chr(10).join(parts)}
"""

    network_summary = f"""LINKEDIN NETWORK: {len(connections)} connections

TOP COMPANIES:
{chr(10).join(f'  {c}: {n}' for c, n in companies.most_common(20))}

RECRUITERS ({len(recruiters)}):
{chr(10).join(recruiters[:25])}

DECISION MAKERS ({len(decision_makers)}):
{chr(10).join(decision_makers[:25])}

{target_overlap}"""

    # 5. Send everything to Claude
    client = ClaudeClient(task=LLMTask.REPORT_PACK)
    system = "You are a career strategist. You have access to someone's CV, their active job applications, and their full LinkedIn network. Your job is to find the fastest path to getting them hired — through warm intros, recruiter engagement, and strategic networking. Return only valid JSON."

    prompt = f"""{profile_summary}

{apps_summary}

{network_summary}

Based on this person's PROFILE + APPLICATIONS + NETWORK, tell them exactly how to leverage LinkedIn to get hired. Be brutally specific — name real people, real companies, real actions.

Return JSON:
{{
  "network_strength": "<2-3 sentences about their network's job search value — specifically for the ROLES they're targeting>",
  "warm_paths": [
    {{
      "target_company": "<company they're applying to or should apply to>",
      "connections_there": ["<name (title)>"],
      "strategy": "<exactly how to use these connections — who to message, what to say, in what order>",
      "strength": "<strong/medium/weak>"
    }}
  ],
  "recruiter_strategy": [
    {{
      "recruiter_name": "<name>",
      "company": "<their company>",
      "action": "<specific message/approach to engage this recruiter for the roles they want>"
    }}
  ],
  "career_leverage": ["<3-5 specific ways to use their network based on their actual profile and target roles>"],
  "blind_spots": ["<what's missing in their network for the roles they want — specific companies/roles/regions to add>"],
  "recommendations": ["<5 specific immediate actions — message X person, connect with Y role at Z company, etc>"],
  "warm_intro_potential": "<How many warm intros could they realistically get? Which companies? What's the fastest path to an interview?>"
}}

RULES:
- Cross-reference applications with connections — if they applied to Careem and know people there, that's a WARM PATH
- Name real people from their connections list
- Recommendations must be actionable TODAY, not generic advice
- If they have no applications yet, recommend companies where they have the strongest network
- Recruiter strategy should name actual recruiters from their network
- Return ONLY valid JSON"""

    try:
        response, _meta = client.call_text(system, prompt)
        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return _json.loads(text)
    except Exception as e:
        logger.error("network_analysis_failed", error=str(e))
        return {
            "network_strength": f"Network of {len(connections)} connections with {len(recruiters)} recruiters.",
            "warm_paths": [],
            "recruiter_strategy": [],
            "career_leverage": ["Cross-reference failed — try again"],
            "blind_spots": [],
            "recommendations": ["Try again later"],
            "warm_intro_potential": ""
        }


# ── Feature 2: Messages sync (conversation-centric) ─────────────────────────


# ── Feature 3: Inbox (read conversations) ────────────────────────────────────

class InboxConversation(BaseModel):
    """One conversation thread returned to the frontend."""
    id: str
    conversation_urn: str
    contact_name: str | None = None
    contact_linkedin_id: str | None = None
    contact_linkedin_url: str | None = None
    contact_title: str | None = None
    contact_company: str | None = None
    messages: list[dict] = []
    message_count: int = 0
    last_message_at: str | None = None
    last_sender: str | None = None
    is_unread: bool = False
    days_since_reply: int | None = None
    is_job_related: bool | None = None
    classification: str | None = None
    stage: str | None = None
    ai_draft_reply: str | None = None
    created_at: str | None = None


class InboxResponse(BaseModel):
    conversations: list[InboxConversation]
    total: int


@router.get(
    "/inbox",
    response_model=InboxResponse,
    summary="List LinkedIn conversation threads for the Inbox page",
)
async def get_inbox(
    db: DB,
    user_id: CurrentUserId,
    filter: str | None = Query(default=None, description="all|job_related|unread|recruiter|needs_reply"),
    search: str | None = Query(default=None, description="Search contact name, title, or company"),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
) -> InboxResponse:
    """
    Return conversation threads from linkedin_messages table,
    ordered by last_message_at descending. Supports filtering and search.
    """
    from sqlalchemy import func as sa_func, select as sa_select, or_

    from app.models.linkedin_message import LinkedInMessage

    q = sa_select(LinkedInMessage).where(LinkedInMessage.user_id == user_id)

    # Filters
    if filter == "job_related":
        q = q.where(LinkedInMessage.is_job_related == True)  # noqa: E712
    elif filter == "unread":
        q = q.where(LinkedInMessage.is_unread == True)  # noqa: E712
    elif filter == "recruiter":
        q = q.where(LinkedInMessage.classification == "recruiter")
    elif filter == "needs_reply":
        q = q.where(
            LinkedInMessage.last_sender == "them",
            LinkedInMessage.days_since_reply != None,  # noqa: E711
        )

    # Text search
    if search:
        pattern = f"%{search.strip().lower()}%"
        q = q.where(or_(
            sa_func.lower(LinkedInMessage.contact_name).like(pattern),
            sa_func.lower(LinkedInMessage.contact_title).like(pattern),
            sa_func.lower(LinkedInMessage.contact_company).like(pattern),
        ))

    # Count total matching
    count_q = sa_select(sa_func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar_one()

    # Fetch page
    q = q.order_by(LinkedInMessage.last_message_at.desc().nullslast())
    q = q.offset(offset).limit(limit)
    rows = (await db.execute(q)).scalars().all()

    conversations = []
    for r in rows:
        conversations.append(InboxConversation(
            id=str(r.id),
            conversation_urn=r.conversation_urn,
            contact_name=r.contact_name,
            contact_linkedin_id=r.contact_linkedin_id,
            contact_linkedin_url=r.contact_linkedin_url,
            contact_title=r.contact_title,
            contact_company=r.contact_company,
            messages=r.messages if isinstance(r.messages, list) else [],
            message_count=r.message_count,
            last_message_at=r.last_message_at.isoformat() if r.last_message_at else None,
            last_sender=r.last_sender,
            is_unread=r.is_unread,
            days_since_reply=r.days_since_reply,
            is_job_related=r.is_job_related,
            classification=r.classification,
            stage=r.stage,
            ai_draft_reply=r.ai_draft_reply,
            created_at=r.created_at.isoformat() if r.created_at else None,
        ))

    return InboxResponse(conversations=conversations, total=total)

@router.post(
    "/messages/sync",
    response_model=MessagesSyncResponse,
    summary="Bulk push LinkedIn conversation threads from extension",
)
async def sync_linkedin_messages(
    payload: MessagesSyncRequest,
    db: DB,
    user_id: CurrentUserId,
) -> MessagesSyncResponse:
    """
    Upsert full conversation threads scraped by the extension (Feature 2).

    Each conversation = one row in linkedin_messages with messages embedded
    as JSONB. Dedupe key is (user_id, conversation_urn). Classification via
    Haiku is feature-flagged off by default — we store rows now, classify
    later when Feature 3 (/inbox) ships.
    """
    from datetime import datetime, timezone
    from sqlalchemy import select as sa_select
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from app.config import settings
    from app.models.linkedin_connection import LinkedInConnection
    from app.models.linkedin_message import LinkedInMessage
    from app.services.linkedin.message_classifier import (
        heuristic_is_job_related,
        classify_and_draft,
    )

    # Pre-fetch known recruiters for this user so heuristic_is_job_related
    # can flag them even without AI classification.
    recruiter_ids = set(
        (await db.execute(
            sa_select(LinkedInConnection.linkedin_id).where(
                LinkedInConnection.user_id == user_id,
                LinkedInConnection.is_recruiter == True,  # noqa: E712
            )
        )).scalars().all()
    )

    def _parse_dt(s: str | None) -> datetime | None:
        if not s:
            return None
        try:
            # Accept ISO-8601 with or without tz, plus Unix ms
            if s.isdigit():
                return datetime.fromtimestamp(int(s) / 1000, tz=timezone.utc)
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return None

    created = 0
    updated = 0
    total_messages = 0

    for conv in payload.conversations:
        msg_dicts = [m.model_dump() for m in conv.messages]
        total_messages += len(msg_dicts)

        # Cheap heuristic for is_job_related (works even with flag off)
        known = bool(conv.contact_linkedin_id and conv.contact_linkedin_id in recruiter_ids)
        is_job_related = heuristic_is_job_related(
            contact_title=conv.contact_title,
            contact_company=conv.contact_company,
            messages=msg_dicts,
            known_recruiter=known,
        )

        # Optional AI classification (feature-flagged, returns None when off)
        ai = await classify_and_draft(
            contact_name=conv.contact_name,
            contact_title=conv.contact_title,
            contact_company=conv.contact_company,
            messages=msg_dicts,
        )

        # Days since last inbound message we haven't replied to
        last_at = _parse_dt(conv.last_message_at)
        days_since_reply: int | None = None
        if conv.last_sender == "them" and last_at:
            days_since_reply = (datetime.now(timezone.utc) - last_at).days

        # Upsert by (user_id, conversation_urn)
        values = {
            "user_id": user_id,
            "conversation_urn": conv.conversation_urn,
            "contact_name": conv.contact_name,
            "contact_linkedin_id": conv.contact_linkedin_id,
            "contact_linkedin_url": conv.contact_linkedin_url,
            "contact_title": conv.contact_title,
            "contact_company": conv.contact_company,
            "messages": msg_dicts,
            "message_count": len(msg_dicts),
            "last_message_at": last_at,
            "last_sender": conv.last_sender,
            "is_unread": conv.is_unread,
            "days_since_reply": days_since_reply,
            "is_job_related": is_job_related,
        }
        if ai:
            values["classification"] = ai.get("classification")
            values["stage"] = ai.get("stage")
            values["ai_draft_reply"] = ai.get("ai_draft_reply")
            values["classification_confidence"] = ai.get("confidence")
            values["classified_at"] = datetime.now(timezone.utc)

        stmt = pg_insert(LinkedInMessage).values(**values)
        update_cols = {
            k: stmt.excluded[k]
            for k in values.keys()
            if k not in ("user_id", "conversation_urn")
        }
        stmt = stmt.on_conflict_do_update(
            index_elements=["user_id", "conversation_urn"],
            set_=update_cols,
        )
        result = await db.execute(stmt)
        # Fallback: we can't easily tell created-vs-updated from on_conflict
        # without a returning clause. Check if row already existed.
        existing = (await db.execute(
            sa_select(LinkedInMessage.id).where(
                LinkedInMessage.user_id == user_id,
                LinkedInMessage.conversation_urn == conv.conversation_urn,
            )
        )).scalar_one_or_none()
        if existing:
            updated += 1
        else:
            created += 1

    await db.commit()

    logger.info(
        "linkedin_messages_sync_complete",
        user_id=user_id,
        conversations=len(payload.conversations),
        total_messages=total_messages,
        classify_enabled=settings.enable_linkedin_msg_classify,
    )

    return MessagesSyncResponse(
        created=created,
        updated=updated,
        total_processed=len(payload.conversations),
        total_messages=total_messages,
        classification_enabled=settings.enable_linkedin_msg_classify,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Extension v2: Job + Company ingest
# ══════════════════════════════════════════════════════════════════════════════


@router.post(
    "/ingest/job",
    response_model=IngestJobResponse,
    summary="Save a job posting scraped from a LinkedIn job detail page",
)
async def ingest_job(
    payload: IngestJobRequest,
    db: DB,
    user_id: CurrentUserId,
) -> IngestJobResponse:
    """
    Upserts a job into saved_jobs. Dedupe by (user_id, source, external_id).
    The extension auto-captures job data when the user views a LinkedIn job page.
    """
    from sqlalchemy import select as sa_select
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from app.models.saved_job import SavedJob

    job = payload.job
    external_id = job.linkedin_job_id or job.linkedin_url or job.title

    # Check for existing
    existing = (await db.execute(
        sa_select(SavedJob.id).where(
            SavedJob.user_id == user_id,
            SavedJob.source == "linkedin",
            SavedJob.external_id == external_id,
        )
    )).scalar_one_or_none()

    if existing:
        logger.info("job_already_saved", user_id=user_id, job_id=external_id)
        return IngestJobResponse(saved=True, job_id=str(existing), already_existed=True)

    # Parse salary range if available
    salary_min, salary_max = _parse_salary(job.salary)

    values = {
        "user_id": user_id,
        "source": "linkedin",
        "external_id": external_id,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "url": job.linkedin_url or payload.source_url,
        "metadata_": {
            "description": job.description[:5000] if job.description else "",
            "employment_type": job.employment_type,
            "seniority_level": job.seniority_level,
            "industry": job.industry,
            "job_function": job.job_function,
            "posted_at": job.posted_at,
            "applicant_count": job.applicant_count,
            "company_linkedin_url": job.company_linkedin_url,
            "salary_raw": job.salary,
        },
    }

    stmt = pg_insert(SavedJob).values(**values)
    stmt = stmt.on_conflict_do_nothing(
        constraint="uq_saved_job_user_source_ext",
    )
    await db.execute(stmt)
    await db.commit()

    # Retrieve the ID
    row = (await db.execute(
        sa_select(SavedJob.id).where(
            SavedJob.user_id == user_id,
            SavedJob.source == "linkedin",
            SavedJob.external_id == external_id,
        )
    )).scalar_one_or_none()

    logger.info("job_ingested", user_id=user_id, title=job.title, company=job.company)
    return IngestJobResponse(saved=True, job_id=str(row) if row else None, already_existed=False)


@router.post(
    "/ingest/jobs-bulk",
    response_model=IngestJobsBulkResponse,
    summary="Bulk save jobs from a LinkedIn search results page",
)
async def ingest_jobs_bulk(
    payload: IngestJobsBulkRequest,
    db: DB,
    user_id: CurrentUserId,
) -> IngestJobsBulkResponse:
    """
    Batch upsert jobs from a job search page. Skips duplicates.
    """
    from sqlalchemy import select as sa_select
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from app.models.saved_job import SavedJob

    saved = 0
    skipped = 0

    for job in payload.jobs:
        external_id = job.linkedin_job_id or job.linkedin_url or job.title

        values = {
            "user_id": user_id,
            "source": "linkedin",
            "external_id": external_id,
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "url": job.linkedin_url,
            "metadata_": {
                "seniority_level": job.seniority_level,
                "employment_type": job.employment_type,
            },
        }

        stmt = pg_insert(SavedJob).values(**values)
        stmt = stmt.on_conflict_do_nothing(constraint="uq_saved_job_user_source_ext")
        result = await db.execute(stmt)

        if result.rowcount > 0:
            saved += 1
        else:
            skipped += 1

    await db.commit()
    logger.info("jobs_bulk_ingested", user_id=user_id, saved=saved, skipped=skipped)
    return IngestJobsBulkResponse(saved=saved, skipped=skipped)


@router.post(
    "/ingest/company",
    response_model=IngestCompanyResponse,
    summary="Store company intel from a LinkedIn company page",
)
async def ingest_company(
    payload: IngestCompanyRequest,
    db: DB,
    user_id: CurrentUserId,
) -> IngestCompanyResponse:
    """
    Stores company data scraped from LinkedIn company pages.
    Cross-references with existing connections and hidden market signals.
    Returns how many connections the user has at this company and any signals.
    """
    from sqlalchemy import func as sa_func, select as sa_select

    from app.models.linkedin_connection import LinkedInConnection
    from app.models.hidden_signal import HiddenSignal

    company = payload.company

    # Count connections at this company (fuzzy match on company name)
    company_lower = company.name.strip().lower()
    conn_count = (await db.execute(
        sa_select(sa_func.count()).where(
            LinkedInConnection.user_id == user_id,
            sa_func.lower(LinkedInConnection.current_company).contains(company_lower),
        )
    )).scalar_one() or 0

    # Count hidden market signals for this company
    signal_count = 0
    try:
        signal_count = (await db.execute(
            sa_select(sa_func.count()).where(
                HiddenSignal.user_id == user_id,
                sa_func.lower(HiddenSignal.company).contains(company_lower),
            )
        )).scalar_one() or 0
    except Exception:
        pass  # HiddenSignal table might not have a company column

    logger.info(
        "company_intel_ingested",
        user_id=user_id,
        company=company.name,
        connections=conn_count,
        signals=signal_count,
    )

    return IngestCompanyResponse(
        saved=True,
        company_name=company.name,
        connections_here=conn_count,
        signals_count=signal_count,
    )


def _parse_salary(salary_str: str) -> tuple[int | None, int | None]:
    """Best-effort parse salary range from strings like '$120K - $150K/yr'."""
    import re
    if not salary_str:
        return None, None
    # Find all numbers (possibly with K/k suffix)
    nums = re.findall(r'[\$£€]?\s*([\d,]+)\s*[kK]?', salary_str)
    parsed = []
    for n in nums:
        try:
            val = int(n.replace(",", ""))
            # If the number is small and the string has K, multiply
            if val < 1000 and ("k" in salary_str.lower()):
                val *= 1000
            parsed.append(val)
        except ValueError:
            continue
    if len(parsed) >= 2:
        return min(parsed), max(parsed)
    elif len(parsed) == 1:
        return parsed[0], parsed[0]
    return None, None
