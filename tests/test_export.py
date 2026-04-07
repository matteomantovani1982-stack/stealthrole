"""
tests/test_export.py

Unit tests for CSV export endpoints (Sprint T).
"""

import csv
import io
import sys
import uuid
from datetime import datetime, timezone
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock

import pytest

if "asyncpg" not in sys.modules:
    sys.modules["asyncpg"] = ModuleType("asyncpg")


def _mock_job_run(
    role_title="VP Strategy",
    company_name="Acme Corp",
    status="completed",
    pipeline_stage="applied",
    keyword_match_score=85,
    apply_url="https://example.com/apply",
):
    run = MagicMock()
    run.id = uuid.uuid4()
    run.user_id = "user-1"
    run.role_title = role_title
    run.company_name = company_name
    run.status = status
    run.pipeline_stage = pipeline_stage
    run.keyword_match_score = keyword_match_score
    run.apply_url = apply_url
    run.created_at = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
    return run


def _mock_shadow(
    company="TechCo",
    signal_type="funding_round",
    hypothesis_role="Head of Engineering",
    status="completed",
    pipeline_stage="sent",
    confidence=0.85,
    radar_score=78,
):
    shadow = MagicMock()
    shadow.id = uuid.uuid4()
    shadow.user_id = "user-1"
    shadow.company = company
    shadow.signal_type = signal_type
    shadow.hypothesis_role = hypothesis_role
    shadow.status = status
    shadow.pipeline_stage = pipeline_stage
    shadow.confidence = confidence
    shadow.radar_score = radar_score
    shadow.created_at = datetime(2026, 3, 19, 10, 0, 0, tzinfo=timezone.utc)
    return shadow


def _parse_csv(content: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(content))
    return list(reader)


# ════════════════════════════════════════════════════════════
# Export applications
# ════════════════════════════════════════════════════════════

class TestExportApplications:

    @pytest.mark.asyncio
    async def test_export_applications_csv(self):
        from app.api.routes.export import export_applications

        mock_db = AsyncMock()
        mock_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [
            _mock_job_run(),
            _mock_job_run(role_title="Product Manager", company_name="BigCo", status="llm_processing", pipeline_stage="watching", keyword_match_score=None, apply_url=None),
        ]
        mock_result.scalars.return_value = scalars_mock
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = await export_applications(current_user_id="user-1", db=mock_db)

        assert response.media_type == "text/csv"
        assert "attachment" in response.headers["content-disposition"]
        assert ".csv" in response.headers["content-disposition"]

        # Parse CSV content
        body_parts = []
        async for chunk in response.body_iterator:
            body_parts.append(chunk if isinstance(chunk, str) else chunk.decode())
        content = "".join(body_parts)
        rows = _parse_csv(content)

        assert len(rows) == 2
        assert rows[0]["role_title"] == "VP Strategy"
        assert rows[0]["company_name"] == "Acme Corp"
        assert rows[0]["status"] == "completed"
        assert rows[0]["keyword_match_score"] == "85"
        assert rows[1]["role_title"] == "Product Manager"
        assert rows[1]["keyword_match_score"] == ""  # None → empty

    @pytest.mark.asyncio
    async def test_export_applications_empty(self):
        from app.api.routes.export import export_applications

        mock_db = AsyncMock()
        mock_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        mock_result.scalars.return_value = scalars_mock
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = await export_applications(current_user_id="user-1", db=mock_db)

        body_parts = []
        async for chunk in response.body_iterator:
            body_parts.append(chunk if isinstance(chunk, str) else chunk.decode())
        content = "".join(body_parts)
        rows = _parse_csv(content)

        assert len(rows) == 0
        # Header should still be present
        assert "role_title" in content
        assert "company_name" in content

    @pytest.mark.asyncio
    async def test_export_applications_csv_columns(self):
        from app.api.routes.export import export_applications, _APP_COLUMNS

        mock_db = AsyncMock()
        mock_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [_mock_job_run()]
        mock_result.scalars.return_value = scalars_mock
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = await export_applications(current_user_id="user-1", db=mock_db)

        body_parts = []
        async for chunk in response.body_iterator:
            body_parts.append(chunk if isinstance(chunk, str) else chunk.decode())
        content = "".join(body_parts)

        header_line = content.split("\r\n")[0]
        for col in _APP_COLUMNS:
            assert col in header_line


