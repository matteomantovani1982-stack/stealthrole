"""
app/services/interview/coach_service.py

Interview Coach + Compensation Negotiation service.

Capabilities:
  1. Interview round CRUD (schedule, prep, debrief)
  2. Per-round prep suggestions (rule-based by round type)
  3. Compensation benchmarks lookup
  4. Negotiation scripts (rule-based templates)
  5. Interview analytics (pass rate, common question patterns)

Zero LLM cost — all rule-based. Uses existing Intelligence Pack
interview data when available.
"""

import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.models.interview import InterviewRound, CompensationBenchmark

logger = structlog.get_logger(__name__)


# ── Prep templates by round type ──────────────────────────────────────────────

_PREP_GUIDES: dict[str, dict] = {
    "phone_screen": {
        "focus": ["Company background", "Role fit", "Your elevator pitch", "Salary expectations"],
        "tips": [
            "Keep answers to 2-3 minutes max",
            "Have your resume in front of you",
            "Research the company's recent news",
            "Prepare 2-3 questions about the role and team",
        ],
        "common_questions": [
            "Tell me about yourself",
            "Why are you interested in this role?",
            "What are your salary expectations?",
            "When can you start?",
        ],
    },
    "technical": {
        "focus": ["Data structures & algorithms", "System design", "Domain-specific skills", "Code quality"],
        "tips": [
            "Think aloud — explain your reasoning",
            "Start with brute force, then optimize",
            "Ask clarifying questions before coding",
            "Test your solution with edge cases",
        ],
        "common_questions": [
            "Design a system that handles X",
            "Optimize this algorithm",
            "Walk me through your approach to debugging",
            "What's the trade-off between X and Y?",
        ],
    },
    "behavioral": {
        "focus": ["STAR method", "Leadership examples", "Conflict resolution", "Failure stories"],
        "tips": [
            "Use STAR format: Situation, Task, Action, Result",
            "Quantify results wherever possible",
            "Be honest about failures — focus on learning",
            "Prepare 5-6 versatile stories that cover multiple themes",
        ],
        "common_questions": [
            "Tell me about a time you disagreed with a manager",
            "Describe a project that failed and what you learned",
            "How do you handle competing priorities?",
            "Give an example of leading without authority",
        ],
    },
    "case_study": {
        "focus": ["Problem structuring", "Market sizing", "Data analysis", "Recommendation framing"],
        "tips": [
            "Structure your approach before diving in",
            "Ask for 2 minutes to organize your thoughts",
            "Use a framework but don't be rigid",
            "End with a clear recommendation + next steps",
        ],
        "common_questions": [
            "How would you enter market X?",
            "The CEO asks you to cut costs by 20% — what's your approach?",
            "Estimate the market size for Y",
            "How would you prioritize these 5 initiatives?",
        ],
    },
    "hiring_manager": {
        "focus": ["Team fit", "Management style", "Vision for the role", "Career growth"],
        "tips": [
            "This is mutual — you're evaluating them too",
            "Ask about team structure and dynamics",
            "Discuss what success looks like in 90 days",
            "Show genuine curiosity about their challenges",
        ],
        "common_questions": [
            "What does the first 90 days look like?",
            "What's the biggest challenge the team faces?",
            "How do you measure success in this role?",
            "Why is this position open?",
        ],
    },
    "panel": {
        "focus": ["Multiple stakeholders", "Eye contact distribution", "Diverse perspectives"],
        "tips": [
            "Address each panelist, not just the one who asked",
            "Note each person's name and role",
            "Expect cross-functional questions",
            "Send individual thank-you notes after",
        ],
        "common_questions": [],
    },
    "final": {
        "focus": ["Executive presence", "Strategic thinking", "Culture add", "Negotiation readiness"],
        "tips": [
            "This is often about culture fit and conviction",
            "Be ready to discuss compensation",
            "Have a strong 'why this company' story",
            "Ask thoughtful questions about company direction",
        ],
        "common_questions": [
            "Where do you see yourself in 5 years?",
            "What questions do you have for us?",
            "Why should we choose you?",
        ],
    },
}


