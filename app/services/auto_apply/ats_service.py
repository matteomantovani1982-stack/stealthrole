"""
app/services/auto_apply/ats_service.py

ATS form-fill service.

Generates form payloads for different ATS platforms from user profile data.
The browser extension uses these payloads to fill forms automatically.

Supported platforms:
  - Greenhouse (boards.greenhouse.io)
  - Lever (jobs.lever.co)
  - Workable (apply.workable.com)
  - Ashby (jobs.ashbyhq.com)
  - Generic fallback

Zero LLM cost — all field mapping is rule-based.
"""

import re
import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auto_apply import (
    AutoApplyProfile,
    AutoApplySubmission,
    ATSPlatform,
    SubmissionStatus,
)
from app.models.application import Application

logger = structlog.get_logger(__name__)


# ── ATS detection by URL ──────────────────────────────────────────────────────

_ATS_URL_PATTERNS = {
    ATSPlatform.GREENHOUSE: [r"boards\.greenhouse\.io", r"greenhouse\.io/.*apply"],
    ATSPlatform.LEVER: [r"jobs\.lever\.co", r"lever\.co/.*apply"],
    ATSPlatform.WORKABLE: [r"apply\.workable\.com", r"workable\.com/.*apply"],
    ATSPlatform.ASHBY: [r"jobs\.ashbyhq\.com"],
    ATSPlatform.ICIMS: [r"icims\.com"],
    ATSPlatform.WORKDAY: [r"myworkdayjobs\.com", r"workday\.com"],
    ATSPlatform.SMARTRECRUITERS: [r"smartrecruiters\.com"],
}


def detect_ats_platform(url: str) -> str:
    """Detect which ATS platform a job URL belongs to."""
    url_lower = url.lower()
    for platform, patterns in _ATS_URL_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, url_lower):
                return platform
    return ATSPlatform.OTHER


# ── Form field mapping per ATS ────────────────────────────────────────────────

def _greenhouse_payload(profile: AutoApplyProfile, company: str, role: str) -> dict:
    """Map profile fields to Greenhouse form field names."""
    return {
        "first_name": (profile.full_name or "").split()[0] if profile.full_name else "",
        "last_name": " ".join((profile.full_name or "").split()[1:]),
        "email": profile.email or "",
        "phone": profile.phone or "",
        "location": profile.location or "",
        "linkedin_profile_url": profile.linkedin_url or "",
        "website_url": profile.website_url or "",
        "resume": "__CV_ATTACHMENT__",
        "cover_letter": _fill_cover_letter(profile.cover_letter_template, company, role),
        **profile.standard_answers,
    }


def _lever_payload(profile: AutoApplyProfile, company: str, role: str) -> dict:
    """Map profile fields to Lever form field names."""
    return {
        "name": profile.full_name or "",
        "email": profile.email or "",
        "phone": profile.phone or "",
        "org": profile.current_company or "",
        "urls[LinkedIn]": profile.linkedin_url or "",
        "urls[Portfolio]": profile.website_url or "",
        "resume": "__CV_ATTACHMENT__",
        "comments": _fill_cover_letter(profile.cover_letter_template, company, role),
        **profile.standard_answers,
    }


def _workable_payload(profile: AutoApplyProfile, company: str, role: str) -> dict:
    """Map profile fields to Workable form field names."""
    return {
        "firstname": (profile.full_name or "").split()[0] if profile.full_name else "",
        "lastname": " ".join((profile.full_name or "").split()[1:]),
        "email": profile.email or "",
        "phone": profile.phone or "",
        "address": profile.location or "",
        "linkedin": profile.linkedin_url or "",
        "website": profile.website_url or "",
        "resume": "__CV_ATTACHMENT__",
        "cover_letter": _fill_cover_letter(profile.cover_letter_template, company, role),
        **profile.standard_answers,
    }


def _generic_payload(profile: AutoApplyProfile, company: str, role: str) -> dict:
    """Best-effort field names for unknown ATS platforms."""
    names = (profile.full_name or "").split()
    return {
        "full_name": profile.full_name or "",
        "first_name": names[0] if names else "",
        "last_name": " ".join(names[1:]) if len(names) > 1 else "",
        "email": profile.email or "",
        "phone": profile.phone or "",
        "location": profile.location or "",
        "linkedin_url": profile.linkedin_url or "",
        "website": profile.website_url or "",
        "current_company": profile.current_company or "",
        "current_title": profile.current_title or "",
        "resume": "__CV_ATTACHMENT__",
        "cover_letter": _fill_cover_letter(profile.cover_letter_template, company, role),
        **profile.standard_answers,
    }


_PLATFORM_MAPPERS = {
    ATSPlatform.GREENHOUSE: _greenhouse_payload,
    ATSPlatform.LEVER: _lever_payload,
    ATSPlatform.WORKABLE: _workable_payload,
}


def _fill_cover_letter(template: str | None, company: str, role: str) -> str:
    """Substitute placeholders in cover letter template."""
    if not template:
        return ""
    return template.replace("{company}", company).replace("{role}", role)


# ── Service ───────────────────────────────────────────────────────────────────