# ════════════════════════════════════════════════════════════
# Export shadows
# ════════════════════════════════════════════════════════════

class TestExportShadows:

    @pytest.mark.asyncio
    async def test_export_shadows_csv(self):
        from app.api.routes.export import export_shadows

        mock_db = AsyncMock()
        mock_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [
            _mock_shadow(),
            _mock_shadow(company="StartupX", confidence=None, radar_score=None, status="generating"),
        ]
        mock_result.scalars.return_value = scalars_mock
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = await export_shadows(current_user_id="user-1", db=mock_db)

        assert response.media_type == "text/csv"

        body_parts = []
        async for chunk in response.body_iterator:
            body_parts.append(chunk if isinstance(chunk, str) else chunk.decode())
        content = "".join(body_parts)
        rows = _parse_csv(content)

        assert len(rows) == 2
        assert rows[0]["company"] == "TechCo"
        assert rows[0]["signal_type"] == "funding_round"
        assert rows[0]["confidence"] == "0.85"
        assert rows[1]["company"] == "StartupX"
        assert rows[1]["confidence"] == ""  # None → empty

    @pytest.mark.asyncio
    async def test_export_shadows_empty(self):
        from app.api.routes.export import export_shadows

        mock_db = AsyncMock()
        mock_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        mock_result.scalars.return_value = scalars_mock
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = await export_shadows(current_user_id="user-1", db=mock_db)

        body_parts = []
        async for chunk in response.body_iterator:
            body_parts.append(chunk if isinstance(chunk, str) else chunk.decode())
        content = "".join(body_parts)
        rows = _parse_csv(content)

        assert len(rows) == 0
        assert "company" in content

    @pytest.mark.asyncio
    async def test_export_shadows_csv_columns(self):
        from app.api.routes.export import export_shadows, _SHADOW_COLUMNS

        mock_db = AsyncMock()
        mock_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [_mock_shadow()]
        mock_result.scalars.return_value = scalars_mock
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = await export_shadows(current_user_id="user-1", db=mock_db)

        body_parts = []
        async for chunk in response.body_iterator:
            body_parts.append(chunk if isinstance(chunk, str) else chunk.decode())
        content = "".join(body_parts)

        header_line = content.split("\r\n")[0]
        for col in _SHADOW_COLUMNS:
            assert col in header_line


# ════════════════════════════════════════════════════════════
# CSV helper
# ════════════════════════════════════════════════════════════

class TestCsvHelper:

    def test_to_csv_with_data(self):
        from app.api.routes.export import _to_csv

        data = [
            {"name": "Alice", "age": "30"},
            {"name": "Bob", "age": "25"},
        ]
        result = _to_csv(data, ["name", "age"])
        rows = _parse_csv(result)
        assert len(rows) == 2
        assert rows[0]["name"] == "Alice"

    def test_to_csv_empty(self):
        from app.api.routes.export import _to_csv

        result = _to_csv([], ["name", "age"])
        rows = _parse_csv(result)
        assert len(rows) == 0
        assert "name" in result

    def test_to_csv_ignores_extra_columns(self):
        from app.api.routes.export import _to_csv

        data = [{"name": "Alice", "age": "30", "extra": "ignored"}]
        result = _to_csv(data, ["name", "age"])
        assert "extra" not in result.split("\r\n")[0]

    def test_csv_response_headers(self):
        from app.api.routes.export import _csv_response

        response = _csv_response("test,data\n", "test.csv")
        assert response.media_type == "text/csv"
        assert 'filename="test.csv"' in response.headers["content-disposition"]
