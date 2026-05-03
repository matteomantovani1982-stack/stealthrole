"""
app/services/applications/application_service.py

CRUD + Kanban board + analytics for the Application Tracker.
"""

import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application, ApplicationStage
from app.schemas.application import (
    ApplicationAnalytics,
    ApplicationCreate,
    ApplicationListItem,
    ApplicationResponse,
    ApplicationUpdate,
    BoardColumn,
    BoardResponse,
    SourcePerformance,
    StageConversion,
)

logger = structlog.get_logger(__name__)

# Ordered columns for the Kanban board
BOARD_COLUMNS = [
    ApplicationStage.WATCHING,
    ApplicationStage.APPLIED,
    ApplicationStage.INTERVIEW,
    ApplicationStage.OFFER,
    ApplicationStage.REJECTED,
]


class ApplicationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ── CRUD ──────────────────────────────────────────────────────────────

    async def create(self, user_id: str, payload: ApplicationCreate) -> ApplicationResponse:
        app = Application(
            user_id=user_id,
            company=payload.company,
            role=payload.role,
            date_applied=payload.date_applied,
            source_channel=payload.source_channel,
            stage=payload.stage,
            notes=payload.notes,
            url=payload.url,
            salary=payload.salary,
            contact_name=payload.contact_name,
            contact_email=payload.contact_email,
            job_run_id=payload.job_run_id,
        )
        # Set stage timestamps based on initial stage
        self._set_stage_timestamp(app, payload.stage)

        self.db.add(app)
        await self.db.flush()
        await self.db.commit()
        await self.db.refresh(app)
        return ApplicationResponse.model_validate(app)

    async def get(self, app_id: uuid.UUID, user_id: str) -> ApplicationResponse | None:
        result = await self.db.execute(
            select(Application).where(
                Application.id == app_id,
                Application.user_id == user_id,
            )
        )
        app = result.scalar_one_or_none()
        if not app:
            return None
        return ApplicationResponse.model_validate(app)

    async def list_all(
        self, user_id: str, *, limit: int = 100, offset: int = 0,
    ) -> list[ApplicationListItem]:
        result = await self.db.execute(
            select(Application)
            .where(Application.user_id == user_id)
            .order_by(Application.date_applied.desc())
            .limit(limit)
            .offset(offset)
        )
        apps = result.scalars().all()
        return [ApplicationListItem.model_validate(a) for a in apps]

    async def update(
        self, app_id: uuid.UUID, user_id: str, payload: ApplicationUpdate
    ) -> ApplicationResponse | None:
        result = await self.db.execute(
            select(Application).where(
                Application.id == app_id,
                Application.user_id == user_id,
            )
        )
        app = result.scalar_one_or_none()
        if not app:
            return None

        update_data = payload.model_dump(exclude_unset=True)

        # If stage is changing, set the timestamp
        if "stage" in update_data:
            old_stage = app.stage
            new_stage = update_data["stage"]
            if old_stage != new_stage:
                self._set_stage_timestamp(app, new_stage)

        for field, value in update_data.items():
            setattr(app, field, value)

        await self.db.flush()
        await self.db.commit()
        await self.db.refresh(app)
        return ApplicationResponse.model_validate(app)

    async def update_stage(
        self, app_id: uuid.UUID, user_id: str, new_stage: str
    ) -> ApplicationResponse | None:
        """Lightweight stage update for drag-and-drop on the Kanban board."""
        result = await self.db.execute(
            select(Application).where(
                Application.id == app_id,
                Application.user_id == user_id,
            )
        )
        app = result.scalar_one_or_none()
        if not app:
            return None

        if app.stage != new_stage:
            self._set_stage_timestamp(app, new_stage)
            app.stage = new_stage

        await self.db.flush()
        await self.db.commit()
        await self.db.refresh(app)
        return ApplicationResponse.model_validate(app)

    async def delete(self, app_id: uuid.UUID, user_id: str) -> bool:
        result = await self.db.execute(
            select(Application).where(
                Application.id == app_id,
                Application.user_id == user_id,
            )
        )
        app = result.scalar_one_or_none()
        if not app:
            return False
        await self.db.delete(app)
        await self.db.commit()
        return True

    # ── Kanban Board ──────────────────────────────────────────────────────

    async def get_board(self, user_id: str) -> BoardResponse:
        """Return all applications grouped into Kanban columns."""
        result = await self.db.execute(
            select(Application)
            .where(Application.user_id == user_id)
            .order_by(Application.date_applied.desc())
        )
        apps = result.scalars().all()

        # Group by stage
        grouped: dict[str, list[ApplicationListItem]] = {s: [] for s in BOARD_COLUMNS}
        for app in apps:
            stage = app.stage if app.stage in grouped else ApplicationStage.APPLIED
            grouped[stage].append(ApplicationListItem.model_validate(app))

        columns = [
            BoardColumn(stage=stage, count=len(items), applications=items)
            for stage, items in grouped.items()
        ]
        return BoardResponse(columns=columns, total=len(apps))

    # ── Analytics ─────────────────────────────────────────────────────────

    async def get_analytics(self, user_id: str) -> ApplicationAnalytics:
        """Compute conversion rates, avg time to interview, best source."""

        # Total + by stage
        stage_rows = (await self.db.execute(
            select(Application.stage, func.count())
            .where(Application.user_id == user_id)
            .group_by(Application.stage)
        )).all()

        total = sum(row[1] for row in stage_rows)
        by_stage = [
            StageConversion(
                stage=row[0],
                count=row[1],
                rate=round(row[1] / total * 100, 1) if total > 0 else 0.0,
            )
            for row in stage_rows
        ]

        # Avg days to interview (applications that reached interview stage)
        avg_interval = (await self.db.execute(
            select(
                func.avg(
                    func.extract("epoch", Application.interview_at - Application.date_applied) / 86400
                )
            ).where(
                Application.user_id == user_id,
                Application.interview_at.isnot(None),
            )
        )).scalar()
        avg_days = round(avg_interval, 1) if avg_interval is not None else None

        # Source channel performance
        source_rows = (await self.db.execute(
            select(
                Application.source_channel,
                func.count().label("total"),
                func.count().filter(
                    Application.stage.in_(["interview", "offer"])
                ).label("interviews"),
                func.count().filter(
                    Application.stage == "offer"
                ).label("offers"),
            )
            .where(Application.user_id == user_id)
            .group_by(Application.source_channel)
        )).all()

        source_performance = []
        best_source = None
        best_rate = -1.0
        for row in source_rows:
            src, src_total, interviews, offers = row
            rate = round(interviews / src_total * 100, 1) if src_total > 0 else 0.0
            source_performance.append(
                SourcePerformance(
                    source=src,
                    total=src_total,
                    interviews=interviews,
                    offers=offers,
                    interview_rate=rate,
                )
            )
            if rate > best_rate and src_total >= 2:  # Minimum 2 applications to qualify
                best_rate = rate
                best_source = src

        return ApplicationAnalytics(
            total_applications=total,
            by_stage=by_stage,
            avg_days_to_interview=avg_days,
            best_source_channel=best_source,
            source_performance=source_performance,
        )

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _set_stage_timestamp(app: Application, stage: str) -> None:
        """Record when an application enters a given stage."""
        now = datetime.now(UTC)
        if stage == ApplicationStage.INTERVIEW and not app.interview_at:
            app.interview_at = now
        elif stage == ApplicationStage.OFFER and not app.offer_at:
            app.offer_at = now
        elif stage == ApplicationStage.REJECTED and not app.rejected_at:
            app.rejected_at = now