# ── Negotiation templates ─────────────────────────────────────────────────────

def _negotiation_script(
    company: str, role: str, offer_amount: int | None, benchmark_p50: int | None
) -> dict:
    """Generate negotiation talking points. Rule-based, zero LLM cost."""
    points = []

    if offer_amount and benchmark_p50:
        diff_pct = round((offer_amount - benchmark_p50) / benchmark_p50 * 100, 1)
        if diff_pct < -10:
            points.append(f"The offer is {abs(diff_pct)}% below market median — strong case to negotiate up")
            points.append(f"Market median for this role/region is ~${benchmark_p50:,}")
        elif diff_pct < 5:
            points.append("Offer is roughly at market rate — negotiate on other terms (equity, sign-on, flexibility)")
        else:
            points.append(f"Offer is {diff_pct}% above market median — competitive")

    points.extend([
        "Always negotiate — it's expected and shows professional confidence",
        "Focus on total compensation: base + bonus + equity + benefits",
        "Ask 'Is there flexibility on X?' rather than making demands",
        f"Frame it as: 'I'm very excited about {company}. To make this work, I was hoping for...'",
        "Get the offer in writing before accepting verbally",
        "Ask for 48-72 hours to review — never accept on the spot",
    ])

    return {
        "company": company,
        "role": role,
        "talking_points": points,
        "counter_offer_strategy": (
            "Lead with enthusiasm, then present your number with reasoning. "
            "Use market data, competing offers, and your unique value as leverage."
        ),
        "things_to_negotiate": [
            "Base salary",
            "Sign-on bonus",
            "Equity/RSU",
            "Annual bonus target",
            "Remote work flexibility",
            "Start date",
            "Title",
            "Professional development budget",
            "Relocation support",
        ],
    }


