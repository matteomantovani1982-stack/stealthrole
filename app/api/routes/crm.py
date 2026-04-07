"""
app/api/routes/crm.py

Interview + Follow-Up CRM endpoints.

Integrates with the Application Tracker — adds timeline, follow-ups,
calendar events, and next-action suggestions.

Routes:
  # Timeline
  POST   /api/v1/crm/applications/{id}/timeline        Add timeline event
  GET    /api/v1/crm/applications/{id}/timeline        Get full timeline
  PATCH  /api/v1/crm/timeline/{event_id}               Update event
  DELETE /api/v1/crm/timeline/{event_id}               Delete event

  # Follow-ups
  GET    /api/v1/crm/followups                         List pending + overdue
  GET    /api/v1/crm/applications/{id}/next-action     AI next-action suggestion

  # Calendar
  GET    /api/v1/crm/calendar                          List detected interview events
  POST   /api/v1/crm/calendar/{id}/link                Link to application

  # Summary
  GET    /api/v1/crm/summary                           Dashboard CRM summary
"""

import uuid

from fastapi import APIRouter, HTTPException, status

from app.dependencies import DB, CurrentUserId
from app.schemas.crm import (
    CalendarEventResponse,
    CRMSummaryResponse,
    FollowUpListResponse,
    LinkCalendarEventRequest,
    NextActionResponse,
    TimelineEventCreate,
    TimelineEventResponse,
    TimelineEventUpdate,
)
from app.services.calendar.crm_service import CRMService

router = APIRouter(prefix="/api/v1/crm", tags=["CRM"])


def _svc(db: DB) -> CRMService:
    return CRMService(db=db)


# ── Timeline ──────────────────────────────────────────────────────────────────

@router.post(
    "/applications/{app_id}/timeline",
    status_code=status.HTTP_201_CREATED,
    response_model=TimelineEventResponse,
    summary="Add a timeline event to an application",
)
async def add_timeline_event(
    app_id: uuid.UUID,
    payload: TimelineEventCreate,
    db: DB,
    user_id: CurrentUserId,
) -> TimelineEventResponse:
    try:
        event = await _svc(db).add_event(
            application_id=app_id,
            user_id=user_id,
            event_type=payload.event_type,
            event_date=payload.event_date,
            title=payload.title,
            notes=payload.notes,
            contact_person=payload.contact_person,
            contact_email=payload.contact_email,
            contact_role=payload.contact_role,
            next_action=payload.next_action,
            next_action_date=payload.next_action_date,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return TimelineEventResponse.model_validate(event)


@router.get(
    "/applications/{app_id}/timeline",
    response_model=list[TimelineEventResponse],
    summary="Get application timeline",
)
async def get_timeline(
    app_id: uuid.UUID,
    db: DB,
    user_id: CurrentUserId,
) -> list[TimelineEventResponse]:
    events = await _svc(db).get_timeline(app_id, user_id)
    return [TimelineEventResponse.model_validate(e) for e in events]


@router.patch(
    "/timeline/{event_id}",
    response_model=TimelineEventResponse,
    summary="Update a timeline event",
)
async def update_timeline_event(
    event_id: uuid.UUID,
    payload: TimelineEventUpdate,
    db: DB,
    user_id: CurrentUserId,
) -> TimelineEventResponse:
    event = await _svc(db).update_event(
        event_id=event_id,
        user_id=user_id,
        **payload.model_dump(exclude_unset=True),
    )
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return TimelineEventResponse.model_validate(event)


@router.delete(
    "/timeline/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a timeline event",
)
async def delete_timeline_event(
    event_id: uuid.UUID,
    db: DB,
    user_id: CurrentUserId,
) -> None:
    deleted = await _svc(db).delete_event(event_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Event not found")


# ── Follow-ups ────────────────────────────────────────────────────────────────

@router.get(
    "/followups",
    response_model=FollowUpListResponse,
    summary="List pending and overdue follow-ups",
)
async def list_followups(
    db: DB,
    user_id: CurrentUserId,
) -> FollowUpListResponse:
    svc = _svc(db)
    overdue = await svc.get_overdue_followups(user_id)
    upcoming = await svc.get_pending_followups(user_id)
    return FollowUpListResponse(
        overdue=[TimelineEventResponse.model_validate(e) for e in overdue],
        upcoming=[TimelineEventResponse.model_validate(e) for e in upcoming],
        total_overdue=len(overdue),
        total_upcoming=len(upcoming),
    )


@router.get(
    "/applications/{app_id}/next-action",
    response_model=NextActionResponse,
    summary="Get AI-suggested next action for an application",
)
async def get_next_action(
    app_id: uuid.UUID,
    db: DB,
    user_id: CurrentUserId,
) -> NextActionResponse:
    result = await _svc(db).suggest_next_action(app_id, user_id)
    return NextActionResponse(**result)


# ── Calendar ──────────────────────────────────────────────────────────────────

@router.get(
    "/calendar",
    response_model=list[CalendarEventResponse],
    summary="List detected interview events from calendar",
)
async def list_calendar_events(
    db: DB,
    user_id: CurrentUserId,
    include_dismissed: bool = False,
) -> list[CalendarEventResponse]:
    events = await _svc(db).list_calendar_events(user_id, include_dismissed)
    return [CalendarEventResponse.model_validate(e) for e in events]


@router.post(
    "/calendar/{event_id}/link",
    response_model=CalendarEventResponse,
    summary="Link a calendar event to an application",
)
async def link_calendar_event(
    event_id: uuid.UUID,
    payload: LinkCalendarEventRequest,
    db: DB,
    user_id: CurrentUserId,
) -> CalendarEventResponse:
    event = await _svc(db).link_calendar_event(
        event_id=event_id, user_id=user_id, application_id=payload.application_id,
    )
    if not event:
        raise HTTPException(status_code=404, detail="Calendar event not found")
    return CalendarEventResponse.model_validate(event)


# ── Summary ───────────────────────────────────────────────────────────────────

@router.get(
    "/summary",
    response_model=CRMSummaryResponse,
    summary="CRM dashboard summary",
)
async def crm_summary(
    db: DB,
    user_id: CurrentUserId,
) -> CRMSummaryResponse:
    result = await _svc(db).get_crm_summary(user_id)
    return CRMSummaryResponse(**result)
