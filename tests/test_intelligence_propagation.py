"""
tests/test_intelligence_propagation.py

Unit tests for Global Propagation Engine (Phase 6).
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.intelligence.propagation_engine import (
    DOWNGRADE_RATE,
    MIN_DISTINCT_USERS,
    MIN_TOTAL_OUTCOMES,
    PROMOTE_RATE,
    ROLLOUT_DAYS,
    SUPPRESS_RATE,
    UPGRADE_RATE,
    PropagationEngine,
    _classify_adjustment,
)

# ── Adjustment classification ───────────────────────────────────────────


class TestClassifyAdjustment:

    def test_suppress_low_rate_high_n(self):
        adj_type, value = _classify_adjustment(0.05, 25)
        assert adj_type == "suppress"
        assert value == -1.0

    def test_suppress_needs_min_n(self):
        # Rate qualifies but n too low
        adj_type, _ = _classify_adjustment(0.05, 10)
        assert adj_type == "downgrade"  # falls through to downgrade

    def test_downgrade(self):
        adj_type, value = _classify_adjustment(0.15, 15)
        assert adj_type == "downgrade"
        assert value < 0

    def test_upgrade(self):
        adj_type, value = _classify_adjustment(0.65, 12)
        assert adj_type == "upgrade"
        assert value > 0

    def test_promote_high_rate_high_n(self):
        adj_type, value = _classify_adjustment(0.80, 20)
        assert adj_type == "promote"
        assert value > 0

    def test_promote_needs_min_n(self):
        # Rate qualifies but n too low
        adj_type, _ = _classify_adjustment(0.80, 10)
        assert adj_type == "upgrade"  # falls to upgrade

    def test_neutral_zone_returns_none(self):
        adj_type, value = _classify_adjustment(0.45, 15)
        assert adj_type is None
        assert value == 0.0

    def test_downgrade_value_capped(self):
        _, value = _classify_adjustment(0.01, 15)
        assert value >= -0.80

    def test_upgrade_value_capped(self):
        _, value = _classify_adjustment(0.99, 12)
        assert value <= 0.50


# ── Rollout progress ────────────────────────────────────────────────────


class TestRolloutProgress:

    @pytest.mark.asyncio
    async def test_update_progress_midway(self):
        db = AsyncMock()
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=3.5)
        end = start + timedelta(days=ROLLOUT_DAYS)

        adj = MagicMock()
        adj.rollout_start = start
        adj.rollout_end = end
        adj.rollout_progress = 0.0
        adj.is_active = True

        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [adj]
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars_mock
        db.execute.return_value = result_mock

        engine = PropagationEngine(db)
        count = await engine.update_rollout_progress()

        assert count == 1
        assert abs(adj.rollout_progress - 0.50) < 0.05

    @pytest.mark.asyncio
    async def test_update_progress_completed(self):
        db = AsyncMock()
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=10)
        end = start + timedelta(days=ROLLOUT_DAYS)

        adj = MagicMock()
        adj.rollout_start = start
        adj.rollout_end = end
        adj.rollout_progress = 0.5
        adj.is_active = True

        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [adj]
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars_mock
        db.execute.return_value = result_mock

        engine = PropagationEngine(db)
        count = await engine.update_rollout_progress()

        assert count == 1
        assert adj.rollout_progress == 1.0

    @pytest.mark.asyncio
    async def test_zero_duration_sets_full(self):
        db = AsyncMock()
        now = datetime.now(timezone.utc)

        adj = MagicMock()
        adj.rollout_start = now
        adj.rollout_end = now  # zero duration
        adj.rollout_progress = 0.0
        adj.is_active = True

        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [adj]
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars_mock
        db.execute.return_value = result_mock

        engine = PropagationEngine(db)
        count = await engine.update_rollout_progress()

        assert count == 1
        assert adj.rollout_progress == 1.0


# ── Effective adjustment ────────────────────────────────────────────────


class TestEffectiveAdjustment:

    @pytest.mark.asyncio
    async def test_no_adjustment_returns_zero(self):
        db = AsyncMock()
        scalar_mock = MagicMock()
        scalar_mock.scalar_one_or_none.return_value = None
        db.execute.return_value = scalar_mock

        engine = PropagationEngine(db)
        val = await engine.get_effective_adjustment(
            "signal_type", "funding",
        )
        assert val == 0.0

    @pytest.mark.asyncio
    async def test_partial_rollout(self):
        adj = MagicMock()
        adj.adjustment_value = 0.30
        adj.rollout_progress = 0.50

        db = AsyncMock()
        scalar_mock = MagicMock()
        scalar_mock.scalar_one_or_none.return_value = adj
        db.execute.return_value = scalar_mock

        engine = PropagationEngine(db)
        val = await engine.get_effective_adjustment(
            "signal_type", "funding",
        )
        assert abs(val - 0.15) < 0.01

    @pytest.mark.asyncio
    async def test_full_rollout(self):
        adj = MagicMock()
        adj.adjustment_value = -0.50
        adj.rollout_progress = 1.0

        db = AsyncMock()
        scalar_mock = MagicMock()
        scalar_mock.scalar_one_or_none.return_value = adj
        db.execute.return_value = scalar_mock

        engine = PropagationEngine(db)
        val = await engine.get_effective_adjustment(
            "company", "acme",
        )
        assert val == -0.50


# ── User override check ────────────────────────────────────────────────


class TestUserOverride:

    @pytest.mark.asyncio
    async def test_no_intelligence_returns_false(self):
        db = AsyncMock()
        scalar_mock = MagicMock()
        scalar_mock.scalar_one_or_none.return_value = None
        db.execute.return_value = scalar_mock

        engine = PropagationEngine(db)
        result = await engine.check_user_override(
            "user-1", "signal_type", "funding",
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_override_present_returns_true(self):
        row = MagicMock()
        row.learning_profile = {
            "overrides": {"signal_type:funding": True},
        }

        db = AsyncMock()
        scalar_mock = MagicMock()
        scalar_mock.scalar_one_or_none.return_value = row
        db.execute.return_value = scalar_mock

        engine = PropagationEngine(db)
        result = await engine.check_user_override(
            "user-1", "signal_type", "funding",
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_different_override_returns_false(self):
        row = MagicMock()
        row.learning_profile = {
            "overrides": {"signal_type:leadership": True},
        }

        db = AsyncMock()
        scalar_mock = MagicMock()
        scalar_mock.scalar_one_or_none.return_value = row
        db.execute.return_value = scalar_mock

        engine = PropagationEngine(db)
        result = await engine.check_user_override(
            "user-1", "signal_type", "funding",
        )
        assert result is False


# ── Thresholds sanity ───────────────────────────────────────────────────


class TestThresholds:

    def test_suppress_rate_less_than_downgrade(self):
        assert SUPPRESS_RATE < DOWNGRADE_RATE

    def test_upgrade_rate_less_than_promote(self):
        assert UPGRADE_RATE < PROMOTE_RATE

    def test_min_users_positive(self):
        assert MIN_DISTINCT_USERS > 0

    def test_min_outcomes_positive(self):
        assert MIN_TOTAL_OUTCOMES > 0

    def test_rollout_days_positive(self):
        assert ROLLOUT_DAYS > 0
