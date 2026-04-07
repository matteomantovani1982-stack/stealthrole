"""
app/workers/tasks/shadow_gen.py

Celery task: generate_shadow_application

Pipeline:
  1. Load ShadowApplication + CV + CandidateProfile
  2. Generate hiring hypothesis + strategy memo + outreach (ShadowGenerator)
  3. Generate tailored CV edit_plan (shadow_generator.py)
  4. Render tailored CV DOCX (reuse render pipeline)
  5. Upload to S3
  6. Update ShadowApplication record

Queue: llm (uses Claude API)
"""

import re
import uuid
from datetime import UTC, datetime

import structlog
from celery import Task

from app.workers.celery_app import celery
from app.workers.db_utils import get_sync_db

logger = structlog.get_logger(__name__)


class ShadowGenTask(Task):
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        shadow_id_str = args[0] if args else kwargs.get("shadow_id")
        if not shadow_id_str:
            return
        logger.error("shadow_gen_failed", shadow_id=shadow_id_str, error=str(exc))
        try:
            _mark_shadow_failed(uuid.UUID(shadow_id_str), str(exc))
        except Exception as e:
            logger.error("shadow_gen_failed_to_update_db", error=str(e))


@celery.task(
    bind=True,
    base=ShadowGenTask,
    name="app.workers.tasks.shadow_gen.generate_shadow_application",
    max_retries=1,
    default_retry_delay=10,
    soft_time_limit=300,
    time_limit=360,
)
def generate_shadow_application(self: Task, shadow_id: str) -> dict:
    """Generate a complete Shadow Application Pack."""
    log = logger.bind(shadow_id=shadow_id, task_id=self.request.id)
    log.info("shadow_gen_started")

    shadow_uuid = uuid.UUID(shadow_id)

    # ── 1. Load inputs ──────────────────────────────────────────────────
    with get_sync_db() as db:
        from app.models.shadow_application import ShadowApplication, ShadowStatus
        from app.models.cv import CV
        from app.models.candidate_profile import CandidateProfile, ProfileStatus
        from sqlalchemy import select

        shadow = db.get(ShadowApplication, shadow_uuid)
        if shadow is None:
            raise ValueError(f"ShadowApplication {shadow_id} not found")
        if shadow.is_terminal:
            return {"status": "already_terminal"}

        shadow.celery_task_id = self.request.id
        db.commit()

        user_id = shadow.user_id
        company = shadow.company
        signal_type = shadow.signal_type
        signal_context = shadow.signal_context or ""
        radar_score = shadow.radar_score

        # Load profile
        profile_dict = None
        profile_id = shadow.profile_id
        if profile_id:
            p = db.get(CandidateProfile, profile_id)
            if p:
                profile_dict = p.to_prompt_dict()
        else:
            result = db.execute(
                select(CandidateProfile).where(
                    CandidateProfile.user_id == user_id,
                    CandidateProfile.status == ProfileStatus.ACTIVE,
                )
            )
            p = result.scalar_one_or_none()
            if not p:
                result = db.execute(
                    select(CandidateProfile).where(
                        CandidateProfile.user_id == user_id,
                    ).order_by(CandidateProfile.updated_at.desc())
                )
                p = result.scalars().first()
            if p:
                profile_dict = p.to_prompt_dict()
                profile_id = p.id

        # Load CV
        cv_id = shadow.cv_id
        parsed_content = None
        original_s3_key = None
        if cv_id:
            cv = db.get(CV, cv_id)
            if cv and cv.parsed_content:
                parsed_content = dict(cv.parsed_content)
                original_s3_key = cv.s3_key
        else:
            # Find user's most recent parsed CV
            result = db.execute(
                select(CV).where(
                    CV.user_id == user_id,
                    CV.parsed_content.isnot(None),
                ).order_by(CV.updated_at.desc())
            )
            cv = result.scalars().first()
            if cv:
                parsed_content = dict(cv.parsed_content)
                original_s3_key = cv.s3_key
                cv_id = cv.id

    # Build profile summary text
    profile_summary = ""
    if profile_dict:
        profile_summary = (
            f"Headline: {profile_dict.get('headline', '')}\n"
            f"Context: {profile_dict.get('global_context', '')}\n"
            f"Notes: {profile_dict.get('global_notes', '')}\n"
        )
        for exp in profile_dict.get("experiences", []):
            profile_summary += (
                f"\n{exp.get('role', '')} at {exp.get('company', '')} "
                f"({exp.get('dates', '')})\n"
            )
            if exp.get("contribution"):
                profile_summary += f"  Contribution: {exp['contribution']}\n"
            if exp.get("outcomes"):
                profile_summary += f"  Outcomes: {exp['outcomes']}\n"

    # Extract likely_roles from signal_context (embedded by the API route)
    likely_roles = []
    if signal_context and "Requested roles:" in signal_context:
        import re as _re
        match = _re.search(r"Requested roles:\s*(.+?)(?:\n|$)", signal_context)
        if match:
            likely_roles = [r.strip() for r in match.group(1).split(",") if r.strip()]

    # Fallback: extract from signal context keywords
    if not likely_roles and signal_context:
        for keyword in ["VP", "Director", "Head of", "Manager", "Engineer", "COO", "CTO", "CFO"]:
            if keyword.lower() in signal_context.lower():
                likely_roles.append(keyword)
    if not likely_roles:
        likely_roles = ["Senior Role"]

    log.info(
        "shadow_inputs_loaded",
        has_profile=profile_dict is not None,
        has_cv=parsed_content is not None,
        company=company,
    )

    # ── 2. Generate hypothesis + memo + outreach ────────────────────────
    try:
        from app.services.shadow.shadow_service import ShadowGenerator

        generator = ShadowGenerator()
        pack = generator.generate_full_pack(
            company=company,
            signal_type=signal_type,
            signal_context=signal_context,
            likely_roles=likely_roles,
            profile_summary=profile_summary,
            tone="confident",
        )
        log.info("shadow_pack_generated", role=pack.hypothesis_role)

    except Exception as exc:
        log.error("shadow_pack_generation_failed", error=str(exc))
        _mark_shadow_failed(shadow_uuid, str(exc))
        raise

    # ── 3. Generate tailored CV (if CV available) ───────────────────────
    tailored_cv_s3_key = None
    if parsed_content and original_s3_key:
        try:
            from app.services.shadow.shadow_generator import generate_shadow_cv_edit_plan
            from app.services.ingest.storage import S3StorageService

            edit_plan = generate_shadow_cv_edit_plan(
                parsed_cv_dict=parsed_content,
                profile_dict=profile_dict,
                company=company,
                hypothesis_role=pack.hypothesis_role,
                hiring_hypothesis=pack.hiring_hypothesis,
                signal_context=signal_context,
            )

            # Render the CV
            storage = S3StorageService()
            docx_bytes = storage.download_bytes(original_s3_key)

            from app.services.rendering.docx_renderer import DOCXRenderer
            renderer = DOCXRenderer()
            render_result = renderer.render(docx_bytes=docx_bytes, edit_plan=edit_plan)

            # Upload
            def _safe(s: str) -> str:
                return re.sub(r'[^\w\s-]', '', s).strip().replace(' ', '_')[:40]

            output_filename = f"{_safe(pack.hypothesis_role)}_{_safe(company)}_Shadow_CV.docx"
            tailored_cv_s3_key = f"shadow/{user_id}/{shadow_id}/{output_filename}"

            storage.upload_bytes(
                data=render_result.docx_bytes,
                s3_key=tailored_cv_s3_key,
                content_type=(
                    "application/vnd.openxmlformats-officedocument"
                    ".wordprocessingml.document"
                ),
                metadata={
                    "shadow_id": shadow_id,
                    "user_id": user_id,
                },
            )
            log.info(
                "shadow_cv_rendered",
                s3_key=tailored_cv_s3_key,
                edits_applied=render_result.edits_applied,
            )

        except Exception as exc:
            # CV failure is non-fatal — shadow app still has hypothesis + memo + outreach
            log.warning("shadow_cv_render_failed_continuing", error=str(exc))
            tailored_cv_s3_key = None

    # ── 4. Persist results ──────────────────────────────────────────────
    with get_sync_db() as db:
        from app.models.shadow_application import ShadowApplication, ShadowStatus
        from app.config import settings

        shadow = db.get(ShadowApplication, shadow_uuid)
        if shadow is None:
            raise ValueError(f"ShadowApplication {shadow_id} disappeared")

        shadow.hypothesis_role = pack.hypothesis_role
        shadow.hiring_hypothesis = pack.hiring_hypothesis
        shadow.strategy_memo = pack.strategy_memo
        shadow.outreach_linkedin = pack.outreach.linkedin_note
        shadow.outreach_email = pack.outreach.cold_email
        shadow.outreach_followup = pack.outreach.follow_up
        shadow.confidence = pack.confidence
        shadow.reasoning = pack.reasoning
        shadow.status = ShadowStatus.COMPLETED

        if tailored_cv_s3_key:
            shadow.tailored_cv_s3_key = tailored_cv_s3_key
            shadow.tailored_cv_s3_bucket = settings.effective_s3_bucket

        if cv_id:
            shadow.cv_id = cv_id
        if profile_id:
            shadow.profile_id = profile_id

        db.commit()

    log.info(
        "shadow_gen_complete",
        company=company,
        role=pack.hypothesis_role,
        has_cv=tailored_cv_s3_key is not None,
    )

    # ── Send shadow completion email ─────────────────────────────────
    try:
        from app.services.email.notifications import notify_shadow_complete
        notify_shadow_complete(
            user_id=user_id,
            shadow_id=shadow_id,
            company=company,
            role=pack.hypothesis_role,
        )
    except Exception as e:
        log.warning("shadow_email_failed_non_fatal", error=str(e))

    return {
        "shadow_id": shadow_id,
        "status": "completed",
        "hypothesis_role": pack.hypothesis_role,
        "has_tailored_cv": tailored_cv_s3_key is not None,
        "confidence": pack.confidence,
    }


def _mark_shadow_failed(shadow_id: uuid.UUID, error_message: str) -> None:
    from app.models.shadow_application import ShadowApplication, ShadowStatus
    try:
        with get_sync_db() as db:
            shadow = db.get(ShadowApplication, shadow_id)
            if shadow and not shadow.is_terminal:
                shadow.status = ShadowStatus.FAILED
                shadow.error_message = error_message[:2000]
                db.commit()
    except Exception as e:
        logger.error("shadow_mark_failed_error", shadow_id=str(shadow_id), error=str(e))
