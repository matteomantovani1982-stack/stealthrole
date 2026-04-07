"""
app/workers/tasks/email_sync.py

Celery tasks for email integration:
  - sync_email_account: sync a single account (triggered manually or by beat)
  - periodic_email_sync: sync ALL active accounts (runs every 30 min via beat)
"""

import uuid

import structlog
from celery import Task

from app.workers.celery_app import celery
from app.workers.db_utils import get_sync_db

logger = structlog.get_logger(__name__)


@celery.task(
    bind=True,
    name="app.workers.tasks.email_sync.sync_email_account",
    max_retries=2,
    soft_time_limit=120,
    time_limit=150,
)
def sync_email_account(self: Task, account_id: str) -> dict:
    """
    Sync a single email account.
    Called manually (from API) or by the periodic task.

    Runs synchronously in Celery — we use asyncio.run() to call the
    async service methods since the providers use httpx async.
    """
    import asyncio

    log = logger.bind(task_id=self.request.id, account_id=account_id)
    log.info("email_sync_started")

    try:
        # We need an async session for the service layer
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                _async_sync(uuid.UUID(account_id))
            )
        finally:
            loop.close()

        log.info("email_sync_complete", new_signals=result)
        return {"status": "complete", "account_id": account_id, "new_signals": result}

    except Exception as e:
        log.error("email_sync_failed", error=str(e))
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


async def _async_sync(account_id: uuid.UUID) -> int:
    """Run the async sync in an event loop."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from app.config import settings
    from app.services.email_integration.scan_service import EmailIntegrationService

    engine = create_async_engine(settings.database_url, pool_size=2)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as db:
        service = EmailIntegrationService(db=db)
        return await service.sync_account(account_id)


@celery.task(
    bind=True,
    name="app.workers.tasks.email_sync.periodic_email_sync",
    max_retries=0,
    soft_time_limit=600,
    time_limit=660,
)
def periodic_email_sync(self: Task) -> dict:
    """
    Sync ALL active email accounts.
    Runs via Celery Beat every 30 minutes.
    Dispatches individual sync tasks for each account.
    """
    log = logger.bind(task_id=self.request.id)
    log.info("periodic_email_sync_started")

    with get_sync_db() as db:
        from app.models.email_account import EmailAccount
        from sqlalchemy import select

        result = db.execute(
            select(EmailAccount.id).where(EmailAccount.is_active == True)  # noqa: E712
        )
        account_ids = [str(row[0]) for row in result.all()]

    log.info("accounts_to_sync", count=len(account_ids))

    # Fan out: dispatch individual sync tasks
    for aid in account_ids:
        sync_email_account.delay(aid)

    return {"status": "dispatched", "accounts": len(account_ids)}