class AutoApplyService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Profile management ────────────────────────────────────────────────

    async def get_or_create_profile(self, user_id: str) -> AutoApplyProfile:
        """Get or create the user's auto-apply profile."""
        result = await self.db.execute(
            select(AutoApplyProfile).where(AutoApplyProfile.user_id == user_id)
        )
        profile = result.scalar_one_or_none()
        if profile:
            return profile

        profile = AutoApplyProfile(user_id=user_id)
        self.db.add(profile)
        await self.db.flush()
        await self.db.commit()
        await self.db.refresh(profile)
        return profile

    async def update_profile(
        self, user_id: str, **fields
    ) -> AutoApplyProfile:
        profile = await self.get_or_create_profile(user_id)
        for field, value in fields.items():
            if hasattr(profile, field) and value is not None:
                setattr(profile, field, value)
        await self.db.flush()
        await self.db.commit()
        await self.db.refresh(profile)
        return profile

    # ── Prepare form payload ──────────────────────────────────────────────

    async def prepare(
        self,
        user_id: str,
        company: str,
        role: str,
        apply_url: str,
        application_id: uuid.UUID | None = None,
        job_run_id: uuid.UUID | None = None,
    ) -> AutoApplySubmission:
        """
        Generate a form payload for the target ATS and create a submission record.
        The extension fetches this payload and fills the form.
        """
        profile = await self.get_or_create_profile(user_id)
        platform = detect_ats_platform(apply_url)

        # Generate form payload using platform-specific mapper
        mapper = _PLATFORM_MAPPERS.get(platform, _generic_payload)
        payload = mapper(profile, company, role)

        # Find CV S3 key if a job_run exists
        cv_key = None
        if job_run_id:
            from app.models.job_run import JobRun
            jr = (await self.db.execute(
                select(JobRun).where(JobRun.id == job_run_id)
            )).scalar_one_or_none()
            if jr and jr.output_s3_key:
                cv_key = jr.output_s3_key

        submission = AutoApplySubmission(
            user_id=user_id,
            application_id=application_id,
            job_run_id=job_run_id,
            company=company,
            role=role,
            apply_url=apply_url,
            ats_platform=platform,
            form_payload=payload,
            cv_s3_key=cv_key,
            status=SubmissionStatus.PREPARED,
        )
        self.db.add(submission)
        await self.db.flush()
        await self.db.commit()
        await self.db.refresh(submission)

        logger.info(
            "auto_apply_prepared",
            user_id=user_id,
            company=company,
            platform=platform,
            submission_id=str(submission.id),
        )
        return submission

    # ── Extension callbacks ───────────────────────────────────────────────

    async def report_submitted(
        self, user_id: str, submission_id: uuid.UUID
    ) -> AutoApplySubmission | None:
        """Extension reports successful form submission."""
        sub = await self._get_submission(submission_id, user_id)
        if not sub:
            return None
        sub.status = SubmissionStatus.SUBMITTED
        sub.submitted_at = datetime.now(UTC)

        # Auto-create application if not linked
        if not sub.application_id:
            app = Application(
                user_id=user_id,
                company=sub.company,
                role=sub.role,
                date_applied=datetime.now(UTC),
                source_channel="auto_apply",
                stage="applied",
                url=sub.apply_url,
            )
            self.db.add(app)
            await self.db.flush()
            sub.application_id = app.id

        await self.db.commit()
        await self.db.refresh(sub)
        return sub

    async def report_failed(
        self, user_id: str, submission_id: uuid.UUID, error: str
    ) -> AutoApplySubmission | None:
        """Extension reports form fill failure."""
        sub = await self._get_submission(submission_id, user_id)
        if not sub:
            return None
        sub.status = SubmissionStatus.FAILED
        sub.error_message = error[:1000]
        await self.db.commit()
        await self.db.refresh(sub)
        return sub

    # ── Queries ───────────────────────────────────────────────────────────

    async def list_submissions(
        self, user_id: str, status_filter: str | None = None
    ) -> list[AutoApplySubmission]:
        query = select(AutoApplySubmission).where(
            AutoApplySubmission.user_id == user_id
        )
        if status_filter:
            query = query.where(AutoApplySubmission.status == status_filter)
        query = query.order_by(AutoApplySubmission.created_at.desc()).limit(50)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_stats(self, user_id: str) -> dict:
        rows = (await self.db.execute(
            select(AutoApplySubmission.status, func.count())
            .where(AutoApplySubmission.user_id == user_id)
            .group_by(AutoApplySubmission.status)
        )).all()
        by_status = {r[0]: r[1] for r in rows}
        return {
            "total": sum(by_status.values()),
            "submitted": by_status.get("submitted", 0),
            "prepared": by_status.get("prepared", 0),
            "failed": by_status.get("failed", 0),
            "by_status": by_status,
        }

    def get_supported_platforms(self) -> list[dict]:
        return [
            {"id": p.value, "name": p.value.replace("_", " ").title(), "supported": True}
            for p in ATSPlatform if p != ATSPlatform.OTHER
        ] + [{"id": "other", "name": "Other (best effort)", "supported": True}]

    async def _get_submission(
        self, sub_id: uuid.UUID, user_id: str
    ) -> AutoApplySubmission | None:
        result = await self.db.execute(
            select(AutoApplySubmission).where(
                AutoApplySubmission.id == sub_id,
                AutoApplySubmission.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()
