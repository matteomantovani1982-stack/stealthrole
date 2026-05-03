"""
app/api/routes/extension.py

Chrome Extension capture API — receives raw data from the
browser extension and triggers signal creation pipeline.

After creating a HiddenSignal, each endpoint runs the
intelligence pipeline inline:
  1. SignalQualityFilter.score_signal()  — quality gate
  2. SignalInterpretationEngine.interpret() — interpretation

The route owns the final db.commit().

Endpoints
---------
  POST /extension/capture-profile  — LinkedIn profile
  POST /extension/capture-job      — Job posting
  POST /extension/capture-company  — Company page
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, status

from app.api.middleware.rate_limiter import rate_limit
from app.dependencies import DB, CurrentUserId
from app.models.hidden_signal import HiddenSignal
from app.schemas.extension import (
    CaptureCompanyRequest,
    CaptureJobRequest,
    CaptureProfileRequest,
    CaptureResponse,
)
from app.services.billing.plan_gating import (
    ExtensionCaptureFeature,
)
from app.services.intelligence.signal_interpretation import (
    SignalInterpretationEngine,
)
from app.services.intelligence.signal_quality import (
    SignalQualityFilter,
)

logger = structlog.get_logger(__name__)
router = APIRouter(
    prefix="/api/v1/extension", tags=["Extension"],
)


# ── Pipeline helper ─────────────────────────────────────────


async def _enrich_signal(
    db: DB,
    signal: HiddenSignal,
    user_id: str,
) -> dict:
    """Run quality + interpretation pipeline on a signal.

    Returns a dict with pipeline results for logging.
    Does NOT commit — caller owns the transaction.
    """
    result: dict = {
        "quality_gate": None,
        "interpreted": False,
    }

    try:
        # 1 — Quality scoring
        quality_filter = SignalQualityFilter(db)
        quality = await quality_filter.score_signal(
            signal, user_id,
        )
        result["quality_gate"] = (
            quality.gate_result
            if quality else None
        )

        # 2 — Interpretation (only if quality passes)
        if signal.quality_gate_result in (
            "pass", "conditional",
        ):
            interp_engine = SignalInterpretationEngine(db)
            interp = await interp_engine.interpret(
                signal, user_id,
            )
            result["interpreted"] = interp is not None

    except Exception:
        # Pipeline errors should not block capture
        logger.exception(
            "extension_pipeline_error",
            signal_id=str(signal.id),
            user_id=user_id,
        )

    return result


# ── Capture Profile ─────────────────────────────────────────


@router.post(
    "/capture-profile",
    response_model=CaptureResponse,
    status_code=status.HTTP_201_CREATED,
)
async def capture_profile(
    body: CaptureProfileRequest,
    current_user_id: CurrentUserId,
    db: DB,
    _gate: ExtensionCaptureFeature,
    _rl: None = Depends(
        rate_limit(
            "ext_capture", max_calls=30,
            window_seconds=60,
        ),
    ),
) -> CaptureResponse:
    """Capture a LinkedIn profile from the extension.

    Stores the raw data and creates a leadership signal
    if the profile suggests hiring authority. Runs the
    intelligence pipeline on the created signal.
    """
    capture_id = str(uuid.uuid4())
    signals_created = 0

    # Create signal if profile suggests hiring role
    hiring_keywords = [
        "hiring", "recruiting", "talent",
        "head of", "vp", "director", "cto",
        "ceo", "founder",
    ]
    headline_lower = body.headline.lower()
    is_hiring_signal = any(
        kw in headline_lower for kw in hiring_keywords
    )

    if is_hiring_signal and body.company:
        signal = HiddenSignal(
            user_id=current_user_id,
            company_name=body.company,
            signal_type="leadership",
            confidence=0.55,
            likely_roles=[],
            reasoning=(
                f"LinkedIn profile captured: "
                f"{body.full_name} — {body.headline} "
                f"at {body.company}"
            ),
            source_url=body.linkedin_url,
            source_name="chrome_extension",
            signal_data={
                "capture_type": "profile",
                "capture_id": capture_id,
                "full_name": body.full_name,
                "headline": body.headline,
            },
            provider="extension",
        )
        db.add(signal)
        await db.flush()
        signals_created = 1

        # Run intelligence pipeline
        pipeline = await _enrich_signal(
            db, signal, current_user_id,
        )
        logger.info(
            "extension_profile_pipeline",
            capture_id=capture_id,
            **pipeline,
        )

    await db.commit()

    logger.info(
        "extension_profile_captured",
        user_id=current_user_id,
        capture_id=capture_id,
        signals=signals_created,
    )

    return CaptureResponse(
        success=True,
        capture_id=capture_id,
        capture_type="profile",
        signals_created=signals_created,
        message=(
            f"Profile captured"
            f"{' — signal created' if signals_created else ''}"
        ),
    )


# ── Capture Job ─────────────────────────────────────────────


@router.post(
    "/capture-job",
    response_model=CaptureResponse,
    status_code=status.HTTP_201_CREATED,
)
async def capture_job(
    body: CaptureJobRequest,
    current_user_id: CurrentUserId,
    db: DB,
    _gate: ExtensionCaptureFeature,
    _rl: None = Depends(
        rate_limit(
            "ext_capture", max_calls=30,
            window_seconds=60,
        ),
    ),
) -> CaptureResponse:
    """Capture a job posting from the extension.

    Creates a hiring_surge signal and runs the
    intelligence pipeline.
    """
    capture_id = str(uuid.uuid4())

    signal = HiddenSignal(
        user_id=current_user_id,
        company_name=body.company or "Unknown",
        signal_type="hiring_surge",
        confidence=0.70,
        likely_roles=(
            [{"role": body.title}] if body.title else []
        ),
        reasoning=(
            f"Job posting captured: {body.title} "
            f"at {body.company}"
        ),
        source_url=body.job_url,
        source_name="chrome_extension",
        signal_data={
            "capture_type": "job",
            "capture_id": capture_id,
            "title": body.title,
            "location": body.location,
            "description": body.description[:500],
        },
        provider="extension",
    )
    db.add(signal)
    await db.flush()

    # Run intelligence pipeline
    pipeline = await _enrich_signal(
        db, signal, current_user_id,
    )
    logger.info(
        "extension_job_pipeline",
        capture_id=capture_id,
        **pipeline,
    )

    await db.commit()

    logger.info(
        "extension_job_captured",
        user_id=current_user_id,
        capture_id=capture_id,
        company=body.company,
    )

    return CaptureResponse(
        success=True,
        capture_id=capture_id,
        capture_type="job",
        signals_created=1,
        message="Job posting captured — signal created",
    )


# ── Capture Company ─────────────────────────────────────────


@router.post(
    "/capture-company",
    response_model=CaptureResponse,
    status_code=status.HTTP_201_CREATED,
)
async def capture_company(
    body: CaptureCompanyRequest,
    current_user_id: CurrentUserId,
    db: DB,
    _gate: ExtensionCaptureFeature,
    _rl: None = Depends(
        rate_limit(
            "ext_capture", max_calls=30,
            window_seconds=60,
        ),
    ),
) -> CaptureResponse:
    """Capture a company page from the extension.

    Creates an expansion signal and runs the
    intelligence pipeline.
    """
    capture_id = str(uuid.uuid4())
    signals_created = 0

    if body.company_name:
        signal = HiddenSignal(
            user_id=current_user_id,
            company_name=body.company_name,
            signal_type="expansion",
            confidence=0.45,
            likely_roles=[],
            reasoning=(
                f"Company page captured: "
                f"{body.company_name}"
                f" — {body.industry}"
            ),
            source_url=body.company_url,
            source_name="chrome_extension",
            signal_data={
                "capture_type": "company",
                "capture_id": capture_id,
                "industry": body.industry,
                "size": body.size,
                "recent_posts_count": len(
                    body.recent_posts,
                ),
            },
            provider="extension",
        )
        db.add(signal)
        await db.flush()
        signals_created = 1

        # Run intelligence pipeline
        pipeline = await _enrich_signal(
            db, signal, current_user_id,
        )
        logger.info(
            "extension_company_pipeline",
            capture_id=capture_id,
            **pipeline,
        )

    await db.commit()

    logger.info(
        "extension_company_captured",
        user_id=current_user_id,
        capture_id=capture_id,
        company=body.company_name,
    )

    return CaptureResponse(
        success=True,
        capture_id=capture_id,
        capture_type="company",
        signals_created=signals_created,
        message=(
            f"Company page captured"
            f"{' — signal created' if signals_created else ''}"
        ),
    )
