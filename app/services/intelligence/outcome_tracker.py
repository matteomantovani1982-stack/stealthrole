"""
app/services/intelligence/outcome_tracker.py

Outcome Tracking — Phase 5 of Signal Intelligence Layer.

Connects terminal application outcomes back to the originating
hidden-market signals so the learning engine can update success
rates per signal type, contact type, and path type.

Terminal outcomes
-----------------
  interview    — user reached interview stage
  hire         — user received an offer
  rejection    — explicit rejection
  no_response  — no activity after 30+ days

Flow
----
1. Application stage changes (via route or Celery task).
2. ``OutcomeTracker.record_outcome()`` is called with the
   application and its new stage.
3. The tracker finds matching ``HiddenSignal`` records for the
   same company + user (fuzzy company match).
4. Sets ``outcome_tracked = True`` and ``outcome_result`` on each
   matched signal.
5. Calls ``LearningUpdater.update_from_outcome()`` to adjust the
   user's learning profile.

Usage
-----
    tracker = OutcomeTracker(db)
    count = await tracker.record_outcome(
        user_id=user_id,
        company_name="Acme Corp",
        outcome="interview",
        path_type="warm_intro",
        contact_type="hiring_manager",
    )
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select, update

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

# Application stage → terminal outcome mapping
_STAGE_TO_OUTCOME: dict[str, str | None] = {
    "watching": None,
    "applied": None,
    "interview": "interview",
    "offer": "hire",
    "rejected": "rejection",
}

# Minimum days before marking as no_response
NO_RESPONSE_DAYS = 30


class OutcomeTracker:
    """Track outcomes and link them to originating signals."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def record_outcome(
        self,
        user_id: str,
        company_name: str,
        outcome: str,
        *,
        path_type: str | None = None,
        contact_type: str | None = None,
        signal_type_hint: str | None = None,
    ) -> int:
        """Record a terminal outcome against matching signals.

        Parameters
        ----------
        user_id : str
        company_name : str
            Company the outcome relates to.
        outcome : str
            One of: interview, hire, rejection, no_response.
        path_type : str | None
            How the user reached this company (warm_intro,
            direct_apply, referral, etc.).
        contact_type : str | None
            Who was contacted (recruiter, hiring_manager, etc.).
        signal_type_hint : str | None
            If known, the signal type that originated this lead.

        Returns
        -------
        int
            Number of signals updated.
        """
        if outcome not in (
            "interview", "hire", "rejection", "no_response",
        ):
            logger.warning(
                "outcome_invalid", outcome=outcome,
                user_id=user_id,
            )
            return 0

        # Find untracked signals for this company + user
        matched = await self._find_matching_signals(
            user_id, company_name,
        )
        if not matched:
            logger.debug(
                "outcome_no_matching_signals",
                user_id=user_id,
                company=company_name,
            )
            return 0

        # Mark signals as tracked
        signal_ids = [sig.id for sig in matched]
        from app.models.hidden_signal import HiddenSignal

        await self._db.execute(
            update(HiddenSignal)
            .where(HiddenSignal.id.in_(signal_ids))
            .values(
                outcome_tracked=True,
                outcome_result=outcome,
            )
        )

        # Update user learning profile
        try:
            from app.services.intelligence.learning_updater import (
                LearningUpdater,
            )

            updater = LearningUpdater(self._db)
            for sig in matched:
                await updater.update_from_outcome(
                    user_id=user_id,
                    signal_type=sig.signal_type,
                    outcome=outcome,
                    path_type=path_type,
                    contact_type=contact_type,
                    company_name=company_name,
                )
        except Exception as exc:
            logger.warning(
                "learning_update_failed",
                error=str(exc),
                user_id=user_id,
            )

        logger.info(
            "outcome_recorded",
            user_id=user_id,
            company=company_name,
            outcome=outcome,
            signals_updated=len(signal_ids),
        )

        return len(signal_ids)

    async def record_from_application_stage(
        self,
        user_id: str,
        company_name: str,
        new_stage: str,
        *,
        source_channel: str | None = None,
    ) -> int:
        """Convenience method: map an application stage change
        to an outcome and record it.

        Returns 0 if the stage is not a terminal outcome.
        """
        outcome = _STAGE_TO_OUTCOME.get(new_stage)
        if outcome is None:
            return 0

        # Map source_channel to path_type
        path_type = _channel_to_path(source_channel)

        return await self.record_outcome(
            user_id=user_id,
            company_name=company_name,
            outcome=outcome,
            path_type=path_type,
        )

    async def sweep_no_response(
        self,
        user_id: str,
    ) -> int:
        """Mark signals older than NO_RESPONSE_DAYS with no
        outcome as ``no_response``.

        Intended to be called periodically (e.g., daily Celery
        task).
        """
        from datetime import timedelta

        from app.models.hidden_signal import HiddenSignal

        cutoff = datetime.now(timezone.utc) - timedelta(
            days=NO_RESPONSE_DAYS,
        )

        q = (
            select(HiddenSignal)
            .where(
                HiddenSignal.user_id == user_id,
                HiddenSignal.outcome_tracked.is_(False),
                HiddenSignal.is_dismissed.is_(False),
                HiddenSignal.created_at <= cutoff,
                HiddenSignal.quality_gate_result.in_(
                    ["pass", "conditional"],
                ),
            )
            .limit(50)
        )
        rows = (await self._db.execute(q)).scalars().all()

        if not rows:
            return 0

        count = 0
        for sig in rows:
            sig.outcome_tracked = True
            sig.outcome_result = "no_response"
            count += 1

        # Update learning for each
        try:
            from app.services.intelligence.learning_updater import (
                LearningUpdater,
            )

            updater = LearningUpdater(self._db)
            for sig in rows:
                await updater.update_from_outcome(
                    user_id=user_id,
                    signal_type=sig.signal_type,
                    outcome="no_response",
                    company_name=sig.company_name,
                )
        except Exception as exc:
            logger.warning(
                "sweep_learning_failed", error=str(exc),
            )

        logger.info(
            "no_response_sweep",
            user_id=user_id,
            marked=count,
        )
        return count

    # ── Helpers ──────────────────────────────────────────────────────

    async def _find_matching_signals(
        self,
        user_id: str,
        company_name: str,
    ) -> list:
        """Find untracked signals matching company name (fuzzy)."""
        from app.models.hidden_signal import HiddenSignal

        norm = _normalise(company_name)
        if not norm:
            return []

        # Query recent untracked signals for this user
        q = (
            select(HiddenSignal)
            .where(
                HiddenSignal.user_id == user_id,
                HiddenSignal.outcome_tracked.is_(False),
                HiddenSignal.is_dismissed.is_(False),
            )
            .order_by(HiddenSignal.created_at.desc())
            .limit(100)
        )
        rows = (await self._db.execute(q)).scalars().all()

        # Fuzzy match company name
        matched = []
        for sig in rows:
            sig_norm = _normalise(sig.company_name)
            if _fuzzy_match(norm, sig_norm):
                matched.append(sig)

        return matched


def _normalise(name: str) -> str:
    """Normalise company name for fuzzy matching."""
    n = name.lower().strip()
    for suffix in (
        " inc", " inc.", " ltd", " ltd.", " llc",
        " corp", " corp.", " co.", " plc", " pjsc",
        " limited", " corporation", " group",
        " holdings",
    ):
        if n.endswith(suffix):
            n = n[: -len(suffix)].rstrip(" ,.")
    return re.sub(r"\s+", " ", n).strip()


def _fuzzy_match(a: str, b: str) -> bool:
    """Fuzzy company name match."""
    if not a or not b:
        return False
    if a == b:
        return True
    # First-10-chars overlap
    if len(a) >= 8 and len(b) >= 8 and a[:8] == b[:8]:
        return True
    # One contains the other
    if a in b or b in a:
        return True
    return False


def _channel_to_path(channel: str | None) -> str | None:
    """Map application source_channel to a learning path_type."""
    if not channel:
        return None
    mapping = {
        "linkedin": "direct_apply",
        "indeed": "direct_apply",
        "referral": "warm_intro",
        "company_site": "direct_apply",
        "recruiter": "recruiter",
        "other": "other",
    }
    return mapping.get(channel.lower(), "other")
