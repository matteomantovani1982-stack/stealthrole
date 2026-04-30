"""
app/api/routes/applications.py

Kanban-style Application Tracker endpoints.

Routes:
  POST   /api/v1/applications              Create application
  GET    /api/v1/applications              List all applications
  GET    /api/v1/applications/board        Kanban board (grouped by stage)
  GET    /api/v1/applications/analytics    Conversion rates & source stats
  GET    /api/v1/applications/{id}         Get single application
  PATCH  /api/v1/applications/{id}         Update application
  PATCH  /api/v1/applications/{id}/stage   Move to new Kanban column
  DELETE /api/v1/applications/{id}         Delete application
"""

import uuid

from fastapi import APIRouter, HTTPException, Query, status

from app.dependencies import DB, CurrentUserId
from app.services.user_data_wipe import wipe_application_and_network_data
from app.schemas.application import (
    ApplicationAnalytics,
    ApplicationCreate,
    ApplicationListItem,
    ApplicationResponse,
    ApplicationStageUpdate,
    ApplicationUpdate,
    BoardResponse,
)
from app.services.applications.application_service import ApplicationService

router = APIRouter(
    prefix="/api/v1/applications",
    tags=["Application Tracker"],
)


def _svc(db: DB) -> ApplicationService:
    return ApplicationService(db=db)


# ── Testing reset (auth) ─────────────────────────────────────────────────────

@router.delete(
    "/wipe-all-for-testing",
    summary="Delete all applications + LinkedIn network sync for your account (irreversible)",
)
async def wipe_all_for_testing(
    db: DB,
    user_id: CurrentUserId,
    confirm: str = Query(
        ...,
        description="Must be exactly: WIPE_MY_DATA",
    ),
    include_intelligence: bool = Query(
        True,
        description="Also clear user_intelligence and email_intelligence rows",
    ),
) -> dict:
    """
    Clears Kanban applications (and cascaded interview/timeline rows), mutuals,
    LinkedIn connections/conversations/messages, warm intros, shadow apps,
    calendar events, scout/hidden/saved jobs, and auto-apply submissions/profile.

    Does not delete your login, CV files, or billing. Extension: re-sync connections after.
    """
    if confirm != "WIPE_MY_DATA":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pass query confirm=WIPE_MY_DATA",
        )
    deleted = await wipe_application_and_network_data(
        db,
        user_id,
        include_intelligence=include_intelligence,
    )
    return {"status": "wiped", "user_id": user_id, "deleted": deleted}


# ── Create ────────────────────────────────────────────────────────────────────

@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ApplicationResponse,
    summary="Add a new application to the tracker",
)
async def create_application(
    payload: ApplicationCreate,
    db: DB,
    user_id: CurrentUserId,
) -> ApplicationResponse:
    return await _svc(db).create(user_id=user_id, payload=payload)


# ── List ──────────────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=list[ApplicationListItem],
    summary="List all tracked applications",
)
async def list_applications(
    db: DB,
    user_id: CurrentUserId,
) -> list[ApplicationListItem]:
    return await _svc(db).list_all(user_id=user_id)


# ── Board (Kanban view) ──────────────────────────────────────────────────────

@router.get(
    "/board",
    response_model=BoardResponse,
    summary="Get Kanban board with applications grouped by stage",
)
async def get_board(
    db: DB,
    user_id: CurrentUserId,
) -> BoardResponse:
    return await _svc(db).get_board(user_id=user_id)


# ── Analytics ─────────────────────────────────────────────────────────────────

@router.get(
    "/analytics",
    response_model=ApplicationAnalytics,
    summary="Application analytics: conversion rates, time to interview, best source",
)
async def get_analytics(
    db: DB,
    user_id: CurrentUserId,
) -> ApplicationAnalytics:
    return await _svc(db).get_analytics(user_id=user_id)


# ── Get single ────────────────────────────────────────────────────────────────

@router.get(
    "/{app_id}",
    response_model=ApplicationResponse,
    summary="Get a single application",
)
async def get_application(
    app_id: uuid.UUID,
    db: DB,
    user_id: CurrentUserId,
) -> ApplicationResponse:
    result = await _svc(db).get(app_id=app_id, user_id=user_id)
    if not result:
        raise HTTPException(status_code=404, detail="Application not found")
    return result


# ── Update ────────────────────────────────────────────────────────────────────

@router.patch(
    "/{app_id}",
    response_model=ApplicationResponse,
    summary="Update an application",
)
async def update_application(
    app_id: uuid.UUID,
    payload: ApplicationUpdate,
    db: DB,
    user_id: CurrentUserId,
) -> ApplicationResponse:
    result = await _svc(db).update(app_id=app_id, user_id=user_id, payload=payload)
    if not result:
        raise HTTPException(status_code=404, detail="Application not found")
    return result


# ── Stage update (drag-and-drop) ─────────────────────────────────────────────

@router.patch(
    "/{app_id}/stage",
    response_model=ApplicationResponse,
    summary="Move application to a different Kanban column",
)
async def update_stage(
    app_id: uuid.UUID,
    payload: ApplicationStageUpdate,
    db: DB,
    user_id: CurrentUserId,
) -> ApplicationResponse:
    result = await _svc(db).update_stage(
        app_id=app_id, user_id=user_id, new_stage=payload.stage,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Application not found")
    return result


# ── Delete ────────────────────────────────────────────────────────────────────

@router.delete(
    "/{app_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an application",
)
async def delete_application(
    app_id: uuid.UUID,
    db: DB,
    user_id: CurrentUserId,
) -> None:
    deleted = await _svc(db).delete(app_id=app_id, user_id=user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Application not found")
