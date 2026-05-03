"""
app/api/routes/profile_import.py

Profile auto-fill from CV or LinkedIn URL.

POST /api/v1/profiles/{profile_id}/import-cv
  — Takes a cv_id already uploaded, extracts text, sends to Claude,
    returns structured profile data (name, headline, experiences, skills).

POST /api/v1/profiles/{profile_id}/import-linkedin
  — Takes a LinkedIn URL, scrapes public profile via Serper,
    returns structured profile data.

POST /api/v1/profiles/{profile_id}/apply-import
  — Applies the extracted data to the profile (upserts experiences, sets headline etc.)
"""

import asyncio
import io
import json
import logging
import re
import uuid
from functools import partial

import anthropic
import boto3
import httpx
import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select

from app.config import settings, should_skip_anthropic_api
from app.dependencies import DB, CurrentUserId
from app.models.candidate_profile import (
    CandidateProfile,
    ExperienceEntry,
    ProfileStatus,
)
from app.models.cv import CV
from app.models.user import User

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["Profile Import"])

TIMEOUT = 15.0


def _demo_mode_active() -> bool:
    """True → skip Anthropic for profile extraction (see config.should_skip_anthropic_api)."""
    return should_skip_anthropic_api()


# ── Schemas ───────────────────────────────────────────────────────────────────

class ImportCVRequest(BaseModel):
    cv_id: str


class ImportLinkedInRequest(BaseModel):
    linkedin_url: str
    paste_text: str = ""  # Optional: user can paste raw LinkedIn profile text


def _coerce_str(v: any) -> str:
    """Accept str or list — join lists with newline."""
    if isinstance(v, list):
        return "\n".join(str(i) for i in v)
    return str(v) if v is not None else ""

class ImportedExperience(BaseModel):
    model_config = {"extra": "ignore"}
    role_title: str = ""
    company_name: str = ""
    start_date: str = ""
    end_date: str = ""
    location: str = ""
    context: str = ""
    contribution: str = ""
    outcomes: str = ""
    methods: str = ""
    hidden: str = ""
    freeform: str = ""

    @classmethod
    def model_validate(cls, obj: any, **kwargs):
        if isinstance(obj, dict):
            for field in ("context","contribution","outcomes","methods","hidden","freeform","role_title","company_name","location"):
                if field in obj and isinstance(obj[field], list):
                    obj[field] = "\n".join(str(i) for i in obj[field])
        return super().model_validate(obj, **kwargs)


class ImportedProfile(BaseModel):
    model_config = {"extra": "ignore"}
    full_name: str = ""
    headline: str = ""
    location: str = ""
    email: str = ""
    phone: str = ""
    nationality: str = ""
    linkedin_url: str = ""
    summary: str = ""
    skills: list[str] = []
    languages: list[str] = []
    education: list[dict] = []
    experiences: list[ImportedExperience] = []
    raw_source: str = ""  # "cv" | "linkedin"


class ApplyImportRequest(BaseModel):
    imported: ImportedProfile
    overwrite_existing: bool = False


