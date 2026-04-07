"""
app/services/cv/fraud_detection.py

CV/JD fraud detection and quality validation.

Detects:
  - Fake CVs (inconsistent data, impossible claims)
  - Timeline inconsistencies (overlapping dates, gaps)
  - Missing critical data
  - Suspicious patterns (too-perfect formatting, templated text)

Rule-based — zero LLM cost. Returns a trust score + list of flags.
"""

import re
from datetime import datetime
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


def validate_cv(parsed_content: dict) -> dict:
    """
    Run fraud detection on parsed CV content.

    Returns:
        {
            "trust_score": 0-100,
            "flags": [{"severity": "high|medium|low", "type": "...", "detail": "..."}],
            "is_suspicious": bool,
            "timeline_valid": bool,
            "data_completeness": float,
        }
    """
    flags = []
    sections = parsed_content.get("sections", [])
    raw_paragraphs = parsed_content.get("raw_paragraphs", [])
    total_words = parsed_content.get("total_words", 0)

    # ── Data completeness ─────────────────────────────────────────────────
    completeness = _check_completeness(sections, raw_paragraphs, total_words)
    flags.extend(completeness["flags"])

    # ── Timeline consistency ──────────────────────────────────────────────
    timeline = _check_timeline(sections, raw_paragraphs)
    flags.extend(timeline["flags"])

    # ── Suspicious patterns ───────────────────────────────────────────────
    patterns = _check_suspicious_patterns(sections, raw_paragraphs, total_words)
    flags.extend(patterns["flags"])

    # ── Compute trust score ───────────────────────────────────────────────
    high_flags = sum(1 for f in flags if f["severity"] == "high")
    medium_flags = sum(1 for f in flags if f["severity"] == "medium")
    low_flags = sum(1 for f in flags if f["severity"] == "low")

    trust_score = 100 - (high_flags * 20) - (medium_flags * 8) - (low_flags * 3)
    trust_score = max(0, min(100, trust_score))

    return {
        "trust_score": trust_score,
        "flags": flags,
        "is_suspicious": trust_score < 50 or high_flags > 0,
        "timeline_valid": not any(f["type"] == "timeline_overlap" for f in flags),
        "data_completeness": completeness["score"],
    }


def _check_completeness(sections: list, paragraphs: list, total_words: int) -> dict:
    """Check if CV has required content."""
    flags = []
    score = 0.0

    # Has enough content?
    if total_words < 50:
        flags.append({"severity": "high", "type": "too_short", "detail": f"CV has only {total_words} words — suspiciously short"})
    elif total_words < 150:
        flags.append({"severity": "medium", "type": "short", "detail": f"CV has only {total_words} words — may be incomplete"})
    else:
        score += 0.3

    # Has section headings?
    headings = [s.get("heading", "").lower() for s in sections if s.get("heading")]
    expected = ["experience", "education", "skills"]
    found = sum(1 for exp in expected if any(exp in h for h in headings))
    if found == 0:
        flags.append({"severity": "medium", "type": "no_sections", "detail": "No standard CV sections detected (Experience, Education, Skills)"})
    else:
        score += found * 0.15

    # Has contact info? (look for email/phone patterns in raw text)
    all_text = " ".join(p.get("text", "") for p in paragraphs)
    has_email = bool(re.search(r'[\w.+-]+@[\w-]+\.[\w.]+', all_text))
    has_phone = bool(re.search(r'[\+\(]?[\d\s\-\(\)]{7,}', all_text))
    if not has_email and not has_phone:
        flags.append({"severity": "low", "type": "no_contact", "detail": "No contact information detected"})
    else:
        score += 0.2

    score = min(1.0, score)
    return {"score": round(score, 2), "flags": flags}


def _check_timeline(sections: list, paragraphs: list) -> dict:
    """Check for timeline inconsistencies."""
    flags = []
    all_text = " ".join(p.get("text", "") for p in paragraphs)

    # Extract year ranges (e.g., "2018 - 2021", "Jan 2019 – Present")
    date_ranges = re.findall(
        r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)?\s*\d{4})\s*[-–—]\s*((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)?\s*\d{4}|[Pp]resent|[Cc]urrent)',
        all_text,
    )

    if not date_ranges:
        return {"flags": flags}

    # Parse and check for overlaps
    ranges = []
    for start_str, end_str in date_ranges:
        start_year = _extract_year(start_str)
        end_year = _extract_year(end_str) if end_str.lower() not in ("present", "current") else datetime.now().year
        if start_year and end_year:
            ranges.append((start_year, end_year, f"{start_str} - {end_str}"))

    # Sort by start year
    ranges.sort(key=lambda x: x[0])

    # Check for overlaps
    for i in range(len(ranges) - 1):
        if ranges[i][1] > ranges[i + 1][0] + 1:  # Allow 1 year overlap (transition)
            flags.append({
                "severity": "medium",
                "type": "timeline_overlap",
                "detail": f"Dates overlap: {ranges[i][2]} and {ranges[i+1][2]}",
            })

    # Check for large gaps (>3 years)
    for i in range(len(ranges) - 1):
        gap = ranges[i + 1][0] - ranges[i][1]
        if gap > 3:
            flags.append({
                "severity": "low",
                "type": "timeline_gap",
                "detail": f"{gap}-year gap between {ranges[i][2]} and {ranges[i+1][2]}",
            })

    # Check for future dates
    current_year = datetime.now().year
    for start, end, label in ranges:
        if start > current_year + 1:
            flags.append({
                "severity": "high",
                "type": "future_dates",
                "detail": f"Date in the future: {label}",
            })

    return {"flags": flags}


def _check_suspicious_patterns(sections: list, paragraphs: list, total_words: int) -> dict:
    """Check for patterns that suggest a fake or low-quality CV."""
    flags = []
    all_text = " ".join(p.get("text", "") for p in paragraphs)
    text_lower = all_text.lower()

    # Impossible claims
    impossible_patterns = [
        (r"(?:25|30|40|50)\+ years? (?:of )?experience", "Claimed exceptionally long experience"),
        (r"(?:phd|doctorate).*(?:age|year).*(?:1[0-9]|2[0-2])", "Suspiciously young for claimed education"),
    ]
    for pattern, detail in impossible_patterns:
        if re.search(pattern, text_lower):
            flags.append({"severity": "high", "type": "impossible_claim", "detail": detail})

    # Excessive buzzwords
    buzzwords = ["synergy", "paradigm", "leverage", "ideate", "disrupt", "innovative",
                 "thought leader", "guru", "ninja", "rockstar", "wizard"]
    bw_count = sum(1 for bw in buzzwords if bw in text_lower)
    if bw_count >= 5:
        flags.append({
            "severity": "low",
            "type": "buzzword_heavy",
            "detail": f"Contains {bw_count} buzzwords — may be over-polished or AI-generated",
        })

    # Very uniform paragraph lengths (possible template)
    para_lengths = [len(p.get("text", "").split()) for p in paragraphs if p.get("text", "").strip()]
    if len(para_lengths) > 5:
        avg_len = sum(para_lengths) / len(para_lengths)
        variance = sum((l - avg_len) ** 2 for l in para_lengths) / len(para_lengths)
        if variance < 5 and avg_len > 10:
            flags.append({
                "severity": "low",
                "type": "uniform_formatting",
                "detail": "Paragraphs are suspiciously uniform in length — possible template",
            })

    return {"flags": flags}


def _extract_year(date_str: str) -> int | None:
    """Extract a year from a date string."""
    match = re.search(r'\d{4}', date_str)
    return int(match.group()) if match else None
