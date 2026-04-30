"""
app/workers/tasks/run_llm.py

Celery task: run_llm_task — profile-aware, 3-output pipeline.

Pipeline:
  1. Load JobRun + CV + CandidateProfile
  2. Apply per-application profile overrides
  3. Web retrieval (Serper)
  4. LLM A — EditPlan
  5. LLM B — PositioningStrategy (profile mode only)
  6. LLM C — ReportPack
  7. Persist all outputs
  8. Chain → render_docx_task

Fallback: if no profile exists, gracefully degrades to CV-only prompts.
Positioning failure is non-fatal — CV + reports still produced.
"""

import uuid
from datetime import UTC, datetime

import structlog
from celery import Task
from celery.exceptions import SoftTimeLimitExceeded

from app.config import should_skip_anthropic_api
from app.workers.celery_app import celery
from app.workers.db_utils import get_sync_db

logger = structlog.get_logger(__name__)


class RunLLMTask(Task):
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        job_run_id_str = args[0] if args else kwargs.get("job_run_id")
        if not job_run_id_str:
            return
        logger.error("run_llm_unexpected_failure", job_run_id=job_run_id_str, error=str(exc))
        try:
            _mark_run_failed(uuid.UUID(job_run_id_str), "llm_processing", str(exc))
        except Exception as e:
            logger.error("failed_to_mark_run_failed", error=str(e))


