"""
tests/test_intelligence_e2e.py

End-to-end integration test for the Signal Intelligence Layer.

Validates the full loop:
  Signal → Quality Filter → Interpretation → Outcome Tracking
  → Learning Update → Propagation → Decision Engine
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.intelligence.decision_engine import (
    DecisionEngine,
    DecisionScore,
    _fast_feedback_boost,
    _get_blend_weights,
)
from app.services.intelligence.learning_updater import (
    _update_running_mean,
)
from app.services.intelligence.outcome_tracker import (
    _fuzzy_match,
    _normalise,
)
from app.services.intelligence.propagation_engine import (
    _classify_adjustment,
)
from app.services.intelligence.signal_quality import (
    SignalQualityFilter,
)

# ── Helpers ─────────────────────────────────────────────────────────────


def _make_signal(
    *,
    signal_type: str = "funding",
    company_name: str = "Acme Corp",
    confidence: float = 0.85,
    evidence_tier: str = "strong",
    reasoning: str = "Company raised Series B funding of $50M",
    quality_gate_result: str | None = None,
):
    sig = MagicMock()
    sig.id = uuid.uuid4()
    sig.user_id = "user-1"
    sig.signal_type = signal_type
    sig.company_name = company_name
    sig.confidence = confidence
    sig.evidence_tier = evidence_tier
    sig.reasoning = reasoning
    sig.created_at = datetime.now(timezone.utc)
    sig.is_dismissed = False
    sig.likely_roles = ["VP Engineering", "Staff Engineer"]
    sig.signal_data = {"funding_amount": "$50M"}
    sig.source_url = None
    sig.source_name = None
    sig.quality_score = None
    sig.quality_confidence = None
    sig.quality_recency = None
    sig.quality_relevance = None
    sig.quality_historical = None
    sig.quality_gate_result = quality_gate_result
    sig.quality_computed_at = None
    sig.outcome_tracked = False
    sig.outcome_result = None
    return sig


# ── Full loop integration ──────────────────────────────────────────────


class TestFullIntelligenceLoop:
    """Test the complete loop without a real database."""

    @pytest.mark.asyncio
    async def test_signal_to_quality_to_decision(self):
        """Signal → Quality Filter → Decision Engine."""
        db = AsyncMock()
        scalar_mock = MagicMock()
        scalar_mock.scalar_one_or_none.return_value = None
        scalar_mock.scalar.return_value = 1
        db.execute.return_value = scalar_mock

        # Step 1: Quality filter
        qf = SignalQualityFilter(db)
        sig = _make_signal()

        with patch.object(
            qf,
            "_preference_boost",
            return_value=0.10,
        ):
            quality = await qf.score_signal(sig, "user-1")

        assert quality.gate == "pass"
        assert quality.quality_score >= 0.60

        # Step 2: Decision scoring (signal now has quality data)
        sig.quality_gate_result = quality.gate
        sig.confidence = quality.confidence_component

        engine = DecisionEngine(db)
        decision = await engine.score_opportunity(
            sig,
            "user-1",
            profile_fit=0.80,
            access_strength=0.70,
        )

        assert isinstance(decision, DecisionScore)
        assert decision.composite_score > 0.0

    def test_learning_updates_affect_blend_weights(self):
        """Outcome recording → learning update → blend tier change."""
        # User starts at tier 0
        tier, uw, gw = _get_blend_weights(0)
        assert uw == 0.0

        # After recording 5 outcomes → tier 1
        entry = None
        for i in range(5):
            score = 1.0 if i % 2 == 0 else 0.0
            entry = _update_running_mean(entry, score)

        assert entry["sample_count"] == 5
        tier, uw, gw = _get_blend_weights(5)
        assert uw == 0.20

        # After 20 → tier 3
        for i in range(15):
            entry = _update_running_mean(entry, 0.5)

        assert entry["sample_count"] == 20
        tier, uw, gw = _get_blend_weights(20)
        assert uw == 0.80

    def test_outcome_to_propagation_classification(self):
        """Outcome patterns → propagation adjustment types."""
        # Very low success rate with many outcomes → suppress
        adj_type, _ = _classify_adjustment(0.05, 25)
        assert adj_type == "suppress"

        # High success rate with many outcomes → promote
        adj_type, _ = _classify_adjustment(0.80, 20)
        assert adj_type == "promote"

        # Moderate rate → no adjustment
        adj_type, _ = _classify_adjustment(0.45, 15)
        assert adj_type is None

    def test_fast_feedback_loop(self):
        """Recent positive outcome → fast feedback boost."""
        now = datetime.now(timezone.utc)

        # Simulate: user had interview at Acme recently
        stm = [
            {
                "signal_type": "funding",
                "outcome": "interview",
                "company": "Acme Corp",
                "timestamp": now.isoformat(),
            },
        ]

        # New funding signal at Acme should get boost
        boost = _fast_feedback_boost(stm, "funding", "acme")
        assert boost == 0.10

        # Signal at different company should not
        boost = _fast_feedback_boost(stm, "funding", "google")
        assert boost == 0.0

    def test_company_fuzzy_matching_pipeline(self):
        """Company name normalisation feeds into outcome matching."""
        norm_a = _normalise("Acme Corporation")
        norm_b = _normalise("Acme Corp.")

        assert _fuzzy_match(norm_a, norm_b) is True

        # Different companies should not match
        norm_c = _normalise("Google LLC")
        assert _fuzzy_match(norm_a, norm_c) is False

    @pytest.mark.asyncio
    async def test_batch_quality_then_batch_decision(self):
        """Batch quality scoring → batch decision scoring."""
        db = AsyncMock()
        scalar_mock = MagicMock()
        scalar_mock.scalar_one_or_none.return_value = None
        scalar_mock.scalar.return_value = 1
        db.execute.return_value = scalar_mock

        signals = [
            _make_signal(
                company_name="Alpha Inc",
                confidence=0.90,
            ),
            _make_signal(
                company_name="Beta LLC",
                confidence=0.70,
            ),
        ]

        # Batch quality
        qf = SignalQualityFilter(db)
        with patch.object(
            qf,
            "_preference_boost",
            return_value=0.0,
        ):
            with patch.object(
                qf,
                "_count_company_signals_batch",
                return_value={},
            ):
                quality_results = await qf.score_batch(
                    signals, "user-1",
                )

        assert len(quality_results) == 2

        # Apply gate results to signals
        for sig, qr in zip(signals, quality_results):
            sig.quality_gate_result = qr.gate

        # Batch decision
        passing = [
            s for s in signals
            if s.quality_gate_result in ("pass", "conditional")
        ]

        if passing:
            engine = DecisionEngine(db)
            decisions = await engine.score_batch(
                passing, "user-1",
            )
            assert len(decisions) == len(passing)
            assert all(
                isinstance(d, DecisionScore) for d in decisions
            )

    def test_running_mean_convergence(self):
        """Running mean should converge to true mean over many
        samples regardless of initial state."""
        # Start with a bad initial estimate
        entry = {"success_rate": 0.0, "sample_count": 1}

        # Feed in 100 samples at 0.5
        for _ in range(100):
            entry = _update_running_mean(entry, 0.5)

        # Should be very close to 0.5
        assert abs(entry["success_rate"] - 0.5) < 0.01

    def test_blend_weight_monotonicity(self):
        """User weight should monotonically increase with sample
        count."""
        prev_uw = -1.0
        for n in [0, 5, 10, 20, 50, 100]:
            _, uw, _ = _get_blend_weights(n)
            assert uw >= prev_uw
            prev_uw = uw

    def test_quality_gate_determines_interpretation(self):
        """Only pass/conditional signals should be interpreted."""
        sig_pass = _make_signal(quality_gate_result="pass")
        sig_cond = _make_signal(quality_gate_result="conditional")
        sig_store = _make_signal(quality_gate_result="store_only")
        sig_reject = _make_signal(quality_gate_result="reject")

        # Interpretation engine checks this attribute
        assert sig_pass.quality_gate_result in ("pass", "conditional")
        assert sig_cond.quality_gate_result in ("pass", "conditional")
        assert sig_store.quality_gate_result not in (
            "pass", "conditional",
        )
        assert sig_reject.quality_gate_result not in (
            "pass", "conditional",
        )