def _demo_imported_profile_from_text(
    text: str,
    raw_source: str,
    *,
    linkedin_url: str = "",
) -> ImportedProfile:
    """
    When DEMO_MODE=true, skip Anthropic entirely (no API credits / billing).

    Heuristically splits parser-style CV text into sections and extracts:
    - full_name, headline, email, phone
    - skills (from labeled sections or inline keywords)
    - languages (from labeled section)
    - education (from EDUCATION section with year-range parsing)
    - experiences (from EXPERIENCE section with year-range parsing)

    For full AI parsing, set DEMO_MODE=false with Anthropic credits.
    """
    t = (text or "").strip()
    lines = [
        ln.strip() for ln in t.splitlines()
        if ln.strip()
    ]

    # ── 1. Split by === SECTION === markers ─────────────────
    section_pat = re.compile(
        r"^===\s*(.+?)\s*===$", re.MULTILINE,
    )
    named_sections: dict[str, str] = {}
    matches = list(section_pat.finditer(t))
    for i, m in enumerate(matches):
        name = m.group(1).strip().upper()
        start = m.end()
        end = (
            matches[i + 1].start()
            if i + 1 < len(matches)
            else len(t)
        )
        named_sections[name] = t[start:end].strip()

    # Fallback for PDFs: no === markers found.
    # Detect ALL-CAPS short lines as section headers.
    _hdr_keywords = {
        "SUMMARY", "PROFILE", "ABOUT", "OBJECTIVE",
        "SKILL", "COMPETENC", "EXPERTISE", "TECHNICAL",
        "LANGUAGE", "EDUCATION", "ACADEMIC", "TRAINING",
        "QUALIFICATION", "EXPERIENCE", "CAREER",
        "EMPLOYMENT", "HISTORY", "PROFESSIONAL",
        "INTEREST", "HOBBY", "CERTIF", "AWARD",
        "PUBLICATION", "REFERENCE", "CONTACT",
        "PERSONAL", "VOLUNTEER",
    }

    if not named_sections:
        caps_headers: list[tuple[int, str]] = []
        for i, ln in enumerate(lines):
            stripped = ln.strip()
            if not stripped or len(stripped) <= 2:
                continue
            if stripped != stripped.upper():
                continue
            words = stripped.split()
            if len(words) > 6:
                continue
            if stripped.startswith(("•", "-", "+")):
                continue
            if re.match(r"^\d{4}\s*[-–]", stripped):
                continue
            # Must contain a known section keyword
            # to avoid treating names as headers
            upper = stripped.upper()
            is_section = any(
                kw in upper for kw in _hdr_keywords
            )
            if not is_section:
                continue
            caps_headers.append((i, stripped))

        for idx, (li, hdr) in enumerate(caps_headers):
            end_li = (
                caps_headers[idx + 1][0]
                if idx + 1 < len(caps_headers)
                else len(lines)
            )
            body = "\n".join(
                lines[li + 1 : end_li],
            ).strip()
            named_sections[hdr.upper()] = body

        # If allcaps headers found, content before
        # the first header is the "preamble"
        if caps_headers and caps_headers[0][0] > 0:
            preamble_body = "\n".join(
                lines[: caps_headers[0][0]],
            ).strip()
            named_sections["PREAMBLE"] = preamble_body

    logger.info(
        "demo_parser_sections",
        section_names=list(named_sections.keys()),
        source=(
            "markers"
            if matches
            else "allcaps"
        ),
    )

    def _find_section(*keywords: str) -> str:
        """Fuzzy section lookup: return first section
        whose name contains any of the keywords."""
        for key in keywords:
            # Exact match first
            if key in named_sections:
                return named_sections[key]
            # Fuzzy: section name contains keyword
            for name, body in named_sections.items():
                if key in name:
                    return body
        return ""

    # ── 2. Extract name + headline ───────────────────────────────
    full_name = "Demo candidate"
    headline = ""
    email = ""
    phone = ""

    preamble = _find_section("PREAMBLE", "CONTACT")
    if preamble:
        preamble_lines = [
            ln.strip() for ln in preamble.splitlines()
            if ln.strip()
        ]
        for pl in preamble_lines:
            # Skip if it's the section name repeated
            if pl.upper() in (
                "PREAMBLE", "CONTACT", "PERSONAL",
            ):
                continue
            # First short non-email line is the name
            if (
                full_name == "Demo candidate"
                and "@" not in pl
                and len(pl) < 80
                and len(pl) > 2
                and not pl.startswith("+")
                and not pl.startswith("http")
            ):
                full_name = pl
                continue
            # Second line is headline (title/role)
            if (
                not headline
                and "@" not in pl
                and not pl.startswith("+")
                and not pl.startswith("http")
                and len(pl) < 200
            ):
                headline = pl[:240]
                continue
            # Extract email
            email_match = re.search(
                r"[\w.+-]+@[\w-]+\.[\w.]+", pl,
            )
            if email_match and not email:
                email = email_match.group(0)
            # Extract phone
            phone_match = re.search(
                r"\+[\d\s\-()]{7,20}", pl,
            )
            if phone_match and not phone:
                phone = phone_match.group(0).strip()
    else:
        # No preamble — use first lines
        for ln in lines[:5]:
            if ln.startswith("==="):
                continue
            if (
                full_name == "Demo candidate"
                and "@" not in ln
                and len(ln) < 80
                and len(ln) > 2
            ):
                full_name = ln
                break

    if not headline:
        headline = (
            f"{full_name} — Profile imported (demo mode)"
        )

    # ── 3. Extract summary ──────────────────────────────────
    summary_text = _find_section(
        "SUMMARY", "PROFILE", "ABOUT",
        "PROFESSIONAL SUMMARY", "EXECUTIVE SUMMARY",
    )
    # Strip the repeated word SUMMARY from the start
    summary_text = re.sub(
        r"^SUMMARY\s*", "", summary_text, flags=re.IGNORECASE,
    ).strip()
    if not summary_text:
        summary_text = (
            "Imported in demo mode. "
            "Set DEMO_MODE=false for AI-generated summary."
        )

    # ── 4. Extract skills ────────────────────────────────────────
    skills: list[str] = []
    tl = t.lower()

    # Check for a named SKILLS section first
    skills_section = _find_section(
        "SKILLS", "COMPETENC", "EXPERTISE",
        "TECHNICAL", "KEY SKILLS",
    )
    if skills_section:
        # Split by commas, bullets, semicolons, pipes, newlines
        raw_sk = re.split(
            r"[,;|•\n]| {2,}", skills_section,
        )
        skills = [
            s.strip()
            for s in raw_sk
            if 1 < len(s.strip()) < 80
        ][:50]

    # Fallback: scan raw text for skills-like blocks
    if not skills:
        # Look for === ... SKILL ... === markers in raw text
        sk_block_pat = re.compile(
            r"===\s*[^=]*(?:SKILL|COMPETENC|EXPERTISE)"
            r"[^=]*===\s*\n([\s\S]*?)(?=\n===|$)",
            re.IGNORECASE,
        )
        sk_m = sk_block_pat.search(t)
        if sk_m:
            raw_sk = re.split(
                r"[,;|•\n]| {2,}",
                sk_m.group(1),
            )
            skills = [
                s.strip()
                for s in raw_sk
                if 1 < len(s.strip()) < 80
            ][:50]

    # Fallback 2: look for inline "skills:" label
    if not skills:
        for label in (
            "skills:", "technical skills:",
            "core competencies:",
        ):
            idx = tl.find(label)
            if idx != -1:
                chunk = t[idx : idx + 800]
                first_line = chunk.split("\n")[0]
                rest = first_line.split(":", 1)[-1]
                raw_sk = re.split(
                    r"[,;|•]| {2,}", rest,
                )
                skills = [
                    s.strip()
                    for s in raw_sk
                    if 1 < len(s.strip()) < 80
                ][:50]
                if skills:
                    break

    # Fallback 3: extract key terms from summary
    if not skills and summary_text:
        _skill_terms = [
            "SaaS", "enterprise", "go-to-market",
            "sales", "strategy", "digital",
            "transformation", "M&A", "partnerships",
            "leadership", "operations", "analytics",
            "product", "engineering", "marketing",
            "finance", "consulting", "agile",
            "scrum", "cloud", "AI", "ML",
            "data", "blockchain", "fintech",
            "e-commerce", "logistics", "growth",
            "P&L", "fundraising", "venture",
        ]
        summary_lower = summary_text.lower()
        for term in _skill_terms:
            if term.lower() in summary_lower:
                skills.append(term)
        # Also extract from experience section
        exp_text_raw = _find_section(
            "EXPERIENCE", "CAREER", "PROFESSIONAL",
        )
        if exp_text_raw:
            exp_lower = exp_text_raw.lower()
            for term in _skill_terms:
                tl_term = term.lower()
                if (
                    tl_term in exp_lower
                    and term not in skills
                ):
                    skills.append(term)
        skills = skills[:30]

    # ── 5. Extract languages ─────────────────────────────────────
    languages: list[str] = []
    lang_section = _find_section("LANGUAGE")
    if lang_section:
        raw_langs = re.split(
            r"[,;•\n]| {2,}", lang_section,
        )
        languages = [
            ln.strip()
            for ln in raw_langs
            if 2 < len(ln.strip()) < 80
        ][:20]

    # Fallback: scan for === ... LANGUAGE ... === block
    if not languages:
        lang_block_pat = re.compile(
            r"===\s*[^=]*LANGUAGE[^=]*===\s*\n"
            r"([\s\S]*?)(?=\n===|$)",
            re.IGNORECASE,
        )
        lang_m = lang_block_pat.search(t)
        if lang_m:
            raw_langs = re.split(
                r"[,;•\n]| {2,}",
                lang_m.group(1),
            )
            languages = [
                ln.strip()
                for ln in raw_langs
                if 2 < len(ln.strip()) < 80
            ][:20]

    # Fallback 2: look for "languages:" inline
    if not languages:
        for label in ("languages:", "languages\n"):
            idx = tl.find(label)
            if idx != -1:
                chunk = t[idx : idx + 500]
                rest = (
                    chunk.split(":", 1)[-1]
                    .split("\n")[0]
                )
                raw_langs = re.split(
                    r"[,;|•]", rest,
                )
                languages = [
                    ln.strip()
                    for ln in raw_langs
                    if 2 < len(ln.strip()) < 60
                ][:20]
                if languages:
                    break

    # ── 6. Extract education ─────────────────────────────────────
    education: list[dict] = []
    edu_section = _find_section(
        "EDUCATION", "ACADEMIC", "QUALIFICATION",
        "DEGREE", "UNIVERSITY",
    )

    # Fallback: scan for === ... EDUCATION ... === block
    if not edu_section:
        edu_block_pat = re.compile(
            r"===\s*[^=]*(?:EDUCATION|ACADEMIC|"
            r"QUALIFICATION|DEGREE|UNIVERSIT)"
            r"[^=]*===\s*\n([\s\S]*?)(?=\n===|$)",
            re.IGNORECASE,
        )
        edu_m = edu_block_pat.search(t)
        if edu_m:
            edu_section = edu_m.group(1).strip()

    logger.info(
        "demo_parser_edu_section",
        has_edu=bool(edu_section),
        edu_len=len(edu_section) if edu_section else 0,
        edu_preview=(
            edu_section[:300] if edu_section else ""
        ),
    )

    if edu_section:
        # Remove repeated section header
        edu_text = re.sub(
            r"^(?:EDUCATION|ACADEMIC)\s*",
            "", edu_section,
            flags=re.IGNORECASE,
        ).strip()

        # Strip "Languages:" line from education text
        # (common at end of 1-page CVs)
        lang_inline = re.search(
            r"[Ll]anguages?\s*:\s*(.+)",
            edu_text,
        )
        if lang_inline:
            if not languages:
                raw_langs = re.split(
                    r"[,;•\n]| {2,}",
                    lang_inline.group(1),
                )
                languages = [
                    ln.strip()
                    for ln in raw_langs
                    if 2 < len(ln.strip()) < 80
                ][:20]
            # Always remove from education text
            edu_text = edu_text[
                : lang_inline.start()
            ].strip()
        edu_lines = [
            ln.strip()
            for ln in edu_text.splitlines()
            if ln.strip()
        ]

        year_pat = re.compile(
            r"((?:19|20)\d{2})\s*[-–—]\s*"
            r"((?:19|20)\d{2}|[Pp]resent|[Cc]urrent|[Nn]ow)"
            r"|(?:19|20)\d{2}",
        )

        i = 0
        while i < len(edu_lines):
            line = edu_lines[i]
            # Institution is typically the first line
            # (or a line with no year)
            institution = line
            degree = ""
            field = ""
            year = ""
            notes = ""

            # Look for year in this line or next lines
            ym = year_pat.search(line)
            if ym:
                year = ym.group(0)
                institution = year_pat.sub("", line).strip()
                institution = re.sub(
                    r"[\s,()]+$", "", institution,
                ).strip()

            # Next line(s) may have degree/field info
            j = i + 1
            while j < len(edu_lines):
                next_ln = edu_lines[j]
                # Stop at another institution-like line
                if j > i + 1:
                    # Has year range → new entry
                    if year_pat.search(next_ln):
                        break
                    # Mostly-caps line → new institution
                    # (e.g. "UNIVERSITA ... Italy")
                    nlu = next_ln.strip()
                    nlu_words = nlu.split()
                    caps_count = sum(
                        1 for w in nlu_words
                        if w == w.upper() and len(w) > 1
                    )
                    if (
                        len(nlu) > 5
                        and len(nlu_words) >= 2
                        and caps_count >= len(nlu_words) // 2
                    ):
                        break
                if not degree:
                    degree = next_ln
                    # Extract year from degree line if missing
                    if not year:
                        ym2 = year_pat.search(next_ln)
                        if ym2:
                            year = ym2.group(0)
                            degree = year_pat.sub(
                                "", next_ln,
                            ).strip()
                elif not field:
                    field = next_ln
                else:
                    notes += next_ln + " "
                j += 1
                # Don't consume more than 4 lines per entry
                if j - i > 4:
                    break

            if institution and institution.upper() != "EDUCATION":
                education.append({
                    "institution": institution[:200],
                    "degree": degree[:200],
                    "field": field[:200],
                    "year": year,
                    "notes": notes.strip()[:300],
                })

            i = j if j > i + 1 else i + 1

    logger.info(
        "demo_parser_edu_result",
        edu_count=len(education),
        edu_institutions=[
            e["institution"] for e in education
        ],
    )

    # ── 7. Extract experiences ───────────────────────────────────
    experiences: list[ImportedExperience] = []
    exp_section = _find_section(
        "EXPERIENCE", "CAREER", "EMPLOYMENT",
        "WORK HISTORY", "PROFESSIONAL",
    )
    logger.info(
        "demo_parser_exp_section",
        has_exp=bool(exp_section),
        exp_len=len(exp_section) if exp_section else 0,
    )

    if exp_section:
        # Remove repeated section header word
        exp_text = re.sub(
            r"^(?:PROFESSIONAL\s+)?EXPERIENCE\s*",
            "", exp_section,
            flags=re.IGNORECASE,
        ).strip()
        exp_lines = [
            ln.strip()
            for ln in exp_text.splitlines()
            if ln.strip()
        ]

        year_range_pat = re.compile(
            r"[\(\s]?((?:19|20)\d{2})\s*[-–—]\s*"
            r"((?:19|20)\d{2}|[Pp]resent|[Cc]urrent|[Nn]ow)"
            r"[\)\s]?",
        )

        # Bullet chars used in CVs
        _bullets = ("•", "-", "–", "·", "*", "◦", "●")

        def _is_bullet(line: str) -> bool:
            return line.startswith(_bullets)

        # Find date-range lines
        header_indices: list[int] = []
        for idx_l, ln in enumerate(exp_lines):
            if (
                year_range_pat.search(ln)
                and len(ln) < 200
                and not _is_bullet(ln)
            ):
                header_indices.append(idx_l)

        for idx, hi in enumerate(header_indices):
            header_line = exp_lines[hi]

            # Extract date range
            dm = year_range_pat.search(header_line)
            start_date = dm.group(1) if dm else ""
            end_date = dm.group(2) if dm else ""

            # Strip dates + parens to get residual
            residual = year_range_pat.sub(
                "", header_line,
            ).strip()
            residual = re.sub(
                r"^[\s|—–\-,()]+|[\s|—–\-,()]+$",
                "", residual,
            ).strip()

            # Scan BACKWARDS from date line to find
            # company (ALL-CAPS) and role (mixed-case).
            # PDF layout examples:
            #   COMPANY NAME        ← caps (hi-3)
            #   Role Title          ← mixed (hi-2)
            #   Subtitle            ← mixed (hi-1)
            #   Location, (dates)   ← date line (hi)
            # Or:
            #   COMPANY NAME        ← caps (hi-2)
            #   Role Title          ← mixed (hi-1)
            #   Location, (dates)   ← date line (hi)
            company = ""
            role = ""
            location = residual  # default: residual=loc

            # Determine scan-back boundary: previous
            # entry's date line or start of section
            prev_boundary = (
                header_indices[idx - 1]
                if idx > 0
                else -1
            )
            scan_lines: list[str] = []
            for back_i in range(hi - 1, prev_boundary, -1):
                cand = exp_lines[back_i].strip()
                if not cand:
                    break
                if _is_bullet(cand):
                    break
                if cand.startswith("==="):
                    break
                if back_i in header_indices:
                    break
                if year_range_pat.search(cand):
                    break
                scan_lines.insert(0, cand)
                # Don't scan more than 4 lines back
                if len(scan_lines) >= 4:
                    break

            # First mostly-caps line in scan = company
            # Remaining mixed-case lines = role parts
            role_parts: list[str] = []
            for sl in scan_lines:
                sl_words = sl.split()
                caps_w = sum(
                    1 for w in sl_words
                    if w == w.upper()
                    and len(w) > 1
                    and w not in ("–", "-", "&")
                )
                total_w = max(len(sl_words), 1)
                is_caps = (
                    caps_w >= total_w * 0.5
                    and len(sl) > 2
                )
                if is_caps and not company:
                    company = sl
                elif company:
                    # Lines after company = role/subtitle
                    role_parts.append(sl)
                else:
                    # Mixed-case before company found
                    # Could be role if company comes later
                    role_parts.append(sl)

            # If no caps company found but we have
            # scan_lines, first line is company
            if not company and scan_lines:
                company = scan_lines[0]
                role_parts = scan_lines[1:]

            # Use first role part as role title
            if role_parts and not role:
                role = role_parts[0]

            # If no company from scanning, split residual
            if not company and residual:
                loc_m = re.search(
                    r"[,]\s*([A-Za-z.\s]+)$",
                    residual,
                )
                if loc_m:
                    location = loc_m.group(1).strip()
                    company = residual[
                        : loc_m.start()
                    ].strip()
                else:
                    company = residual
                    location = ""

            # Fallback role: line after date-range header
            if not role:
                role_line_idx = hi + 1
                if role_line_idx < len(exp_lines):
                    cand = exp_lines[
                        role_line_idx
                    ].strip()
                    if (
                        cand
                        and len(cand) < 150
                        and not year_range_pat.search(cand)
                        and not cand.startswith("===")
                        and not _is_bullet(cand)
                        and role_line_idx
                        not in header_indices
                    ):
                        role = cand

            # Body: lines after date line until next
            # entry's scan-back zone.
            # If role came from AFTER date line, skip it.
            role_after = (
                role
                and role_parts == []
                and hi + 1 < len(exp_lines)
                and exp_lines[hi + 1].strip() == role
            )
            body_start = hi + (2 if role_after else 1)

            # End boundary: scan back from next entry's
            # date line to find where its block starts
            if idx + 1 < len(header_indices):
                nxt_hi = header_indices[idx + 1]
                body_end = nxt_hi
                # Exclude lines belonging to next entry
                # (company + role lines before its dates)
                for be in range(
                    nxt_hi - 1, hi, -1,
                ):
                    bel = exp_lines[be].strip()
                    if not bel:
                        break
                    if _is_bullet(bel):
                        break
                    if year_range_pat.search(bel):
                        break
                    if be in header_indices:
                        break
                    body_end = be
            else:
                body_end = len(exp_lines)

            body_lines = exp_lines[body_start:body_end]

            # Split body into bullets vs prose
            bullets: list[str] = []
            prose: list[str] = []
            for bl in body_lines:
                if _is_bullet(bl):
                    bullets.append(
                        bl.lstrip("•-–·*◦● ").strip(),
                    )
                elif bl.startswith("  "):
                    bullets.append(
                        bl.lstrip(" •●").strip(),
                    )
                else:
                    prose.append(bl)

            # Build structured fields from bullets
            contribution = "\n".join(
                bullets[:5],
            ) if bullets else "\n".join(prose[:3])
            outcomes = ""
            # Extract bullet points that contain numbers
            number_bullets = [
                b for b in bullets
                if re.search(r"\d+[%XxMmBbKk]|\$|€|£|\d{2,}", b)
            ]
            if number_bullets:
                outcomes = "\n".join(number_bullets[:5])

            freeform = "\n".join(
                body_lines,
            ).strip()[:6000]

            if freeform or role:
                experiences.append(
                    ImportedExperience(
                        role_title=(
                            role[:120]
                            if role
                            else "Role (demo extraction)"
                        ),
                        company_name=(
                            company[:120]
                            if company
                            else "Company"
                        ),
                        start_date=start_date,
                        end_date=end_date,
                        location=location,
                        context=(
                            "Demo mode extraction. "
                            "Set DEMO_MODE=false for "
                            "full AI analysis."
                        ),
                        contribution=contribution[:2000],
                        outcomes=outcomes[:2000],
                        methods="",
                        hidden="",
                        freeform=freeform,
                    )
                )

    # Fallback: if no === EXPERIENCE === section, try raw year-range detection
    if not experiences:
        year_range_pat = re.compile(
            r"[\(\s]?((?:19|20)\d{2})\s*[-–—]\s*"
            r"((?:19|20)\d{2}|[Pp]resent|[Cc]urrent|[Nn]ow)"
            r"[\)\s]?",
        )
        header_indices: list[int] = []
        for i, ln in enumerate(lines):
            if year_range_pat.search(ln) and len(ln) < 200:
                header_indices.append(i)

        if header_indices:
            for idx, hi in enumerate(header_indices):
                header_line = lines[hi]
                dm = year_range_pat.search(header_line)
                start_date = dm.group(1) if dm else ""
                end_date = dm.group(2) if dm else ""
                company = year_range_pat.sub(
                    "", header_line,
                ).strip()
                company = re.sub(
                    r"^[\s|—–\-,]+|[\s|—–\-,()]+$",
                    "", company,
                ).strip()

                role = ""
                role_idx = hi + 1
                if role_idx < len(lines):
                    c = lines[role_idx].strip()
                    if (
                        c and len(c) < 100
                        and not year_range_pat.search(c)
                        and not c.startswith("===")
                        and role_idx not in header_indices
                    ):
                        role = c

                body_start = hi + (2 if role else 1)
                body_end = (
                    header_indices[idx + 1]
                    if idx + 1 < len(header_indices)
                    else len(lines)
                )
                body = "\n".join(
                    lines[body_start:body_end],
                ).strip()[:6000]

                if body or role:
                    experiences.append(
                        ImportedExperience(
                            role_title=(
                                role[:120]
                                if role
                                else "Role (demo extraction)"
                            ),
                            company_name=(
                                company[:120]
                                if company
                                else "Company"
                            ),
                            start_date=start_date,
                            end_date=end_date,
                            location="",
                            context=(
                                "Demo mode extraction."
                            ),
                            contribution="",
                            outcomes="",
                            methods="",
                            hidden="",
                            freeform=body,
                        )
                    )

    # Ultimate fallback — one blob
    if not experiences:
        snippet = t[:12000] if len(t) > 12000 else t
        experiences = [
            ImportedExperience(
                role_title="Full document (demo mode)",
                company_name="Local extraction",
                start_date="",
                end_date="Present",
                location="",
                context=(
                    "DEMO_MODE=true: could not split "
                    "into individual roles."
                ),
                contribution="",
                outcomes="",
                methods="",
                hidden="",
                freeform=snippet,
            )
        ]

    logger.info(
        "demo_parser_result",
        name=full_name,
        skills_count=len(skills),
        langs_count=len(languages),
        edu_count=len(education),
        exp_count=len(experiences),
        exp_companies=[
            e.company_name for e in experiences
        ],
    )

    return ImportedProfile(
        full_name=full_name,
        headline=headline,
        location="",
        email=email,
        phone=phone,
        nationality="",
        linkedin_url=linkedin_url or "",
        summary=summary_text[:4000],
        skills=skills,
        languages=languages,
        education=education,
        experiences=experiences,
        raw_source=raw_source,
    )