@celery.task(
    bind=True,
    base=RunLLMTask,
    name="app.workers.tasks.run_llm.run_llm_task",
    max_retries=2,
    default_retry_delay=5,
)
def run_llm_task(self: Task, job_run_id: str) -> dict:
    log = logger.bind(job_run_id=job_run_id, task_id=self.request.id)
    log.info("run_llm_task_started")

    # Set Sentry context for this job run (populated after DB fetch below)
    from app.monitoring.sentry import set_job_run_context, capture_retrieval_breadcrumb

    try:
        run_uuid = uuid.UUID(job_run_id)
    except ValueError as e:
        log.error("invalid_uuid", error=str(e))
        raise

    # ── 1. Load inputs ────────────────────────────────────────────────────
    with get_sync_db() as db:
        from app.models.job_run import JobRun, JobRunStatus
        from app.models.cv import CV
        from app.models.candidate_profile import CandidateProfile, ProfileStatus
        from sqlalchemy import select

        job_run = db.get(JobRun, run_uuid)
        if job_run is None:
            raise ValueError(f"JobRun {job_run_id} not found")
        if job_run.is_terminal:
            return {"status": "already_terminal"}

        cv = db.get(CV, job_run.cv_id)
        if cv is None or cv.parsed_content is None:
            raise ValueError(f"CV {job_run.cv_id} not parsed")

        jd_text = job_run.jd_text or ""
        preferences = dict(job_run.preferences or {})

        # If no jd_text but jd_url provided, fetch it now in the worker
        if not jd_text.strip() and job_run.jd_url:
            try:
                import httpx as _httpx
                _headers = {
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
                }
                _r = _httpx.get(job_run.jd_url, headers=_headers, timeout=20.0, follow_redirects=True)
                _r.raise_for_status()
                # Strip HTML quickly
                import re as _re
                _html = _r.text
                _html = _re.sub(r"<(script|style|nav|footer)[^>]*>.*?</\1>", "", _html, flags=_re.DOTALL|_re.IGNORECASE)
                _html = _re.sub(r"<[^>]+>", " ", _html)
                _html = _re.sub(r"[ \t]+", " ", _html)
                _html = _re.sub(r"\n{3,}", "\n\n", _html)
                jd_text = _html.strip()[:6000]
                job_run.jd_text = jd_text
                db.commit()
                log.info("jd_fetched_from_url", chars=len(jd_text))
            except Exception as _e:
                log.warning("jd_url_fetch_failed", error=str(_e))
        parsed_content = dict(cv.parsed_content)
        profile_id = job_run.profile_id
        profile_overrides_raw = dict(job_run.profile_overrides or {})
        cv_build_mode = cv.build_mode or "edit"
        cv_quality_feedback = dict(cv.quality_feedback or {})
        known_contacts = list(job_run.preferences.get("known_contacts", []) or [])

        # Resolve profile — explicit > active > any > None
        profile_dict = None
        if profile_id:
            p = db.get(CandidateProfile, profile_id)
            if p:
                profile_dict = p.to_prompt_dict()
        else:
            # Try ACTIVE first
            result = db.execute(
                select(CandidateProfile).where(
                    CandidateProfile.user_id == job_run.user_id,
                    CandidateProfile.status == ProfileStatus.ACTIVE,
                )
            )
            p = result.scalar_one_or_none()
            # Fall back to any profile for this user (DRAFT etc.)
            if not p:
                result = db.execute(
                    select(CandidateProfile).where(
                        CandidateProfile.user_id == job_run.user_id,
                    ).order_by(CandidateProfile.updated_at.desc())
                )
                p = result.scalars().first()
            if p:
                profile_dict = p.to_prompt_dict()
                profile_id = p.id

        job_run.status = JobRunStatus.RETRIEVING
        job_run.celery_task_id = self.request.id
        if profile_id:
            job_run.profile_id = profile_id
        db.commit()

    log.info("inputs_loaded", has_profile=profile_dict is not None)

    # ── 2. Deserialise ParsedCV ───────────────────────────────────────────
    from app.schemas.cv import ParsedCV
    try:
        parsed_cv = ParsedCV.model_validate(parsed_content)
    except Exception as e:
        _mark_run_failed(run_uuid, "llm_processing", str(e))
        raise ValueError(f"Invalid ParsedCV: {e}") from e

    # ── 3. Apply profile overrides ────────────────────────────────────────
    if profile_dict and profile_overrides_raw:
        try:
            from app.schemas.candidate_profile import ApplicationProfileOverrides
            overrides = ApplicationProfileOverrides.model_validate(profile_overrides_raw)
            if overrides.additional_global_context:
                profile_dict["application_context"] = overrides.additional_global_context
        except Exception as e:
            log.warning("profile_overrides_invalid_ignoring", error=str(e))

    # ── 4. Retrieval ──────────────────────────────────────────────────────
    retrieve_step_id = _create_job_step(run_uuid, "retrieve", self.request.id)
    retrieval_data: dict = {}
    try:
        # Tag Sentry scope with run + user IDs for all events in this task
        set_job_run_context(str(job_run.id), str(job_run.user_id))

        if should_skip_anthropic_api():
            retrieval_data = {
                "company_overview": "",
                "salary_data": "",
                "news": [],
                "competitors": "",
                "contacts": [],
                "sources": ["skipped-demo-mode"],
                "partial_failure": True,
                "error_notes": ["Web retrieval skipped in DEMO_MODE (faster local runs)"],
            }
            log.info("retrieval_skipped_demo_mode")
        else:
            retrieval_data = _run_retrieval(jd_text, preferences, log)
        _complete_job_step(retrieve_step_id, {
            "sources": retrieval_data.get("sources", []),
            "partial_failure": retrieval_data.get("partial_failure", False),
        })
    except SoftTimeLimitExceeded:
        _mark_run_failed(run_uuid, "retrieve", "Time limit exceeded")
        capture_retrieval_breadcrumb(
            sources=len(retrieval_data.get("sources", [])),
            contacts_found=len(retrieval_data.get("contacts", [])),
            partial_failure=retrieval_data.get("partial_failure", False),
        )
        raise
    except Exception as e:
        log.warning("retrieval_failed_continuing", error=str(e))
        _fail_job_step(retrieve_step_id, e)
        retrieval_data = {}

    # ── 5. Transition → LLM_PROCESSING ───────────────────────────────────
    _update_run_status(run_uuid, "llm_processing")

    # ── 6 + 7. LLM calls — fork on build mode ────────────────────────────
    # edit        → normal EditPlan + Positioning + ReportPack pipeline
    # rebuild     → CVBuildService generates full CV, then Positioning + ReportPack
    # from_scratch → CVBuildService generates full CV, then Positioning + ReportPack
    from app.models.cv import CVBuildMode

    llm_step_id = _create_job_step(run_uuid, "llm_call", self.request.id)
    try:
        if cv_build_mode in (CVBuildMode.FROM_SCRATCH, CVBuildMode.REBUILD):
            log.info("cv_build_mode_active", mode=cv_build_mode)
            edit_plan, positioning, report_pack, llm_meta = _run_cv_build_pipeline(
                profile_dict=profile_dict,
                build_mode=cv_build_mode,
                quality_feedback=cv_quality_feedback,
                jd_text=jd_text,
                preferences=preferences,
                retrieval_data=retrieval_data,
                known_contacts=known_contacts,
                log=log,
            )
        else:
            # Standard edit pipeline
            prompts = _build_prompts(
                profile_dict, parsed_cv, jd_text, preferences, retrieval_data, log,
                known_contacts=known_contacts,
            )
            edit_plan, positioning, report_pack, llm_meta = _run_llm_calls(
                prompts=prompts,
                has_profile=profile_dict is not None,
                log=log,
            )
        _complete_job_step(llm_step_id, llm_meta)
    except SoftTimeLimitExceeded:
        _fail_job_step(llm_step_id, SoftTimeLimitExceeded())
        _mark_run_failed(run_uuid, "llm_processing", "Time limit exceeded")
        raise
    except (ValueError, RuntimeError) as exc:
        _fail_job_step(llm_step_id, exc)
        log.error("llm_calls_failed", error=str(exc))
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            _mark_run_failed(run_uuid, "llm_processing", str(exc))
            raise

    # ── 8. Persist ────────────────────────────────────────────────────────
    with get_sync_db() as db:
        from app.models.job_run import JobRun, JobRunStatus
        job_run = db.get(JobRun, run_uuid)
        if job_run is None:
            raise ValueError(f"JobRun {job_run_id} disappeared")
        job_run.retrieval_data = retrieval_data
        job_run.edit_plan = edit_plan
        job_run.positioning = positioning
        job_run.reports = report_pack
        job_run.status = JobRunStatus.RENDERING
        # Save role/company for kanban display
        if report_pack:
            job_run.role_title = (report_pack.get("role") or {}).get("role_title") or None
            job_run.company_name = (report_pack.get("company") or {}).get("company_name") or None
        # Save match score immediately
        score = edit_plan.get("keyword_match_score")
        if score is not None:
            job_run.keyword_match_score = int(score)
        db.commit()

    headline = (positioning or {}).get("positioning_headline", "")
    log.info("run_llm_complete", score=edit_plan.get("keyword_match_score", 0), headline=headline)

    # ── 9. Mark reports as phase 1 (quick) ───────────────────────────────
    with get_sync_db() as db:
        from app.models.job_run import JobRun
        jr = db.get(JobRun, run_uuid)
        if jr and jr.reports:
            rp = dict(jr.reports)
            rp["__detail_phase"] = "quick"
            jr.reports = rp
            db.commit()

    # ── 10. Chain → render, then detail enrichment ─────────────────────
    from app.workers.tasks.render_docx import render_docx_task
    render_docx_task.delay(job_run_id)
    # Dispatch phase 2 (detailed) — runs on LLM queue after quick pack
    run_detail_task.apply_async(args=[job_run_id], countdown=2)

    return {
        "job_run_id": job_run_id,
        "status": "llm_complete_rendering_dispatched",
        "keyword_match_score": edit_plan.get("keyword_match_score", 0),
        "positioning_headline": headline,
        "has_positioning": positioning is not None,
        "report_sections": list(report_pack.keys()) if report_pack else [],
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _run_cv_build_pipeline(
    profile_dict: dict | None,
    build_mode: str,
    quality_feedback: dict,
    jd_text: str,
    preferences: dict,
    retrieval_data: dict,
    log,
    known_contacts: list | None = None,
) -> tuple[dict, dict | None, dict, dict]:
    """
    CV build pipeline — used when build_mode is FROM_SCRATCH or REBUILD.

    Instead of an EditPlan diff, generates a full BuiltCV spec.
    Runs ReportPack (haiku, fast). Positioning skipped for speed.

    Returns the same tuple shape as _run_llm_calls so the persist step
    is unchanged: (edit_plan_or_built_cv, positioning, report_pack, meta)
    """
    from app.services.cv.cv_build_service import CVBuildService
    from app.services.llm.client import ClaudeClient
    from app.services.llm.schemas import ReportPack
    from app.services.llm.profile_prompt import _render_candidate_profile
    from app.services.llm.prompts import build_report_pack_user_prompt, REPORT_PACK_SYSTEM

    total_tokens = 0
    total_cost = 0.0
    meta = {"build_mode": build_mode}

    # Call A: CV Build (replaces EditPlan)
    build_svc = CVBuildService()
    built_cv = build_svc.build_from_profile(
        profile_dict=profile_dict or {},
        build_mode=build_mode,
        quality_feedback=quality_feedback,
        jd_text=jd_text,
        preferences=preferences,
    )
    # Wrap in a marker so renderer knows this is a built CV, not an EditPlan
    edit_plan_slot = {"built_cv": built_cv, "build_mode": build_mode}
    meta["cv_build"] = {"sections": len(built_cv.get("sections", []))}
    log.info("cv_build_complete", mode=build_mode, sections=len(built_cv.get("sections", [])))

    # Positioning skipped for speed
    positioning_dict = None

    # Call B: ReportPack (using haiku for speed)
    profile_summary = _render_candidate_profile(profile_dict) if profile_dict else None
    rp_user = build_report_pack_user_prompt(
        parsed_cv=None,
        jd_text=jd_text,
        retrieval_data=retrieval_data or {},
        preferences=preferences,
        profile_summary=profile_summary,
        known_contacts=known_contacts,
    )
    _QUICK_PREFIX = (
        "IMPORTANT — QUICK MODE: Keep every field value to 1-2 SHORT sentences. "
        "Use bullet lists with max 3 items per array field. "
        "For question_bank: include exactly 2 questions per category (not 4-6). "
        "For interview_process: include exactly 3 stages. "
        "For salary: include 1 entry only. For named_contacts: max 2 contacts. "
        "Brevity is critical — the full detailed version will follow.\n\n"
    )
    from app.services.llm.router import LLMTask
    rp_client = ClaudeClient(task=LLMTask.REPORT_PACK, max_tokens=8000)
    rp_obj, rp_result = rp_client.call_structured(
        system_prompt=_QUICK_PREFIX + REPORT_PACK_SYSTEM,
        user_prompt=rp_user,
        schema=ReportPack,
        temperature=0.3,
    )
    total_tokens += rp_result.input_tokens + rp_result.output_tokens
    total_cost += rp_result.cost_usd
    meta["report_pack"] = rp_result.to_metadata()
    meta["total_tokens"] = total_tokens
    meta["total_cost_usd"] = round(total_cost, 6)
    meta["has_positioning"] = positioning_dict is not None
    log.info("report_pack_done")

    return edit_plan_slot, positioning_dict, rp_obj.model_dump(), meta


def _build_prompts(profile_dict, parsed_cv, jd_text, preferences, retrieval_data, log, known_contacts=None) -> dict:
    if profile_dict:
        log.info("using_profile_prompts")
        from app.services.llm.profile_prompt import build_all_profile_prompts
        return build_all_profile_prompts(
            profile_dict=profile_dict,
            parsed_cv=parsed_cv,
            jd_text=jd_text,
            preferences=preferences,
            retrieval_data=retrieval_data,
            known_contacts=known_contacts,
        )
    else:
        log.info("using_cv_only_prompts")
        from app.services.llm.prompts import build_all_prompts
        prompts = build_all_prompts(
            parsed_cv=parsed_cv,
            jd_text=jd_text,
            retrieval_data=retrieval_data,
            preferences=preferences,
        )
        prompts["positioning"] = None
        return prompts


def _run_retrieval(jd_text: str, preferences: dict, log) -> dict:
    from app.services.retrieval.web_search import RetrievalService
    service = RetrievalService()
    try:
        result = service.retrieve_parallel(
            jd_text=jd_text,
            role_title=preferences.get("role_title", ""),
            region=preferences.get("region", "UAE"),
        )
        log.info("retrieval_complete", sources=len(result.sources))
        return result.to_dict()
    finally:
        service.close()


def _run_llm_calls(prompts: dict, has_profile: bool, log) -> tuple[dict, dict | None, dict, dict]:
    from app.services.llm.schemas import EditPlan, ReportPack
    from concurrent.futures import ThreadPoolExecutor

    total_tokens = 0
    total_cost = 0.0
    meta = {}

    # Run EditPlan and ReportPack in PARALLEL — they are independent
    edit_system, edit_user = prompts["edit_plan"]
    rp_system, rp_user = prompts["report_pack"]

    # Quick mode: prepend concise instruction to avoid JSON truncation at 8000 tokens
    _QUICK_PREFIX = (
        "IMPORTANT — QUICK MODE: Keep every field value to 1-2 SHORT sentences. "
        "Use bullet lists with max 3 items per array field. "
        "For question_bank: include exactly 2 questions per category (not 4-6). "
        "For interview_process: include exactly 3 stages. "
        "For salary: include 1 entry only. "
        "For named_contacts: max 2 contacts. "
        "Brevity is critical — the full detailed version will follow.\n\n"
    )
    rp_system_quick = _QUICK_PREFIX + rp_system

    ep_obj = ep_result = rp_obj = rp_result = None

    def call_edit_plan():
        from app.services.llm.client import ClaudeClient as _C
        from app.services.llm.router import LLMTask
        return _C(task=LLMTask.EDIT_PLAN).call_structured(
            system_prompt=edit_system, user_prompt=edit_user, schema=EditPlan, temperature=0.2,
        )

    def call_report_pack():
        from app.services.llm.client import ClaudeClient as _C
        from app.services.llm.router import LLMTask
        return _C(task=LLMTask.REPORT_PACK, max_tokens=8000).call_structured(
            system_prompt=rp_system_quick, user_prompt=rp_user, schema=ReportPack, temperature=0.3,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_ep = executor.submit(call_edit_plan)
        future_rp = executor.submit(call_report_pack)
        ep_obj, ep_result = future_ep.result()
        rp_obj, rp_result = future_rp.result()

    total_tokens += ep_result.input_tokens + ep_result.output_tokens
    total_cost += ep_result.cost_usd
    meta["edit_plan"] = ep_result.to_metadata()
    log.info("edit_plan_done", score=ep_obj.keyword_match_score)

    total_tokens += rp_result.input_tokens + rp_result.output_tokens
    total_cost += rp_result.cost_usd
    meta["report_pack"] = rp_result.to_metadata()
    log.info("report_pack_done")

    # Positioning skipped for speed — set to None
    positioning_dict = None

    meta["total_tokens"] = total_tokens
    meta["total_cost_usd"] = round(total_cost, 6)
    meta["has_positioning"] = positioning_dict is not None

    return ep_obj.model_dump(), positioning_dict, rp_obj.model_dump(), meta


def _create_job_step(job_run_id: uuid.UUID, step_name: str, celery_task_id: str) -> uuid.UUID:
    from app.models.job_step import JobStep, StepStatus
    step_id = uuid.uuid4()
    with get_sync_db() as db:
        db.add(JobStep(
            id=step_id, job_run_id=job_run_id, step_name=step_name,
            status=StepStatus.RUNNING, celery_task_id=celery_task_id,
            started_at=datetime.now(UTC),
        ))
        db.commit()
    return step_id


def _complete_job_step(step_id: uuid.UUID, metadata: dict) -> None:
    from app.models.job_step import JobStep, StepStatus
    with get_sync_db() as db:
        step = db.get(JobStep, step_id)
        if step:
            now = datetime.now(UTC)
            step.status = StepStatus.COMPLETED
            step.completed_at = now
            if step.started_at:
                step.duration_seconds = (now - step.started_at).total_seconds()
            step.metadata_json = metadata
            db.commit()


def _fail_job_step(step_id: uuid.UUID, error: Exception) -> None:
    from app.models.job_step import JobStep, StepStatus
    with get_sync_db() as db:
        step = db.get(JobStep, step_id)
        if step:
            now = datetime.now(UTC)
            step.status = StepStatus.FAILED
            step.completed_at = now
            if step.started_at:
                step.duration_seconds = (now - step.started_at).total_seconds()
            step.error_type = type(error).__name__
            step.error_message = str(error)[:2000]
            db.commit()


def _update_run_status(job_run_id: uuid.UUID, status_name: str) -> None:
    from app.models.job_run import JobRun, JobRunStatus
    with get_sync_db() as db:
        jr = db.get(JobRun, job_run_id)
        if jr:
            jr.status = JobRunStatus(status_name)
            db.commit()


def _mark_run_failed(job_run_id: uuid.UUID, failed_step: str, error_message: str) -> None:
    from app.models.job_run import JobRun, JobRunStatus
    try:
        with get_sync_db() as db:
            jr = db.get(JobRun, job_run_id)
            if jr and not jr.is_terminal:
                jr.status = JobRunStatus.FAILED
                jr.failed_step = failed_step
                jr.error_message = error_message[:2000]
                db.commit()
    except Exception as e:
        logger.error("failed_to_mark_run_failed", job_run_id=str(job_run_id), error=str(e))


# ── Phase 2: Detailed enrichment ─────────────────────────────────────────────

_DETAIL_EXTRA_INSTRUCTIONS = """
DETAILED MODE — go deep. This replaces a quick summary with a thorough analysis.

For COMPANY INTELLIGENCE: include specific revenue figures, funding rounds, employee count,
and recent strategic moves. Red flags should be things a candidate would never find on their own.

For ROLE INTELLIGENCE: be brutally specific about what they REALLY want vs what the JD says.
hiring_manager_worries must reference THIS candidate's actual gaps.
keyword_match_gaps must list exact missing keywords from CV vs JD.

For SALARY: include multiple data points with source URLs where available.

For NETWORKING: find REAL named people from the research data. Each outreach_message must be
personalised and ready to copy-paste (≤300 chars).

For APPLICATION STRATEGY:
- interview_process: minimum 4 stages with specific assessor roles
- question_bank: 4-6 questions per category, each referencing THIS candidate's background
- For behavioural questions: map to a SPECIFIC story from the candidate's CV
- For business cases: reference the company's ACTUAL strategic challenges from research
- questions_to_ask_them: 5 questions that signal deep preparation about THIS company
- thirty_sixty_ninety: specific to THIS company's situation, not generic
- risks_to_address and differentiators: at least 3 each, brutally honest

"""

_CV_POSITIONING_SYSTEM = """You are CareerOS Intelligence — a world-class career strategist.

Analyse this candidate's CV against a specific job description and produce a precise,
actionable Positioning Strategy as JSON.

Be SPECIFIC, not generic. Reference the candidate's actual experiences and the JD's actual requirements.
If a gap is serious, say so honestly — and give a real mitigation strategy.

OUTPUT — return ONLY this JSON:
{
  "positioning_headline": "one punchy sentence for THIS role",
  "strongest_angles": [
    {
      "angle": "name of this strength",
      "why_it_matters_here": "why it matters for THIS role and company",
      "how_to_play_it": "concrete guidance for CV, cover letter, and interviews",
      "evidence": ["specific examples from their CV"]
    }
  ],
  "gaps_to_address": [
    {"gap": "the gap", "severity": "low|medium|high", "mitigation": "how to handle it"}
  ],
  "narrative_thread": "the single through-line connecting all their experiences for this application",
  "red_flags_and_responses": [
    {"red_flag": "concern the interviewer will raise", "response": "how to address it"}
  ],
  "interview_themes": ["5-7 most likely interview themes"],
  "cover_letter_angle": "the single angle the cover letter should lead with"
}

RULES:
- strongest_angles must have exactly 3 entries
- gaps_to_address must have at least 2 entries with honest severity ratings
- red_flags_and_responses must have at least 3 entries
- Never invent experience the candidate doesn't have
- RETURN ONLY JSON. No preamble. No markdown.
"""


@celery.task(
    bind=True,
    name="app.workers.tasks.run_llm.run_detail_task",
    max_retries=1,
    default_retry_delay=10,
    soft_time_limit=600,
    time_limit=660,
)
def run_detail_task(self: Task, job_run_id: str) -> dict:
    """
    Phase 2: Deep enrichment with Sonnet + fresh web research.

    1. Run fresh detailed web retrieval (more queries, deeper research)
    2. Generate full ReportPack with Sonnet (replaces quick Haiku version)
    3. Generate Positioning Strategy (works with CV or profile)
    4. Update job_run — frontend auto-refreshes
    """
    log = logger.bind(job_run_id=job_run_id, task_id=self.request.id, phase="detail")
    log.info("run_detail_task_started")

    try:
        run_uuid = uuid.UUID(job_run_id)
    except ValueError as e:
        log.error("invalid_uuid", error=str(e))
        raise

    # ── 1. Load inputs ─────────────────────────────────────────────────
    with get_sync_db() as db:
        from app.models.job_run import JobRun
        from app.models.cv import CV
        from app.models.candidate_profile import CandidateProfile
        from sqlalchemy import select

        job_run = db.get(JobRun, run_uuid)
        if job_run is None:
            return {"status": "not_found"}

        jd_text = job_run.jd_text or ""
        preferences = dict(job_run.preferences or {})
        known_contacts = list(preferences.get("known_contacts", []) or [])

        cv = db.get(CV, job_run.cv_id)
        parsed_content = dict(cv.parsed_content) if cv and cv.parsed_content else None

        profile_dict = None
        if job_run.profile_id:
            p = db.get(CandidateProfile, job_run.profile_id)
            if p:
                profile_dict = p.to_prompt_dict()
        else:
            result = db.execute(
                select(CandidateProfile).where(
                    CandidateProfile.user_id == job_run.user_id,
                ).order_by(CandidateProfile.updated_at.desc())
            )
            p = result.scalars().first()
            if p:
                profile_dict = p.to_prompt_dict()

    if not jd_text.strip():
        return {"status": "skipped_no_jd"}

    log.info("detail_inputs_loaded", has_profile=profile_dict is not None)

    # ── 2. Fresh detailed retrieval ────────────────────────────────────
    try:
        retrieval_data = _run_retrieval(jd_text, preferences, log)
        log.info("detail_retrieval_done", sources=len(retrieval_data.get("sources", [])))
    except Exception as e:
        log.warning("detail_retrieval_failed", error=str(e))
        retrieval_data = {}

    # Update retrieval data in DB
    with get_sync_db() as db:
        from app.models.job_run import JobRun
        jr = db.get(JobRun, run_uuid)
        if jr and retrieval_data:
            jr.retrieval_data = retrieval_data
            db.commit()

    # ── 3. Build prompts ───────────────────────────────────────────────
    from app.services.llm.client import ClaudeClient
    from app.services.llm.schemas import ReportPack
    from app.services.llm.prompts import build_report_pack_user_prompt, REPORT_PACK_SYSTEM
    from concurrent.futures import ThreadPoolExecutor
    import json, re

    # CV summary for prompts
    profile_summary = None
    parsed_cv_obj = None
    cv_text_for_positioning = ""
    if profile_dict:
        from app.services.llm.profile_prompt import _render_candidate_profile
        profile_summary = _render_candidate_profile(profile_dict)
        cv_text_for_positioning = profile_summary
    elif parsed_content:
        from app.schemas.cv import ParsedCV
        try:
            parsed_cv_obj = ParsedCV.model_validate(parsed_content)
            # Render CV as text for positioning
            lines = []
            for sec in parsed_cv_obj.sections:
                if sec.heading:
                    lines.append(f"\n{sec.heading.upper()}")
                for p in sec.paragraphs[:8]:
                    if not p.is_empty:
                        lines.append(p.text)
            cv_text_for_positioning = "\n".join(lines)[:4000]
        except Exception:
            pass

    rp_user = build_report_pack_user_prompt(
        parsed_cv=parsed_cv_obj,
        jd_text=jd_text,
        retrieval_data=retrieval_data,
        preferences=preferences,
        profile_summary=profile_summary,
        known_contacts=known_contacts,
    )

    # Detailed system prompt
    detail_system = _DETAIL_EXTRA_INSTRUCTIONS + REPORT_PACK_SYSTEM

    # ── 4. Run Sonnet calls in parallel ────────────────────────────────
    total_tokens = 0
    total_cost = 0.0
    detailed_report = None
    positioning_dict = None

    def call_detail_report():
        from app.services.llm.router import LLMTask as _T
        # 12000 tokens — detail report needs space for company/role/salary/networking
        # /application/exec_summary sections. 6000 was too low and caused truncation
        # → "Unterminated string" JSON parse errors.
        c = ClaudeClient(task=_T.REPORT_PACK, max_tokens=12000)
        return c.call_structured(
            system_prompt=detail_system,
            user_prompt=rp_user,
            schema=ReportPack,
            temperature=0.3,
        )

    def call_positioning():
        """Generate positioning from CV or profile — works without profile."""
        if not cv_text_for_positioning:
            return None, None
        # Build positioning prompt from CV text
        if profile_dict:
            from app.services.llm.profile_prompt import build_positioning_strategy_prompt
            pos_system, pos_user = build_positioning_strategy_prompt(
                profile_dict=profile_dict,
                jd_text=jd_text,
                preferences=preferences,
                retrieval_data=retrieval_data,
            )
        else:
            # CV-based positioning (no profile needed)
            pos_system = _CV_POSITIONING_SYSTEM
            company_overview = (retrieval_data.get("company_overview") or "")[:1500]
            pos_user = (
                f"CANDIDATE CV:\n{cv_text_for_positioning}\n\n"
                f"JOB DESCRIPTION:\n{jd_text[:6000]}\n\n"
                f"COMPANY RESEARCH:\n{company_overview}\n\n"
                f"Region: {preferences.get('region', 'UAE')}"
            )
        from app.services.llm.router import LLMTask as _T
        # Cost optimization: positioning JSON fits in 4000 tokens
        c = ClaudeClient(task=_T.POSITIONING, max_tokens=4000)
        raw, result = c.call_raw(
            system_prompt=pos_system, user_prompt=pos_user, temperature=0.3,
        )
        text = re.sub(r"^```(?:json)?\s*", "", raw.strip())
        text = re.sub(r"\s*```$", "", text).strip()
        return json.loads(text), result

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_rp = executor.submit(call_detail_report)
            future_pos = executor.submit(call_positioning)

            rp_obj, rp_result = future_rp.result()
            detailed_report = rp_obj.model_dump()
            total_tokens += rp_result.input_tokens + rp_result.output_tokens
            total_cost += rp_result.cost_usd
            log.info("detail_report_pack_done")

            try:
                pos_data, pos_result = future_pos.result()
                if pos_data:
                    positioning_dict = pos_data
                    total_tokens += pos_result.input_tokens + pos_result.output_tokens
                    total_cost += pos_result.cost_usd
                    log.info("detail_positioning_done",
                             headline=positioning_dict.get("positioning_headline", ""))
            except Exception as e:
                log.warning("detail_positioning_failed_continuing", error=str(e))

    except Exception as e:
        log.error("detail_llm_calls_failed", error=str(e))
        with get_sync_db() as db:
            from app.models.job_run import JobRun
            jr = db.get(JobRun, run_uuid)
            if jr and jr.reports:
                rp = dict(jr.reports)
                rp["__detail_phase"] = "failed"
                jr.reports = rp
                db.commit()
        return {"status": "detail_failed", "error": str(e)}

    # ── 5. Persist ─────────────────────────────────────────────────────
    with get_sync_db() as db:
        from app.models.job_run import JobRun
        jr = db.get(JobRun, run_uuid)
        if jr:
            if detailed_report:
                detailed_report["__detail_phase"] = "detailed"
                jr.reports = detailed_report
            if positioning_dict:
                jr.positioning = positioning_dict
            if detailed_report:
                jr.role_title = (detailed_report.get("role") or {}).get("role_title") or jr.role_title
                jr.company_name = (detailed_report.get("company") or {}).get("company_name") or jr.company_name
            db.commit()

    log.info("run_detail_complete",
             tokens=total_tokens, cost=round(total_cost, 4),
             has_positioning=positioning_dict is not None)

    return {
        "job_run_id": job_run_id,
        "status": "detail_complete",
        "total_tokens": total_tokens,
        "total_cost_usd": round(total_cost, 6),
        "has_positioning": positioning_dict is not None,
    }
