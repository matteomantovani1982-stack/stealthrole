"""
app/services/linkedin/linkedin_service.py

LinkedIn integration service.

Handles:
  - Bulk import of connections from browser extension
  - Mutual connection & network scan storage
  - Recruiter / hiring manager detection (rule-based, zero LLM cost)
  - Company matching (link connections to applications)
  - Conversation tracking & message sync
  - Inbox queries with filtering/search
  - Job & company intel ingestion
  - AI conversation analysis & network cross-referencing
  - CSV import parsing
  - Warm intro surfacing
"""

import csv
import io
import json
import re
import uuid
from collections import Counter
from datetime import UTC, datetime, timezone

import structlog
from sqlalchemy import delete as sa_delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.application import Application
from app.models.candidate_profile import CandidateProfile, ExperienceEntry, ProfileStatus
from app.models.hidden_signal import HiddenSignal
from app.models.linkedin_connection import LinkedInConnection
from app.models.linkedin_conversation import LinkedInConversation
from app.models.linkedin_message import LinkedInMessage
from app.models.mutual_connection import MutualConnection
from app.models.saved_job import SavedJob
from app.services.linkedin.message_classifier import classify_and_draft, heuristic_is_job_related
from app.services.llm.client import ClaudeClient
from app.services.llm.router import LLMTask
from app.services.profile.profile_service import ProfileService

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

    # ── Mutual connections ────────────────────────────────────────────────

    async def store_mutual_connections(
        self, user_id: str, target: dict, mutuals: list[dict], mutual_count: int = 0,
    ) -> dict:
        """
        Store mutual connection data scraped from a profile page.
        Resolves mutuals against the user's 1st-degree connections.
        """
        if not target.get("linkedin_id") or not mutuals:
            return {"stored": 0, "target": target.get("full_name", "")}

        # Build lookup of user's 1st-degree connections
        all_conns = (await self.db.execute(
            select(LinkedInConnection).where(LinkedInConnection.user_id == user_id)
        )).scalars().all()
        conn_by_name = {c.full_name.lower().strip(): c for c in all_conns}
        conn_by_url = {c.linkedin_url: c for c in all_conns if c.linkedin_url}

        stored = 0
        for m in mutuals:
            if not m.get("name"):
                continue

            resolved_id = m.get("linkedin_id") or ""
            resolved_url = m.get("linkedin_url") or ""

            # Match by LinkedIn URL first (most reliable), then by name
            matched_conn = conn_by_url.get(resolved_url) if resolved_url else None
            if not matched_conn:
                matched_conn = conn_by_name.get(m["name"].lower().strip())

            if matched_conn and matched_conn.linkedin_id:
                resolved_id = matched_conn.linkedin_id
                if not resolved_url and matched_conn.linkedin_url:
                    resolved_url = matched_conn.linkedin_url

            if not resolved_id:
                resolved_id = m["name"]

            # Check if already stored
            existing = (await self.db.execute(
                select(MutualConnection).where(
                    MutualConnection.user_id == user_id,
                    MutualConnection.target_linkedin_id == target["linkedin_id"],
                    or_(
                        MutualConnection.mutual_linkedin_id == resolved_id,
                        MutualConnection.mutual_name == m["name"],
                    ),
                )
            )).scalars().first()

            if existing:
                if matched_conn and matched_conn.linkedin_id and existing.mutual_linkedin_id != matched_conn.linkedin_id:
                    existing.mutual_linkedin_id = matched_conn.linkedin_id
                    existing.mutual_linkedin_url = matched_conn.linkedin_url or existing.mutual_linkedin_url
                continue

            self.db.add(MutualConnection(
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
            await self.db.flush()
            await self.db.commit()

        return {"stored": stored, "target": target.get("full_name", "")}

    async def ingest_network_scan(
        self, user_id: str, connector_url: str, connector_name: str,
        target_company: str, matches: list[dict],
    ) -> dict:
        """
        Store results of an on-demand network scan: connector's connections
        at a target company, stored as MutualConnections for find_way_in().
        """
        if not connector_url or not target_company or not matches:
            return {"stored": 0, "reason": "missing_required_fields"}

        # Find the connector in user's 1st-degree connections
        connector = None
        if connector_url:
            result = await self.db.execute(
                select(LinkedInConnection).where(
                    LinkedInConnection.user_id == user_id,
                    LinkedInConnection.linkedin_url == connector_url,
                ).limit(1)
            )
            connector = result.scalar_one_or_none()
        if not connector and connector_name:
            result = await self.db.execute(
                select(LinkedInConnection).where(
                    LinkedInConnection.user_id == user_id,
                )
            )
            for c in result.scalars().all():
                if c.full_name and c.full_name.lower().strip() == connector_name.lower().strip():
                    connector = c
                    break

        connector_linkedin_id = (
            connector.linkedin_id if connector
            else (connector_url.split("/in/")[-1].rstrip("/") if "/in/" in connector_url else connector_name.lower().replace(" ", "-"))
        )

        stored = 0
        for m in matches:
            target_name = (m.get("name") or "").strip()
            target_url = (m.get("linkedin_url") or "").strip()
            target_headline = (m.get("headline") or "").strip()
            if not target_name:
                continue

            target_lid = (
                target_url.split("/in/")[-1].rstrip("/") if "/in/" in target_url
                else target_name.lower().replace(" ", "-")
            )

            existing = (await self.db.execute(
                select(MutualConnection).where(
                    MutualConnection.user_id == user_id,
                    MutualConnection.target_linkedin_id == target_lid,
                    MutualConnection.mutual_linkedin_id == connector_linkedin_id,
                ).limit(1)
            )).scalar_one_or_none()
            if existing:
                continue

            self.db.add(MutualConnection(
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
            await self.db.flush()
            await self.db.commit()

        logger.info("network_scan_ingest", user_id=user_id, connector=connector_name,
                     target_company=target_company, stored=stored, total=len(matches))
        return {
            "stored": stored,
            "connector": connector_name,
            "target_company": target_company,
            "total_matches": len(matches),
        }

    async def deduplicate_mutual_connections(self, user_id: str) -> dict:
        """Remove duplicate mutual_connection records, keeping one per (target, mutual_name)."""
        all_records = (await self.db.execute(
            select(MutualConnection).where(MutualConnection.user_id == user_id)
            .order_by(MutualConnection.created_at)
        )).scalars().all()

        seen = set()
        to_delete = []
        for rec in all_records:
            key = (rec.target_linkedin_id, rec.mutual_name.lower().strip())
            if key in seen:
                to_delete.append(rec.id)
            else:
                seen.add(key)

        for did in to_delete:
            await self.db.execute(sa_delete(MutualConnection).where(MutualConnection.id == did))

        if to_delete:
            await self.db.flush()
            await self.db.commit()

        return {"deleted": len(to_delete), "remaining": len(seen)}

    # ── CSV import ───────────────────────────────────────────────────────

    def parse_linkedin_csv(self, csv_bytes: bytes) -> list[dict]:
        """
        Parse a LinkedIn Connections.csv export into a list of connection dicts
        ready for import_connections().
        """
        text = csv_bytes.decode("utf-8", errors="ignore")
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
        return connections

    # ── Conversation analysis (AI) ───────────────────────────────────────

    async def analyze_conversation(
        self, user_id: str, messages_text: str,
        context: str | None = None, tone: str = "professional",
    ) -> dict:
        """Analyze a LinkedIn conversation and draft a reply using Claude."""
        # Get user profile for context
        profile_svc = ProfileService(self.db)
        profile = await profile_svc.get_active_profile_orm(user_id)
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
{messages_text}

{f'CONTEXT: {context}' if context else ''}
{f'MY PROFILE: {profile_summary}' if profile_summary else ''}
TONE: {tone}

Analyze this conversation and draft a reply."""

        client = ClaudeClient(task=LLMTask.OUTREACH, max_tokens=2000)
        try:
            raw, result = client.call_text(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.3,
            )
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

    # ── Network analysis (AI) ────────────────────────────────────────────

    async def analyze_network(self, user_id: str) -> dict:
        """Cross-reference LinkedIn connections with profile, applications, and scout."""
        # 1. Get connections
        connections = (await self.db.execute(
            select(LinkedInConnection).where(LinkedInConnection.user_id == user_id).limit(2000)
        )).scalars().all()

        if not connections:
            return {"error": "No connections imported yet"}

        # 2. Get profile + experiences
        profile = (await self.db.execute(
            select(CandidateProfile).where(
                CandidateProfile.user_id == user_id,
                CandidateProfile.status == ProfileStatus.ACTIVE,
            )
        )).scalar_one_or_none()

        profile_summary = "No profile uploaded yet."
        if profile:
            experiences = (await self.db.execute(
                select(ExperienceEntry).where(ExperienceEntry.profile_id == profile.id)
            )).scalars().all()

            ctx = {}
            try:
                ctx = json.loads(profile.global_context or "{}")
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

        # 3. Get applications
        applications = (await self.db.execute(
            select(Application).where(Application.user_id == user_id)
            .order_by(Application.created_at.desc()).limit(20)
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
            elif any(k in tl for k in ["director", "vp", "vice president", "head of", "chief",
                                        "ceo", "coo", "cfo", "cto", "founder", "partner", "managing"]):
                decision_makers.append(f"{c.full_name} — {title} at {company}")

            if company and company.lower().strip() in target_companies:
                key = company.lower().strip()
                if key not in connections_at_target_companies:
                    connections_at_target_companies[key] = []
                connections_at_target_companies[key].append(f"{c.full_name} ({title})")

        target_overlap = ""
        if connections_at_target_companies:
            parts = [f"  {comp.title()}: {', '.join(people[:5])}"
                     for comp, people in connections_at_target_companies.items()]
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

        # 5. Send to Claude
        client = ClaudeClient(task=LLMTask.REPORT_PACK)
        system = ("You are a career strategist. You have access to someone's CV, their active job applications, "
                   "and their full LinkedIn network. Your job is to find the fastest path to getting them hired — "
                   "through warm intros, recruiter engagement, and strategic networking. Return only valid JSON.")

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
            return json.loads(text)
        except Exception as e:
            logger.error("network_analysis_failed", error=str(e))
            return {
                "network_strength": f"Network of {len(connections)} connections with {len(recruiters)} recruiters.",
                "warm_paths": [],
                "recruiter_strategy": [],
                "career_leverage": ["Cross-reference failed — try again"],
                "blind_spots": [],
                "recommendations": ["Try again later"],
                "warm_intro_potential": "",
            }

    # ── Inbox ────────────────────────────────────────────────────────────

    async def get_inbox(
        self, user_id: str, filter_type: str | None = None,
        search: str | None = None, limit: int = 50, offset: int = 0,
    ) -> tuple[list, int]:
        """
        Return conversation threads from linkedin_messages,
        ordered by last_message_at desc. Supports filtering and search.
        Returns (rows, total_count).
        """
        q = select(LinkedInMessage).where(LinkedInMessage.user_id == user_id)

        if filter_type == "job_related":
            q = q.where(LinkedInMessage.is_job_related == True)  # noqa: E712
        elif filter_type == "unread":
            q = q.where(LinkedInMessage.is_unread == True)  # noqa: E712
        elif filter_type == "recruiter":
            q = q.where(LinkedInMessage.classification == "recruiter")
        elif filter_type == "needs_reply":
            q = q.where(
                LinkedInMessage.last_sender == "them",
                LinkedInMessage.days_since_reply != None,  # noqa: E711
            )

        if search:
            pattern = f"%{search.strip().lower()}%"
            q = q.where(or_(
                func.lower(LinkedInMessage.contact_name).like(pattern),
                func.lower(LinkedInMessage.contact_title).like(pattern),
                func.lower(LinkedInMessage.contact_company).like(pattern),
            ))

        count_q = select(func.count()).select_from(q.subquery())
        total = (await self.db.execute(count_q)).scalar_one()

        q = q.order_by(
            func.coalesce(
                LinkedInMessage.last_message_at,
                LinkedInMessage.updated_at,
                LinkedInMessage.created_at,
            ).desc().nullslast()
        )
        q = q.offset(offset).limit(limit)
        rows = (await self.db.execute(q)).scalars().all()

        return rows, total

    # ── Messages sync ────────────────────────────────────────────────────

    async def sync_messages(
        self, user_id: str, conversations: list,
    ) -> dict:
        """
        Upsert full conversation threads scraped by the extension.
        Each conversation = one row in linkedin_messages with messages as JSONB.
        """
        recruiter_ids = set(
            (await self.db.execute(
                select(LinkedInConnection.linkedin_id).where(
                    LinkedInConnection.user_id == user_id,
                    LinkedInConnection.is_recruiter == True,  # noqa: E712
                )
            )).scalars().all()
        )

        created = 0
        updated = 0
        total_messages = 0

        for conv in conversations:
            msg_dicts = [m.model_dump() for m in conv.messages]
            total_messages += len(msg_dicts)

            known = bool(conv.contact_linkedin_id and conv.contact_linkedin_id in recruiter_ids)
            is_job_related = heuristic_is_job_related(
                contact_title=conv.contact_title,
                contact_company=conv.contact_company,
                messages=msg_dicts,
                known_recruiter=known,
            )

            ai = await classify_and_draft(
                contact_name=conv.contact_name,
                contact_title=conv.contact_title,
                contact_company=conv.contact_company,
                messages=msg_dicts,
            )

            last_at = _parse_dt(conv.last_message_at)
            days_since_reply: int | None = None
            if conv.last_sender == "them" and last_at:
                days_since_reply = (datetime.now(timezone.utc) - last_at).days

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
            await self.db.execute(stmt)

            existing = (await self.db.execute(
                select(LinkedInMessage.id).where(
                    LinkedInMessage.user_id == user_id,
                    LinkedInMessage.conversation_urn == conv.conversation_urn,
                )
            )).scalar_one_or_none()
            if existing:
                updated += 1
            else:
                created += 1

        await self.db.commit()

        logger.info(
            "linkedin_messages_sync_complete",
            user_id=user_id,
            conversations=len(conversations),
            total_messages=total_messages,
            classify_enabled=settings.enable_linkedin_msg_classify,
        )

        # Auto-deduplicate: remove legacy "thread:" rows that now have proper URN equivalents
        dedup_result = await self.deduplicate_conversations(user_id)

        return {
            "created": created,
            "updated": updated,
            "total_processed": len(conversations),
            "total_messages": total_messages,
            "classification_enabled": settings.enable_linkedin_msg_classify,
            "duplicates_removed": dedup_result.get("removed", 0),
        }

    async def deduplicate_conversations(self, user_id: str) -> dict:
        """
        Remove duplicate conversation rows.
        Duplicates arise when the same conversation was synced with different URN
        formats, e.g. 'thread:ABC' (DOM scrape) vs 'urn:li:fsd_conversation:ABC' (API).
        Keeps the row with the most messages; deletes the other.
        """
        all_rows = (await self.db.execute(
            select(
                LinkedInMessage.id,
                LinkedInMessage.conversation_urn,
                LinkedInMessage.message_count,
                LinkedInMessage.last_message_at,
                LinkedInMessage.contact_name,
            ).where(LinkedInMessage.user_id == user_id)
        )).all()

        # Build a map: normalized_key → list of (id, urn, message_count, last_message_at, contact_name)
        from collections import defaultdict
        groups = defaultdict(list)
        for row in all_rows:
            rid, urn, msg_count, last_at, name = row
            # Normalize: strip known prefixes to get the core thread ID
            key = urn
            key = key.replace("thread:", "")
            for prefix in [
                "urn:li:fsd_conversation:",
                "urn:li:fs_conversation:",
                "urn:li:msg_conversation:",
            ]:
                key = key.replace(prefix, "")
            # Also strip parentheses and extra wrapper chars from compound URNs
            # e.g. "(urn:li:fsd_profile:A,urn:li:fsd_profile:B)" → "urn:li:fsd_profile:A,urn:li:fsd_profile:B"
            key = key.strip("()")
            groups[key].append({
                "id": rid, "urn": urn, "msg_count": msg_count or 0,
                "last_at": last_at, "name": name,
            })

        to_delete = []
        for key, rows in groups.items():
            if len(rows) < 2:
                continue
            # Keep the best row: prefer most messages, then has name, then has timestamp
            rows.sort(key=lambda r: (
                r["msg_count"],
                1 if r["name"] else 0,
                r["last_at"] or "",
            ), reverse=True)
            # Delete all except the best
            for r in rows[1:]:
                to_delete.append(r["id"])

        if to_delete:
            await self.db.execute(
                sa_delete(LinkedInMessage).where(LinkedInMessage.id.in_(to_delete))
            )
            await self.db.commit()
            logger.info(
                "linkedin_conversations_deduped",
                user_id=user_id,
                removed=len(to_delete),
            )

        return {"removed": len(to_delete)}

    # ── Job ingestion ────────────────────────────────────────────────────

    async def ingest_job(
        self, user_id: str, job: "object", source_url: str | None = None,
    ) -> dict:
        """Upsert a job into saved_jobs. Dedupe by (user_id, source, external_id)."""
        external_id = job.linkedin_job_id or job.linkedin_url or job.title

        existing = (await self.db.execute(
            select(SavedJob.id).where(
                SavedJob.user_id == user_id,
                SavedJob.source == "linkedin",
                SavedJob.external_id == external_id,
            )
        )).scalar_one_or_none()

        if existing:
            logger.info("job_already_saved", user_id=user_id, job_id=external_id)
            return {"saved": True, "job_id": str(existing), "already_existed": True}

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
            "url": job.linkedin_url or source_url,
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
        stmt = stmt.on_conflict_do_nothing(constraint="uq_saved_job_user_source_ext")
        await self.db.execute(stmt)
        await self.db.commit()

        row = (await self.db.execute(
            select(SavedJob.id).where(
                SavedJob.user_id == user_id,
                SavedJob.source == "linkedin",
                SavedJob.external_id == external_id,
            )
        )).scalar_one_or_none()

        logger.info("job_ingested", user_id=user_id, title=job.title, company=job.company)
        return {"saved": True, "job_id": str(row) if row else None, "already_existed": False}

    async def ingest_jobs_bulk(
        self, user_id: str, jobs: list,
    ) -> dict:
        """Batch upsert jobs from a job search page. Skips duplicates."""
        saved = 0
        skipped = 0

        for job in jobs:
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
            result = await self.db.execute(stmt)

            if result.rowcount > 0:
                saved += 1
            else:
                skipped += 1

        await self.db.commit()
        logger.info("jobs_bulk_ingested", user_id=user_id, saved=saved, skipped=skipped)
        return {"saved": saved, "skipped": skipped}

    # ── Company intel ────────────────────────────────────────────────────

    async def ingest_company(
        self, user_id: str, company_name: str,
    ) -> dict:
        """
        Cross-reference company with user's connections and hidden market signals.
        Returns connection count and signal count.
        """
        company_lower = company_name.strip().lower()

        conn_count = (await self.db.execute(
            select(func.count()).where(
                LinkedInConnection.user_id == user_id,
                func.lower(LinkedInConnection.current_company).contains(company_lower),
            )
        )).scalar_one() or 0

        signal_count = 0
        try:
            signal_count = (await self.db.execute(
                select(func.count()).where(
                    HiddenSignal.user_id == user_id,
                    func.lower(HiddenSignal.company).contains(company_lower),
                )
            )).scalar_one() or 0
        except Exception:
            pass  # HiddenSignal table might not have a company column

        logger.info("company_intel_ingested", user_id=user_id, company=company_name,
                     connections=conn_count, signals=signal_count)

        return {
            "saved": True,
            "company_name": company_name,
            "connections_here": conn_count,
            "signals_count": signal_count,
        }

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


def _parse_dt(s: str | None) -> datetime | None:
    """Parse ISO-8601 or Unix-ms timestamp string."""
    if not s:
        return None
    try:
        if s.isdigit():
            return datetime.fromtimestamp(int(s) / 1000, tz=timezone.utc)
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def _parse_salary(salary_str: str | None) -> tuple[int | None, int | None]:
    """Best-effort parse salary range from strings like '$120K - $150K/yr'."""
    if not salary_str:
        return None, None
    nums = re.findall(r'[\$£€]?\s*([\d,]+)\s*[kK]?', salary_str)
    parsed = []
    for n in nums:
        try:
            val = int(n.replace(",", ""))
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
