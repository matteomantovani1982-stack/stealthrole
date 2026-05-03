"""
app/services/email_integration/intelligence_service.py

Full Email Intelligence — deep 5-year scan + behavioral pattern analysis.

Pipeline:
  1. Fetch all job-related emails (5 years back)
  2. Classify each email (applied/interview/offer/rejection)
  3. Group into application timelines (cluster by company)
  4. Compute behavioral patterns (response rates, timing, industries)
  5. Generate insights (strengths, weaknesses, recommendations)

Steps 1-4: rule-based (zero LLM cost)
Step 5: Haiku for insight generation (optional, cached)
"""

import re
from collections import defaultdict
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.email_account import EmailAccount
from app.models.email_intelligence import EmailIntelligence
from app.models.email_scan import EmailScan

logger = structlog.get_logger(__name__)


class EmailIntelligenceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create(self, user_id: str) -> EmailIntelligence:
        result = await self.db.execute(
            select(EmailIntelligence).where(EmailIntelligence.user_id == user_id)
        )
        intel = result.scalar_one_or_none()
        if intel:
            return intel

        intel = EmailIntelligence(user_id=user_id)
        self.db.add(intel)
        await self.db.flush()
        await self.db.commit()
        await self.db.refresh(intel)
        return intel

    async def get_report(self, user_id: str) -> EmailIntelligence | None:
        result = await self.db.execute(
            select(EmailIntelligence).where(EmailIntelligence.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def start_scan(self, user_id: str) -> EmailIntelligence:
        """Mark scan as started. Actual work happens in Celery task."""
        intel = await self.get_or_create(user_id)
        intel.scan_status = "scanning"
        intel.scan_started_at = datetime.now(UTC)
        intel.error_message = None
        await self.db.commit()
        await self.db.refresh(intel)
        return intel

    async def store_analysis(self, user_id: str, analysis: dict, total_emails: int) -> EmailIntelligence:
        """Store Claude-generated analysis results."""
        intel = await self.get_or_create(user_id)
        intel.scan_status = "completed"
        intel.scan_completed_at = datetime.now(UTC)
        intel.total_emails_scanned = total_emails
        intel.job_emails_found = analysis.get("applications_found", 0)
        intel.applications_reconstructed = analysis.get("total_companies_applied", 0)

        intel.patterns = {
            "avg_response_days": analysis.get("avg_response_days"),
            "response_rate_pct": analysis.get("response_rate_pct", 0),
            "best_day_to_apply": analysis.get("best_day_to_apply"),
            "best_time_to_apply": analysis.get("best_time_to_apply"),
            "avg_interviews_per_app": analysis.get("avg_interviews_per_app", 0),
            "total_companies_applied": analysis.get("total_companies_applied", 0),
            "total_responses": analysis.get("total_responses", 0),
            "rejection_stage_distribution": analysis.get("rejection_stage_distribution", {}),
        }
        intel.industry_breakdown = analysis.get("industry_breakdown", {})
        intel.writing_style = analysis.get("writing_style", {})
        intel.insights = analysis.get("insights", {})

        # Store extra data
        if "key_contacts" in analysis:
            intel.reconstructed_timeline = analysis.get("key_contacts", [])
        if "activity_timeline" in analysis:
            extra = intel.patterns or {}
            extra["activity_timeline"] = analysis["activity_timeline"]
            intel.patterns = extra

        await self.db.commit()
        await self.db.refresh(intel)
        return intel

    async def run_analysis(self, user_id: str) -> EmailIntelligence:
        """
        Run the full analysis on already-scanned emails.
        Called from Celery task after email fetch completes.
        """
        intel = await self.get_or_create(user_id)
        intel.scan_status = "analyzing"
        await self.db.flush()

        try:
            # Load all scans for this user
            accounts = (await self.db.execute(
                select(EmailAccount.id).where(EmailAccount.user_id == user_id)
            )).all()
            account_ids = [r[0] for r in accounts]

            if not account_ids:
                intel.scan_status = "completed"
                intel.scan_completed_at = datetime.now(UTC)
                intel.error_message = "No email accounts connected"
                await self.db.commit()
                return intel

            scans = (await self.db.execute(
                select(EmailScan)
                .where(EmailScan.email_account_id.in_(account_ids))
                .order_by(EmailScan.email_date.asc())
            )).scalars().all()

            intel.total_emails_scanned = len(scans)
            intel.job_emails_found = len(scans)

            # Reconstruct timeline
            timeline = _reconstruct_timeline(scans)
            intel.reconstructed_timeline = timeline
            intel.applications_reconstructed = len(set(
                (e["company"], e.get("role", "")) for e in timeline if e.get("company")
            ))

            # Compute patterns
            intel.patterns = _compute_patterns(timeline, scans)

            # Industry breakdown
            intel.industry_breakdown = _compute_industry_breakdown(timeline)

            # Generate insights (rule-based)
            intel.insights = _generate_insights(
                intel.patterns or {},
                intel.industry_breakdown or {},
                intel.applications_reconstructed,
            )

            # Extract writing style from outgoing emails
            intel.writing_style = _extract_writing_style(scans)

            intel.scan_status = "completed"
            intel.scan_completed_at = datetime.now(UTC)

        except Exception as e:
            intel.scan_status = "failed"
            intel.error_message = str(e)[:500]
            logger.error("email_intelligence_failed", user_id=user_id, error=str(e))

        await self.db.commit()
        await self.db.refresh(intel)
        return intel


# ── Analysis functions (rule-based, zero LLM cost) ───────────────────────────

def _reconstruct_timeline(scans: list[EmailScan]) -> list[dict]:
    """Group scans into a chronological application timeline."""
    timeline = []
    for scan in scans:
        timeline.append({
            "company": scan.company,
            "role": scan.role,
            "stage": scan.detected_stage,
            "date": scan.email_date.isoformat() if scan.email_date else None,
            "subject": scan.email_subject,
            "source": scan.email_from,
            "confidence": scan.confidence,
        })
    return timeline


def _compute_patterns(timeline: list[dict], scans: list[EmailScan]) -> dict:
    """Compute behavioral patterns from the timeline."""
    if not timeline:
        return {}

    # Group by company for per-application analysis
    by_company: dict[str, list[dict]] = defaultdict(list)
    for entry in timeline:
        company = (entry.get("company") or "unknown").lower().strip()
        by_company[company].append(entry)

    # Response time analysis
    response_days = []
    for company, events in by_company.items():
        applied_date = None
        for e in events:
            if e["stage"] == "applied" and e.get("date"):
                applied_date = datetime.fromisoformat(e["date"].replace("Z", "+00:00"))
            elif e["stage"] in ("interview", "offer", "rejected") and applied_date and e.get("date"):
                resp_date = datetime.fromisoformat(e["date"].replace("Z", "+00:00"))
                days = (resp_date - applied_date).days
                if 0 < days < 180:
                    response_days.append(days)

    # Day-of-week analysis
    day_counts: dict[str, int] = defaultdict(int)
    hour_counts: dict[str, int] = defaultdict(int)
    for scan in scans:
        if scan.email_date and scan.detected_stage == "applied":
            day_counts[scan.email_date.strftime("%A")] += 1
            hour = scan.email_date.hour
            if hour < 12:
                hour_counts["morning"] += 1
            elif hour < 17:
                hour_counts["afternoon"] += 1
            else:
                hour_counts["evening"] += 1

    # Stage distribution
    stage_counts: dict[str, int] = defaultdict(int)
    for entry in timeline:
        stage_counts[entry.get("stage", "unknown")] += 1

    total_apps = len(by_company)
    interviews = stage_counts.get("interview", 0)
    offers = stage_counts.get("offer", 0)
    _rejections = stage_counts.get("rejected", 0)

    return {
        "avg_response_days": round(sum(response_days) / len(response_days), 1) if response_days else None,
        "response_rate_pct": round(
            (interviews + offers) / total_apps * 100, 1
        ) if total_apps > 0 else 0,
        "best_day_to_apply": max(day_counts, key=day_counts.get) if day_counts else None,
        "best_time_to_apply": max(hour_counts, key=hour_counts.get) if hour_counts else None,
        "avg_interviews_per_app": round(interviews / total_apps, 2) if total_apps > 0 else 0,
        "rejection_stage_distribution": dict(stage_counts),
        "longest_process_days": max(response_days) if response_days else None,
        "fastest_offer_days": min(
            d for d, e in zip(response_days, timeline) if e.get("stage") == "offer"
        ) if any(e.get("stage") == "offer" for e in timeline) and response_days else None,
        "total_companies_applied": total_apps,
        "total_responses": len(response_days),
    }


def _compute_industry_breakdown(timeline: list[dict]) -> dict:
    """Group applications by detected industry/company."""
    by_company: dict[str, dict] = defaultdict(lambda: {
        "applied": 0, "interview": 0, "offer": 0, "rejected": 0
    })
    for entry in timeline:
        company = entry.get("company") or "unknown"
        stage = entry.get("stage", "unknown")
        if stage in by_company[company]:
            by_company[company][stage] += 1
    return dict(by_company)


def _generate_insights(
    patterns: dict, industry: dict, total_apps: int
) -> dict:
    """Generate behavioral insights. Rule-based, zero LLM cost."""
    strengths = []
    weaknesses = []
    recommendations = []

    response_rate = patterns.get("response_rate_pct", 0)
    avg_days = patterns.get("avg_response_days")
    best_day = patterns.get("best_day_to_apply")

    # Response rate analysis
    if response_rate > 30:
        strengths.append(f"Strong response rate ({response_rate}%) — your profile is compelling")
    elif response_rate > 15:
        strengths.append(f"Decent response rate ({response_rate}%) — room to improve targeting")
    elif total_apps > 5:
        weaknesses.append(f"Low response rate ({response_rate}%) — consider tailoring applications more")
        recommendations.append("Use the Intelligence Pack to tailor your CV for each role")

    # Timing insights
    if best_day:
        recommendations.append(f"You tend to get better results applying on {best_day}s")
    if avg_days and avg_days > 14:
        recommendations.append("Companies take a while to respond to you — follow up after 7 days")

    # Industry insights
    best_industry = None
    best_rate = 0
    for company, stats in industry.items():
        total = sum(stats.values())
        if total < 2:
            continue
        interview_rate = (stats.get("interview", 0) + stats.get("offer", 0)) / total
        if interview_rate > best_rate:
            best_rate = interview_rate
            best_industry = company

    if best_industry and best_rate > 0.3:
        strengths.append(f"Strong conversion at {best_industry} — consider focusing here")

    # Volume
    if total_apps > 50:
        recommendations.append("You've applied broadly — consider being more selective and investing more per application")
    elif total_apps < 5:
        recommendations.append("Low volume — increase applications to improve your chances")

    return {
        "strengths": strengths,
        "weaknesses": weaknesses,
        "recommendations": recommendations,
        "career_trajectory": f"Based on {total_apps} tracked applications across your email history",
    }


def _extract_writing_style(scans: list) -> dict:
    """
    Extract writing style profile from outgoing email snippets.
    Analyzes: formality, sentence length, tone, greetings, closings, common phrases.
    Rule-based — zero LLM cost.
    """
    # Collect outgoing email text (snippets from emails the user sent)
    # In scans, outgoing emails are harder to identify — use snippets that
    # look like user-authored text (shorter, less formal than auto-replies)
    texts = []
    for scan in scans:
        snippet = scan.email_snippet or ""
        # Skip very short or obviously auto-generated snippets
        if len(snippet) < 30:
            continue
        texts.append(snippet)

    if not texts:
        return {
            "formality": "professional",
            "tone": "neutral",
            "greeting_style": "Hi,",
            "closing_style": "Best regards,",
            "common_phrases": [],
            "sample_sentences": [],
        }

    all_text = " ".join(texts)
    words = all_text.split()
    total_words = len(words)

    # Sentence analysis
    sentences = re.split(r'[.!?]+', all_text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 5]
    avg_sentence_len = round(
        sum(len(s.split()) for s in sentences) / len(sentences), 1
    ) if sentences else 12.0

    avg_word_len = round(
        sum(len(w) for w in words) / total_words, 1
    ) if total_words > 0 else 4.5

    # Formality detection
    informal_markers = ["hey", "thanks!", "lol", "haha", "gonna", "wanna", "btw", "fyi"]
    formal_markers = ["dear", "sincerely", "pursuant", "herewith", "kindly", "respectfully"]
    text_lower = all_text.lower()

    informal_count = sum(1 for m in informal_markers if m in text_lower)
    formal_count = sum(1 for m in formal_markers if m in text_lower)

    if formal_count > informal_count:
        formality = "formal"
    elif informal_count > formal_count + 2:
        formality = "casual"
    else:
        formality = "professional"

    # Tone detection
    confident_markers = ["I believe", "I'm confident", "I can", "I will", "I'd love to", "excited to"]
    tentative_markers = ["I think maybe", "perhaps", "I was wondering if", "would it be possible", "sorry to bother"]

    confident_count = sum(1 for m in confident_markers if m.lower() in text_lower)
    tentative_count = sum(1 for m in tentative_markers if m.lower() in text_lower)

    if confident_count > tentative_count:
        tone = "confident"
    elif tentative_count > confident_count:
        tone = "tentative"
    else:
        tone = "neutral"

    # Vocabulary level
    if avg_word_len > 5.5:
        vocabulary_level = "advanced"
    elif avg_word_len > 4.5:
        vocabulary_level = "intermediate"
    else:
        vocabulary_level = "basic"

    # Greeting style
    greeting_patterns = [
        (r"Hi [A-Z]\w+", "Hi [Name],"),
        (r"Hey [A-Z]\w+", "Hey [Name],"),
        (r"Hello [A-Z]\w+", "Hello [Name],"),
        (r"Dear [A-Z]\w+", "Dear [Name],"),
        (r"Good (?:morning|afternoon|evening)", "Good [time of day],"),
    ]
    greeting_style = "Hi,"
    for pattern, style in greeting_patterns:
        if re.search(pattern, all_text):
            greeting_style = style
            break

    # Closing style
    closing_patterns = [
        (r"(?:Best|Kind) regards", "Best regards,"),
        (r"Thanks,?$", "Thanks,"),
        (r"Cheers,?$", "Cheers,"),
        (r"Best,?$", "Best,"),
        (r"Thank you,?$", "Thank you,"),
        (r"Sincerely", "Sincerely,"),
    ]
    closing_style = "Best regards,"
    for pattern, style in closing_patterns:
        if re.search(pattern, all_text, re.MULTILINE):
            closing_style = style
            break

    # Common phrases (job-search specific)
    phrase_candidates = [
        "looking forward to", "happy to discuss", "excited about",
        "interested in", "would love to", "let me know",
        "great opportunity", "reach out", "touch base",
        "thanks for", "appreciate your", "hope you're well",
    ]
    common_phrases = [p for p in phrase_candidates if p in text_lower]

    # Sample sentences (pick 5 diverse ones)
    sample_sentences = []
    for s in sentences:
        if 8 <= len(s.split()) <= 25 and len(sample_sentences) < 5:
            if not any(s[:20] == existing[:20] for existing in sample_sentences):
                sample_sentences.append(s.strip())

    return {
        "formality": formality,
        "avg_sentence_length": avg_sentence_len,
        "avg_word_length": avg_word_len,
        "vocabulary_level": vocabulary_level,
        "tone": tone,
        "greeting_style": greeting_style,
        "closing_style": closing_style,
        "uses_emoji": bool(re.search(r'[\U0001F600-\U0001F9FF]', all_text)),
        "common_phrases": common_phrases[:8],
        "sample_sentences": sample_sentences,
    }
