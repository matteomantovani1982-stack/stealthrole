"""
app/api/routes/uploads.py

CV upload and status endpoints.

Routes:
  POST   /api/v1/cvs          Upload a CV file (DOCX or PDF)
  GET    /api/v1/cvs          List user's uploaded CVs
  GET    /api/v1/cvs/{cv_id}  Get parse status of a specific CV

Design rules enforced here:
  - No business logic — delegate everything to CVService
  - No direct DB or S3 access — injected via dependencies
  - File data read into memory here (max 10MB enforced by service)
  - user_id sourced from API key header for now (replace with JWT later)
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.dependencies import DB, CurrentUserId, S3Client
from app.schemas.cv import CVListItem, CVStatusResponse, CVUploadResponse
from app.services.ingest.cv_service import CVService
from app.services.ingest.anomaly_detector import detect_anomalies
from app.services.ingest.storage import S3StorageService

router = APIRouter(
    prefix="/api/v1/cvs",
    tags=["CV Upload"],
)

# ── Temporary user identity ─────────────────────────────────────────────────
# In production this will come from a JWT / auth middleware.
# For now, clients pass X-User-Id header.
# This is intentionally simple — auth is not in Sprint 1 scope.



# ── Helper: build service from injected deps ────────────────────────────────

def _make_cv_service(db: DB, s3_client: S3Client) -> CVService:
    """
    Constructs a CVService from injected dependencies.
    Wraps the raw boto3 client in our S3StorageService abstraction.
    """
    storage = S3StorageService(client=s3_client)
    return CVService(db=db, storage=storage)


# ── Routes ──────────────────────────────────────────────────────────────────

@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=CVUploadResponse,
    summary="Upload a CV file",
    description=(
        "Upload a DOCX or PDF CV file. "
        "Returns immediately with status=uploaded. "
        "Parsing runs asynchronously — poll GET /api/v1/cvs/{cv_id} for status."
    ),
)
async def upload_cv(
    db: DB,
    s3_client: S3Client,
    x_user_id: CurrentUserId,
    file: UploadFile = File(
        ...,
        description="CV file to upload. Must be .docx or .pdf, max 10MB.",
    ),
) -> CVUploadResponse:
    """
    Accepts a multipart file upload.

    Flow:
    1. Read file bytes into memory
    2. Delegate to CVService.upload_cv (validate → S3 → DB → dispatch task)
    3. Return 202 Accepted with CV id and initial status

    Why 202 and not 201?
    The resource (parsed CV) isn't ready yet — parsing is async.
    202 correctly signals "accepted for processing".
    """
    # Read file bytes — FastAPI's UploadFile is a SpooledTemporaryFile
    file_data = await file.read()

    # Normalise content_type — browsers often send wrong MIME for .docx
    # Always derive from filename extension to be safe
    filename = file.filename or "untitled.docx"
    _ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    _mime_map = {
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pdf": "application/pdf",
    }
    content_type = _mime_map.get(_ext) or file.content_type or "application/octet-stream"

    # Quick content check: warn if the file looks like a JD, not a CV
    content_warning = None
    try:
        text = _extract_text(file_data, filename)
        if text and _detect_document_type(text) == "jd":
            content_warning = (
                "This file appears to be a Job Description, not a CV. "
                "If you intended to upload your CV, please check the file."
            )
    except Exception:
        pass  # Don't block upload on classification failure

    service = _make_cv_service(db=db, s3_client=s3_client)

    result = await service.upload_cv(
        user_id=x_user_id,
        filename=filename,
        content_type=content_type,
        file_data=file_data,
    )

    # Attach warning to response if detected
    if content_warning:
        import json as _json
        result_dict = _json.loads(result.model_dump_json()) if hasattr(result, "model_dump_json") else result
        if isinstance(result_dict, dict):
            result_dict["content_warning"] = content_warning
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=202, content=result_dict)

    return result


@router.get(
    "",
    response_model=list[CVListItem],
    summary="List uploaded CVs",
    description="Returns all CVs uploaded by the authenticated user, newest first.",
)
async def list_cvs(
    db: DB,
    s3_client: S3Client,
    x_user_id: CurrentUserId,
) -> list[CVListItem]:
    service = _make_cv_service(db=db, s3_client=s3_client)
    return await service.list_cvs(user_id=x_user_id)


@router.get(
    "/{cv_id}",
    response_model=CVStatusResponse,
    summary="Get CV parse status",
    description=(
        "Poll this endpoint after uploading a CV to check parse progress. "
        "When status=parsed, the CV is ready to use in a job run."
    ),
)
async def get_cv_status(
    cv_id: uuid.UUID,
    db: DB,
    s3_client: S3Client,
    x_user_id: CurrentUserId,
) -> CVStatusResponse:
    service = _make_cv_service(db=db, s3_client=s3_client)
    return await service.get_cv_status(cv_id=cv_id, user_id=x_user_id)


@router.delete(
    "/{cv_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a CV",
)
async def delete_cv(
    cv_id: uuid.UUID,
    db: DB,
    s3_client: S3Client,
    x_user_id: CurrentUserId,
) -> dict:
    """Delete a CV and its S3 object. Only the owner can delete."""
    from sqlalchemy import select, delete as sql_delete
    from app.models.cv import CV

    result = await db.execute(
        select(CV).where(CV.id == cv_id, CV.user_id == x_user_id)
    )
    cv = result.scalar_one_or_none()
    if not cv:
        raise HTTPException(status_code=404, detail="CV not found")

    # Delete from S3 if key exists
    if cv.s3_key:
        try:
            from app.config import settings
            s3_client.delete_object(
                Bucket=settings.effective_s3_bucket,
                Key=cv.s3_key,
            )
        except Exception:
            pass  # S3 cleanup failure is non-fatal

    await db.execute(sql_delete(CV).where(CV.id == cv_id))
    await db.commit()

    return {"status": "deleted", "cv_id": str(cv_id)}


# ── Ingest endpoint ─────────────────────────────────────────────────────────

# Keywords that indicate a job description rather than a CV
_JD_KEYWORDS = {
    "requirements", "responsibilities", "we are looking", "qualifications",
    "about the role", "what you'll do", "who we're looking for",
    "about the company", "how to apply", "apply now", "job description",
    "the ideal candidate", "you will be responsible", "key responsibilities",
    "what we offer", "benefits", "equal opportunity", "must have",
    "nice to have", "the role", "reporting to", "you will",
}

# Keywords that indicate a CV / resume
_CV_KEYWORDS = {
    "experience", "education", "skills", "objective", "references",
    "certifications", "achievements", "career history", "employment history",
    "professional experience", "work experience",
}


class IngestResponse(BaseModel):
    document_type: str  # 'cv' | 'jd' | 'other'
    anomaly_flags: list[dict]
    file_id: str


def _detect_document_type(text: str) -> str:
    """Classify document as CV, JD, or other.

    Uses keyword density, strong phrases, and voice detection
    (second person = JD, first person = CV).
    """
    lower = text.lower()

    jd_hits = sum(1 for kw in _JD_KEYWORDS if kw in lower)
    cv_hits = sum(1 for kw in _CV_KEYWORDS if kw in lower)

    # Strong JD phrases — one hit is high confidence
    strong_jd = any(phrase in lower for phrase in [
        "about the role", "about the company", "how to apply",
        "the ideal candidate", "key responsibilities", "we are looking",
        "what we offer", "reporting to", "join our team",
        "this position", "we need", "we're hiring", "the position",
        "role overview", "company overview", "main duties",
        "job purpose", "role purpose", "you will be responsible",
    ])

    # Voice: JDs use second/third person, CVs use first person
    jd_voice_phrases = [
        "you will", "we are", "the candidate", "this role", "we need",
        "we offer", "you are", "you have", "the successful", "the role",
        "should have", "will be", "ability to", "strong knowledge",
        "years of experience", "degree in", "bachelor", "working knowledge",
        "proven track record", "excellent communication",
    ]
    cv_voice_phrases = [
        " i ", " my ", "managed ", "led ", "built ", "developed ",
        "achieved ", "delivered ", "spearheaded ", "oversaw ",
        "responsible for ", "contributed to ",
    ]

    jd_voice = sum(1 for p in jd_voice_phrases if p in lower)
    cv_voice = sum(1 for p in cv_voice_phrases if p in lower)

    jd_total = jd_hits + jd_voice
    cv_total = cv_hits + cv_voice

    # Structural signal: JDs often have one role title repeated,
    # CVs have multiple date ranges (YYYY patterns)
    import re
    date_count = len(re.findall(r'\b20[0-2]\d\b', lower))  # year mentions
    # Many dates (5+) = likely a CV with multiple roles
    if date_count >= 5:
        cv_total += 2

    if strong_jd:
        return "jd"
    if jd_total >= 3 and jd_total > cv_total:
        return "jd"
    if cv_total >= 3 and cv_total > jd_total:
        return "cv"
    if jd_total >= 2 and cv_total <= 1:
        return "jd"
    if cv_total >= 2 and jd_total <= 1:
        return "cv"
    # Tiebreaker: if similar counts but no personal pronouns (" i "), lean JD
    if jd_total >= 1 and " i " not in lower and " my " not in lower:
        return "jd"
    if jd_total >= 1 and cv_total == 0:
        return "jd"
    return "other"


def _extract_text(file_data: bytes, filename: str) -> str:
    """Extract text from PDF or DOCX bytes. Tries multiple libraries."""
    import io
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

    if ext == "pdf":
        # Try pdfminer first (most reliable for text extraction)
        try:
            import pdfminer.high_level as pdf_hl
            text = pdf_hl.extract_text(io.BytesIO(file_data))
            if text and text.strip():
                return text
        except Exception:
            pass

        # Try PyMuPDF (fitz)
        try:
            import fitz
            doc = fitz.open(stream=file_data, filetype="pdf")
            text = "\n".join(page.get_text() for page in doc)
            if text and text.strip():
                return text
        except Exception:
            pass

        # Try pdfplumber as last resort
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(file_data)) as pdf:
                text = "\n".join(page.extract_text() or "" for page in pdf.pages)
                if text and text.strip():
                    return text
        except Exception:
            pass

        raise HTTPException(status_code=422, detail="Failed to parse PDF file. Ensure it contains selectable text (not scanned images).")

    elif ext == "docx":
        try:
            import docx
            doc = docx.Document(io.BytesIO(file_data))
            return "\n".join(p.text for p in doc.paragraphs)
        except Exception:
            raise HTTPException(status_code=422, detail="Failed to parse DOCX file.")
    else:
        raise HTTPException(status_code=422, detail=f"Unsupported file type: .{ext}. Upload PDF or DOCX.")


def _extract_sections_for_anomaly(text: str) -> dict:
    """Extract experience and education entries from raw text for anomaly detection.

    Uses simple heuristics: date patterns (YYYY-MM, MM/YYYY) near title-like lines
    indicate experience entries. Lines containing 'university', 'degree', 'bachelor',
    'master', 'mba' indicate education.
    """
    import re
    lines = text.split("\n")
    experiences = []
    education = []

    # Date pattern: YYYY-MM, MM/YYYY, Month YYYY, YYYY – Present, etc.
    date_re = re.compile(r'(\d{4}[-/]\d{2}|\d{2}[-/]\d{4}|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{4}|\b\d{4}\b)')
    edu_re = re.compile(r'\b(university|bachelor|master|mba|phd|degree|diploma|bsc|msc|b\.?a\.?|m\.?a\.?)\b', re.IGNORECASE)

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        dates = date_re.findall(line)
        # If we find dates on a line, it's likely an experience or education entry
        if len(dates) >= 1:
            # Check if it's education
            context = " ".join(lines[max(0, i-1):min(len(lines), i+3)])
            if edu_re.search(context):
                education.append({
                    "title": line,
                    "start_date": dates[0] if dates else "",
                    "end_date": dates[1] if len(dates) > 1 else "",
                })
            else:
                # Treat as experience
                experiences.append({
                    "title": line,
                    "start_date": dates[0] if dates else "",
                    "end_date": dates[1] if len(dates) > 1 else "",
                })
        i += 1

    return {"experience": experiences, "education": education}


@router.post(
    "/ingest",
    status_code=status.HTTP_200_OK,
    response_model=IngestResponse,
    summary="Ingest and analyse a document",
    description=(
        "Upload a PDF or DOCX file. Returns document type classification "
        "(CV vs JD) and any anomaly flags detected via heuristic analysis."
    ),
)
async def ingest_file(
    x_user_id: CurrentUserId,
    file: UploadFile = File(
        ...,
        description="PDF or DOCX file to ingest and analyse.",
    ),
) -> IngestResponse:
    file_data = await file.read()
    if not file_data:
        raise HTTPException(status_code=422, detail="Empty file.")

    filename = file.filename or "untitled"
    text = _extract_text(file_data, filename)

    if not text.strip():
        raise HTTPException(status_code=422, detail="Could not extract text from file.")

    doc_type = _detect_document_type(text)

    # Build parsed structure for anomaly detection from extracted text
    parsed_data: dict = {}
    if doc_type == "cv":
        parsed_data = _extract_sections_for_anomaly(text)

    anomalies = detect_anomalies(parsed_data) if doc_type == "cv" else []

    file_id = str(uuid.uuid4())

    return IngestResponse(
        document_type=doc_type,
        anomaly_flags=anomalies,
        file_id=file_id,
    )
