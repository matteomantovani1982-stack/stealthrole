"""
app/api/routes/linkedin.py

LinkedIn integration endpoints — browser extension API + queries.

Thin HTTP handlers — all business logic lives in LinkedInService.

Extension endpoints (POST /ingest*):
  Called by the StealthRole browser extension to push scraped data.
  Extension authenticates with the user's Bearer token.

Query endpoints:
  Used by the frontend to display connections, recruiters, conversations.

Routes:
  POST   /api/v1/linkedin/ingest/connections        Bulk push connections from extension
  POST   /api/v1/linkedin/ingest/mutual-connections  Store mutual connection data
  POST   /api/v1/linkedin/ingest/network-scan        Store network scan results
  POST   /api/v1/linkedin/ingest/conversations       Push conversation messages
  POST   /api/v1/linkedin/ingest/job                 Save a scraped job posting
  POST   /api/v1/linkedin/ingest/jobs-bulk           Batch save job search results
  POST   /api/v1/linkedin/ingest/company             Store company intel
  GET    /api/v1/linkedin/connections                List connections (filterable)
  GET    /api/v1/linkedin/recruiters                 List detected recruiters
  GET    /api/v1/linkedin/companies/{company}        Connections at a specific company
  GET    /api/v1/linkedin/conversations              List conversation messages
  POST   /api/v1/linkedin/conversations/link         Link thread to application
  GET    /api/v1/linkedin/stats                      Quick stats for dashboard
  GET    /api/v1/linkedin/inbox                      Conversation threads for Inbox page
  POST   /api/v1/linkedin/messages/sync              Bulk push conversation threads
  POST   /api/v1/linkedin/import-csv                 Import connections from CSV
  POST   /api/v1/linkedin/analyze-conversation       AI conversation analysis + reply draft
  POST   /api/v1/linkedin/analyze-network            AI network cross-reference
  POST   /api/v1/linkedin/cleanup/mutual-connections Deduplicate mutual connections
"""

import uuid

import structlog
from fastapi import APIRouter, File, Query, UploadFile, status
from pydantic import BaseModel, Field

from app.dependencies import DB, CurrentUserId
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

logger = structlog.get_logger(__name__)
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
    return await _svc(db).store_mutual_connections(
        user_id=user_id,
        target=payload.get("target_person", {}),
        mutuals=payload.get("mutual_connections", []),
        mutual_count=payload.get("mutual_count", 0),
    )


@router.post(
    "/ingest/network-scan",
    summary="Store an on-demand network scan: connector + matches at target company",
)
async def ingest_network_scan(
    payload: dict,
    db: DB,
    user_id: CurrentUserId,
) -> dict:
    return await _svc(db).ingest_network_scan(
        user_id=user_id,
        connector_url=(payload.get("connector_url") or "").strip(),
        connector_name=(payload.get("connector_name") or "").strip(),
        target_company=(payload.get("target_company") or "").strip(),
        matches=payload.get("matches", []),
    )


@router.post(
    "/cleanup/mutual-connections",
    summary="Deduplicate mutual connections table",
)
async def cleanup_mutual_connections(
    db: DB,
    user_id: CurrentUserId,
) -> dict:
    return await _svc(db).deduplicate_mutual_connections(user_id=user_id)


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
    svc = _svc(db)
    connections = svc.parse_linkedin_csv(content)

    if not connections:
        return IngestConnectionsResponse(created=0, updated=0, total_processed=0, recruiters_detected=0, applications_matched=0)

    result = await svc.import_connections(user_id=user_id, connections=connections)
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
    return await _svc(db).analyze_conversation(
        user_id=user_id,
        messages_text=payload.messages,
        context=payload.context,
        tone=payload.tone,
    )


@router.post(
    "/analyze-network",
    summary="AI analysis of LinkedIn network cross-referenced with profile, applications, and scout",
)
async def analyze_network(
    db: DB,
    user_id: CurrentUserId,
) -> dict:
    return await _svc(db).analyze_network(user_id=user_id)


# ── Inbox ─────────────────────────────────────────────────────────────────────


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


_dedup_done: set[str] = set()  # track which users have been deduped this process lifetime

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
    limit: int = Query(default=50, le=5000),
    offset: int = Query(default=0, ge=0),
) -> InboxResponse:
    # One-time dedup on first inbox load per user per process restart
    if user_id not in _dedup_done:
        try:
            result = await _svc(db).deduplicate_conversations(user_id=user_id)
            _dedup_done.add(user_id)
            if result.get("removed", 0) > 0:
                import structlog
                structlog.get_logger().info("auto_dedup_conversations", user_id=user_id, **result)
        except Exception:
            pass  # don't block inbox load if dedup fails

    rows, total = await _svc(db).get_inbox(
        user_id=user_id,
        filter_type=filter,
        search=search,
        limit=limit,
        offset=offset,
    )

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
            messages=list(r.messages) if r.messages else [],
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


# ── Messages sync ────────────────────────────────────────────────────────────


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
    result = await _svc(db).sync_messages(
        user_id=user_id,
        conversations=payload.conversations,
    )
    return MessagesSyncResponse(**result)


@router.post(
    "/messages/dedup",
    summary="Remove duplicate conversation rows (thread: vs urn: URNs)",
)
async def dedup_conversations(
    db: DB,
    user_id: CurrentUserId,
):
    result = await _svc(db).deduplicate_conversations(user_id=user_id)
    return result


# ── Extension v2: Job + Company ingest ───────────────────────────────────────


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
    result = await _svc(db).ingest_job(
        user_id=user_id,
        job=payload.job,
        source_url=payload.source_url,
    )
    return IngestJobResponse(**result)


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
    result = await _svc(db).ingest_jobs_bulk(
        user_id=user_id,
        jobs=payload.jobs,
    )
    return IngestJobsBulkResponse(**result)


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
    result = await _svc(db).ingest_company(
        user_id=user_id,
        company_name=payload.company.name,
    )
    return IngestCompanyResponse(**result)
