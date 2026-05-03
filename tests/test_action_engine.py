"""
tests/test_action_engine.py

Integration tests for the Action Engine (Phases 1-6).

Covers:
  - signal → interpretation → decision → action generation
  - action lifecycle transitions
  - quick-start → actions
  - extension capture → signal creation
  - plan gating limits
  - value/ROI insights output
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.action.action_executor import (
    _VALID_TRANSITIONS,
    ActionExecutor,
)
from app.services.action.action_generator import (
    _TYPE_PRIORITY,
    ActionGenerator,
    GeneratedAction,
)
from app.services.billing.plan_gating import (
    get_intelligence_limits,
)
from app.services.intelligence.decision_engine import (
    DecisionScore,
)

# ── Helpers ──────────────────────────────────────────────────────────


def _make_signal(
    *,
    signal_type: str = "funding",
    company_name: str = "TestCorp",
    confidence: float = 0.80,
):
    """Create a mock HiddenSignal."""
    sig = MagicMock()
    sig.id = uuid.uuid4()
    sig.user_id = "user-1"
    sig.signal_type = signal_type
    sig.company_name = company_name
    sig.confidence = confidence
    sig.reasoning = "Series B raised"
    sig.likely_roles = [{"role": "Staff Engineer"}]
    sig.source_url = None
    sig.source_name = None
    sig.created_at = datetime.now(timezone.utc)
    sig.is_dismissed = False
    sig.quality_gate_result = "pass"
    sig.outcome_tracked = False
    sig.outcome_result = None
    sig.signal_data = {}
    sig.evidence_tier = "strong"
    return sig


def _make_interpretation(signal_id):
    """Create a mock SignalInterpretation."""
    interp = MagicMock()
    interp.id = uuid.uuid4()
    interp.signal_id = signal_id
    interp.user_id = "user-1"
    interp.business_change = "Company expanding EU operations"
    interp.hiring_reason = "Need local engineering leads"
    interp.hiring_owner_title = "VP Engineering"
    interp.hiring_owner_dept = "Engineering"
    interp.predicted_roles = [
        {
            "role": "Senior Backend Engineer",
            "confidence": 0.85,
            "timeline": "1_3_months",
            "urgency": "likely",
        },
    ]
    return interp


def _make_decision(
    composite: float = 0.72,
    access: float = 0.65,
):
    """Create a DecisionScore."""
    return DecisionScore(
        composite_score=composite,
        profile_fit=0.70,
        signal_strength=0.80,
        company_responsiveness=0.60,
        access_strength=access,
        timing=0.75,
        recency=0.90,
        fast_feedback_boost=0.0,
        blend_tier=2,
        user_weight=0.50,
        global_weight=0.50,
    )


# ══════════════════════════════════════════════════════════════════════
# 1. Signal → Decision → Action generation
# ══════════════════════════════════════════════════════════════════════


class TestActionGeneration:
    """Test action generation from pipeline objects."""

    @pytest.fixture()
    def db(self):
        return AsyncMock()

    @pytest.mark.asyncio()
    async def test_generates_actions_from_real_objects(
        self, db,
    ):
        """Actions are generated from real signal +
        interpretation + decision objects."""
        signal = _make_signal()
        interp = _make_interpretation(signal.id)
        decision = _make_decision(composite=0.72)

        gen = ActionGenerator(db)
        actions = await gen.generate_actions(
            signal=signal,
            interpretation=interp,
            decision=decision,
            user_id="user-1",
        )

        assert len(actions) > 0
        for a in actions:
            assert isinstance(a, GeneratedAction)
            assert a.target_company == "TestCorp"
            assert a.confidence > 0
            assert a.priority in _TYPE_PRIORITY.values()

    @pytest.mark.asyncio()
    async def test_linkedin_threshold(self, db):
        """LinkedIn actions require composite >= 0.40."""
        signal = _make_signal()
        decision = _make_decision(composite=0.39)

        gen = ActionGenerator(db)
        actions = await gen.generate_actions(
            signal=signal,
            interpretation=None,
            decision=decision,
            user_id="user-1",
        )

        types = [a.action_type for a in actions]
        assert "linkedin_message" not in types

    @pytest.mark.asyncio()
    async def test_email_threshold(self, db):
        """Email outreach requires composite >= 0.50."""
        signal = _make_signal()
        decision = _make_decision(composite=0.49)

        gen = ActionGenerator(db)
        actions = await gen.generate_actions(
            signal=signal,
            interpretation=None,
            decision=decision,
            user_id="user-1",
        )

        types = [a.action_type for a in actions]
        assert "email_outreach" not in types

    @pytest.mark.asyncio()
    async def test_referral_requires_access(self, db):
        """Referral actions require access_strength >= 0.60."""
        signal = _make_signal()
        decision = _make_decision(
            composite=0.80, access=0.59,
        )

        gen = ActionGenerator(db)
        actions = await gen.generate_actions(
            signal=signal,
            interpretation=None,
            decision=decision,
            user_id="user-1",
        )

        types = [a.action_type for a in actions]
        assert "referral_request" not in types

    @pytest.mark.asyncio()
    async def test_high_score_generates_all_types(
        self, db,
    ):
        """A high composite + access score generates all
        action types."""
        signal = _make_signal()
        interp = _make_interpretation(signal.id)
        decision = _make_decision(
            composite=0.85, access=0.70,
        )

        gen = ActionGenerator(db)
        actions = await gen.generate_actions(
            signal=signal,
            interpretation=interp,
            decision=decision,
            user_id="user-1",
        )

        types = {a.action_type for a in actions}
        assert "linkedin_message" in types
        assert "email_outreach" in types
        assert "referral_request" in types
        assert "follow_up_sequence" in types

    @pytest.mark.asyncio()
    async def test_no_duplicate_actions(self, db):
        """Each action type appears at most once."""
        signal = _make_signal()
        decision = _make_decision(
            composite=0.85, access=0.70,
        )

        gen = ActionGenerator(db)
        actions = await gen.generate_actions(
            signal=signal,
            interpretation=None,
            decision=decision,
            user_id="user-1",
        )

        types = [a.action_type for a in actions]
        assert len(types) == len(set(types))

    @pytest.mark.asyncio()
    async def test_reason_from_interpretation(self, db):
        """When interpretation exists, reason uses
        business_change + hiring_reason."""
        signal = _make_signal()
        interp = _make_interpretation(signal.id)
        decision = _make_decision(composite=0.60)

        gen = ActionGenerator(db)
        actions = await gen.generate_actions(
            signal=signal,
            interpretation=interp,
            decision=decision,
            user_id="user-1",
        )

        assert len(actions) > 0
        reason = actions[0].reason
        assert "EU operations" in reason
        assert "engineering leads" in reason

    @pytest.mark.asyncio()
    async def test_reason_fallback_to_signal(self, db):
        """Without interpretation, reason falls back to
        signal.reasoning."""
        signal = _make_signal()
        signal.reasoning = "Strong funding signal detected"
        decision = _make_decision(composite=0.60)

        gen = ActionGenerator(db)
        actions = await gen.generate_actions(
            signal=signal,
            interpretation=None,
            decision=decision,
            user_id="user-1",
        )

        assert len(actions) > 0
        assert "Strong funding" in actions[0].reason


# ══════════════════════════════════════════════════════════════════════
# 2. Action lifecycle transitions
# ══════════════════════════════════════════════════════════════════════


class TestActionLifecycle:
    """Test lifecycle state machine transitions."""

    def test_valid_transitions_complete(self):
        """All defined states have entries in the
        transitions dict."""
        all_states = {
            "generated", "queued", "sent",
            "responded", "expired", "dismissed",
        }
        assert set(_VALID_TRANSITIONS.keys()) == all_states

    def test_terminal_states_have_no_exits(self):
        """Terminal states cannot transition further."""
        for state in ("responded", "expired", "dismissed"):
            assert _VALID_TRANSITIONS[state] == set()

    def test_generated_can_queue(self):
        assert "queued" in _VALID_TRANSITIONS["generated"]

    def test_generated_can_dismiss(self):
        assert "dismissed" in _VALID_TRANSITIONS["generated"]

    def test_queued_can_send(self):
        assert "sent" in _VALID_TRANSITIONS["queued"]

    def test_sent_can_respond(self):
        assert "responded" in _VALID_TRANSITIONS["sent"]

    def test_cannot_skip_queue_to_respond(self):
        """Cannot go generated → responded directly."""
        assert (
            "responded"
            not in _VALID_TRANSITIONS["generated"]
        )

    @pytest.mark.asyncio()
    async def test_executor_rejects_invalid_transition(
        self,
    ):
        """Executor returns None for invalid transitions."""
        db = AsyncMock()
        record = MagicMock()
        record.status = "responded"  # terminal
        record.id = str(uuid.uuid4())

        # Mock _load_action to return our record
        executor = ActionExecutor(db)
        executor._load_action = AsyncMock(
            return_value=record,
        )

        result = await executor._transition(
            str(record.id), "user-1", "queued",
        )
        assert result is None

    @pytest.mark.asyncio()
    async def test_executor_valid_transition_sets_status(
        self,
    ):
        """Executor updates status and timestamp on
        valid transition."""
        db = AsyncMock()
        record = MagicMock()
        record.status = "generated"
        record.id = str(uuid.uuid4())

        executor = ActionExecutor(db)
        executor._load_action = AsyncMock(
            return_value=record,
        )

        result = await executor._transition(
            str(record.id), "user-1", "queued",
        )
        assert result is not None
        assert record.status == "queued"
        assert record.queued_at is not None


# ══════════════════════════════════════════════════════════════════════
# 3. Quick Start → Actions
# ══════════════════════════════════════════════════════════════════════


class TestQuickStart:
    """Test quick-start engine output."""

    @pytest.mark.asyncio()
    async def test_empty_when_no_signals(self):
        """Returns empty result when user has no signals."""
        from app.services.entry.quick_start_engine import (
            QuickStartEngine,
        )

        db = AsyncMock()
        # Mock execute to return no results
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute.return_value = mock_result

        engine = QuickStartEngine(db)
        result = await engine.quick_start("user-1")

        assert result["signals"] == []
        assert result["actions"] == []
        assert result["summary"]["total_signals"] == 0

    @pytest.mark.asyncio()
    async def test_returns_scored_signals_and_actions(
        self,
    ):
        """With signals, returns scored items and actions."""
        from app.services.entry.quick_start_engine import (
            QuickStartEngine,
        )

        signal = _make_signal()
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            signal,
        ]
        db.execute.return_value = mock_result

        decision = _make_decision(composite=0.60)

        with patch(
            "app.services.entry.quick_start_engine"
            ".DecisionEngine",
        ) as mock_de:
            mock_de_inst = AsyncMock()
            mock_de_inst.score_opportunity.return_value = (
                decision
            )
            mock_de.return_value = mock_de_inst

            engine = QuickStartEngine(db)
            result = await engine.quick_start("user-1")

        assert len(result["signals"]) == 1
        assert (
            result["signals"][0]["company"] == "TestCorp"
        )
        assert result["signals"][0]["decision_score"] == (
            0.60
        )
        assert result["summary"]["total_signals"] == 1

    @pytest.mark.asyncio()
    async def test_target_role_in_summary(self):
        """Target role is included in summary output."""
        from app.services.entry.quick_start_engine import (
            QuickStartEngine,
        )

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute.return_value = mock_result

        engine = QuickStartEngine(db)
        result = await engine.quick_start(
            "user-1", target_role="Staff Engineer",
        )

        assert (
            result["summary"]["target_role"]
            == "Staff Engineer"
        )

    @pytest.mark.asyncio()
    async def test_max_three_actions(self):
        """Quick-start returns at most 3 actions."""
        from app.services.entry.quick_start_engine import (
            _MAX_ACTIONS,
            QuickStartEngine,
        )

        assert _MAX_ACTIONS == 3

        signals = [_make_signal() for _ in range(5)]
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = (
            signals
        )
        db.execute.return_value = mock_result

        decision = _make_decision(composite=0.85)

        with patch(
            "app.services.entry.quick_start_engine"
            ".DecisionEngine",
        ) as mock_de:
            mock_de_inst = AsyncMock()
            mock_de_inst.score_opportunity.return_value = (
                decision
            )
            mock_de.return_value = mock_de_inst

            engine = QuickStartEngine(db)
            result = await engine.quick_start("user-1")

        assert len(result["actions"]) <= _MAX_ACTIONS


# ══════════════════════════════════════════════════════════════════════
# 4. Extension capture → signal creation
# ══════════════════════════════════════════════════════════════════════


class TestExtensionCapture:
    """Test extension capture signal creation logic."""

    def test_profile_hiring_keywords(self):
        """Profile capture detects hiring signals from
        headline keywords."""
        from app.schemas.extension import (
            CaptureProfileRequest,
        )

        # Hiring headline
        req = CaptureProfileRequest(
            linkedin_url="https://linkedin.com/in/test",
            full_name="Jane Smith",
            headline="VP Engineering at TestCorp",
            company="TestCorp",
        )
        assert "vp" in req.headline.lower()

        # Non-hiring headline
        req2 = CaptureProfileRequest(
            linkedin_url="https://linkedin.com/in/test",
            full_name="Bob Dev",
            headline="Software Developer",
            company="TestCorp",
        )
        hiring_keywords = [
            "hiring", "recruiting", "talent",
            "head of", "vp", "director", "cto",
            "ceo", "founder",
        ]
        headline_lower = req2.headline.lower()
        is_hiring = any(
            kw in headline_lower
            for kw in hiring_keywords
        )
        assert not is_hiring

    def test_job_capture_creates_signal_data(self):
        """Job capture request has all required fields."""
        from app.schemas.extension import (
            CaptureJobRequest,
        )

        req = CaptureJobRequest(
            job_url="https://example.com/job/123",
            title="Staff Engineer",
            company="TestCorp",
            location="London, UK",
            description="Build distributed systems...",
        )
        assert req.company == "TestCorp"
        assert req.title == "Staff Engineer"

    def test_company_capture_accepts_posts(self):
        """Company capture accepts recent_posts list."""
        from app.schemas.extension import (
            CaptureCompanyRequest,
        )

        req = CaptureCompanyRequest(
            company_url="https://linkedin.com/company/test",
            company_name="TestCorp",
            industry="Technology",
            size="500-1000",
            recent_posts=[
                {"text": "We're hiring!", "date": "2026-01"},
            ],
        )
        assert len(req.recent_posts) == 1


# ══════════════════════════════════════════════════════════════════════
# 5. Plan gating limits
# ══════════════════════════════════════════════════════════════════════


class TestPlanGating:
    """Test intelligence plan gating configuration."""

    def test_free_plan_limits(self):
        """FREE plan has restricted intelligence access."""
        from app.models.subscription import PlanTier

        limits = get_intelligence_limits(PlanTier.FREE)
        assert limits["actions_per_month"] == 5
        assert limits["signals_max"] == 10
        assert limits["quick_starts_per_day"] == 1
        assert limits["has_value_insights"] is False
        assert limits["has_extension_capture"] is False

    def test_starter_plan_limits(self):
        """STARTER plan has moderate limits."""
        from app.models.subscription import PlanTier

        limits = get_intelligence_limits(PlanTier.STARTER)
        assert limits["actions_per_month"] == 20
        assert limits["has_value_insights"] is True
        assert limits["has_extension_capture"] is True

    def test_pro_plan_limits(self):
        """PRO plan has high limits."""
        from app.models.subscription import PlanTier

        limits = get_intelligence_limits(PlanTier.PRO)
        assert limits["actions_per_month"] == 100
        assert limits["signals_max"] is None  # unlimited
        assert limits["has_value_insights"] is True

    def test_unlimited_plan_limits(self):
        """UNLIMITED plan has no limits."""
        from app.models.subscription import PlanTier

        limits = get_intelligence_limits(PlanTier.UNLIMITED)
        assert limits["actions_per_month"] is None
        assert limits["signals_max"] is None
        assert limits["quick_starts_per_day"] is None

    def test_all_plan_tiers_defined(self):
        """All plan tiers have intelligence limits."""
        from app.models.subscription import PlanTier

        for tier in PlanTier:
            limits = get_intelligence_limits(tier)
            assert isinstance(limits, dict)
            assert "actions_per_month" in limits


# ══════════════════════════════════════════════════════════════════════
# 6. Value / ROI insights output
# ══════════════════════════════════════════════════════════════════════


class TestValueEngine:
    """Test value engine output structure."""

    @pytest.mark.asyncio()
    async def test_compute_insights_structure(self):
        """compute_insights returns all expected keys."""
        from app.services.intelligence.value_engine import (
            ValueEngine,
        )

        db = AsyncMock()
        # Mock all DB queries to return empty results
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_result.one.return_value = MagicMock(
            avg_to_send=None, avg_to_respond=None,
        )
        mock_result.scalar_one_or_none.return_value = None
        db.execute.return_value = mock_result

        engine = ValueEngine(db)
        result = await engine.compute_insights("user-1")

        assert result["user_id"] == "user-1"
        assert "computed_at" in result
        assert "signal_effectiveness" in result
        assert "action_effectiveness" in result
        assert "path_performance" in result
        assert "timing" in result
        assert "summary" in result
        assert "recommendations" in result

    def test_build_summary_aggregates(self):
        """_build_summary aggregates stats correctly."""
        from app.services.intelligence.value_engine import (
            ValueEngine,
        )

        signal_stats = [
            {
                "signal_type": "funding",
                "total_signals": 10,
                "positive_outcomes": 3,
                "hires": 1,
                "success_rate": 0.30,
                "hire_rate": 0.10,
            },
            {
                "signal_type": "leadership",
                "total_signals": 5,
                "positive_outcomes": 2,
                "hires": 0,
                "success_rate": 0.40,
                "hire_rate": 0.00,
            },
        ]
        action_stats = [
            {
                "action_type": "linkedin_message",
                "total_generated": 8,
                "sent": 5,
                "responded": 2,
                "dismissed": 1,
                "response_rate": 0.29,
                "execution_rate": 0.88,
            },
        ]
        path_stats = [
            {
                "path": "warm_intro",
                "success_rate": 0.45,
                "sample_count": 10,
            },
        ]

        summary = ValueEngine._build_summary(
            signal_stats, action_stats, path_stats,
        )

        assert summary["total_signals_tracked"] == 15
        assert summary["total_positive_outcomes"] == 5
        assert summary["total_hires"] == 1
        assert summary["best_signal_type"] == "leadership"
        assert summary["best_path"] == "warm_intro"

    def test_generate_recommendations(self):
        """_generate_recommendations produces actionable
        recs from stats."""
        from app.services.intelligence.value_engine import (
            ValueEngine,
        )

        signal_stats = [
            {
                "signal_type": "funding",
                "total_signals": 10,
                "positive_outcomes": 5,
                "hires": 2,
                "success_rate": 0.50,
                "hire_rate": 0.20,
            },
            {
                "signal_type": "expansion",
                "total_signals": 8,
                "positive_outcomes": 0,
                "hires": 0,
                "success_rate": 0.00,
                "hire_rate": 0.00,
            },
        ]
        action_stats = [
            {
                "action_type": "linkedin_message",
                "total_generated": 5,
                "sent": 3,
                "responded": 2,
                "dismissed": 0,
                "response_rate": 0.40,
                "execution_rate": 1.0,
            },
        ]
        path_stats = [
            {
                "path": "warm_intro",
                "success_rate": 0.60,
                "sample_count": 5,
            },
        ]

        recs = ValueEngine._generate_recommendations(
            signal_stats, action_stats, path_stats,
        )

        assert len(recs) >= 2
        titles = [r["title"] for r in recs]
        # Should recommend best signal
        assert any("funding" in t for t in titles)
        # Should warn about low-performing signal
        assert any("expansion" in t for t in titles)


# ══════════════════════════════════════════════════════════════════════
# 7. Schema validation
# ══════════════════════════════════════════════════════════════════════


class TestSchemas:
    """Test schema consistency."""

    def test_action_item_defaults(self):
        """ActionItem has sensible defaults."""
        from app.schemas.actions import ActionItem

        item = ActionItem()
        assert item.status == "generated"
        assert item.priority == 50
        assert item.confidence == 0.0

    def test_insights_response_defaults(self):
        """InsightsResponse has empty defaults."""
        from app.schemas.insights import InsightsResponse

        resp = InsightsResponse()
        assert resp.signal_effectiveness == []
        assert resp.recommendations == []

    def test_quick_start_response_defaults(self):
        """QuickStartResponse has empty defaults."""
        from app.schemas.quick_start import (
            QuickStartResponse,
        )

        resp = QuickStartResponse()
        assert resp.signals == []
        assert resp.actions == []

    def test_capture_response_defaults(self):
        """CaptureResponse has sensible defaults."""
        from app.schemas.extension import CaptureResponse

        resp = CaptureResponse()
        assert resp.success is True
        assert resp.signals_created == 0

    def test_action_status_values_consistent(self):
        """All lifecycle states are in the transition dict."""
        from app.schemas.actions import ActionItem

        valid_statuses = set(_VALID_TRANSITIONS.keys())
        # Default status should be valid
        item = ActionItem()
        assert item.status in valid_statuses
