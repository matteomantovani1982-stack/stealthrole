"""
app/services/calendar/crm_service.py

Follow-Up CRM service — timeline management, follow-up scheduling,
calendar sync, and AI next-action suggestions.
"""

import uuid
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.models.application_timeline import ApplicationTimeline
from app.models.calendar_event import CalendarEvent
from app.models.email_account import EmailAccount

logger = structlog.get_logger(__name__)


class CRMService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Timeline CRUD ─────────────────────────────────────────────────────

    async def add_event(
        self,
        application_id: uuid.UUID,
        user_id: str,
        event_type: str,
        event_date: datetime,
        title: str,
        notes: str | None = None,
        contact_person: str | None = None,
        contact_email: str | None = None,
        contact_role: str | None = None,
        next_action: str | None = None,
        next_action_date: datetime | None = None,
        source: str = "manual",
        source_ref: str | None = None,
    ) -> ApplicationTimeline:
        """Add a timeline event to an application."""
        # Verify application belongs to user
        app = await self._get_application(application_id, user_id)
        if not app:
            raise ValueError("Application not found")

        event = ApplicationTimeline(
            application_id=application_id,
            event_type=event_type,
            event_date=event_date,
            title=title,
            notes=notes,
            contact_person=contact_person,
            contact_email=contact_email,
            contact_role=contact_role,
            next_action=next_action,
            next_action_date=next_action_date,
            source=source,
            source_ref=source_ref,
        )
        self.db.add(event)
        await self.db.flush()
        await self.db.commit()
        await self.db.refresh(event)
        return event

    async def get_timeline(
        self, application_id: uuid.UUID, user_id: str
    ) -> list[ApplicationTimeline]:
        """Get full timeline for an application, chronological."""
        app = await self._get_application(application_id, user_id)
        if not app:
            return []

        result = await self.db.execute(
            select(ApplicationTimeline)
            .where(ApplicationTimeline.application_id == application_id)
            .order_by(ApplicationTimeline.event_date.asc())
        )
        return list(result.scalars().all())

    async def update_event(
        self,
        event_id: uuid.UUID,
        user_id: str,
        **fields,
    ) -> ApplicationTimeline | None:
        """Update a timeline event."""
        event = await self._get_user_event(event_id, user_id)
        if not event:
            return None

        for field, value in fields.items():
            if hasattr(event, field) and value is not None:
                setattr(event, field, value)

        await self.db.flush()
        await self.db.commit()
        await self.db.refresh(event)
        return event

    async def delete_event(self, event_id: uuid.UUID, user_id: str) -> bool:
        event = await self._get_user_event(event_id, user_id)
        if not event:
            return False
        await self.db.delete(event)
        await self.db.commit()
        return True

    # ── Follow-up reminders ───────────────────────────────────────────────

    async def get_pending_followups(
        self, user_id: str, days_ahead: int = 7
    ) -> list[ApplicationTimeline]:
        """Get timeline events with pending follow-ups in the next N days."""
        cutoff = datetime.now(UTC) + timedelta(days=days_ahead)
        result = await self.db.execute(
            select(ApplicationTimeline)
            .join(Application, ApplicationTimeline.application_id == Application.id)
            .where(
                Application.user_id == user_id,
                ApplicationTimeline.next_action_date.isnot(None),
                ApplicationTimeline.next_action_date <= cutoff,
                ApplicationTimeline.follow_up_sent == False,  # noqa: E712
            )
            .order_by(ApplicationTimeline.next_action_date.asc())
        )
        return list(result.scalars().all())

    async def get_overdue_followups(self, user_id: str) -> list[ApplicationTimeline]:
        """Get follow-ups that are past due."""
        now = datetime.now(UTC)
        result = await self.db.execute(
            select(ApplicationTimeline)
            .join(Application, ApplicationTimeline.application_id == Application.id)
            .where(
                Application.user_id == user_id,
                ApplicationTimeline.next_action_date.isnot(None),
                ApplicationTimeline.next_action_date < now,
                ApplicationTimeline.follow_up_sent == False,  # noqa: E712
            )
            .order_by(ApplicationTimeline.next_action_date.asc())
        )
        return list(result.scalars().all())

    async def mark_followup_sent(self, event_id: uuid.UUID) -> None:
        """Mark a follow-up reminder as sent."""
        result = await self.db.execute(
            select(ApplicationTimeline).where(ApplicationTimeline.id == event_id)
        )
        event = result.scalar_one_or_none()
        if event:
            event.follow_up_sent = True
            await self.db.commit()

    # ── Calendar events ───────────────────────────────────────────────────

    async def list_calendar_events(
        self, user_id: str, include_dismissed: bool = False
    ) -> list[CalendarEvent]:
        query = (
            select(CalendarEvent)
            .where(CalendarEvent.user_id == user_id)
        )
        if not include_dismissed:
            query = query.where(CalendarEvent.is_dismissed == False)  # noqa: E712
        query = query.order_by(CalendarEvent.start_time.desc())

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def link_calendar_event(
        self, event_id: uuid.UUID, user_id: str, application_id: uuid.UUID
    ) -> CalendarEvent | None:
        """Link a calendar event to an application."""
        result = await self.db.execute(
            select(CalendarEvent).where(
                CalendarEvent.id == event_id,
                CalendarEvent.user_id == user_id,
            )
        )
        event = result.scalar_one_or_none()
        if not event:
            return None

        event.application_id = application_id
        await self.db.commit()
        await self.db.refresh(event)

        # Also add a timeline event
        await self.add_event(
            application_id=application_id,
            user_id=user_id,
            event_type=event.interview_round or "interview",
            event_date=event.start_time,
            title=event.title,
            contact_person=event.organizer_email,
            source="calendar",
            source_ref=event.provider_event_id,
        )

        return event

    # ── Next action suggestions ───────────────────────────────────────────

    async def suggest_next_action(
        self, application_id: uuid.UUID, user_id: str
    ) -> dict:
        """
        AI-lite next action suggestion based on timeline state.
        Rule-based for now (no LLM call = no cost).
        """
        app = await self._get_application(application_id, user_id)
        if not app:
            return {"action": "Application not found", "urgency": "none"}

        timeline = await self.get_timeline(application_id, user_id)
        stage = app.stage
        days_since_last = 0
        if timeline:
            last_event = timeline[-1]
            days_since_last = (datetime.now(UTC) - last_event.event_date.replace(tzinfo=UTC if last_event.event_date.tzinfo is None else last_event.event_date.tzinfo)).days

        # Rule-based suggestions
        if stage == "applied":
            if days_since_last >= 7:
                return {
                    "action": "Follow up on your application — it's been a week",
                    "urgency": "medium",
                    "suggested_date": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
                    "template": "follow_up_after_apply",
                }
            return {
                "action": "Wait for response — follow up in a few days if no reply",
                "urgency": "low",
                "suggested_date": (datetime.now(UTC) + timedelta(days=3)).isoformat(),
            }

        if stage == "interview":
            if days_since_last >= 3:
                return {
                    "action": "Send a thank-you note if you haven't already",
                    "urgency": "high",
                    "suggested_date": datetime.now(UTC).isoformat(),
                    "template": "thank_you_after_interview",
                }
            return {
                "action": "Prepare for next round — review company intel and interview prep",
                "urgency": "medium",
            }

        if stage == "offer":
            return {
                "action": "Review the offer, prepare negotiation points",
                "urgency": "high",
                "template": "offer_negotiation",
            }

        if stage == "rejected":
            return {
                "action": "Send a gracious thank-you — keep the door open for future roles",
                "urgency": "low",
                "template": "post_rejection_thank_you",
            }

        return {"action": "No specific action needed right now", "urgency": "none"}

    # ── Dashboard aggregation ─────────────────────────────────────────────

    async def get_crm_summary(self, user_id: str) -> dict:
        """Summary for the dashboard: upcoming events, overdue follow-ups."""
        overdue = await self.get_overdue_followups(user_id)
        upcoming = await self.get_pending_followups(user_id, days_ahead=7)
        calendar = await self.list_calendar_events(user_id)

        # Upcoming interviews (next 7 days)
        now = datetime.now(UTC)
        upcoming_interviews = [
            e for e in calendar
            if e.start_time > now and e.start_time < now + timedelta(days=7)
        ]

        return {
            "overdue_followups": len(overdue),
            "upcoming_followups": len(upcoming),
            "upcoming_interviews": len(upcoming_interviews),
            "next_interview": upcoming_interviews[0].start_time.isoformat() if upcoming_interviews else None,
        }

    # ── Helpers ───────────────────────────────────────────────────────────

    async def _get_application(
        self, app_id: uuid.UUID, user_id: str
    ) -> Application | None:
        result = await self.db.execute(
            select(Application).where(
                Application.id == app_id,
                Application.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def _get_user_event(
        self, event_id: uuid.UUID, user_id: str
    ) -> ApplicationTimeline | None:
        result = await self.db.execute(
            select(ApplicationTimeline)
            .join(Application, ApplicationTimeline.application_id == Application.id)
            .where(
                ApplicationTimeline.id == event_id,
                Application.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()