class InterviewCoachService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Round CRUD ────────────────────────────────────────────────────────

    async def add_round(
        self, user_id: str, application_id: uuid.UUID, **fields
    ) -> InterviewRound:
        # Verify ownership
        app = await self._get_app(application_id, user_id)
        if not app:
            raise ValueError("Application not found")

        # Auto-set round number
        count = (await self.db.execute(
            select(func.count()).where(InterviewRound.application_id == application_id)
        )).scalar() or 0

        round_ = InterviewRound(
            application_id=application_id,
            user_id=user_id,
            round_number=count + 1,
            **fields,
        )
        self.db.add(round_)
        await self.db.flush()
        await self.db.commit()
        await self.db.refresh(round_)
        return round_

    async def list_rounds(
        self, user_id: str, application_id: uuid.UUID
    ) -> list[InterviewRound]:
        result = await self.db.execute(
            select(InterviewRound).where(
                InterviewRound.application_id == application_id,
                InterviewRound.user_id == user_id,
            ).order_by(InterviewRound.round_number)
        )
        return list(result.scalars().all())

    async def update_round(
        self, user_id: str, round_id: uuid.UUID, **fields
    ) -> InterviewRound | None:
        result = await self.db.execute(
            select(InterviewRound).where(
                InterviewRound.id == round_id,
                InterviewRound.user_id == user_id,
            )
        )
        round_ = result.scalar_one_or_none()
        if not round_:
            return None
        for k, v in fields.items():
            if hasattr(round_, k) and v is not None:
                setattr(round_, k, v)
        await self.db.flush()
        await self.db.commit()
        await self.db.refresh(round_)
        return round_

    async def delete_round(self, user_id: str, round_id: uuid.UUID) -> bool:
        result = await self.db.execute(
            select(InterviewRound).where(
                InterviewRound.id == round_id,
                InterviewRound.user_id == user_id,
            )
        )
        round_ = result.scalar_one_or_none()
        if not round_:
            return False
        await self.db.delete(round_)
        await self.db.commit()
        return True

    # ── Prep guide ────────────────────────────────────────────────────────

    async def get_prep_guide(
        self, user_id: str, round_id: uuid.UUID
    ) -> dict:
        """Get prep guide for a specific interview round."""
        result = await self.db.execute(
            select(InterviewRound).where(
                InterviewRound.id == round_id,
                InterviewRound.user_id == user_id,
            )
        )
        round_ = result.scalar_one_or_none()
        if not round_:
            return {"error": "Round not found"}

        guide = _PREP_GUIDES.get(round_.round_type, _PREP_GUIDES.get("behavioral", {}))

        return {
            "round_type": round_.round_type,
            "round_number": round_.round_number,
            "interviewer": round_.interviewer_name,
            "interviewer_title": round_.interviewer_title,
            **guide,
            "user_prep_notes": round_.prep_notes,
            "user_focus_areas": round_.focus_areas,
        }

    # ── Negotiation ───────────────────────────────────────────────────────

    async def get_negotiation_guide(
        self, user_id: str, application_id: uuid.UUID,
        offer_amount: int | None = None,
    ) -> dict:
        app = await self._get_app(application_id, user_id)
        if not app:
            return {"error": "Application not found"}

        # Try to find benchmark
        benchmark = await self._find_benchmark(app.role, "global")
        p50 = benchmark.p50 if benchmark else None

        guide = _negotiation_script(
            company=app.company,
            role=app.role,
            offer_amount=offer_amount,
            benchmark_p50=p50,
        )

        if benchmark:
            guide["benchmark"] = {
                "role": benchmark.role_title,
                "region": benchmark.region,
                "p25": benchmark.p25,
                "p50": benchmark.p50,
                "p75": benchmark.p75,
                "p90": benchmark.p90,
                "total_comp_p50": benchmark.total_comp_p50,
                "source": benchmark.source,
            }

        return guide

    # ── Compensation benchmarks ───────────────────────────────────────────

    async def get_benchmark(
        self, role: str, region: str
    ) -> CompensationBenchmark | None:
        return await self._find_benchmark(role, region)

    # ── Analytics ─────────────────────────────────────────────────────────

    async def get_interview_stats(self, user_id: str) -> dict:
        total = (await self.db.execute(
            select(func.count()).where(InterviewRound.user_id == user_id)
        )).scalar() or 0

        by_outcome = (await self.db.execute(
            select(InterviewRound.outcome, func.count())
            .where(InterviewRound.user_id == user_id, InterviewRound.outcome.isnot(None))
            .group_by(InterviewRound.outcome)
        )).all()

        by_type = (await self.db.execute(
            select(InterviewRound.round_type, func.count())
            .where(InterviewRound.user_id == user_id)
            .group_by(InterviewRound.round_type)
        )).all()

        passed = sum(r[1] for r in by_outcome if r[0] == "passed")
        decided = sum(r[1] for r in by_outcome if r[0] in ("passed", "failed"))

        return {
            "total_rounds": total,
            "by_outcome": {r[0]: r[1] for r in by_outcome},
            "by_type": {r[0]: r[1] for r in by_type},
            "pass_rate": round(passed / decided * 100, 1) if decided > 0 else None,
        }

    # ── Helpers ───────────────────────────────────────────────────────────

    async def _get_app(self, app_id: uuid.UUID, user_id: str) -> Application | None:
        result = await self.db.execute(
            select(Application).where(
                Application.id == app_id,
                Application.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def _find_benchmark(
        self, role: str, region: str
    ) -> CompensationBenchmark | None:
        result = await self.db.execute(
            select(CompensationBenchmark).where(
                func.lower(CompensationBenchmark.role_title).contains(role.lower()),
                func.lower(CompensationBenchmark.region).contains(region.lower()),
            ).limit(1)
        )
        return result.scalar_one_or_none()
