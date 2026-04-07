"""
app/services/linkedin/linkedin_service.py

LinkedIn integration service.

Handles:
  - Bulk import of connections from browser extension
  - Recruiter / hiring manager detection (rule-based, zero LLM cost)
  - Company matching (link connections to applications)
  - Conversation tracking
  - Warm intro surfacing
"""

import re
import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.models.linkedin_connection import LinkedInConnection
from app.models.linkedin_conversation import LinkedInConversation

logger = structlog.get_logger(__name__)

# ── Recruiter detection keywords ─────────────────────────────────────────────

_RECRUITER_TITLES = [
    "recruiter", "recruiting", "talent acquisition", "talent partner",
    "talent scout", "sourcer", "sourcing", "staffing", "hr partner",
    "human resources", "people operations", "employer brand",
    "recruitment", "headhunter",
]

_HIRING_MANAGER_TITLES = [
    "director", "head of", "vp ", "vice president", "senior director",
    "chief", "ceo", "cto", "coo", "cfo", "cmo", "managing director",
    "general manager", "partner", "principal",
    "engineering manager", "product manager", "design manager",
    "senior manager", "group manager", "staff manager",
]


def _is_recruiter(title: str | None, headline: str | None) -> bool:
    """Detect if a person is a recruiter based on title/headline."""
    text = f"{title or ''} {headline or ''}".lower()
    return any(kw in text for kw in _RECRUITER_TITLES)


def _is_hiring_manager(title: str | None, headline: str | None) -> bool:
    """Detect if a person is likely a hiring manager (senior title)."""
    text = f"{title or ''} {headline or ''}".lower()
    if _is_recruiter(title, headline):
        return False  # Recruiters are not hiring managers
    return any(kw in text for kw in _HIRING_MANAGER_TITLES)


