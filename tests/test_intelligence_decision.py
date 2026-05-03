"""
tests/test_intelligence_decision.py

Unit tests for Decision Engine (Phase 7).
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.intelligence.decision_engine import (
    FAST_FEEDBACK_BOOST,
    FAST_FEEDBACK_WINDOW_HOURS,
    W_ACCESS,
    W_COMPANY_RESP,
    W_PROFILE_FIT,
    W_RECENCY,
    W_SIGNAL_STRENGTH,
    W_TIMING,
    DecisionEngine,
    DecisionScore,
    _blend,
    _fast_feedback_boost,
    _get_blend_weights,
    _user_rate,
)

# ── Blend weights ───────────────────────────────────────────────────────


class TestBlendWeights:

    def test_tier_0_all_global(self):
        tier, uw, gw = _get_blend_weights(0)
        assert uw == 0.0
        assert gw == 1.0

    def test_tier_0_at_4(self):
        tier, uw, gw = _get_blend_weights(4)
        assert uw == 0.0
        assert gw == 1.0

    def test_tier_1_at_5(self):
        tier, uw, gw = _get_blend_weights(5)
        assert uw == 0.20
        assert gw == 0.80

    def test_tier_2_at_10(self):
        tier, uw, gw = _get_blend_weights(10)
        assert uw == 0.50
        assert gw == 0.50

    def test_tier_3_at_20(self):
        tier, uw, gw = _get_blend_weights(20)
        assert uw == 0.80
        assert gw == 0.20

    def test_tier_4_at_50(self):
        tier, uw, gw = _get_blend_weights(50)
        assert uw == 0.95
        assert gw == 0.05

    def test_tier_4_at_100(self):
        tier, uw, gw = _get_blend_weights(100)
        assert uw == 0.95
        assert gw == 0.05

    def test_weights_sum_to_one(self):
        for n in [0, 3, 5, 10, 20, 50, 100]:
            _, uw, gw = _get_blend_weights(n)
            assert abs(uw + gw - 1.0) < 0.001


# ── Blending function ──────────────────────────────────────────────────


class TestBlend:

    def test_pure_global(self):
        result = _blend(0.80, 0.50, 0.0, 1.0)
        assert result == 0.50

    def test_pure_user(self):
        result = _blend(0.80, 0.50, 1.0, 0.0)
        assert result == 0.80

    def test_equal_blend(self):
        result = _blend(0.80, 0.40, 0.50, 0.50)
        assert abs(result - 0.60) < 0.001


# ── User rate extraction ───────────────────────────────────────────────


class TestUserRate:

    def test_specific_key(self):
        learning = {
            "signal_effectiveness": {
                "funding": {
                    "success_rate": 0.42,
                    "sample_count": 12,
                },
            },
        }
        rate = _user_rate(learning, "signal_effectiveness", "funding")
        assert rate == 0.42

    def test_missing_key_returns_default(self):
        learning = {"signal_effectiveness": {}}
        rate = _user_rate(
            learning, "signal_effectiveness", "unknown",
        )
        assert rate == 0.50

    def test_any_key_averages(self):
        learning = {
            "contact_type": {
                "recruiter": {"success_rate": 0.60},
                "hiring_manager": {"success_rate": 0.40},
            },
        }
        rate = _user_rate(learning, "contact_type", "any")
        assert abs(rate - 0.50) < 0.001

    def test_any_key_empty_returns_default(self):
        learning = {"contact_type": {}}
        rate = _user_rate(learning, "contact_type", "any")
        assert rate == 0.50

    def test_missing_dimension_returns_default(self):
        learning = {}
        rate = _user_rate(learning, "nonexistent", "key")
        assert rate == 0.50


# ── Fast feedback boost ────────────────────────────────────────────────


class TestFastFeedbackBoost:

    def test_empty_stm(self):
        assert _fast_feedback_boost([], "funding", "acme") == 0.0

    def test_recent_positive_match(self):
        now = datetime.now(timezone.utc)
        stm = [
            {
                "signal_type": "funding",
                "outcome": "interview",
                "company": "Acme Corp",
                "timestamp": now.isoformat(),
            },
        ]
        boost = _fast_feedback_boost(stm, "funding", "acme")
        assert boost == FAST_FEEDBACK_BOOST

    def test_old_positive_no_boost(self):
        old = datetime.now(timezone.utc) - timedelta(
            hours=FAST_FEEDBACK_WINDOW_HOURS + 1,
        )
        stm = [
            {
                "signal_type": "funding",
                "outcome": "interview",
                "company": "Acme",
                "timestamp": old.isoformat(),
            },
        ]
        boost = _fast_feedback_boost(stm, "funding", "acme")
        assert boost == 0.0

    def test_negative_outcome_no_boost(self):
        now = datetime.now(timezone.utc)
        stm = [
            {
                "signal_type": "funding",
                "outcome": "rejection",
                "company": "Acme",
                "timestamp": now.isoformat(),
            },
        ]
        boost = _fast_feedback_boost(stm, "funding", "acme")
        assert boost == 0.0

    def test_company_match_boost(self):
        now = datetime.now(timezone.utc)
        stm = [
            {
                "signal_type": "leadership",
                "outcome": "hire",
                "company": "Acme Corp",
                "timestamp": now.isoformat(),
            },
        ]
        boost = _fast_feedback_boost(stm, "funding", "acme")
        assert boost == FAST_FEEDBACK_BOOST

    def test_no_timestamp_skipped(self):
        stm = [
            {
                "signal_type": "funding",
                "outcome": "interview",
                "company": "Acme",
                "timestamp": "",
            },
        ]
        boost = _fast_feedback_boost(stm, "funding", "acme")
        assert boost == 0.0


# ── Decision Score dataclass ────────────────────────────────────────────


class TestDecisionScore:

    def test_frozen(self):
        score = DecisionScore(
            composite_score=0.75,
            profile_fit=0.80,
            signal_strength=0.70,
            company_responsiveness=0.60,
            access_strength=0.50,
            timing=0.65,
            recency=0.90,
            fast_feedback_boost=0.10,
            blend_tier=3,
            user_weight=0.80,
            global_weight=0.20,
        )
        with pytest.raises(AttributeError):
            score.composite_score = 0.99


# ── Composite weights ──────────────────────────────────────────────────


class TestCompositeWeights:

    def test_weights_sum_to_one(self):
        total = (
            W_PROFILE_FIT
            + W_SIGNAL_STRENGTH
            + W_COMPANY_RESP
            + W_ACCESS
            + W_TIMING
            + W_RECENCY
        )
        assert abs(total - 1.0) < 0.001


# ── Score opportunity ───────────────────────────────────────────────────


class TestScoreOpportunity:

    def _make_signal(self):
        sig = MagicMock()
        sig.id = uuid.uuid4()
        sig.signal_type = "funding"
        sig.company_name = "TestCorp"
        sig.quality_gate_result = "pass"
        sig.confidence = 0.85
        sig.created_at = datetime.now(timezone.utc)
        return sig

    @pytest.mark.asyncio
    async def test_basic_scoring(self):
        db = AsyncMock()
        scalar_mock = MagicMock()
        scalar_mock.scalar_one_or_none.return_value = None
        db.execute.return_value = scalar_mock

        engine = DecisionEngine(db)
        sig = self._make_signal()

        score = await engine.score_opportunity(
            sig, "user-1",
            profile_fit=0.75,
            access_strength=0.60,
        )

        assert isinstance(score, DecisionScore)
        assert 0.0 <= score.composite_score <= 1.0
        assert score.profile_fit == 0.75
        assert score.access_strength == 0.60

    @pytest.mark.asyncio
    async def test_new_user_uses_global(self):
        """Tier 0 user (0 samples) should use 100% global weight."""
        db = AsyncMock()
        scalar_mock = MagicMock()
        scalar_mock.scalar_one_or_none.return_value = None
        db.execute.return_value = scalar_mock

        engine = DecisionEngine(db)
        sig = self._make_signal()

        score = await engine.score_opportunity(sig, "user-new")

        assert score.user_weight == 0.0
        assert score.global_weight == 1.0
        assert score.blend_tier == 0

    @pytest.mark.asyncio
    async def test_experienced_user_uses_mostly_user(self):
        row = MagicMock()
        row.learning_profile = {
            "signal_effectiveness": {
                "funding": {
                    "success_rate": 0.75,
                    "sample_count": 30,
                },
            },
            "contact_type": {},
        }
        row.learning_sample_count = 55
        row.short_term_memory = []

        db = AsyncMock()
        scalar_mock = MagicMock()
        scalar_mock.scalar_one_or_none.return_value = row
        db.execute.return_value = scalar_mock

        engine = DecisionEngine(db)
        sig = self._make_signal()

        score = await engine.score_opportunity(sig, "expert-user")

        assert score.user_weight == 0.95
        assert score.global_weight == 0.05

    @pytest.mark.asyncio
    async def test_composite_clamped_0_1(self):
        db = AsyncMock()
        scalar_mock = MagicMock()
        scalar_mock.scalar_one_or_none.return_value = None
        db.execute.return_value = scalar_mock

        engine = DecisionEngine(db)
        sig = self._make_signal()

        score = await engine.score_opportunity(
            sig, "user-1",
            profile_fit=1.0,
            access_strength=1.0,
        )

        assert score.composite_score <= 1.0
        assert score.composite_score >= 0.0


# ── Batch scoring ──────────────────────────────────────────────────────


class TestBatchScoring:

    @pytest.mark.asyncio
    async def test_batch_returns_correct_count(self):
        db = AsyncMock()
        scalar_mock = MagicMock()
        scalar_mock.scalar_one_or_none.return_value = None
        db.execute.return_value = scalar_mock

        engine = DecisionEngine(db)

        signals = []
        for _ in range(3):
            sig = MagicMock()
            sig.id = uuid.uuid4()
            sig.signal_type = "funding"
            sig.company_name = "Co"
            sig.quality_gate_result = "pass"
            sig.confidence = 0.8
            sig.created_at = datetime.now(timezone.utc)
            signals.append(sig)

        results = await engine.score_batch(signals, "user-1")
        assert len(results) == 3
        assert all(
            isinstance(r, DecisionScore) for r in results
        )
