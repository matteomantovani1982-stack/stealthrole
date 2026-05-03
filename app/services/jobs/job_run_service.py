"""
app/services/jobs/job_run_service.py

Business logic for creating and monitoring JobRuns.

Responsibilities:
- Validate that the CV exists, belongs to the user, and is parsed
- Create JobRun DB record
- Dispatch the run_llm Celery task
- Fetch run status (with steps and download URL)
- Generate pre-signed download URLs for completed runs
"""

import asyncio
import uuid
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.middleware.error_handler import NotFoundError, ValidationError
from app.models.cv import CV, CVStatus
from app.models.job_run import JobRun, JobRunStatus
from app.schemas.job_run import (
    JobRunCreate,
    JobRunListItem,
    JobRunResponse,
    JobRunStatusResponse,
    JobStepResponse,
)
from app.services.ingest.storage import S3StorageService

import structlog

logger = structlog.get_logger(__name__)

_executor = ThreadPoolExecutor(max_workers=2)


class JobRunService:
    """Orchestrates JobRun creation and status retrieval."""

    def __init__(self, db: AsyncSession, storage: S3StorageService) -> None:
        self._db = db
        self._storage = storage

    async def create_run(
        self,
        user_id: str,
        payload: JobRunCreate,
        plan_features: dict | None = None,
    ) -> JobRunResponse:
        """
        Create a new JobRun and dispatch the LLM pipeline.
        Quota has already been verified by QuotaCheck dependency.
        plan_features controls which outputs are generated.
        """
        # Validate CV
        cv = await self._get_cv_or_error(
            cv_id=payload.cv_id,
            user_id=user_id,
        )

        # PDF sources can't use "edit" mode (python-docx needs a zip/DOCX file).
        # Auto-switch to "rebuild" so pack generation still works.
        if cv.mime_type == "application/pdf" and (cv.build_mode or "edit") == "edit":
            cv.build_mode = "rebuild"
            if not cv.template_slug:
                cv.template_slug = "classic"
            logger.info("pdf_auto_switch_rebuild", cv_id=str(cv.id), original_mode="edit")

        # Merge plan feature flags into preferences so the LLM task can read them
        prefs = payload.preferences.model_dump()

        # Auto-inject LinkedIn connections at target company as known_contacts
        # This makes Claude write personalized intros instead of generic templates
        known = list(payload.known_contacts or [])
        if not known:
            try:
                from app.models.linkedin_connection import LinkedInConnection
                from sqlalchemy import select, func
                # Extract company from JD text (first line often has company name)
                company_hint = ""
                jd = payload.jd_text or ""
                if jd:
                    import re
                    at_match = re.search(r'(?:at|@)\s+([A-Z][\w\s&.-]+)', jd[:500])
                    if at_match:
                        company_hint = at_match.group(1).strip()

                if company_hint:
                    result = await self._db.execute(
                        select(LinkedInConnection).where(
                            LinkedInConnection.user_id == user_id,
                            func.lower(LinkedInConnection.current_company).contains(company_hint.lower()),
                        ).limit(10)
                    )
                    connections = result.scalars().all()
                    for conn in connections:
                        label = f"{conn.full_name}"
                        if conn.current_title:
                            label += f" ({conn.current_title})"
                        if conn.is_recruiter:
                            label += " [Recruiter]"
                        elif conn.is_hiring_manager:
                            label += " [Hiring Manager]"
                        known.append(label)
            except Exception:
                pass  # Non-fatal — pack still generates without known contacts

        if known:
            prefs["known_contacts"] = known[:20]
        if plan_features:
            prefs["plan_features"] = plan_features

        # Create JobRun record
        job_run = JobRun(
            user_id=user_id,
            cv_id=cv.id,
            jd_text=payload.jd_text,
            jd_url=payload.jd_url,
            preferences=prefs,
            profile_id=payload.profile_id,
            profile_overrides=payload.profile_overrides,
            status=JobRunStatus.CREATED,
        )
        self._db.add(job_run)
        await self._db.flush()

        logger.info(
            "job_run_created",
            extra={
                "job_run_id": str(job_run.id),
                "user_id": user_id,
                "cv_id": str(cv.id),
            },
        )

        # Dispatch pipeline: if CV already parsed, go straight to LLM
        # If CV still parsing, create_run leaves status=CREATED until parse_cv
        # dispatch_waiting_job_runs_after_cv_parse(), or get_status() resumes.
        if cv.status == CVStatus.PARSED:
            from app.workers.tasks.run_llm import run_llm_task
            task = run_llm_task.delay(str(job_run.id))
            job_run.status = JobRunStatus.RETRIEVING
            job_run.celery_task_id = task.id
        else:
            # CV still parsing — run_llm is dispatched when parse completes
            # (dispatch_waiting_job_runs_after_cv_parse) or on GET /jobs/{id} heal.
            logger.warning(
                "job_run_created_cv_not_yet_parsed",
                extra={"cv_status": cv.status, "job_run_id": str(job_run.id)},
            )

        return JobRunResponse(
            id=job_run.id,
            status=job_run.status,
            cv_id=job_run.cv_id,
            created_at=job_run.created_at,
        )

    async def get_status(
        self,
        job_run_id: uuid.UUID,
        user_id: str,
    ) -> JobRunStatusResponse:
        """Fetch full status including per-step detail and download URL."""
        job_run = await self._get_run_or_404(
            job_run_id=job_run_id,
            user_id=user_id,
        )
        job_run = await self._maybe_resume_created_job_run(job_run, user_id)

        download_url: str | None = None
        if (
            job_run.status == JobRunStatus.COMPLETED
            and job_run.output_s3_key
        ):
            loop = asyncio.get_running_loop()
            download_url = await loop.run_in_executor(
                _executor,
                lambda: self._storage.generate_presigned_url(
                    job_run.output_s3_key,
                    expires_in_seconds=3600,
                ),
            )

        steps = [
            JobStepResponse(
                id=step.id,
                step_name=step.step_name,
                status=step.status,
                started_at=step.started_at,
                completed_at=step.completed_at,
                duration_seconds=step.duration_seconds,
                error_type=step.error_type,
                error_message=step.error_message,
            )
            for step in (job_run.steps or [])
        ]

        return JobRunStatusResponse(
            id=job_run.id,
            status=job_run.status,
            cv_id=job_run.cv_id,
            created_at=job_run.created_at,
            updated_at=job_run.updated_at,
            completed_at=job_run.updated_at if job_run.status == JobRunStatus.COMPLETED else None,
            steps=steps,
            download_url=download_url,
            positioning=job_run.positioning,
            reports=job_run.reports,
            failed_step=job_run.failed_step,
            error_message=job_run.error_message,
            jd_url=job_run.jd_url,
            company_name=job_run.company_name,
            role_title=job_run.role_title,
            keyword_match_score=job_run.keyword_match_score,
        )

    async def get_download_url(
        self,
        job_run_id: uuid.UUID,
        user_id: str,
    ) -> str:
        """Generate a fresh pre-signed URL for a completed run's output DOCX."""
        job_run = await self._get_run_or_404(
            job_run_id=job_run_id,
            user_id=user_id,
        )

        if job_run.status != JobRunStatus.COMPLETED:
            raise ValidationError(
                f"Job run is not completed (status: {job_run.status}). "
                "Download is only available when status=completed."
            )

        if not job_run.output_s3_key:
            raise ValidationError(
                "Job run is marked completed but has no output file. "
                "This may indicate a rendering error — please contact support."
            )

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            _executor,
            lambda: self._storage.generate_presigned_url(
                job_run.output_s3_key,
                expires_in_seconds=3600,
            ),
        )

    async def list_runs(
        self, user_id: str, *, limit: int = 50, offset: int = 0,
    ) -> list[JobRunListItem]:
        """List all runs for a user, newest first."""
        result = await self._db.execute(
            select(JobRun)
            .where(JobRun.user_id == user_id)
            .order_by(JobRun.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        runs = result.scalars().all()
        return [
            JobRunListItem(
                id=r.id,
                status=r.status,
                cv_id=r.cv_id,
                profile_id=r.profile_id,
                created_at=r.created_at,
                updated_at=r.updated_at,
                failed_step=r.failed_step,
                jd_text=r.jd_text,
                jd_url=r.jd_url,
                keyword_match_score=r.keyword_match_score,
                pipeline_stage=r.pipeline_stage or 'watching',
                pipeline_notes=r.pipeline_notes,
                applied_at=r.applied_at,
                output_s3_key=r.output_s3_key,
                role_title=r.role_title,
                company_name=r.company_name,
                apply_url=r.apply_url,
            )
            for r in runs
        ]

    # ── Private helpers ─────────────────────────────────────────────────────

    async def _maybe_resume_created_job_run(
        self,
        job_run: JobRun,
        user_id: str,
    ) -> JobRun:
        """
        Heal JobRuns stuck in CREATED after the CV finished parsing.

        create_run does not dispatch Celery while CV.status != PARSED; until
        parse_cv runs dispatch_waiting_job_runs_after_cv_parse(), those runs
        stayed CREATED forever. This path fixes older rows on each status poll.
        """
        if job_run.status != JobRunStatus.CREATED:
            return job_run

        cv_row = await self._db.execute(
            select(CV).where(
                CV.id == job_run.cv_id,
                CV.user_id == user_id,
            )
        )
        cv = cv_row.scalar_one_or_none()
        if cv is None or cv.status != CVStatus.PARSED:
            return job_run

        stmt = (
            update(JobRun)
            .where(
                JobRun.id == job_run.id,
                JobRun.user_id == user_id,
                JobRun.status == JobRunStatus.CREATED,
            )
            .values(status=JobRunStatus.RETRIEVING)
        )
        res = await self._db.execute(stmt)
        await self._db.commit()

        if res.rowcount != 1:
            return await self._get_run_or_404(job_run.id, user_id)

        from app.workers.tasks.run_llm import run_llm_task

        task = run_llm_task.delay(str(job_run.id))
        await self._db.execute(
            update(JobRun)
            .where(JobRun.id == job_run.id)
            .values(celery_task_id=task.id)
        )
        await self._db.commit()

        logger.info(
            "job_run_resumed_after_cv_parse",
            extra={"job_run_id": str(job_run.id), "celery_task_id": task.id},
        )
        return await self._get_run_or_404(job_run.id, user_id)

    async def _get_cv_or_error(
        self,
        cv_id: uuid.UUID,
        user_id: str,
    ) -> CV:
        """Fetch CV, validate ownership, validate it's parsed."""
        result = await self._db.execute(
            select(CV).where(CV.id == cv_id, CV.user_id == user_id)
        )
        cv = result.scalar_one_or_none()

        if cv is None:
            raise NotFoundError(resource="CV", resource_id=str(cv_id))

        if cv.status == CVStatus.FAILED:
            raise ValidationError(
                f"CV {cv_id} failed to parse. Please upload a new CV."
            )

        if cv.status == CVStatus.UPLOADED:
            raise ValidationError(
                f"CV {cv_id} is still being uploaded. Wait for status=parsed."
            )

        return cv

    async def _get_run_or_404(
        self,
        job_run_id: uuid.UUID,
        user_id: str,
    ) -> JobRun:
        result = await self._db.execute(
            select(JobRun).where(
                JobRun.id == job_run_id,
                JobRun.user_id == user_id,
            )
        )
        run = result.scalar_one_or_none()
        if run is None:
            raise NotFoundError(resource="JobRun", resource_id=str(job_run_id))
        return run