class LinkedInService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Bulk import (from extension) ──────────────────────────────────────

    async def import_connections(
        self, user_id: str, connections: list[dict]
    ) -> dict:
        """
        Bulk import connections pushed by the browser extension.
        Upserts by linkedin_id — updates existing, creates new.
        Returns import stats.
        """
        created = 0
        updated = 0
        recruiters = 0

        for conn in connections:
            linkedin_id = conn.get("linkedin_id") or conn.get("linkedin_url", "")
            if not linkedin_id and not conn.get("full_name"):
                continue

            # Check for existing
            existing = None
            if linkedin_id:
                result = await self.db.execute(
                    select(LinkedInConnection).where(
                        LinkedInConnection.user_id == user_id,
                        LinkedInConnection.linkedin_id == linkedin_id,
                    )
                )
                existing = result.scalar_one_or_none()

            title = conn.get("current_title") or conn.get("title")
            headline = conn.get("headline")
            is_rec = _is_recruiter(title, headline)
            is_hm = _is_hiring_manager(title, headline)

            if existing:
                # Update
                existing.full_name = conn.get("full_name", existing.full_name)
                existing.headline = headline or existing.headline
                existing.current_title = title or existing.current_title
                existing.current_company = conn.get("current_company") or conn.get("company") or existing.current_company
                existing.location = conn.get("location") or existing.location
                existing.linkedin_url = conn.get("linkedin_url") or existing.linkedin_url
                existing.profile_image_url = conn.get("profile_image_url") or existing.profile_image_url
                existing.is_recruiter = is_rec
                existing.is_hiring_manager = is_hm
                updated += 1
            else:
                lc = LinkedInConnection(
                    user_id=user_id,
                    linkedin_id=linkedin_id or None,
                    linkedin_url=conn.get("linkedin_url"),
                    full_name=conn.get("full_name", "Unknown"),
                    headline=headline,
                    current_title=title,
                    current_company=conn.get("current_company") or conn.get("company"),
                    location=conn.get("location"),
                    profile_image_url=conn.get("profile_image_url"),
                    connected_at=_parse_date(conn.get("connected_at")),
                    is_recruiter=is_rec,
                    is_hiring_manager=is_hm,
                    relationship_strength=conn.get("relationship_strength", "medium"),
                )
                self.db.add(lc)
                created += 1

            if is_rec:
                recruiters += 1

        await self.db.flush()
        await self.db.commit()

        # Auto-match to applications
        matched = await self._auto_match_applications(user_id)

        logger.info(
            "linkedin_import_done",
            user_id=user_id,
            created=created,
            updated=updated,
            recruiters=recruiters,
            matched=matched,
        )

        return {
            "created": created,
            "updated": updated,
            "total_processed": len(connections),
            "recruiters_detected": recruiters,
            "applications_matched": matched,
        }

    # ── Queries ───────────────────────────────────────────────────────────

    async def list_connections(
        self, user_id: str, company: str | None = None, recruiters_only: bool = False,
    ) -> list[LinkedInConnection]:
        query = select(LinkedInConnection).where(
            LinkedInConnection.user_id == user_id
        )
        if company:
            query = query.where(
                LinkedInConnection.current_company.ilike(f"%{company}%")
            )
        if recruiters_only:
            query = query.where(LinkedInConnection.is_recruiter == True)  # noqa: E712
        query = query.order_by(LinkedInConnection.full_name)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_recruiters(self, user_id: str) -> list[LinkedInConnection]:
        return await self.list_connections(user_id, recruiters_only=True)

    async def get_connections_at_company(
        self, user_id: str, company: str
    ) -> list[LinkedInConnection]:
        """Find all connections at a target company — for warm intros."""
        return await self.list_connections(user_id, company=company)

    async def get_stats(self, user_id: str) -> dict:
        """Quick stats for dashboard."""
        total = (await self.db.execute(
            select(func.count()).where(LinkedInConnection.user_id == user_id)
        )).scalar() or 0
        recruiters = (await self.db.execute(
            select(func.count()).where(
                LinkedInConnection.user_id == user_id,
                LinkedInConnection.is_recruiter == True,  # noqa: E712
            )
        )).scalar() or 0
        companies = (await self.db.execute(
            select(func.count(func.distinct(LinkedInConnection.current_company)))
            .where(
                LinkedInConnection.user_id == user_id,
                LinkedInConnection.current_company.isnot(None),
            )
        )).scalar() or 0

        return {
            "total_connections": total,
            "recruiters": recruiters,
            "unique_companies": companies,
        }

    # ── Conversations ─────────────────────────────────────────────────────

    async def add_conversation(
        self, user_id: str, messages: list[dict]
    ) -> int:
        """
        Import conversation messages from extension.
        Messages should have: sender_name, message_text, sent_at, direction,
        thread_id (optional), linkedin_id (optional for connection matching).
        """
        added = 0
        for msg in messages:
            # Try to match to a connection
            connection_id = None
            linkedin_id = msg.get("linkedin_id")
            if linkedin_id:
                result = await self.db.execute(
                    select(LinkedInConnection.id).where(
                        LinkedInConnection.user_id == user_id,
                        LinkedInConnection.linkedin_id == linkedin_id,
                    )
                )
                row = result.first()
                if row:
                    connection_id = row[0]

            conv = LinkedInConversation(
                user_id=user_id,
                connection_id=connection_id,
                thread_id=msg.get("thread_id"),
                direction=msg.get("direction", "inbound"),
                sender_name=msg.get("sender_name", "Unknown"),
                message_text=msg.get("message_text", ""),
                sent_at=_parse_date(msg.get("sent_at")) or datetime.now(UTC),
            )
            self.db.add(conv)
            added += 1

        await self.db.flush()
        await self.db.commit()
        return added

    async def list_conversations(
        self, user_id: str, connection_id: uuid.UUID | None = None,
        application_id: uuid.UUID | None = None,
    ) -> list[LinkedInConversation]:
        query = select(LinkedInConversation).where(
            LinkedInConversation.user_id == user_id
        )
        if connection_id:
            query = query.where(LinkedInConversation.connection_id == connection_id)
        if application_id:
            query = query.where(LinkedInConversation.application_id == application_id)
        query = query.order_by(LinkedInConversation.sent_at.desc()).limit(50)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def link_conversation_to_application(
        self, user_id: str, thread_id: str, application_id: uuid.UUID
    ) -> int:
        """Link all messages in a thread to an application."""
        result = await self.db.execute(
            select(LinkedInConversation).where(
                LinkedInConversation.user_id == user_id,
                LinkedInConversation.thread_id == thread_id,
            )
        )
        messages = result.scalars().all()
        for msg in messages:
            msg.application_id = application_id
        await self.db.commit()
        return len(messages)

    # ── Auto-matching ─────────────────────────────────────────────────────

    async def _auto_match_applications(self, user_id: str) -> int:
        """
        Auto-match connections to applications by company name.
        Runs after import — links connections at companies where user has applied.
        """
        # Get all user applications with company names
        apps = (await self.db.execute(
            select(Application).where(Application.user_id == user_id)
        )).scalars().all()

        if not apps:
            return 0

        matched = 0
        for app in apps:
            company = app.company.lower().strip()
            if not company:
                continue

            # Find unmatched connections at this company
            result = await self.db.execute(
                select(LinkedInConnection).where(
                    LinkedInConnection.user_id == user_id,
                    LinkedInConnection.matched_application_id.is_(None),
                    LinkedInConnection.current_company.isnot(None),
                    func.lower(LinkedInConnection.current_company).contains(company),
                )
            )
            for conn in result.scalars().all():
                conn.matched_application_id = app.id
                matched += 1

        if matched:
            await self.db.flush()
            await self.db.commit()

        return matched


def _parse_date(val: str | None) -> datetime | None:
    """Parse a date string, return None on failure."""
    if not val:
        return None
    try:
        return datetime.fromisoformat(val.replace("Z", "+00:00"))
    except Exception:
        return None
