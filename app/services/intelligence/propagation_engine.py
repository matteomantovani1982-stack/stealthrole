"""
app/services/intelligence/propagation_engine.py

Global Intelligence Propagation — Phase 6 of Signal Intelligence Layer.

Aggregates outcome data across ALL users to detect cross-user
patterns and create ``PropagationAdjustment`` records that modify
global weights for signals, companies, contacts, and paths.

Activation thresholds
---------------------
  - Minimum 5 distinct users with tracked outcomes.
  - Minimum 10 total outcomes for the dimension/key.
  - Statistical significance: rate must deviate ≥ 20% from
    the global mean for the dimension.

Adjustment types
----------------
  downgrade  — reduce weight (success rate < 0.25)
  upgrade    — increase weight (success rate > 0.60)
  suppress   — remove from recommendations (rate < 0.10, n ≥ 20)
  promote    — mark as recommended (rate > 0.70, n ≥ 15)

Rollout
-------
Each adjustment uses a 7-day gradual rollout.
``rollout_progress`` moves from 0.0 → 1.0 linearly over 7 days.
Consumers multiply adjustment_value × rollout_progress for the
effective weight.

Usage
-----
    # Typically called from a daily Celery task
    engine = PropagationEngine(db)
    adjustments = await engine.run_propagation()

    # Update rollout progress (called hourly or daily)
    updated = await engine.update_rollout_progress()
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import func, select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

# ── Thresholds ───────────────────────────────────────────────────────
MIN_DISTINCT_USERS = 5
MIN_TOTAL_OUTCOMES = 10
DEVIATION_THRESHOLD = 0.20  # ≥20% deviation from mean
ROLLOUT_DAYS = 7

# ── Adjustment thresholds ────────────────────────────────────────────
SUPPRESS_RATE = 0.10
SUPPRESS_MIN_N = 20
DOWNGRADE_RATE = 0.25
UPGRADE_RATE = 0.60
PROMOTE_RATE = 0.70
PROMOTE_MIN_N = 15

# ── Dimensions to analyse ───────────────────────────────────────────
DIMENSIONS = ("signal_type", "company", "path_type", "contact_type")


class PropagationEngine:
    """Cross-user pattern detection and global weight adjustment."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def run_propagation(self) -> list:
        """Analyse cross-user outcomes and create adjustments.

        Returns list of newly created PropagationAdjustment records.
        The caller owns ``db.commit()``.
        """
        from app.models.propagation_adjustment import (
            PropagationAdjustment,
        )

        new_adjustments: list[PropagationAdjustment] = []

        for dimension in DIMENSIONS:
            stats = await self._aggregate_dimension(dimension)
            if not stats:
                continue

            # Compute global mean for this dimension
            total_successes = sum(
                s["weighted_sum"] for s in stats.values()
            )
            total_n = sum(s["total"] for s in stats.values())
            if total_n == 0:
                continue
            global_mean = total_successes / total_n

            for key, data in stats.items():
                if (
                    data["distinct_users"] < MIN_DISTINCT_USERS
                    or data["total"] < MIN_TOTAL_OUTCOMES
                ):
                    continue

                rate = data["rate"]
                deviation = abs(rate - global_mean)

                if deviation < DEVIATION_THRESHOLD:
                    continue

                # Check for existing active adjustment
                existing = await self._find_active(
                    dimension, key,
                )
                if existing:
                    continue  # Already adjusted

                # Determine adjustment type
                adj_type, adj_value = _classify_adjustment(
                    rate, data["total"],
                )
                if adj_type is None:
                    continue

                metric = (
                    f"rate={rate:.3f} n={data['total']} "
                    f"users={data['distinct_users']} "
                    f"mean={global_mean:.3f}"
                )

                now = datetime.now(timezone.utc)
                adj = PropagationAdjustment(
                    dimension=dimension,
                    target_key=key,
                    adjustment_type=adj_type,
                    adjustment_value=adj_value,
                    previous_value=global_mean,
                    activation_metric=metric,
                    distinct_users=data["distinct_users"],
                    total_outcomes=data["total"],
                    rollout_start=now,
                    rollout_end=now + timedelta(days=ROLLOUT_DAYS),
                    rollout_progress=0.0,
                    is_active=True,
                )
                self._db.add(adj)
                new_adjustments.append(adj)

                logger.info(
                    "propagation_adjustment_created",
                    dimension=dimension,
                    key=key,
                    type=adj_type,
                    value=adj_value,
                    rate=round(rate, 3),
                    n=data["total"],
                )

        return new_adjustments

    async def update_rollout_progress(self) -> int:
        """Update rollout_progress for all active adjustments.

        Returns count of updated adjustments.
        """
        from app.models.propagation_adjustment import (
            PropagationAdjustment,
        )

        q = select(PropagationAdjustment).where(
            PropagationAdjustment.is_active.is_(True),
            PropagationAdjustment.rollout_progress < 1.0,
        )
        rows = (await self._db.execute(q)).scalars().all()

        now = datetime.now(timezone.utc)
        updated = 0

        for adj in rows:
            if not adj.rollout_start or not adj.rollout_end:
                continue

            total_secs = (
                adj.rollout_end - adj.rollout_start
            ).total_seconds()
            if total_secs <= 0:
                adj.rollout_progress = 1.0
                updated += 1
                continue

            elapsed = (now - adj.rollout_start).total_seconds()
            progress = min(1.0, max(0.0, elapsed / total_secs))
            if progress != adj.rollout_progress:
                adj.rollout_progress = round(progress, 4)
                updated += 1

        if updated:
            logger.info(
                "rollout_progress_updated", count=updated,
            )

        return updated

    async def get_effective_adjustment(
        self,
        dimension: str,
        key: str,
    ) -> float:
        """Get the effective adjustment value for a dimension/key,
        accounting for rollout progress.

        Returns 0.0 if no active adjustment exists.
        """
        adj = await self._find_active(dimension, key)
        if adj is None:
            return 0.0
        return adj.adjustment_value * adj.rollout_progress

    async def check_user_override(
        self,
        user_id: str,
        dimension: str,
        key: str,
    ) -> bool:
        """Check if a user has overridden a global adjustment.

        Looks at the ``overrides`` key in the user's
        ``learning_profile``.
        """
        from app.models.user_intelligence import UserIntelligence

        q = select(UserIntelligence).where(
            UserIntelligence.user_id == user_id,
        )
        row = (
            await self._db.execute(q)
        ).scalar_one_or_none()

        if not row or not row.learning_profile:
            return False

        overrides = row.learning_profile.get("overrides", {})
        override_key = f"{dimension}:{key}"
        return overrides.get(override_key, False)

    # ── Aggregation ──────────────────────────────────────────────────

    async def _aggregate_dimension(
        self,
        dimension: str,
    ) -> dict[str, dict]:
        """Aggregate outcomes across all users for a dimension.

        Returns dict of {key: {rate, total, distinct_users,
        weighted_sum}}.
        """
        from app.models.hidden_signal import HiddenSignal

        # Map dimension to the column on hidden_signals
        # For path_type and contact_type we'd need the
        # short_term_memory or a join — for now we only
        # aggregate signal_type and company directly.
        if dimension == "signal_type":
            col = HiddenSignal.signal_type
        elif dimension == "company":
            col = func.lower(HiddenSignal.company_name)
        else:
            # path_type and contact_type come from
            # learning profiles, not signals directly.
            return await self._aggregate_from_profiles(
                dimension,
            )

        q = (
            select(
                col.label("key"),
                func.count().label("total"),
                func.count(
                    func.distinct(HiddenSignal.user_id),
                ).label("distinct_users"),
                func.sum(
                    func.case(
                        (
                            HiddenSignal.outcome_result.in_(
                                ["interview", "hire"],
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("successes"),
            )
            .where(
                HiddenSignal.outcome_tracked.is_(True),
            )
            .group_by(col)
        )
        rows = (await self._db.execute(q)).all()

        result: dict[str, dict] = {}
        for row in rows:
            total = row.total or 0
            successes = row.successes or 0
            if total == 0:
                continue
            result[row.key] = {
                "rate": successes / total,
                "total": total,
                "distinct_users": row.distinct_users or 0,
                "weighted_sum": successes,
            }

        return result

    async def _aggregate_from_profiles(
        self,
        dimension: str,
    ) -> dict[str, dict]:
        """Aggregate a dimension from user learning profiles
        (for path_type and contact_type which aren't direct
        signal columns)."""
        from app.models.user_intelligence import UserIntelligence

        q = select(UserIntelligence).where(
            UserIntelligence.learning_profile.isnot(None),
            UserIntelligence.learning_sample_count > 0,
        )
        rows = (await self._db.execute(q)).scalars().all()

        aggregated: dict[str, dict] = {}

        for row in rows:
            profile = row.learning_profile or {}
            section = profile.get(dimension, {})

            for key, entry in section.items():
                if not isinstance(entry, dict):
                    continue
                rate = entry.get("success_rate", 0.0)
                count = entry.get("sample_count", 0)
                if count == 0:
                    continue

                if key not in aggregated:
                    aggregated[key] = {
                        "weighted_sum": 0.0,
                        "total": 0,
                        "distinct_users": 0,
                    }

                agg = aggregated[key]
                agg["weighted_sum"] += rate * count
                agg["total"] += count
                agg["distinct_users"] += 1

        # Compute final rates
        for key, agg in aggregated.items():
            if agg["total"] > 0:
                agg["rate"] = agg["weighted_sum"] / agg["total"]
            else:
                agg["rate"] = 0.0

        return aggregated

    async def _find_active(
        self,
        dimension: str,
        key: str,
    ):
        """Find an existing active adjustment for dimension/key."""
        from app.models.propagation_adjustment import (
            PropagationAdjustment,
        )

        q = (
            select(PropagationAdjustment)
            .where(
                PropagationAdjustment.dimension == dimension,
                PropagationAdjustment.target_key == key,
                PropagationAdjustment.is_active.is_(True),
            )
            .limit(1)
        )
        return (
            await self._db.execute(q)
        ).scalar_one_or_none()


def _classify_adjustment(
    rate: float,
    n: int,
) -> tuple[str | None, float]:
    """Classify the adjustment type and value from rate + count."""
    if rate < SUPPRESS_RATE and n >= SUPPRESS_MIN_N:
        return "suppress", -1.0
    if rate < DOWNGRADE_RATE:
        # Scale: 0.10 rate → -0.60, 0.25 rate → -0.30
        value = round(-0.30 - (DOWNGRADE_RATE - rate) * 2, 2)
        return "downgrade", max(-0.80, value)
    if rate > PROMOTE_RATE and n >= PROMOTE_MIN_N:
        return "promote", round(rate - 0.50, 2)
    if rate > UPGRADE_RATE:
        value = round((rate - 0.50) * 0.5, 2)
        return "upgrade", min(0.50, value)
    return None, 0.0