# ── CV text extraction ────────────────────────────────────────────────────────

def _cv_to_text(parsed_content: dict) -> str:
    """
    Convert parsed CV JSONB into plain text for Claude.
    Uses sections if available, falls back to raw_paragraphs.
    Preserves ALL text — no truncation here.
    """
    lines = []

    sections = parsed_content.get("sections", [])
    if sections:
        for section in sections:
            heading = section.get("heading", "")
            if heading:
                lines.append(f"\n=== {heading.upper()} ===")
            for para in section.get("paragraphs", []):
                text = para.get("text", "").strip()
                if not text:
                    continue
                # Detect bullet-like paragraphs by style or leading chars
                style = para.get("style", "")
                is_bullet = (
                    "list" in style.lower() or
                    "bullet" in style.lower() or
                    text.startswith(("•", "-", "–", "·", "*", "◦", "▪"))
                )
                lines.append(f"  • {text}" if is_bullet else text)
    else:
        # Fallback: use raw flat paragraphs
        for para in parsed_content.get("raw_paragraphs", []):
            text = para.get("text", "").strip()
            if text:
                lines.append(text)

    result = "\n".join(lines)
    # Log how much text we got
    logging.getLogger(__name__).info(f"cv_to_text extracted {len(result)} chars from {len(sections)} sections")
    return result


