"""
app/workers/tasks/intelligence_tasks.py

Celery tasks for the Signal Intelligence Layer:

  1. propagation_sweep  — daily: run global propagation engine +
     update rollout progress + sweep no_response signals.

Uses sync DB sessions (Celery runs outside the async event loop).
"""

import structlog
from celery import Task
from sqlalchemy import select

from app.workers.celery_app import celery

logger = structlog.get_logger(__name__)


@celery.task(
    bind=True,
    name="intelligence.propagation_sweep",
    max_retries=1,
    soft_time_limit=300,
    time_limit=360,
    queue="default",
)
def propagation_sweep(self: Task) -> dict:
    """Daily intelligence sweep.

    1. Sweep no_response outcomes for each user.
    2. Run global propagation engine.
    3. Update rollout progress on active adjustments.

    Since the intelligence services are async, we run them
    inside a one-shot event loop.
    """
    import asyncio

    log = logger.bind(task_id=self.request.id)
    log.info("propagation_sweep_started")

    result = asyncio.run(_async_sweep(log))

    log.info("propagation_sweep_complete", **result)
    return result


async def _async_sweep(log) -> dict:
    """Async implementation of the propagation sweep."""
    from app.db.session import AsyncSessionLocal

    no_response_total = 0
    adjustments_created = 0
    rollout_updated = 0

    async with AsyncSessionLocal() as db:
        # 1. Sweep no_response for all users with signals
        try:
            from app.models.hidden_signal import HiddenSignal
            from app.services.intelligence.outcome_tracker import (
                OutcomeTracker,
            )

            user_ids_q = (
                select(HiddenSignal.user_id)
                .where(HiddenSignal.outcome_tracked.is_(False))
                .distinct()
                .limit(100)
            )
            user_ids = (
                await db.execute(user_ids_q)
            ).scalars().all()

            tracker = OutcomeTracker(db)
            for uid in user_ids:
                count = await tracker.sweep_no_response(uid)
                no_response_total += count

            if no_response_total > 0:
                await db.commit()
                log.info(
                    "no_response_swept",
                    count=no_response_total,
                )
        except Exception as exc:
            log.warning(
                "no_response_sweep_failed",
                error=str(exc),
            )
            await db.rollback()

        # 2. Run global propagation
        try:
            from app.services.intelligence.propagation_engine import (
                PropagationEngine,
            )

            engine = PropagationEngine(db)
            new_adjs = await engine.run_propagation()
            adjustments_created = len(new_adjs)

            if new_adjs:
                await db.commit()
        except Exception as exc:
            log.warning(
                "propagation_failed", error=str(exc),
            )
            await db.rollback()

        # 3. Update rollout progress
        try:
            from app.services.intelligence.propagation_engine import (
                PropagationEngine,
            )

            engine = PropagationEngine(db)
            rollout_updated = (
                await engine.update_rollout_progress()
            )
            if rollout_updated > 0:
                await db.commit()
        except Exception as exc:
            log.warning(
                "rollout_update_failed", error=str(exc),
            )
            await db.rollback()

    return {
        "no_response_swept": no_response_total,
        "adjustments_created": adjustments_created,
        "rollout_updated": rollout_updated,
    }
