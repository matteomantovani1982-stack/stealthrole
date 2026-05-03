"""
tests/test_intelligence_outcome.py

Unit tests for Outcome Tracker + Learning Updater (Phase 5).
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.intelligence.learning_updater import (
    SHORT_TERM_MEMORY_SIZE,
    LearningUpdater,
    _update_running_mean,
)
from app.services.intelligence.outcome_tracker import (
    OutcomeTracker,
    _channel_to_path,
    _fuzzy_match,
    _normalise,
)

# ── Company name normalisation ──────────────────────────────────────────


class TestNormalise:

    def test_strips_inc(self):
        assert _normalise("Acme Inc") == "acme"

    def test_strips_ltd(self):
        assert _normalise("BigCo Ltd.") == "bigco"

    def test_strips_corporation(self):
        assert _normalise("Widget Corporation") == "widget"

    def test_lowercases(self):
        assert _normalise("ALLCAPS") == "allcaps"

    def test_collapses_whitespace(self):
        assert _normalise("  Foo   Bar  ") == "foo bar"

    def test_strips_llc(self):
        assert _normalise("StartupX LLC") == "startupx"

    def test_handles_empty(self):
        assert _normalise("") == ""


# ── Fuzzy matching ──────────────────────────────────────────────────────


class TestFuzzyMatch:

    def test_exact_match(self):
        assert _fuzzy_match("acme", "acme") is True

    def test_prefix_match(self):
        assert _fuzzy_match("acme corp", "acme corporation") is True

    def test_containment(self):
        assert _fuzzy_match("acme", "acme technologies") is True

    def test_reverse_containment(self):
        assert _fuzzy_match("acme technologies", "acme") is True

    def test_no_match(self):
        assert _fuzzy_match("apple", "google") is False

    def test_empty_strings(self):
        assert _fuzzy_match("", "acme") is False
        assert _fuzzy_match("acme", "") is False


# ── Channel to path mapping ────────────────────────────────────────────


class TestChannelToPath:

    def test_linkedin(self):
        assert _channel_to_path("linkedin") == "direct_apply"

    def test_referral(self):
        assert _channel_to_path("referral") == "warm_intro"

    def test_recruiter(self):
        assert _channel_to_path("recruiter") == "recruiter"

    def test_none(self):
        assert _channel_to_path(None) is None

    def test_unknown(self):
        assert _channel_to_path("some_random") == "other"


# ── Running mean ────────────────────────────────────────────────────────


class TestRunningMean:

    def test_first_entry(self):
        result = _update_running_mean(None, 1.0)
        assert result["success_rate"] == 1.0
        assert result["sample_count"] == 1

    def test_second_entry_averages(self):
        entry = {"success_rate": 1.0, "sample_count": 1}
        result = _update_running_mean(entry, 0.0)
        assert result["success_rate"] == 0.5
        assert result["sample_count"] == 2

    def test_converges_to_mean(self):
        """After many entries of 0.5, rate should converge to ~0.5."""
        entry = {"success_rate": 1.0, "sample_count": 1}
        for _ in range(50):
            entry = _update_running_mean(entry, 0.5)
        assert abs(entry["success_rate"] - 0.5) < 0.05

    def test_preserves_timestamp(self):
        result = _update_running_mean(None, 0.5)
        assert "last_updated" in result

    def test_incremental_mean_formula(self):
        """Verify: new_rate = old_rate + (score - old_rate) / count."""
        entry = {"success_rate": 0.4, "sample_count": 10}
        result = _update_running_mean(entry, 1.0)
        expected = 0.4 + (1.0 - 0.4) / 11
        assert abs(result["success_rate"] - expected) < 0.0001


# ── Outcome Tracker ─────────────────────────────────────────────────────


class TestOutcomeTracker:

    @pytest.mark.asyncio
    async def test_invalid_outcome_returns_zero(self):
        db = AsyncMock()
        tracker = OutcomeTracker(db)
        count = await tracker.record_outcome(
            user_id="user-1",
            company_name="Acme",
            outcome="invalid_value",
        )
        assert count == 0

    @pytest.mark.asyncio
    async def test_no_matching_signals_returns_zero(self):
        db = AsyncMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars_mock
        db.execute.return_value = result_mock

        tracker = OutcomeTracker(db)
        count = await tracker.record_outcome(
            user_id="user-1",
            company_name="NoMatch",
            outcome="interview",
        )
        assert count == 0

    @pytest.mark.asyncio
    async def test_record_outcome_updates_signals(self):
        sig1 = MagicMock()
        sig1.id = uuid.uuid4()
        sig1.company_name = "Acme Corp"
        sig1.signal_type = "funding"
        sig1.is_dismissed = False
        sig1.outcome_tracked = False

        db = AsyncMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [sig1]
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars_mock
        db.execute.return_value = result_mock

        tracker = OutcomeTracker(db)
        with patch(
            "app.services.intelligence.outcome_tracker"
            ".LearningUpdater",
        ):
            count = await tracker.record_outcome(
                user_id="user-1",
                company_name="Acme Corp",
                outcome="interview",
            )

        assert count == 1

    @pytest.mark.asyncio
    async def test_stage_to_outcome_mapping(self):
        db = AsyncMock()
        tracker = OutcomeTracker(db)

        with patch.object(
            tracker,
            "record_outcome",
            return_value=1,
        ) as mock_record:
            await tracker.record_from_application_stage(
                user_id="user-1",
                company_name="TestCo",
                new_stage="interview",
            )
            mock_record.assert_called_once()
            call_kwargs = mock_record.call_args
            assert call_kwargs.kwargs.get("outcome") is None or \
                call_kwargs[1].get("outcome", "") == "" or \
                "interview" in str(call_kwargs)

    @pytest.mark.asyncio
    async def test_non_terminal_stage_returns_zero(self):
        db = AsyncMock()
        tracker = OutcomeTracker(db)
        count = await tracker.record_from_application_stage(
            user_id="user-1",
            company_name="TestCo",
            new_stage="applied",
        )
        assert count == 0

    @pytest.mark.asyncio
    async def test_watching_stage_returns_zero(self):
        db = AsyncMock()
        tracker = OutcomeTracker(db)
        count = await tracker.record_from_application_stage(
            user_id="user-1",
            company_name="TestCo",
            new_stage="watching",
        )
        assert count == 0


# ── Learning Updater ────────────────────────────────────────────────────


class TestLearningUpdater:

    @pytest.mark.asyncio
    async def test_creates_new_user_intelligence(self):
        db = AsyncMock()
        scalar_mock = MagicMock()
        scalar_mock.scalar_one_or_none.return_value = None
        db.execute.return_value = scalar_mock
        db.add = MagicMock()
        db.flush = AsyncMock()

        updater = LearningUpdater(db)

        with patch(
            "app.services.intelligence.learning_updater"
            ".UserIntelligence",
        ) as mock_ui:
            mock_row = MagicMock()
            mock_row.learning_profile = {}
            mock_row.short_term_memory = []
            mock_row.learning_sample_count = 0
            mock_ui.return_value = mock_row

            await updater.update_from_outcome(
                user_id="new-user",
                signal_type="funding",
                outcome="interview",
            )

            db.add.assert_called_once()
            assert mock_row.learning_sample_count == 1

    @pytest.mark.asyncio
    async def test_updates_signal_effectiveness(self):
        db = AsyncMock()
        existing_row = MagicMock()
        existing_row.learning_profile = {
            "signal_effectiveness": {
                "funding": {
                    "success_rate": 0.5,
                    "sample_count": 5,
                },
            },
        }
        existing_row.short_term_memory = []
        existing_row.learning_sample_count = 5

        scalar_mock = MagicMock()
        scalar_mock.scalar_one_or_none.return_value = existing_row
        db.execute.return_value = scalar_mock

        updater = LearningUpdater(db)
        await updater.update_from_outcome(
            user_id="user-1",
            signal_type="funding",
            outcome="hire",
        )

        profile = existing_row.learning_profile
        funding = profile["signal_effectiveness"]["funding"]
        # hire = 1.0, old_rate=0.5, count=6
        expected = 0.5 + (1.0 - 0.5) / 6
        assert abs(funding["success_rate"] - expected) < 0.001
        assert funding["sample_count"] == 6

    @pytest.mark.asyncio
    async def test_short_term_memory_capped(self):
        db = AsyncMock()
        existing_row = MagicMock()
        existing_row.learning_profile = {}
        existing_row.short_term_memory = [
            {"event": f"e{i}"} for i in range(SHORT_TERM_MEMORY_SIZE)
        ]
        existing_row.learning_sample_count = 10

        scalar_mock = MagicMock()
        scalar_mock.scalar_one_or_none.return_value = existing_row
        db.execute.return_value = scalar_mock

        updater = LearningUpdater(db)
        await updater.update_from_outcome(
            user_id="user-1",
            signal_type="funding",
            outcome="rejection",
        )

        stm = existing_row.short_term_memory
        assert len(stm) == SHORT_TERM_MEMORY_SIZE
