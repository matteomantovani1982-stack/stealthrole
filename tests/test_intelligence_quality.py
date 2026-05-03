"""
tests/test_intelligence_quality.py

Unit tests for Signal Quality Filter (Phase 2).
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.intelligence.signal_quality import (
    GATE_CONDITIONAL,
    GATE_PASS,
    GATE_STORE_ONLY,
    RECENCY_HALF_LIFE_DAYS,
    STACK_BONUS_CAP,
    QualityResult,
    SignalQualityFilter,
)

# ── Helpers ─────────────────────────────────────────────────────────────


def _make_signal(
    *,
    confidence: float = 0.80,
    signal_type: str = "funding",
    evidence_tier: str = "medium",
    company_name: str = "TestCorp",
    created_at: datetime | None = None,
    likely_roles: list | None = None,
    signal_data: dict | None = None,
):
    """Create a mock HiddenSignal with sensible defaults."""
    sig = MagicMock()
    sig.id = uuid.uuid4()
    sig.user_id = "user-1"
    sig.confidence = confidence
    sig.signal_type = signal_type
    sig.evidence_tier = evidence_tier
    sig.company_name = company_name
    sig.created_at = created_at or datetime.now(timezone.utc)
    sig.is_dismissed = False
    sig.likely_roles = likely_roles or []
    sig.signal_data = signal_data or {}
    sig.reasoning = "Test reasoning"
    sig.source_url = None
    sig.source_name = None
    sig.quality_score = None
    sig.quality_confidence = None
    sig.quality_recency = None
    sig.quality_relevance = None
    sig.quality_historical = None
    sig.quality_gate_result = None
    sig.quality_computed_at = None
    return sig


def _mock_db():
    """Create an AsyncMock DB session."""
    db = AsyncMock()
    db.execute = AsyncMock()
    return db


# ── Confidence Component ────────────────────────────────────────────────


class TestConfidenceComponent:
    """Tests for _score_confidence."""

    def test_uses_signal_confidence(self):
        sig = _make_signal(confidence=0.90, evidence_tier="medium")
        score = SignalQualityFilter._score_confidence(sig)
        assert score == 0.90

    def test_floor_from_strong_tier(self):
        sig = _make_signal(confidence=0.10, evidence_tier="strong")
        score = SignalQualityFilter._score_confidence(sig)
        assert score == 0.70  # strong floor

    def test_floor_from_weak_tier(self):
        sig = _make_signal(confidence=0.10, evidence_tier="weak")
        score = SignalQualityFilter._score_confidence(sig)
        assert score == 0.30  # weak floor

    def test_speculative_low_confidence(self):
        sig = _make_signal(confidence=0.05, evidence_tier="speculative")
        score = SignalQualityFilter._score_confidence(sig)
        assert score == 0.10  # speculative floor

    def test_none_confidence_defaults(self):
        sig = _make_signal(confidence=0.0, evidence_tier="medium")
        sig.confidence = None
        score = SignalQualityFilter._score_confidence(sig)
        assert score == 0.50  # max(floor=0.50, raw=0.5)

    def test_capped_at_one(self):
        sig = _make_signal(confidence=1.5, evidence_tier="strong")
        score = SignalQualityFilter._score_confidence(sig)
        assert score == 1.0


# ── Recency Component ──────────────────────────────────────────────────


class TestRecencyComponent:

    def test_brand_new_signal_is_one(self):
        sig = _make_signal(created_at=datetime.now(timezone.utc))
        score = SignalQualityFilter._score_recency(sig)
        assert score == 1.0

    def test_half_life_produces_half(self):
        created = datetime.now(timezone.utc) - timedelta(
            days=RECENCY_HALF_LIFE_DAYS,
        )
        sig = _make_signal(created_at=created)
        score = SignalQualityFilter._score_recency(sig)
        assert abs(score - 0.50) < 0.02

    def test_very_old_signal_near_zero(self):
        created = datetime.now(timezone.utc) - timedelta(days=365)
        sig = _make_signal(created_at=created)
        score = SignalQualityFilter._score_recency(sig)
        assert score < 0.01

    def test_none_created_at(self):
        sig = _make_signal()
        sig.created_at = None
        score = SignalQualityFilter._score_recency(sig)
        assert score == 0.3


# ── Gate Classification ─────────────────────────────────────────────────


class TestGateClassification:

    def test_pass_gate(self):
        assert SignalQualityFilter._apply_gate(0.75) == "pass"

    def test_conditional_gate(self):
        assert (
            SignalQualityFilter._apply_gate(0.50) == "conditional"
        )

    def test_store_only_gate(self):
        assert (
            SignalQualityFilter._apply_gate(0.25) == "store_only"
        )

    def test_reject_gate(self):
        assert SignalQualityFilter._apply_gate(0.10) == "reject"

    def test_boundary_pass(self):
        assert SignalQualityFilter._apply_gate(GATE_PASS) == "pass"

    def test_boundary_conditional(self):
        assert (
            SignalQualityFilter._apply_gate(GATE_CONDITIONAL)
            == "conditional"
        )

    def test_boundary_store_only(self):
        assert (
            SignalQualityFilter._apply_gate(GATE_STORE_ONLY)
            == "store_only"
        )


# ── Persistence ─────────────────────────────────────────────────────────


class TestPersistence:

    def test_persist_writes_all_columns(self):
        sig = _make_signal()
        result = QualityResult(
            quality_score=0.72,
            confidence_component=0.80,
            recency_component=0.95,
            relevance_component=0.60,
            historical_component=0.50,
            gate="pass",
            stacking_bonus=0.05,
        )
        SignalQualityFilter._persist(sig, result)
        assert sig.quality_score == 0.72
        assert sig.quality_confidence == 0.80
        assert sig.quality_recency == 0.95
        assert sig.quality_relevance == 0.60
        assert sig.quality_historical == 0.50
        assert sig.quality_gate_result == "pass"
        assert sig.quality_computed_at is not None


# ── Full score_signal ───────────────────────────────────────────────────


class TestScoreSignal:

    @pytest.mark.asyncio
    async def test_score_signal_basic(self):
        db = _mock_db()
        # Mock out DB calls
        scalar_mock = MagicMock()
        scalar_mock.scalar_one_or_none.return_value = None
        scalar_mock.scalar.return_value = 1
        db.execute.return_value = scalar_mock

        qf = SignalQualityFilter(db)
        sig = _make_signal(
            confidence=0.85,
            evidence_tier="strong",
        )

        with patch.object(
            qf,
            "_preference_boost",
            return_value=0.0,
        ):
            result = await qf.score_signal(sig, "user-1")

        assert isinstance(result, QualityResult)
        assert 0.0 <= result.quality_score <= 1.0
        assert result.gate in (
            "pass", "conditional", "store_only", "reject",
        )

    @pytest.mark.asyncio
    async def test_high_quality_signal_passes(self):
        db = _mock_db()
        scalar_mock = MagicMock()
        scalar_mock.scalar_one_or_none.return_value = None
        scalar_mock.scalar.return_value = 1
        db.execute.return_value = scalar_mock

        qf = SignalQualityFilter(db)
        sig = _make_signal(
            confidence=0.90,
            evidence_tier="strong",
            created_at=datetime.now(timezone.utc),
        )

        with patch.object(
            qf,
            "_preference_boost",
            return_value=0.10,
        ):
            result = await qf.score_signal(sig, "user-1")

        assert result.gate == "pass"
        assert result.quality_score >= GATE_PASS

    @pytest.mark.asyncio
    async def test_stacking_bonus_applied(self):
        db = _mock_db()
        scalar_mock = MagicMock()
        scalar_mock.scalar_one_or_none.return_value = None
        db.execute.return_value = scalar_mock

        qf = SignalQualityFilter(db)
        sig = _make_signal()

        with patch.object(
            qf,
            "_preference_boost",
            return_value=0.0,
        ):
            r1 = await qf.score_signal(
                sig, "user-1", company_signal_count=1,
            )
            r3 = await qf.score_signal(
                sig, "user-1", company_signal_count=4,
            )

        # 3 extra types × 0.05 = 0.15 bonus (capped)
        assert r3.stacking_bonus == STACK_BONUS_CAP
        assert r3.quality_score > r1.quality_score