def _call_claude_for_profile(
    prompt: str, max_tokens: int = 5000, timeout: float = 120.0
) -> ImportedProfile | None:
    """
    Shared helper: call Claude API for profile extraction, parse JSON, return ImportedProfile.

    Args:
        prompt: The full Claude prompt (instructions + JSON schema + content)
        max_tokens: Max tokens for Claude response (default 5000)
        timeout: Timeout for API call in seconds (default 120.0)

    Returns:
        ImportedProfile on success, None on error (errors logged and HTTPException raised)
    """
    if _demo_mode_active():
        logger.warning(
            "claude_profile_skipped_demo_mode",
            hint="Extraction should use _demo_imported_profile_from_text before calling this",
        )
        raise HTTPException(
            status_code=500,
            detail="DEMO_MODE is on: profile extraction must not call Anthropic. Restart the API after changing DEMO_MODE.",
        )

    if not settings.anthropic_api_key or settings.anthropic_api_key == "PASTE_YOUR_ANTHROPIC_KEY_HERE":
        raise HTTPException(
            status_code=501,
            detail="Anthropic API key not configured. Set ANTHROPIC_API_KEY in environment.",
        )

    try:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key, timeout=timeout)
        logger.info("claude_call_start", max_tokens=max_tokens)

        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        logger.info("claude_call_done")

        # Strip markdown fences
        raw = resp.content[0].text.strip()
        raw = re.sub(r'^```json\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)

        # Parse JSON
        data = json.loads(raw)

        # Build ImportedProfile from parsed data
        experiences = [ImportedExperience(**e) for e in data.get("experiences", [])]
        return ImportedProfile(
            full_name=data.get("full_name", ""),
            headline=data.get("headline", ""),
            location=data.get("location", ""),
            email=data.get("email", ""),
            phone=data.get("phone", ""),
            nationality=data.get("nationality", ""),
            linkedin_url=data.get("linkedin_url", ""),
            summary=data.get("summary", ""),
            skills=data.get("skills", []),
            languages=data.get("languages", []),
            education=data.get("education", []),
            experiences=experiences,
            raw_source="",  # Caller will set this
        )
    except json.JSONDecodeError as e:
        logger.error("profile_parse_json_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to parse Claude response as JSON")
    except TimeoutError:
        logger.error("profile_parse_timeout")
        raise HTTPException(status_code=504, detail="Profile extraction timed out — try again or use shorter input")
    except Exception as e:
        import traceback
        logger.error("profile_parse_error", error=str(e), tb=traceback.format_exc()[-500:])
        raise HTTPException(status_code=500, detail=f"Profile extraction failed: {str(e)}")


def _extract_profile_with_claude(cv_text: str) -> ImportedProfile:
    """Send CV text to Claude, get back structured profile JSON."""
    if _demo_mode_active():
        logger.info(
            "demo_cv_raw_text_preview",
            text_len=len(cv_text),
            first_2000=cv_text[:2000],
        )
        p = _demo_imported_profile_from_text(cv_text, "cv")
        logger.info(
            "extract_cv_demo_mode",
            experiences=len(p.experiences),
        )
        return p

    prompt = f"""You are an expert CV parser and career analyst. Your job is to extract EVERYTHING from this CV — leave nothing out.

CV TEXT (full document — extract EVERYTHING, do not skip any section):
{cv_text[:20000]}

Return ONLY a valid JSON object. No markdown fences, no preamble, no explanation. Just the JSON.

{{
  "full_name": "Full legal name",
  "headline": "Craft a sharp 1-line professional headline — e.g. 'CFO | Series A–C Fintech | MENA & Europe | $500M+ P&L'",
  "location": "Current city and country",
  "email": "email address or empty string",
  "phone": "phone number or empty string",
  "linkedin_url": "LinkedIn URL or empty string",
  "nationality": "nationality if mentioned",
  "summary": "Write a 3–5 sentence professional summary capturing who they are, what they've built, and what makes them distinctive. Infer from the whole CV if no summary section exists.",
  "skills": ["Every technical skill, tool, methodology, and competency mentioned — aim for 15-30 items"],
  "languages": ["Language (proficiency level)", "..."],
  "education": [
    {{"institution": "University/school name", "degree": "BSc/MBA/etc", "field": "subject", "year": "graduation year", "notes": "any honours, thesis, or notable detail"}}
  ],
  "experiences": [
    {{
      "role_title": "Exact job title as written",
      "company_name": "Exact company name",
      "start_date": "YYYY-MM or YYYY",
      "end_date": "YYYY-MM or Present",
      "location": "City, Country",
      "context": "DETAILED: What was the company stage, size, revenue, team size, sector? What was the situation/challenge when they joined? What did they inherit?",
      "contribution": "DETAILED: What did THIS PERSON specifically own and drive — not the team, not the company. Their exact decisions, initiatives, workstreams. Be specific.",
      "outcomes": "DETAILED: Quantified results — revenue grown, cost saved, headcount scaled, valuations achieved, time to market, customer numbers. Extract every number from bullet points.",
      "methods": "DETAILED: How did they do it — frameworks, tools, partners, approaches, management style.",
      "hidden": "What is impressive about this role that a plain CV reading might miss? Infer from context, scale, complexity.",
      "freeform": "Any other relevant detail: board relationships, equity, awards, press mentions, context about why they left."
    }}
  ]
}}

CRITICAL RULES:
- Extract EVERY job listed, even short stints and early-career roles — do NOT skip any
- For each experience: get the EXACT title, EXACT company name, EXACT dates as written
- For outcomes: pull out EVERY number, percentage, and metric mentioned
- For skills: include sector knowledge, functional expertise, tools/frameworks — aim for 20+ items
- For education: extract EVERY degree, certification, course — include institution, degree type, field, year, and any honours/GPA/thesis
- For languages: extract ALL languages mentioned with proficiency levels
- For summary: write it as if you're a headhunter briefing a client — make it compelling
- If a field genuinely has no data, use empty string — do NOT omit the field
- Reverse chronological order for experiences (most recent first)
- DO NOT merge or skip any experiences — if the CV lists 8 jobs, return 8 experiences
- DO NOT truncate education — if there are 3 degrees, return all 3"""

    # Call shared helper
    profile = _call_claude_for_profile(prompt, max_tokens=5000, timeout=120.0)
    if profile:
        profile.raw_source = "cv"
        logger.info("extract_cv_done", experiences=len(profile.experiences))
    return profile


# ── LinkedIn scraping ─────────────────────────────────────────────────────────

def _scrape_linkedin_via_serper(linkedin_url: str) -> str:
    """
    Multi-source LinkedIn profile scraper.
    1. Try to fetch the LinkedIn page directly (often works for public profiles)
    2. Use Serper Google search for snippets
    3. Use Serper News for any press mentions
    Combines all sources for maximum coverage.
    """
    profile_slug = linkedin_url.rstrip("/").split("/in/")[-1].split("/")[0].split("?")[0]
    text_parts = [f"LinkedIn Profile: {linkedin_url}", f"Profile slug: {profile_slug}"]

    # Source 1: Direct HTTP fetch of LinkedIn page (works for some public profiles)
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        }
        r = httpx.get(linkedin_url, headers=headers, timeout=8.0, follow_redirects=True)
        if r.status_code == 200 and len(r.text) > 500:
            html = r.text
            # Strip scripts/styles
            html = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL|re.IGNORECASE)
            # Extract text
            text = re.sub(r"<[^>]+>", " ", html)
            text = re.sub(r"[ \t]+", " ", text)
            text = re.sub(r"\n{3,}", "\n\n", text)
            text_parts.append("=== LINKEDIN PAGE CONTENT ===")
            text_parts.append(text.strip()[:5000])
    except Exception as e:
        logger.debug("linkedin_direct_fetch_failed", error=str(e))

    if not settings.serper_api_key:
        return "\n".join(text_parts)

    # Source 2: Google search for LinkedIn profile
    queries = [
        f'site:linkedin.com "{profile_slug}"',
        f'linkedin.com/in/{profile_slug} experience background',
        f'"{profile_slug.replace("-", " ")}" linkedin executive career',
    ]
    try:
        for q in queries:
            r = httpx.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": settings.serper_api_key, "Content-Type": "application/json"},
                json={"q": q, "num": 8},
                timeout=TIMEOUT,
            )
            r.raise_for_status()
            for item in r.json().get("organic", []):
                title = item.get("title", "")
                snippet = item.get("snippet", "")
                if title or snippet:
                    text_parts.append(f"Search result: {title}")
                    text_parts.append(snippet)
    except Exception as e:
        logger.warning("linkedin_serper_error", error=str(e))

    # Source 3: News mentions of the person
    try:
        name_guess = profile_slug.replace("-", " ").title()
        news_q = f'"{name_guess}" executive career appointment'
        r = httpx.post(
            "https://google.serper.dev/news",
            headers={"X-API-KEY": settings.serper_api_key, "Content-Type": "application/json"},
            json={"q": news_q, "num": 5},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        for item in r.json().get("news", []):
            text_parts.append(f"News: {item.get('title', '')} — {item.get('snippet', '')}")
    except Exception as e:
        logger.debug("linkedin_news_error", error=str(e))

    result = "\n".join(text_parts)
    logger.info("linkedin_scrape_done", chars=len(result), sources=len(text_parts))
    return result


def _extract_profile_from_linkedin(linkedin_url: str, scraped_text: str) -> ImportedProfile:
    """Send scraped LinkedIn data to Claude for structuring."""
    if _demo_mode_active():
        p = _demo_imported_profile_from_text(
            scraped_text, "linkedin", linkedin_url=linkedin_url
        )
        logger.info("extract_linkedin_demo_mode", experiences=len(p.experiences))
        return p

    prompt = f"""You are an expert LinkedIn profile analyst and career researcher. Extract EVERYTHING from this LinkedIn profile data.

LINKEDIN URL: {linkedin_url}
PROFILE DATA:
{scraped_text[:10000]}

The data above may come from: direct page scrape, Google search snippets, news articles, and other public sources.
Extract the most complete profile possible from all available data.

Return ONLY a valid JSON object. No markdown, no preamble. Just JSON.

{{
  "full_name": "Full name",
  "headline": "Craft a sharp 1-line professional headline from their experience — e.g. 'COO | MENA Scale-ups | $200M P&L'",
  "location": "City, Country",
  "email": "",
  "phone": "",
  "linkedin_url": "{linkedin_url}",
  "nationality": "",
  "summary": "Write a 3–5 sentence professional summary from what you know. Make it compelling for a senior executive audience.",
  "skills": ["List every professional skill, domain expertise, tool or competency you can infer — aim for 15-20"],
  "languages": ["Language (level)"],
  "education": [{{"institution": "", "degree": "", "field": "", "year": "", "notes": ""}}],
  "experiences": [
    {{
      "role_title": "Exact title",
      "company_name": "Company name",
      "start_date": "YYYY-MM or YYYY",
      "end_date": "YYYY-MM or Present",
      "location": "City, Country",
      "context": "Company stage, size, sector context when they joined",
      "contribution": "What they specifically owned and drove in this role",
      "outcomes": "Any numbers, metrics, achievements mentioned or inferable",
      "methods": "How they operated — management style, frameworks, approaches",
      "hidden": "What is impressive or notable about this role that stands out",
      "freeform": "Additional context from LinkedIn description, any notable detail"
    }}
  ]
}}

RULES:
- Extract ALL positions listed, even brief ones
- Infer skills from their roles and sectors even if not explicitly listed
- For experiences with LinkedIn descriptions, put the full description in freeform
- If data is limited, still construct the best possible profile from what's available
- Reverse chronological order"""

    # Call shared helper
    profile = _call_claude_for_profile(prompt, max_tokens=4000, timeout=60.0)
    if profile:
        profile.raw_source = "linkedin"
        # Ensure linkedin_url is set from the parameter (not from Claude response)
        profile.linkedin_url = linkedin_url
        logger.info("extract_linkedin_done", experiences=len(profile.experiences))
    return profile



def _extract_text_from_bytes(file_bytes: bytes, filename: str) -> str:
    """Extract plain text from a DOCX or PDF file bytes."""
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

    if ext == "docx":
        # Optional: imported at call site because python-docx may not be installed
        from docx import Document
        from docx.text.paragraph import Paragraph as _Para
        doc = Document(io.BytesIO(file_bytes))
        # Walk full XML to catch text in tables, text boxes, etc.
        seen, paras = set(), []
        for child in doc.element.body.iter():
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if tag == "p":
                try:
                    p = _Para(child, doc)
                    pid = id(p._element)
                    if pid not in seen:
                        seen.add(pid)
                        paras.append(p)
                except Exception:
                    pass
        lines = [p.text.strip() for p in paras if p.text.strip()]
        return "\n".join(lines)

    elif ext == "pdf":
        try:
            # Optional: imported at call site because pdfminer may not be installed
            import pdfminer.high_level as _pdf
            text = _pdf.extract_text(io.BytesIO(file_bytes))
            return text or ""
        except ImportError:
            pass
        try:
            # Optional: imported at call site because PyMuPDF may not be installed
            import fitz
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            return "\n".join(page.get_text() for page in doc)
        except ImportError:
            pass
        raise HTTPException(status_code=400, detail="PDF parsing not available — please upload a .docx file")

    raise HTTPException(status_code=400, detail=f"Unsupported file type: .{ext}. Please upload .docx or .pdf")


# ── Routes ────────────────────────────────────────────────────────────────────


@router.get("/api/v1/debug/cv-text/{cv_id}")
async def debug_cv_text(
    cv_id: str,
    db: DB,
    current_user_id: CurrentUserId,
) -> dict:
    """DEBUG: dump raw cv_text for a CV. Remove later."""
    result = await db.execute(
        select(CV).where(
            CV.id == uuid.UUID(cv_id),
            CV.user_id == str(current_user_id),
        )
    )
    cv = result.scalar_one_or_none()
    if not cv:
        raise HTTPException(404, "CV not found")
    if not cv.parsed_content:
        return {"error": "not parsed yet"}
    text = _cv_to_text(cv.parsed_content)
    return {
        "cv_id": cv_id,
        "text_len": len(text),
        "text": text[:5000],
    }


@router.post("/api/v1/profiles/{profile_id}/import-cv")
async def import_from_cv(
    profile_id: uuid.UUID,
    payload: ImportCVRequest,
    db: DB,
    current_user_id: CurrentUserId,
) -> ImportedProfile:
    """Extract profile data from an uploaded CV using Claude.
    Reads raw file bytes directly from S3 — no need to wait for Celery parsing.
    Works immediately after upload.
    """
    result = await db.execute(
        select(CV).where(CV.id == uuid.UUID(payload.cv_id), CV.user_id == str(current_user_id))
    )
    cv = result.scalar_one_or_none()
    if not cv:
        raise HTTPException(status_code=404, detail="CV not found")

    logger.info("import_cv_start", cv_id=payload.cv_id)

    # Path 1: Celery already parsed it — use stored structured text (fast)
    cv_text = ""
    if cv.parsed_content:
        cv_text = _cv_to_text(cv.parsed_content)

    # Path 2: Not yet parsed — read raw bytes from S3 and extract text directly
    if not cv_text.strip():
        try:
            s3 = boto3.client(
                "s3",
                endpoint_url=settings.s3_endpoint_url,
                aws_access_key_id=settings.s3_access_key_id,
                aws_secret_access_key=settings.s3_secret_access_key,
                region_name=settings.s3_region,
            )
            loop = asyncio.get_running_loop()
            obj = await loop.run_in_executor(
                None, lambda: s3.get_object(Bucket=cv.s3_bucket, Key=cv.s3_key)
            )
            file_bytes = obj["Body"].read()
            cv_text = _extract_text_from_bytes(file_bytes, cv.original_filename)
            logger.info("import_cv_read_from_s3_direct", bytes=len(file_bytes), text_chars=len(cv_text))
        except HTTPException:
            raise
        except Exception as e:
            logger.error("import_cv_s3_read_failed", error=str(e))
            raise HTTPException(status_code=500, detail=f"Could not read CV file: {str(e)}")

    if not cv_text.strip():
        raise HTTPException(status_code=400, detail="Could not extract text from CV — ensure it is a valid .docx or .pdf")

    loop = asyncio.get_running_loop()
    imported = await loop.run_in_executor(None, partial(_extract_profile_with_claude, cv_text))
    logger.info("import_cv_done", experiences=len(imported.experiences))
    return imported


@router.post("/api/v1/profiles/{profile_id}/import-linkedin")
async def import_from_linkedin(
    profile_id: uuid.UUID,
    payload: ImportLinkedInRequest,
    db: DB,
    current_user_id: CurrentUserId,
) -> dict:
    """Extract profile data from a LinkedIn URL."""
    has_url = "linkedin.com" in payload.linkedin_url
    has_paste = len(payload.paste_text.strip()) > 50
    if not has_url and not has_paste:
        raise HTTPException(status_code=400, detail="Provide a LinkedIn URL or paste your profile text")

    logger.info("import_linkedin_start", url=payload.linkedin_url)

    loop = asyncio.get_running_loop()
    # If user pasted their profile text, use that (much richer than scraping)
    if payload.paste_text and len(payload.paste_text.strip()) > 100:
        source_text = f"LinkedIn URL: {payload.linkedin_url}\n\n=== PASTED PROFILE TEXT ===\n{payload.paste_text[:8000]}"
        logger.info("import_linkedin_using_paste", chars=len(payload.paste_text))
    else:
        source_text = await loop.run_in_executor(
            None, partial(_scrape_linkedin_via_serper, payload.linkedin_url)
        )

    imported = await loop.run_in_executor(
        None, partial(_extract_profile_from_linkedin, payload.linkedin_url, source_text)
    )

    logger.info("import_linkedin_done", experiences=len(imported.experiences))

    # Quality check: flag empty experiences
    result = json.loads(imported.model_dump_json())

    empty_experiences = sum(
        1 for exp in imported.experiences
        if not exp.role_title.strip() and not exp.company_name.strip()
    )
    total_experiences = len(imported.experiences)

    warnings = []
    warnings.append(
        "LinkedIn import uses public data which may be inaccurate or belong to a "
        "different person with a similar name. Please review all fields before applying."
    )
    if empty_experiences > 0:
        warnings.append(
            f"{empty_experiences} of {total_experiences} experience entries have missing "
            f"titles or companies. LinkedIn's public page may not expose full career data. "
            f"Consider pasting your LinkedIn profile text directly for better results."
        )
    if total_experiences == 0:
        warnings.append(
            "No experiences were extracted. Try pasting your LinkedIn profile text "
            "in the paste_text field for better extraction."
        )

    # Filter out empty or placeholder experiences
    def _is_real_experience(exp: dict) -> bool:
        title = (exp.get("role_title") or "").strip()
        company = (exp.get("company_name") or "").strip()
        # Must have at least one meaningful field (> 2 chars, not a placeholder)
        placeholders = {"", "?", "n/a", "unknown", "none", "-", "...", "tbd"}
        title_valid = len(title) > 2 and title.lower() not in placeholders
        company_valid = len(company) > 2 and company.lower() not in placeholders
        return title_valid or company_valid

    result["experiences"] = [
        exp for exp in result.get("experiences", [])
        if _is_real_experience(exp)
    ]

    result["_warnings"] = warnings
    result["_verification_needed"] = True
    result["_extraction_quality"] = "good" if empty_experiences == 0 and total_experiences > 0 else "partial" if total_experiences > 0 else "poor"

    return result


@router.post("/api/v1/profiles/{profile_id}/apply-import")
async def apply_import(
    profile_id: uuid.UUID,
    payload: ApplyImportRequest,
    db: DB,
    current_user_id: CurrentUserId,
) -> dict:
    """
    Apply imported profile data to an existing profile.
    Upserts experiences, updates headline/summary/skills.
    """
    imp = payload.imported

    # Load profile
    result = await db.execute(
        select(CandidateProfile).where(
            CandidateProfile.id == profile_id,
            CandidateProfile.user_id == str(current_user_id),
        )
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    # Update profile-level fields. NOTE: location lives inside global_context
    # below — there is no DB column for it on CandidateProfile.
    if imp.headline:
        profile.headline = imp.headline

    # Mark profile as active once we have real data
    if imp.experiences or imp.headline:
        profile.status = ProfileStatus.ACTIVE

    # Store skills, languages, education, summary in global_context
    try:
        ctx = json.loads(profile.global_context or "{}")
    except Exception:
        ctx = {}

    if imp.summary:
        ctx["summary"] = imp.summary
    if imp.skills:
        ctx["skills"] = imp.skills
    if imp.languages:
        ctx["languages"] = imp.languages
    if imp.full_name:
        ctx["full_name"] = imp.full_name
    if imp.location:
        ctx["location"] = imp.location
    if imp.linkedin_url:
        ctx["linkedin_url"] = imp.linkedin_url
    if imp.email:
        ctx["email"] = imp.email
    if imp.phone:
        ctx["phone"] = imp.phone
    if imp.nationality:
        ctx["nationality"] = imp.nationality
    if imp.education:
        ctx["education"] = [e if isinstance(e, dict) else e.model_dump() for e in imp.education]

    profile.global_context = json.dumps(ctx)

    # Update user full_name if we have it
    if imp.full_name:
        user_result = await db.execute(
            select(User).where(User.id == uuid.UUID(current_user_id))
        )
        user = user_result.scalar_one_or_none()
        if user and not user.full_name:
            user.full_name = imp.full_name

    # Upsert experiences
    experiences_added = 0
    if payload.overwrite_existing:
        # Delete existing experiences
        await db.execute(
            delete(ExperienceEntry).where(ExperienceEntry.profile_id == profile_id)
        )

    for i, exp in enumerate(imp.experiences):
        entry = ExperienceEntry(
            id=uuid.uuid4(),
            profile_id=profile_id,
            company_name=exp.company_name,
            role_title=exp.role_title,
            start_date=exp.start_date or None,
            end_date=exp.end_date or None,
            location=exp.location or None,
            context=exp.context or None,
            contribution=exp.contribution or None,
            outcomes=exp.outcomes or None,
            methods=exp.methods or None,
            hidden=exp.hidden or None,
            freeform=exp.freeform or None,
            display_order=i,
        )
        db.add(entry)
        experiences_added += 1

    # Request-scope session commits in app/db/session.py:get_db_session.
    await db.flush()

    logger.info("apply_import_done", experiences_added=experiences_added)
    return {
        "success": True,
        "experiences_added": experiences_added,
        "headline_set": bool(imp.headline),
        "profile_id": str(profile_id),
    }
