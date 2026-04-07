"""
app/services/intelligence/user_intelligence_service.py

User Intelligence Engine — aggregates all data sources into a unified
behavioral profile with actionable insights.

Zero LLM cost — all rule-based computation.
"""

import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.models.application_timeline import ApplicationTimeline
from app.models.candidate_profile import CandidateProfile
from app.models.cv import CV
from app.models.email_intelligence import EmailIntelligence
from app.models.interview import InterviewRound
from app.models.linkedin_connection import LinkedInConnection
from app.models.user_intelligence import UserIntelligence
from app.models.warm_intro import WarmIntro

logger = structlog.get_logger(__name__)


class UserIntelligenceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def compute(self, user_id: str) -> UserIntelligence:
        """Compute full intelligence profile from all data sources."""
        # Get or create record
        result = await self.db.execute(
            select(UserIntelligence).where(UserIntelligence.user_id == user_id)
        )
        intel = result.scalar_one_or_none()
        if not intel:
            intel = UserIntelligence(user_id=user_id)
            self.db.add(intel)

        # Compute each section
        intel.strength_breakdown = await self._compute_strength(user_id)
        intel.profile_strength = round(
            sum(intel.strength_breakdown.values()) / max(len(intel.strength_breakdown), 1)
        )
        intel.behavioral_profile = await self._compute_behavioral(user_id)
        intel.success_patterns = await self._compute_success(user_id)
        intel.failure_patterns = await self._compute_failure(user_id)
        intel.recommendations = self._generate_recommendations(
            intel.strength_breakdown,
            intel.behavioral_profile or {},
            intel.success_patterns or {},
            intel.failure_patterns or {},
        )

        await self.db.flush()
        await self.db.commit()
        await self.db.refresh(intel)
        return intel

    async def get(self, user_id: str) -> UserIntelligence | None:
        result = await self.db.execute(
            select(UserIntelligence).where(UserIntelligence.user_id == user_id)
        )
        return result.scalar_one_or_none()

    # ── Profile strength ──────────────────────────────────────────────────

    async def _compute_strength(self, user_id: str) -> dict:
        scores = {}

        # CV: has uploaded + parsed CV?
        cv_count = (await self.db.execute(
            select(func.count()).select_from(CV).where(CV.user_id == user_id, CV.parsed_content.isnot(None))
        )).scalar() or 0
        scores["cv"] = min(100, cv_count * 50)

        # Profile: has active candidate profile with experiences?
        from app.models.candidate_profile import CandidateProfile, ProfileStatus, ExperienceEntry
        profile = (await self.db.execute(
            select(CandidateProfile).where(
                CandidateProfile.user_id == user_id,
                CandidateProfile.status == ProfileStatus.ACTIVE,
            )
        )).scalar_one_or_none()
        if profile:
            exp_count = (await self.db.execute(
                select(func.count()).select_from(ExperienceEntry).where(
                    ExperienceEntry.profile_id == profile.id,
                    ExperienceEntry.is_complete == True,  # noqa: E712
                )
            )).scalar() or 0
            scores["profile"] = min(100, 30 + exp_count * 15)
        else:
            scores["profile"] = 0

        # LinkedIn: connected + imported connections?
        li_count = (await self.db.execute(
            select(func.count()).select_from(LinkedInConnection).where(
                LinkedInConnection.user_id == user_id
            )
        )).scalar() or 0
        scores["linkedin"] = min(100, li_count * 2)  # 50 connections = 100%

        # Email: has email intelligence report?
        email_intel = (await self.db.execute(
            select(EmailIntelligence).where(
                EmailIntelligence.user_id == user_id,
                EmailIntelligence.scan_status == "completed",
            )
        )).scalar_one_or_none()
        scores["email"] = 100 if email_intel else 0

        # Applications: has active applications?
        app_count = (await self.db.execute(
            select(func.count()).select_from(Application).where(
                Application.user_id == user_id
            )
        )).scalar() or 0
        scores["applications"] = min(100, app_count * 10)

        return scores

    # ── Behavioral profile ────────────────────────────────────────────────

    async def _compute_behavioral(self, user_id: str) -> dict:
        # Application velocity (apps per week, last 30 days)
        cutoff = datetime.now(UTC) - timedelta(days=30)
        recent_apps = (await self.db.execute(
            select(func.count()).select_from(Application).where(
                Application.user_id == user_id,
                Application.created_at >= cutoff,
            )
        )).scalar() or 0
        velocity = round(recent_apps / 4.3, 1)  # 4.3 weeks in a month

        # Avg time in each stage
        apps = (await self.db.execute(
            select(Application).where(Application.user_id == user_id)
        )).scalars().all()

        stage_times = defaultdict(list)
        for app in apps:
            if app.interview_at and app.date_applied:
                days = (app.interview_at - app.date_applied).days
                if 0 < days < 180:
                    stage_times["applied"].append(days)
            if app.offer_at and app.interview_at:
                days = (app.offer_at - app.interview_at).days
                if 0 < days < 180:
                    stage_times["interview"].append(days)

        avg_times = {
            stage: round(sum(days) / len(days), 1)
            for stage, days in stage_times.items() if days
        }

        # Follow-up rate
        total_apps = len(apps)
        with_followup = (await self.db.execute(
            select(func.count(func.distinct(ApplicationTimeline.application_id))).where(
                ApplicationTimeline.application_id.in_([a.id for a in apps]) if apps else False,
                ApplicationTimeline.event_type == "follow_up",
            )
        )).scalar() or 0 if apps else 0
        followup_rate = round(with_followup / total_apps, 2) if total_apps > 0 else 0

        # Source channel breakdown
        channel_rows = (await self.db.execute(
            select(Application.source_channel, func.count())
            .where(Application.user_id == user_id)
            .group_by(Application.source_channel)
            .order_by(func.count().desc())
        )).all()
        preferred_channels = [r[0] for r in channel_rows[:3]]

        # Writing style from email intel
        email_intel = (await self.db.execute(
            select(EmailIntelligence).where(EmailIntelligence.user_id == user_id)
        )).scalar_one_or_none()
        style_summary = ""
        if email_intel and email_intel.writing_style:
            ws = email_intel.writing_style
            style_summary = f"{ws.get('formality', 'professional').title()}, {ws.get('tone', 'neutral')} tone"

        return {
            "application_velocity": velocity,
            "avg_time_in_stage": avg_times,
            "follow_up_rate": followup_rate,
            "networking_active": (await self.db.execute(
                select(func.count()).select_from(LinkedInConnection).where(
                    LinkedInConnection.user_id == user_id
                )
            )).scalar() or 0 > 10,
            "preferred_channels": preferred_channels,
            "writing_style_summary": style_summary,
        }

    # ── Success patterns ──────────────────────────────────────────────────

    async def _compute_success(self, user_id: str) -> dict:
        # Best source channel (highest interview conversion)
        channel_rows = (await self.db.execute(
            select(
                Application.source_channel,
                func.count().label("total"),
                func.count().filter(
                    Application.stage.in_(["interview", "offer"])
                ).label("progressed"),
            )
            .where(Application.user_id == user_id)
            .group_by(Application.source_channel)
        )).all()

        best_channel = None
        best_rate = 0
        for channel, total, progressed in channel_rows:
            if total >= 2:
                rate = progressed / total
                if rate > best_rate:
                    best_rate = rate
                    best_channel = channel

        # Interview pass rate
        interview_rows = (await self.db.execute(
            select(InterviewRound.outcome, func.count())
            .where(InterviewRound.user_id == user_id, InterviewRound.outcome.isnot(None))
            .group_by(InterviewRound.outcome)
        )).all()
        outcome_map = {r[0]: r[1] for r in interview_rows}
        passed = outcome_map.get("passed", 0)
        decided = passed + outcome_map.get("failed", 0)

        # Strongest round type
        round_pass = (await self.db.execute(
            select(InterviewRound.round_type, func.count())
            .where(InterviewRound.user_id == user_id, InterviewRound.outcome == "passed")
            .group_by(InterviewRound.round_type)
            .order_by(func.count().desc())
            .limit(1)
        )).first()

        # Offer rate
        total_apps = (await self.db.execute(
            select(func.count()).select_from(Application).where(Application.user_id == user_id)
        )).scalar() or 0
        offers = (await self.db.execute(
            select(func.count()).select_from(Application).where(
                Application.user_id == user_id, Application.stage == "offer"
            )
        )).scalar() or 0

        return {
            "best_source_channel": best_channel,
            "interview_pass_rate": round(passed / decided, 2) if decided > 0 else None,
            "offer_rate": round(offers / total_apps, 2) if total_apps > 0 else None,
            "strongest_round_type": round_pass[0] if round_pass else None,
        }

    # ── Failure patterns ──────────────────────────────────────────────────

    async def _compute_failure(self, user_id: str) -> dict:
        # Most common rejection stage
        rejected = (await self.db.execute(
            select(Application).where(
                Application.user_id == user_id,
                Application.stage == "rejected",
            )
        )).scalars().all()

        ghosted = sum(1 for a in rejected if not a.interview_at)
        total_rejected = len(rejected)

        # Weakest round type
        round_fail = (await self.db.execute(
            select(InterviewRound.round_type, func.count())
            .where(InterviewRound.user_id == user_id, InterviewRound.outcome == "failed")
            .group_by(InterviewRound.round_type)
            .order_by(func.count().desc())
            .limit(1)
        )).first()

        return {
            "common_rejection_stage": "applied (no response)" if ghosted > total_rejected / 2 and total_rejected > 3 else "interview",
            "ghosted_rate": round(ghosted / total_rejected, 2) if total_rejected > 0 else None,
            "weakest_round_type": round_fail[0] if round_fail else None,
            "total_rejections": total_rejected,
        }

    # ── Recommendations ───────────────────────────────────────────────────

    @staticmethod
    def _generate_recommendations(
        strength: dict, behavioral: dict, success: dict, failure: dict,
    ) -> dict:
        recs = []

        # Profile completeness
        for area, score in strength.items():
            if score < 50:
                recs.append(f"Improve your {area} profile — currently at {score}%")

        # Velocity
        vel = behavioral.get("application_velocity", 0)
        if vel < 1:
            recs.append("Increase application volume — aim for 3-5 per week")
        elif vel > 10:
            recs.append("You're applying a lot — consider being more selective to improve quality")

        # Follow-up
        if behavioral.get("follow_up_rate", 0) < 0.3:
            recs.append("Follow up more — less than 30% of your applications have follow-ups")

        # Channel optimization
        best = success.get("best_source_channel")
        if best:
            recs.append(f"Double down on {best} — it's your best-converting channel")

        # Ghosting
        if (failure.get("ghosted_rate") or 0) > 0.5:
            recs.append("High ghosting rate — your initial application may need stronger positioning")

        # Round weakness
        weak = failure.get("weakest_round_type")
        if weak:
            recs.append(f"Practice {weak} interviews — this is where you lose most candidates")

        return {
            "top_actions": recs[:5],
            "total_recommendations": len(recs),
        }
