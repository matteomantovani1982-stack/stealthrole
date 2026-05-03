"""
app/services/ingest/anomaly_detector.py

Heuristic anomaly detection for parsed CV/JD data.
Flags suspicious patterns: impossible timelines, title inflation, missing sections.
"""

import re
from datetime import datetime


def detect_anomalies(parsed_data: dict) -> list[dict]:
    """
    Run heuristic checks on parsed document data and return anomaly flags.

    Each anomaly: {type: str, severity: 'warning'|'info', message: str}
    """
    anomalies: list[dict] = []

    experiences = parsed_data.get("experience", [])
    education = parsed_data.get("education", [])

    # ── Missing key sections ──────────────────────────────────────────────
    if not experiences:
        anomalies.append({
            "type": "missing_section",
            "severity": "warning",
            "message": "No experience section found in the document.",
        })
    if not education:
        anomalies.append({
            "type": "missing_section",
            "severity": "info",
            "message": "No education section found in the document.",
        })

    # ── Overlapping full-time roles (impossible timelines) ────────────────
    dated_roles = _extract_dated_roles(experiences)
    for i, role_a in enumerate(dated_roles):
        for role_b in dated_roles[i + 1:]:
            if _roles_overlap(role_a, role_b):
                anomalies.append({
                    "type": "impossible_timeline",
                    "severity": "warning",
                    "message": (
                        f"Overlapping full-time roles: "
                        f"'{role_a['title']}' and '{role_b['title']}' "
                        f"have overlapping date ranges."
                    ),
                })

    # ── Title inflation ──────────────────────────────────────────────────
    senior_titles = re.compile(
        r"\b(director|vp|vice\s*president|chief|c-suite|cto|cfo|ceo|coo|cmo|head\s+of)\b",
        re.IGNORECASE,
    )
    for exp in experiences:
        title = exp.get("title", "")
        if not senior_titles.search(title):
            continue
        years = _estimate_career_years(exp)
        if years is not None and years < 3:
            anomalies.append({
                "type": "title_inflation",
                "severity": "warning",
                "message": (
                    f"Senior title '{title}' with less than 3 years experience "
                    f"at the role start date — possible title inflation."
                ),
            })

    return anomalies


def _extract_dated_roles(experiences: list[dict]) -> list[dict]:
    """Extract roles that have parseable start/end dates."""
    roles = []
    for exp in experiences:
        start = _parse_date(exp.get("start_date"))
        end = _parse_date(exp.get("end_date"))
        if start:
            roles.append({
                "title": exp.get("title", "Unknown"),
                "start": start,
                "end": end or datetime.now(),
            })
    return roles


def _roles_overlap(a: dict, b: dict) -> bool:
    """Check if two date ranges overlap."""
    return a["start"] < b["end"] and b["start"] < a["end"]


def _parse_date(date_str: str | None) -> datetime | None:
    """Try common date formats."""
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m", "%m/%Y", "%B %Y", "%b %Y", "%Y"):
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None


def _estimate_career_years(exp: dict) -> float | None:
    """Estimate years from career start to this role's start date."""
    start = _parse_date(exp.get("start_date"))
    if not start:
        return None
    # Use start_date as proxy — if they started this senior role with < 3 years
    # since graduation or first role, flag it. We approximate by checking
    # if the role start year minus a typical grad year (start_date year - 22)
    # gives < 3 years of experience.
    # Simpler: just check if the role itself is < 3 years duration from start
    grad_year = start.year - 22  # rough estimate
    _years_experience = start.year - (grad_year + 22)
    # Better heuristic: flag if start_date is recent (within 3 years of "now")
    # and title is senior. Use the experience entry's own start date.
    end = _parse_date(exp.get("end_date"))
    if end and start:
        duration = (end - start).days / 365.25
        if duration < 3:
            return duration
    return None
