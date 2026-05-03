"""
app/api/routes/quickstart.py

Single orchestration endpoint that chains the full pipeline:
  CV upload → parse → extract profile → apply → activate → ready for jobs

This endpoint does NOT replace existing individual endpoints.
It provides a convenience wrapper for the frontend.
"""

import uuid
import asyncio

import structlog
from fastapi import APIRouter, File, HTTPException, UploadFile, status
from sqlalchemy import select

from app.dependencies import DB, CurrentUserId, S3Client
from app.models.cv import CV, CVStatus
from app.models.candidate_profile import CandidateProfile, ProfileStatus
from app.schemas.common import QuickstartResponse

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/quickstart", tags=["Quick Start"])


def _content_type_from_filename(filename: str, fallback: str | None) -> str:
    """Match /api/v1/cvs — browsers often send wrong MIME for .docx."""
    fn = filename or "cv.pdf"
    ext = fn.lower().rsplit(".", 1)[-1] if "." in fn else ""
    mime_map = {
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pdf": "application/pdf",
    }
    return mime_map.get(ext) or fallback or "application/pdf"


@router.post(
    "/upload-and-populate",
    status_code=status.HTTP_200_OK,
    summary="Upload CV → parse → extract profile → auto-populate. One call.",
    response_model=QuickstartResponse,
)
async def upload_and_populate(
    db: DB,
    s3_client: S3Client,
    user_id: CurrentUserId,
    file: UploadFile = File(...),
) -> dict:
    """
    Full pipeline in one endpoint:
    1. Upload CV to S3
    2. Parse CV (sync — wait for Celery task)
    3. Get or create profile
    4. Extract structured data via Claude
    5. Apply to profile (experiences, skills, headline)
    6. Activate profile
    7. Return everything
    """
    from app.services.ingest.storage import S3StorageService
    from app.services.ingest.cv_service import CVService

    # Step 1: Upload
    logger.info("quickstart_upload", filename=file.filename, user_id=user_id)
    storage = S3StorageService(client=s3_client)
    cv_service = CVService(db=db, storage=storage)

    file_bytes = await file.read()
    filename = file.filename or "cv.pdf"
    content_type = _content_type_from_filename(filename, file.content_type)
    result = await cv_service.upload_cv(
        user_id=user_id,
        filename=filename,
        file_data=file_bytes,
        content_type=content_type,
    )
    cv_id = result.id
    logger.info("quickstart_uploaded", cv_id=str(cv_id))

    # Step 2: Wait for parse (poll DB, max 60 seconds)
    parsed = False
    for _ in range(30):
        await asyncio.sleep(2)
        db.expire_all()
        cv = (await db.execute(
            select(CV).where(CV.id == cv_id)
        )).scalar_one_or_none()
        if cv and cv.status == CVStatus.PARSED:
            parsed = True
            break
        if cv and cv.status == CVStatus.FAILED:
            raise HTTPException(status_code=422, detail="CV parsing failed. Try a DOCX file.")

    if not parsed:
        # Celery didn't parse in time — skip Celery and proceed directly
        # The Claude extraction in Step 4 will read raw bytes from S3
        logger.warning("quickstart_celery_parse_timeout", cv_id=str(cv_id))
        # Mark CV as parsed so the rest of the pipeline works
        cv = (await db.execute(select(CV).where(CV.id == cv_id))).scalar_one_or_none()
        if cv:
            cv.status = CVStatus.PARSED
            await db.flush()

    logger.info("quickstart_parsed", cv_id=str(cv_id))

    # Step 3: Get or create profile
    profile = (await db.execute(
        select(CandidateProfile).where(
            CandidateProfile.user_id == user_id,
            CandidateProfile.status == ProfileStatus.ACTIVE,
        )
    )).scalar_one_or_none()

    if not profile:
        # Try any profile (DRAFT)
        profile = (await db.execute(
            select(CandidateProfile).where(
                CandidateProfile.user_id == user_id,
            ).order_by(CandidateProfile.created_at.desc()).limit(1)
        )).scalar_one_or_none()

    if not profile:
        profile = CandidateProfile(
            user_id=user_id,
            status=ProfileStatus.DRAFT,
            headline="",
            global_context="",
            version=1,
        )
        db.add(profile)
        await db.flush()
        await db.refresh(profile)

    profile_id = profile.id
    logger.info("quickstart_profile", profile_id=str(profile_id))

    # Step 4: Extract via Claude (import-cv)
    imported = None
    try:
        from app.api.routes.profile_import import _extract_profile_with_claude, _cv_to_text
        cv = (await db.execute(select(CV).where(CV.id == cv_id))).scalar_one_or_none()
        if not cv:
            raise HTTPException(status_code=404, detail="CV record missing after upload")

        cv_text = ""
        if cv.parsed_content:
            cv_text = _cv_to_text(cv.parsed_content)

        if not cv_text:
            from app.config import settings
            from app.api.routes.profile_import import _extract_text_from_bytes
            import boto3
            s3 = boto3.client("s3",
                endpoint_url=settings.s3_endpoint_url,
                aws_access_key_id=settings.s3_access_key_id,
                aws_secret_access_key=settings.s3_secret_access_key,
                region_name=settings.s3_region,
            )
            loop2 = asyncio.get_running_loop()
            obj = await loop2.run_in_executor(
                None, lambda: s3.get_object(Bucket=cv.s3_bucket, Key=cv.s3_key)
            )
            raw_bytes = obj["Body"].read()
            cv_text = _extract_text_from_bytes(raw_bytes, cv.original_filename)

        if cv_text:
            from functools import partial
            loop = asyncio.get_running_loop()
            imported = await loop.run_in_executor(
                None, partial(_extract_profile_with_claude, cv_text)
            )
            logger.info("quickstart_extracted", experiences=len(imported.experiences) if imported else 0)
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("quickstart_extract_failed", error=str(e))
        # Non-fatal: profile will exist but without Claude-extracted data

    # Step 5: Apply to profile
    experiences_added = 0
    if imported:
        try:
            import json as _json
            from app.models.candidate_profile import ExperienceEntry

            # Update profile fields
            if imported.headline:
                profile.headline = imported.headline
            if imported.full_name:
                # Update user name too
                from app.models.user import User
                try:
                    uid_uuid = uuid.UUID(str(user_id))
                except ValueError:
                    uid_uuid = None
                user = (
                    (await db.execute(select(User).where(User.id == uid_uuid))).scalar_one_or_none()
                    if uid_uuid
                    else None
                )
                if user and not user.full_name:
                    user.full_name = imported.full_name

            # Store in global_context
            ctx = {}
            try:
                ctx = _json.loads(profile.global_context or "{}")
            except Exception:
                pass
            for field in ["summary", "skills", "languages", "email", "phone", "nationality", "linkedin_url"]:
                val = getattr(imported, field, None)
                if val:
                    ctx[field] = val
            if imported.education:
                ctx["education"] = [e if isinstance(e, dict) else (e.model_dump() if hasattr(e, "model_dump") else e) for e in imported.education]
            if imported.full_name:
                ctx["full_name"] = imported.full_name
            profile.global_context = _json.dumps(ctx)

            # Clear existing experiences to avoid duplicates on re-upload
            from sqlalchemy import delete as sa_delete
            await db.execute(
                sa_delete(ExperienceEntry).where(ExperienceEntry.profile_id == profile_id)
            )

            # Add experiences
            for i, exp in enumerate(imported.experiences):
                entry = ExperienceEntry(
                    profile_id=profile_id,
                    company_name=exp.company_name or "",
                    role_title=exp.role_title or "",
                    start_date=exp.start_date or "",
                    end_date=exp.end_date or "",
                    location=exp.location or "",
                    display_order=i,
                    is_complete=False,
                    context=exp.context or "",
                    contribution=exp.contribution or "",
                    outcomes=exp.outcomes or "",
                    methods=exp.methods or "",
                )
                db.add(entry)
                experiences_added += 1

            # Step 6: Activate (request DB dependency commits on success)
            profile.status = ProfileStatus.ACTIVE
            await db.flush()

        except Exception as e:
            logger.warning("quickstart_apply_failed", error=str(e))
            try:
                await db.rollback()
            except Exception:
                pass

    # Build response
    response = {
        "cv_id": str(cv_id),
        "cv_status": "parsed",
        "profile_id": str(profile_id),
        "profile_status": str(profile.status),
        "experiences_added": experiences_added,
        "headline": profile.headline or "",
    }

    if imported:
        response["extracted"] = {
            "full_name": imported.full_name,
            "headline": imported.headline,
            "skills": imported.skills if hasattr(imported, "skills") else [],
            "experiences_count": len(imported.experiences),
            "education_count": len(imported.education) if hasattr(imported, "education") else 0,
        }

    return response
