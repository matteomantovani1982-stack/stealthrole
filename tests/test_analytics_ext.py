"""
tests/test_analytics_ext.py

Unit tests for analytics extensions: shadow metrics and weekly trends.
"""

import sys
import uuid
from datetime import UTC, datetime, timedelta
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure asyncpg is available as a mock so the import chain doesn't fail
if "asyncpg" not in sys.modules:
    sys.modules["asyncpg"] = ModuleType("asyncpg")


# ════════════════════════════════════════════════════════════
# Shadow metrics in analytics summary
# ════════════════════════════════════════════════════════════

class TestAnalyticsSummaryResponse:
    """Verify the summary endpoint returns shadow metrics fields."""

    @pytest.mark.asyncio
    async def test_summary_includes_shadow_fields(self):
        """Summary response must include shadow metrics."""
        from app.api.routes.analytics import analytics_summary

        mock_db = AsyncMock()
        # Mock execute calls in order:
        # 1. total job runs
        # 2. job run stages
        # 3. avg keyword score
        # 4. total shadows
        # 5. shadow by status
        # 6. shadow by signal type
        # 7. avg confidence
        mock_total = MagicMock()
        mock_total.scalar.return_value = 5

        mock_stages = MagicMock()
        mock_stages.all.return_value = [("applied", 3), ("watching", 2)]

        mock_avg_score = MagicMock()
        mock_avg_score.scalar.return_value = 75.5

        mock_shadow_total = MagicMock()
        mock_shadow_total.scalar.return_value = 3

        mock_shadow_status = MagicMock()
        mock_shadow_status.all.return_value = [("completed", 2), ("generating", 1)]

        mock_shadow_signal = MagicMock()
        mock_shadow_signal.all.return_value = [("funding_round", 2), ("job_posting", 1)]

        mock_avg_confidence = MagicMock()
        mock_avg_confidence.scalar.return_value = 0.82

        mock_db.execute = AsyncMock(side_effect=[
            mock_total, mock_stages, mock_avg_score,
            mock_shadow_total, mock_shadow_status, mock_shadow_signal,
            mock_avg_confidence,
        ])

        result = await analytics_summary(current_user_id="user-123", db=mock_db)

        assert result["total_applications"] == 5
        assert result["total_shadows"] == 3
        assert result["shadow_by_status"] == {"completed": 2, "generating": 1}
        assert result["shadow_by_signal"] == {"funding_round": 2, "job_posting": 1}
        assert result["avg_shadow_confidence"] == 0.82
        assert result["response_rate"] == 0.0  # no interviewing/offer
        assert result["avg_keyword_score"] == 75.5

    @pytest.mark.asyncio
    async def test_summary_empty_shadows(self):
        """Shadow fields should be zero/empty when user has no shadows."""
        from app.api.routes.analytics import analytics_summary

        mock_db = AsyncMock()
        mock_total = MagicMock()
        mock_total.scalar.return_value = 0

        mock_stages = MagicMock()
        mock_stages.all.return_value = []

        mock_avg_score = MagicMock()
        mock_avg_score.scalar.return_value = None

        mock_shadow_total = MagicMock()
        mock_shadow_total.scalar.return_value = 0

        mock_shadow_status = MagicMock()
        mock_shadow_status.all.return_value = []

        mock_shadow_signal = MagicMock()
        mock_shadow_signal.all.return_value = []

        mock_avg_confidence = MagicMock()
        mock_avg_confidence.scalar.return_value = None

        mock_db.execute = AsyncMock(side_effect=[
            mock_total, mock_stages, mock_avg_score,
            mock_shadow_total, mock_shadow_status, mock_shadow_signal,
            mock_avg_confidence,
        ])

        result = await analytics_summary(current_user_id="user-123", db=mock_db)

        assert result["total_shadows"] == 0
        assert result["shadow_by_status"] == {}
        assert result["shadow_by_signal"] == {}
        assert result["avg_shadow_confidence"] is None


# ════════════════════════════════════════════════════════════
# Weekly trends endpoint
# ════════════════════════════════════════════════════════════

class TestAnalyticsTrends:
    """Verify the trends endpoint returns weekly data."""

    @pytest.mark.asyncio
    async def test_trends_returns_weekly_data(self):
        """Trends should return applications and shadows per week."""
        from app.api.routes.analytics import analytics_trends

        mock_db = AsyncMock()

        week1 = datetime(2026, 3, 9, tzinfo=UTC)
        week2 = datetime(2026, 3, 16, tzinfo=UTC)

        mock_app_rows = MagicMock()
        mock_app_rows.all.return_value = [(week1, 2), (week2, 3)]

        mock_shadow_rows = MagicMock()
        mock_shadow_rows.all.return_value = [(week2, 1)]

        mock_db.execute = AsyncMock(side_effect=[mock_app_rows, mock_shadow_rows])

        result = await analytics_trends(current_user_id="user-123", db=mock_db, weeks=8)

        assert result["weeks"] == 8
        assert len(result["applications"]) == 2
        assert result["applications"][0]["count"] == 2
        assert result["applications"][1]["count"] == 3
        assert len(result["shadows"]) == 1
        assert result["shadows"][0]["count"] == 1

    @pytest.mark.asyncio
    async def test_trends_empty(self):
        """Trends should return empty lists when no activity."""
        from app.api.routes.analytics import analytics_trends

        mock_db = AsyncMock()

        mock_app_rows = MagicMock()
        mock_app_rows.all.return_value = []

        mock_shadow_rows = MagicMock()
        mock_shadow_rows.all.return_value = []

        mock_db.execute = AsyncMock(side_effect=[mock_app_rows, mock_shadow_rows])

        result = await analytics_trends(current_user_id="user-123", db=mock_db, weeks=4)

        assert result["weeks"] == 4
        assert result["applications"] == []
        assert result["shadows"] == []


# ════════════════════════════════════════════════════════════
# Response rate calculation
# ════════════════════════════════════════════════════════════

class TestResponseRate:
    """Verify response rate calculation in summary."""

    @pytest.mark.asyncio
    async def test_response_rate_with_interviews(self):
        """Response rate = (interviewing + offer) / (applied + interviewing + offer + rejected) * 100."""
        from app.api.routes.analytics import analytics_summary

        mock_db = AsyncMock()
        mock_total = MagicMock()
        mock_total.scalar.return_value = 10

        mock_stages = MagicMock()
        mock_stages.all.return_value = [
            ("applied", 5), ("interviewing", 3), ("offer", 1), ("rejected", 1),
        ]

        mock_avg_score = MagicMock()
        mock_avg_score.scalar.return_value = 80.0

        mock_shadow_total = MagicMock()
        mock_shadow_total.scalar.return_value = 0
        mock_shadow_status = MagicMock()
        mock_shadow_status.all.return_value = []
        mock_shadow_signal = MagicMock()
        mock_shadow_signal.all.return_value = []
        mock_avg_confidence = MagicMock()
        mock_avg_confidence.scalar.return_value = None

        mock_db.execute = AsyncMock(side_effect=[
            mock_total, mock_stages, mock_avg_score,
            mock_shadow_total, mock_shadow_status, mock_shadow_signal,
            mock_avg_confidence,
        ])

        result = await analytics_summary(current_user_id="user-123", db=mock_db)

        # (3 + 1) / (5 + 3 + 1 + 1) * 100 = 40.0
        assert result["response_rate"] == 40.0
