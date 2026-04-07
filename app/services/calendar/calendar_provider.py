"""
app/services/calendar/calendar_provider.py

Fetch interview-related events from Google Calendar / Outlook Calendar.

Reuses OAuth tokens from the email_accounts table (same Google/Microsoft OAuth).
Requires additional scopes:
  Google:    https://www.googleapis.com/auth/calendar.readonly
  Microsoft: Calendars.Read

Filters events by keyword to only return interview-related entries.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, UTC, timedelta

import httpx
import structlog

logger = structlog.get_logger(__name__)

TIMEOUT = 15.0

# Keywords that indicate an event is interview-related
_INTERVIEW_KEYWORDS = [
    "interview", "screening", "phone screen", "technical round",
    "onsite", "on-site", "final round", "panel", "case study",
    "hiring", "recruitment", "career", "job", "assessment",
    "meet the team", "culture fit",
]

# Patterns to detect interview round
_ROUND_PATTERNS = [
    (r"phone\s*screen", "phone_screen"),
    (r"(1st|first|round\s*1)", "round_1"),
    (r"(2nd|second|round\s*2)", "round_2"),
    (r"(3rd|third|round\s*3)", "round_3"),
    (r"technical", "technical"),
    (r"on-?site", "onsite"),
    (r"final", "final"),
]


@dataclass
class CalendarEventData:
    """Normalized calendar event from any provider."""
    provider_event_id: str
    title: str
    description: str
    start_time: datetime
    end_time: datetime | None
    location: str
    organizer_email: str
    attendees: list[str]
    detected_company: str | None
    detected_role: str | None
    interview_round: str | None


def _is_interview_event(title: str, description: str) -> bool:
    """Check if a calendar event looks interview-related."""
    text = f"{title} {description}".lower()
    return any(kw in text for kw in _INTERVIEW_KEYWORDS)


def _detect_round(title: str, description: str) -> str | None:
    """Detect interview round from event text."""
    text = f"{title} {description}".lower()
    for pattern, round_name in _ROUND_PATTERNS:
        if re.search(pattern, text):
            return round_name
    return None


def _extract_company_from_event(
    title: str, organizer_email: str, description: str
) -> str | None:
    """Best-effort company extraction from calendar event."""
    # "Interview with Google" / "Google - Technical Round"
    for pattern in [
        r"(?:interview|call|meeting)\s+(?:with|at|@)\s+([A-Z][\w\s&.-]+)",
        r"^([A-Z][\w\s&.-]+?)\s*[-–|:]\s*(?:interview|round|screen)",
    ]:
        m = re.search(pattern, title, re.IGNORECASE)
        if m:
            return m.group(1).strip()

    # Fallback: organizer domain
    if organizer_email and "@" in organizer_email:
        domain = organizer_email.split("@")[1].split(".")[0]
        if domain not in ("gmail", "outlook", "hotmail", "yahoo", "google"):
            return domain.capitalize()

    return None


# ── Google Calendar ───────────────────────────────────────────────────────────

GCAL_API = "https://www.googleapis.com/calendar/v3"


async def fetch_google_calendar_events(
    access_token: str,
    days_ahead: int = 30,
    days_back: int = 14,
    max_results: int = 50,
) -> list[CalendarEventData]:
    """Fetch interview-related events from Google Calendar."""
    now = datetime.now(UTC)
    time_min = (now - timedelta(days=days_back)).isoformat()
    time_max = (now + timedelta(days=days_ahead)).isoformat()

    events = []
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(
            f"{GCAL_API}/calendars/primary/events",
            headers={"Authorization": f"Bearer {access_token}"},
            params={
                "timeMin": time_min,
                "timeMax": time_max,
                "maxResults": max_results,
                "singleEvents": "true",
                "orderBy": "startTime",
            },
        )
        if resp.status_code != 200:
            logger.warning("gcal_fetch_failed", status=resp.status_code)
            return []

        data = resp.json()
        for item in data.get("items", []):
            title = item.get("summary", "")
            desc = item.get("description", "")

            if not _is_interview_event(title, desc):
                continue

            start = item.get("start", {})
            end = item.get("end", {})
            start_dt = _parse_gcal_datetime(start)
            end_dt = _parse_gcal_datetime(end)
            if not start_dt:
                continue

            organizer = item.get("organizer", {}).get("email", "")
            attendee_emails = [
                a.get("email", "")
                for a in item.get("attendees", [])
                if a.get("email")
            ]

            events.append(CalendarEventData(
                provider_event_id=item.get("id", ""),
                title=title,
                description=desc[:500],
                start_time=start_dt,
                end_time=end_dt,
                location=item.get("location", ""),
                organizer_email=organizer,
                attendees=attendee_emails,
                detected_company=_extract_company_from_event(title, organizer, desc),
                detected_role=None,
                interview_round=_detect_round(title, desc),
            ))

    logger.info("gcal_fetch_done", count=len(events))
    return events


def _parse_gcal_datetime(dt_obj: dict) -> datetime | None:
    """Parse Google Calendar dateTime or date field."""
    raw = dt_obj.get("dateTime") or dt_obj.get("date")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return None


# ── Outlook Calendar ──────────────────────────────────────────────────────────

GRAPH_API = "https://graph.microsoft.com/v1.0"


async def fetch_outlook_calendar_events(
    access_token: str,
    days_ahead: int = 30,
    days_back: int = 14,
    max_results: int = 50,
) -> list[CalendarEventData]:
    """Fetch interview-related events from Outlook Calendar via Graph API."""
    now = datetime.now(UTC)
    time_min = (now - timedelta(days=days_back)).isoformat() + "Z"
    time_max = (now + timedelta(days=days_ahead)).isoformat() + "Z"

    events = []
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(
            f"{GRAPH_API}/me/calendarView",
            headers={"Authorization": f"Bearer {access_token}"},
            params={
                "startDateTime": time_min,
                "endDateTime": time_max,
                "$top": max_results,
                "$select": "id,subject,bodyPreview,start,end,location,organizer,attendees",
                "$orderby": "start/dateTime",
            },
        )
        if resp.status_code != 200:
            logger.warning("outlook_cal_fetch_failed", status=resp.status_code)
            return []

        data = resp.json()
        for item in data.get("value", []):
            title = item.get("subject", "")
            desc = item.get("bodyPreview", "")

            if not _is_interview_event(title, desc):
                continue

            start_raw = item.get("start", {}).get("dateTime", "")
            end_raw = item.get("end", {}).get("dateTime", "")

            try:
                start_dt = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
            except Exception:
                continue
            try:
                end_dt = datetime.fromisoformat(end_raw.replace("Z", "+00:00"))
            except Exception:
                end_dt = None

            organizer = item.get("organizer", {}).get("emailAddress", {}).get("address", "")
            attendee_emails = [
                a.get("emailAddress", {}).get("address", "")
                for a in item.get("attendees", [])
                if a.get("emailAddress", {}).get("address")
            ]
            location = item.get("location", {}).get("displayName", "")

            events.append(CalendarEventData(
                provider_event_id=item.get("id", ""),
                title=title,
                description=desc[:500],
                start_time=start_dt,
                end_time=end_dt,
                location=location,
                organizer_email=organizer,
                attendees=attendee_emails,
                detected_company=_extract_company_from_event(title, organizer, desc),
                detected_role=None,
                interview_round=_detect_round(title, desc),
            ))

    logger.info("outlook_cal_fetch_done", count=len(events))
    return events
