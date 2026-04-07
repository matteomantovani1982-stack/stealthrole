"""
app/services/timeline.py

Thin helper to log ApplicationEvents.
Call from routes (async) or workers (sync).
"""

import uuid
from datetime import UTC, datetime


async def log_event_async(db, job_run_id: uuid.UUID, event_type: str, title: str, detail: str | None = None):
    """Log a timeline event from an async context (FastAPI routes)."""
    from app.models.application_event import ApplicationEvent
    ev = ApplicationEvent(
        job_run_id=job_run_id,
        event_type=event_type,
        title=title,
        detail=detail,
    )
    db.add(ev)
    await db.flush()


def log_event_sync(job_run_id: uuid.UUID, event_type: str, title: str, detail: str | None = None):
    """Log a timeline event from a sync context (Celery workers)."""
    from app.models.application_event import ApplicationEvent
    from app.workers.db_utils import get_sync_db
    with get_sync_db() as db:
        ev = ApplicationEvent(
            job_run_id=job_run_id,
            event_type=event_type,
            title=title,
            detail=detail,
        )
        db.add(ev)
        db.commit()
