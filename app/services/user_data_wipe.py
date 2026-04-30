"""
Bulk-delete per-user rows for local/testing resets.

Does NOT delete: users, cvs, candidate_profiles, credits, subscriptions, email_accounts.
"""

from __future__ import annotations

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

# Order respects typical FKs. `applications` CASCADE clears interview_rounds + application_timeline.
_APPLICATION_AND_NETWORK_TABLES: tuple[str, ...] = (
    "warm_intros",
    "auto_apply_submissions",
    "applications",
    "mutual_connections",
    "linkedin_messages",
    "linkedin_conversations",
    "linkedin_connections",
    "auto_apply_profiles",
    "shadow_applications",
    "calendar_events",
    "scout_results",
    "hidden_signals",
    "saved_jobs",
)

# Optional: intelligence caches (safe to rebuild)
_INTELLIGENCE_TABLES: tuple[str, ...] = (
    "user_intelligence",
    "email_intelligence",
)


async def wipe_application_and_network_data(
    session: AsyncSession,
    user_id: str,
    *,
    include_intelligence: bool = True,
) -> dict[str, int | str]:
    """
    Delete job-tracker + LinkedIn sync data for one user.
    Returns per-table rowcounts (or error strings).
    """
    deleted: dict[str, int | str] = {}
    tables = _APPLICATION_AND_NETWORK_TABLES + (
        _INTELLIGENCE_TABLES if include_intelligence else ()
    )
    for table in tables:
        try:
            r = await session.execute(
                text(f"DELETE FROM {table} WHERE user_id = :uid"),
                {"uid": user_id},
            )
            deleted[table] = r.rowcount or 0
        except Exception as e:
            logger.warning("user_wipe_table_failed", table=table, error=str(e))
            deleted[table] = f"error: {e}"
    # Caller commits (e.g. FastAPI DB dependency or explicit session.commit()).
    return deleted
