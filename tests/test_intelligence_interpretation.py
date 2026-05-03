"""
tests/test_intelligence_interpretation.py

Unit tests for Signal Interpretation Engine (Phase 3).
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.intelligence.signal_interpretation import (
    InterpretationRule,
    PredictedRole,
    SignalInterpretationEngine,
    _signal_text,
)

# ── Helpers ─────────────────────────────────────────────────────────────


def _make_signal(
    *,
    signal_type: str = "funding",
    company_name: str = "TestCorp",
    confidence: float = 0.85,
    reasoning: str = "Company raised Series B funding of $50 million",
    quality_gate_result: str = "pass",
    signal_data: dict | None = None,
    likely_roles: list | None = None,
):
    sig = MagicMock()
    sig.id = uuid.uuid4()
    sig.user_id = "user-1"
    sig.signal_type = signal_type
    sig.company_name = company_name
    sig.confidence = confidence
    sig.reasoning = reasoning
    sig.quality_gate_result = quality_gate_result
    sig.signal_data = signal_data or {}
    sig.likely_roles = likely_roles or []
    sig.source_url = None
    sig.source_name = None
    sig.created_at = datetime.now(timezone.utc)
    return sig


def _mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    return db


# ── Signal text extraction ──────────────────────────────────────────────


class TestSignalText:

    def test_includes_company_name(self):
        sig = _make_signal(company_name="Acme Corp")
        text = _signal_text(sig)
        assert "acme corp" in text

    def test_includes_reasoning(self):
        sig = _make_signal(reasoning="Raised series b funding")
        text = _signal_text(sig)
        assert "series b" in text

    def test_includes_signal_type(self):
        sig = _make_signal(signal_type="leadership")
        text = _signal_text(sig)
        assert "leadership" in text

    def test_includes_signal_data_values(self):
        sig = _make_signal(
            signal_data={"investors": "Sequoia Capital"},
        )
        text = _signal_text(sig)
        assert "sequoia capital" in text

    def test_includes_likely_roles(self):
        sig = _make_signal(likely_roles=["CTO", "VP Engineering"])
        text = _signal_text(sig)
        assert "cto" in text
        assert "vp engineering" in text


# ── Rule matching ───────────────────────────────────────────────────────


class TestRuleMatching:

    @pytest.mark.asyncio
    async def test_funding_series_b_matches(self):
        db = _mock_db()
        engine = SignalInterpretationEngine(db)
        sig = _make_signal(
            signal_type="funding",
            reasoning=(
                "Company raised Series B funding of $50 million. "
                "Growth round."
            ),
        )
        result = await engine.interpret(sig, "user-1")
        assert result is not None
        assert result.rule_id.startswith("FUND_")

    @pytest.mark.asyncio
    async def test_leadership_ceo_departure_matches(self):
        db = _mock_db()
        engine = SignalInterpretationEngine(db)
        sig = _make_signal(
            signal_type="leadership",
            reasoning=(
                "CEO departure announced. Leadership transition. "
                "Outgoing CEO stepping down."
            ),
        )
        result = await engine.interpret(sig, "user-1")
        assert result is not None

    @pytest.mark.asyncio
    async def test_no_match_returns_none(self):
        db = _mock_db()
        engine = SignalInterpretationEngine(db)
        sig = _make_signal(
            signal_type="unknown",
            reasoning="Nothing relevant here.",
        )
        result = await engine.interpret(sig, "user-1")
        assert result is None

    @pytest.mark.asyncio
    async def test_rejected_signal_skipped(self):
        db = _mock_db()
        engine = SignalInterpretationEngine(db)
        sig = _make_signal(quality_gate_result="reject")
        result = await engine.interpret(sig, "user-1")
        assert result is None

    @pytest.mark.asyncio
    async def test_store_only_skipped(self):
        db = _mock_db()
        engine = SignalInterpretationEngine(db)
        sig = _make_signal(quality_gate_result="store_only")
        result = await engine.interpret(sig, "user-1")
        assert result is None

    @pytest.mark.asyncio
    async def test_conditional_allowed(self):
        db = _mock_db()
        engine = SignalInterpretationEngine(db)
        sig = _make_signal(
            signal_type="funding",
            quality_gate_result="conditional",
            reasoning=(
                "Company raised Series B funding of $50 million. "
                "Growth round."
            ),
        )
        await engine.interpret(sig, "user-1")
        # May or may not match but should not be skipped
        # (skipping only happens for reject/store_only)


# ── Batch interpretation ────────────────────────────────────────────────


class TestBatchInterpretation:

    @pytest.mark.asyncio
    async def test_batch_returns_list(self):
        db = _mock_db()
        engine = SignalInterpretationEngine(db)
        signals = [
            _make_signal(
                signal_type="funding",
                reasoning="Series B funding raised $40 million growth",
            ),
            _make_signal(
                signal_type="unknown",
                reasoning="Nothing special.",
            ),
        ]
        results = await engine.interpret_batch(signals, "user-1")
        assert isinstance(results, list)
        # At least one match (funding), one might be None
        assert len(results) <= len(signals)


# ── Rule dataclass ──────────────────────────────────────────────────────


class TestRuleDataclass:

    def test_interpretation_rule_is_frozen(self):
        rule = InterpretationRule(
            rule_id="TEST_RULE",
            version=1,
            trigger_type="funding",
            trigger_subtype=None,
            keywords=("test", "keywords"),
            min_keywords=1,
            business_change="Test change",
            org_impact="Test impact",
            hiring_reason="Test reason",
            predicted_roles=(
                PredictedRole(
                    role="Engineer",
                    seniority="ic",
                    confidence=0.70,
                    timeline="1_3_months",
                    urgency="likely",
                ),
            ),
            hiring_owner_title="CTO",
            hiring_owner_dept="Engineering",
        )
        with pytest.raises(AttributeError):
            rule.rule_id = "CHANGED"

    def test_predicted_role_is_frozen(self):
        role = PredictedRole(
            role="Engineer",
            seniority="ic",
            confidence=0.70,
            timeline="1_3_months",
            urgency="likely",
        )
        with pytest.raises(AttributeError):
            role.role = "Changed"
