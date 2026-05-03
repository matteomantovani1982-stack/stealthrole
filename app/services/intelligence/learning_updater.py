"""
app/services/intelligence/learning_updater.py

User Learning Updater — Phase 5 of Signal Intelligence Layer.

Updates the ``user_intelligence.learning_profile`` JSONB column
with running means when outcomes are recorded.  Manages three
learning dimensions:

  signal_effectiveness
      Success rate per signal type (funding, leadership, etc.).
  contact_type
      Response / conversion rate per contact type
      (recruiter, hiring_manager, etc.).
  path_success
      Success rate per application path
      (warm_intro, direct_apply, etc.).

Also maintains ``short_term_memory`` — a rolling window of the
last 10 actions with outcomes, used for fast feedback detection
by downstream services.

Running mean
------------
The update uses a simple incremental mean:

    new_rate = old_rate + (outcome_score - old_rate) / new_count

This avoids storing raw events while still converging to the
true mean as sample count grows.

Usage
-----
    updater = LearningUpdater(db)
    await updater.update_from_outcome(
        user_id="...",
        signal_type="funding",
        outcome="interview",
        path_type="warm_intro",
        contact_type="hiring_manager",
        company_name="Acme Corp",
    )
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

# Outcome → numeric score for running mean
_OUTCOME_SCORE: dict[str, float] = {
    "hire": 1.0,
    "interview": 0.50,
    "rejection": 0.10,
    "no_response": 0.0,
}

# Maximum entries in short_term_memory
SHORT_TERM_MEMORY_SIZE = 10


class LearningUpdater:
    """Update user learning profile from tracked outcomes."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def update_from_outcome(
        self,
        user_id: str,
        signal_type: str,
        outcome: str,
        *,
        path_type: str | None = None,
        contact_type: str | None = None,
        company_name: str | None = None,
    ) -> None:
        """Record one outcome into the user's learning profile.

        Updates signal_effectiveness, contact_type, path_success
        dimensions using incremental running means.  Also appends
        the event to short_term_memory.

        The caller owns ``db.commit()``.
        """
        score = _OUTCOME_SCORE.get(outcome, 0.0)

        ui = await self._get_or_create(user_id)
        profile = dict(ui.learning_profile or {})

        # 1. signal_effectiveness
        sig_eff = dict(profile.get("signal_effectiveness", {}))
        sig_eff[signal_type] = _update_running_mean(
            sig_eff.get(signal_type), score,
        )
        profile["signal_effectiveness"] = sig_eff

        # 2. contact_type
        if contact_type:
            ct = dict(profile.get("contact_type", {}))
            ct[contact_type] = _update_running_mean(
                ct.get(contact_type), score,
            )
            profile["contact_type"] = ct

        # 3. path_success
        if path_type:
            ps = dict(profile.get("path_success", {}))
            ps[path_type] = _update_running_mean(
                ps.get(path_type), score,
            )
            profile["path_success"] = ps

        # 4. short_term_memory (FIFO, last N events)
        stm = list(ui.short_term_memory or [])
        stm.append({
            "signal_type": signal_type,
            "outcome": outcome,
            "success_score": score,
            "path_type": path_type,
            "contact_type": contact_type,
            "company": company_name,
            "timestamp": datetime.now(
                timezone.utc,
            ).isoformat(),
        })
        if len(stm) > SHORT_TERM_MEMORY_SIZE:
            stm = stm[-SHORT_TERM_MEMORY_SIZE:]

        # Persist
        ui.learning_profile = profile
        ui.short_term_memory = stm
        ui.learning_sample_count = (
            ui.learning_sample_count + 1
        )
        ui.learning_updated_at = datetime.now(timezone.utc)

        logger.debug(
            "learning_updated",
            user_id=user_id,
            signal_type=signal_type,
            outcome=outcome,
            sample_count=ui.learning_sample_count,
        )

    # ── Helpers ──────────────────────────────────────────────────────

    async def _get_or_create(self, user_id: str):
        """Get or create the UserIntelligence row."""
        from app.models.user_intelligence import (
            UserIntelligence,
        )

        q = select(UserIntelligence).where(
            UserIntelligence.user_id == user_id,
        )
        row = (
            await self._db.execute(q)
        ).scalar_one_or_none()

        if row is not None:
            return row

        # Create a new row
        row = UserIntelligence(
            user_id=user_id,
            profile_strength=0,
            learning_profile={},
            learning_sample_count=0,
            short_term_memory=[],
        )
        self._db.add(row)
        await self._db.flush()
        return row


def _update_running_mean(
    entry: dict | None,
    new_score: float,
) -> dict:
    """Incremental running-mean update for a learning dimension
    entry.

    Parameters
    ----------
    entry : dict | None
        Existing entry with ``success_rate``, ``sample_count``,
        ``last_updated``.
    new_score : float
        Outcome score (0.0–1.0).

    Returns
    -------
    dict
        Updated entry.
    """
    if entry is None:
        entry = {
            "success_rate": 0.0,
            "sample_count": 0,
        }

    old_rate = entry.get("success_rate", 0.0)
    old_count = entry.get("sample_count", 0)
    new_count = old_count + 1

    # Incremental mean: avoids storing raw events
    new_rate = old_rate + (new_score - old_rate) / new_count

    return {
        "success_rate": round(new_rate, 4),
        "sample_count": new_count,
        "last_updated": datetime.now(
            timezone.utc,
        ).isoformat(),
    }
