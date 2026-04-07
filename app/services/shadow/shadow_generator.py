"""
app/services/shadow/shadow_generator.py

CV generation component for Shadow Applications.

Reuses the existing edit_plan pipeline to generate a tailored CV
for a shadow application (company + hypothesised role).

This module builds a synthetic JD from the hypothesis, then calls
the same LLM pipeline used for regular job applications.
"""

import structlog

logger = structlog.get_logger(__name__)


def build_shadow_jd(
    company: str,
    hypothesis_role: str,
    hiring_hypothesis: str,
    signal_context: str,
) -> str:
    """
    Build a synthetic job description from shadow application context.

    Since there's no real JD (the job doesn't exist yet), we construct
    one from the hiring hypothesis. This feeds into the existing
    edit_plan pipeline which expects jd_text.
    """
    return (
        f"Role: {hypothesis_role}\n"
        f"Company: {company}\n\n"
        f"Context:\n{signal_context}\n\n"
        f"About this opportunity:\n{hiring_hypothesis}\n\n"
        f"This is a proactive application based on market signals. "
        f"The candidate is approaching the company before the role is posted. "
        f"Tailor the CV to demonstrate fit for {hypothesis_role} at {company}, "
        f"emphasising relevant experience and transferable skills."
    )


def generate_shadow_cv_edit_plan(
    parsed_cv_dict: dict,
    profile_dict: dict | None,
    company: str,
    hypothesis_role: str,
    hiring_hypothesis: str,
    signal_context: str,
) -> dict:
    """
    Generate an edit_plan for a shadow application CV.

    Reuses the exact same LLM prompts and schema as the regular
    pipeline, but with a synthetic JD built from the hypothesis.

    Returns the edit_plan dict (same shape as regular JobRun.edit_plan).
    """
    from app.schemas.cv import ParsedCV
    from app.services.llm.client import ClaudeClient
    from app.services.llm.schemas import EditPlan

    synthetic_jd = build_shadow_jd(
        company=company,
        hypothesis_role=hypothesis_role,
        hiring_hypothesis=hiring_hypothesis,
        signal_context=signal_context,
    )

    parsed_cv = ParsedCV.model_validate(parsed_cv_dict)

    # Build prompts — use profile-aware if available, else CV-only
    if profile_dict:
        from app.services.llm.profile_prompt import build_all_profile_prompts
        prompts = build_all_profile_prompts(
            profile_dict=profile_dict,
            parsed_cv=parsed_cv,
            jd_text=synthetic_jd,
            preferences={},
            retrieval_data={},
        )
    else:
        from app.services.llm.prompts import build_all_prompts
        prompts = build_all_prompts(
            parsed_cv=parsed_cv,
            jd_text=synthetic_jd,
            retrieval_data={},
            preferences={},
        )

    edit_system, edit_user = prompts["edit_plan"]

    from app.services.llm.router import LLMTask
    client = ClaudeClient(task=LLMTask.EDIT_PLAN, max_tokens=8000)
    ep_obj, ep_result = client.call_structured(
        system_prompt=edit_system,
        user_prompt=edit_user,
        schema=EditPlan,
        temperature=0.2,
    )

    logger.info(
        "shadow_cv_edit_plan_generated",
        company=company,
        role=hypothesis_role,
        score=ep_obj.keyword_match_score,
        tokens=ep_result.input_tokens + ep_result.output_tokens,
        cost=ep_result.cost_usd,
    )

    return ep_obj.model_dump()
