"""
app/services/action/action_generator.py

Action Generator — converts intelligence pipeline outputs into concrete,
prioritised user actions.

Input chain
-----------
  HiddenSignal → SignalInterpretation → DecisionScore → ActionRecommendation

Each generated action includes:
  - target (who to contact)
  - reason (why now — derived from interpretation)
  - timing (when to act — derived from predicted role timeline)
  - message (structured outreach content)
  - confidence score (blends decision score + action-type effectiveness)

Action types
------------
  linkedin_message   — Direct LinkedIn outreach to hiring owner
  email_outreach     — Email to decision maker or talent team
  referral_request   — Ask a mutual connection for a warm intro
  follow_up_sequence — Multi-step follow-up plan for active conversations

The generator does NOT call LLM APIs directly — it builds structured
messages from the interpretation's business context. LLM-polished versions
can be layered on top via the existing run_llm service if desired.

Usage
-----
    gen = ActionGenerator(db)
    actions = await gen.generate_actions(
        signal=signal,
        interpretation=interp,
        decision=decision_score,
        user_id=user_id,
    )
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.hidden_signal import HiddenSignal
    from app.models.signal_interpretation import SignalInterpretation
    from app.services.intelligence.decision_engine import DecisionScore

logger = structlog.get_logger(__name__)

# ── Action type priorities (lower = higher priority) ──────────────────
_TYPE_PRIORITY = {
    "referral_request": 10,
    "linkedin_message": 20,
    "email_outreach": 30,
    "follow_up_sequence": 40,
}

# ── Timeline to timing label ─────────────────────────────────────────
_TIMELINE_TO_TIMING = {
    "immediate": "today",
    "1_3_months": "this_week",
    "3_6_months": "next_week",
    "6_12_months": "flexible",
}

# ── Timing label to expiry days ──────────────────────────────────────
_TIMING_EXPIRY_DAYS = {
    "immediate": 3,
    "today": 3,
    "this_week": 7,
    "next_week": 14,
    "flexible": 30,
}


@dataclass(frozen=True, slots=True)
class GeneratedAction:
    """Immutable result of action generation before persistence."""

    action_type: str
    target_name: str
    target_title: str
    target_company: str
    reason: str
    message_subject: str | None
    message_body: str
    timing_label: str
    expires_at: datetime | None
    confidence: float
    priority: int
    decision_score: float
    channel_metadata: dict


class ActionGenerator:
    """Converts intelligence outputs into actionable recommendations."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def generate_actions(
        self,
        signal: HiddenSignal,
        interpretation: SignalInterpretation | None,
        decision: DecisionScore,
        user_id: str,
    ) -> list[GeneratedAction]:
        """Generate all applicable action types for one opportunity.

        Parameters
        ----------
        signal : HiddenSignal
            The raw market signal.
        interpretation : SignalInterpretation | None
            Structured interpretation (may be None for low-quality signals).
        decision : DecisionScore
            The composite decision score.
        user_id : str
            For looking up user context (profile, connections).
        """
        company = signal.company_name or "Unknown"
        actions: list[GeneratedAction] = []

        # Extract the best predicted role from interpretation
        role_info = self._best_role(interpretation)
        role_title = role_info.get("role", "Senior Role")
        timeline = role_info.get("timeline", "3_6_months")
        urgency = role_info.get("urgency", "likely")

        # Build the "why now" reason from interpretation context
        reason = self._build_reason(signal, interpretation)

        # Determine timing from timeline
        timing_label = _TIMELINE_TO_TIMING.get(timeline, "this_week")
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=_TIMING_EXPIRY_DAYS.get(timing_label, 14),
        )

        # Hiring owner from interpretation
        owner_title = ""
        owner_dept = ""
        if interpretation:
            owner_title = interpretation.hiring_owner_title or ""
            owner_dept = interpretation.hiring_owner_dept or ""

        # ── 1. LinkedIn Message ──────────────────────────────────────
        if decision.composite_score >= 0.40:
            actions.append(self._linkedin_message(
                company=company,
                role_title=role_title,
                owner_title=owner_title,
                reason=reason,
                timing_label=timing_label,
                expires_at=expires_at,
                decision=decision,
                signal=signal,
            ))

        # ── 2. Email Outreach ────────────────────────────────────────
        if decision.composite_score >= 0.50:
            actions.append(self._email_outreach(
                company=company,
                role_title=role_title,
                owner_title=owner_title,
                owner_dept=owner_dept,
                reason=reason,
                timing_label=timing_label,
                expires_at=expires_at,
                decision=decision,
                signal=signal,
            ))

        # ── 3. Referral Request ──────────────────────────────────────
        if decision.access_strength >= 0.60:
            actions.append(self._referral_request(
                company=company,
                role_title=role_title,
                owner_title=owner_title,
                reason=reason,
                timing_label=timing_label,
                expires_at=expires_at,
                decision=decision,
            ))

        # ── 4. Follow-up Sequence ────────────────────────────────────
        if urgency in ("imminent", "likely") and decision.composite_score >= 0.45:
            actions.append(self._follow_up_sequence(
                company=company,
                role_title=role_title,
                reason=reason,
                timing_label=timing_label,
                expires_at=expires_at,
                decision=decision,
            ))

        logger.info(
            "actions_generated",
            user_id=user_id,
            company=company,
            signal_type=signal.signal_type,
            action_count=len(actions),
            decision_score=decision.composite_score,
        )

        return actions

    async def generate_batch(
        self,
        opportunities: list[tuple],
        user_id: str,
    ) -> list[GeneratedAction]:
        """Generate actions for multiple (signal, interp, decision) tuples.

        Parameters
        ----------
        opportunities : list of (HiddenSignal, SignalInterpretation|None, DecisionScore)
        user_id : str
        """
        all_actions: list[GeneratedAction] = []
        for signal, interp, decision in opportunities:
            actions = await self.generate_actions(
                signal=signal,
                interpretation=interp,
                decision=decision,
                user_id=user_id,
            )
            all_actions.extend(actions)

        # Sort by priority (lower number = higher priority)
        all_actions.sort(key=lambda a: (a.priority, -a.confidence))
        return all_actions

    # ── Action builders ──────────────────────────────────────────────

    @staticmethod
    def _linkedin_message(
        *,
        company: str,
        role_title: str,
        owner_title: str,
        reason: str,
        timing_label: str,
        expires_at: datetime | None,
        decision: DecisionScore,
        signal: HiddenSignal,
    ) -> GeneratedAction:
        target = owner_title or "hiring manager"
        body = (
            f"Hi — I noticed {company} is going through an exciting "
            f"transition. {reason} "
            f"I have relevant experience in {role_title}-level work "
            f"and would love to explore how I could contribute. "
            f"Would you be open to a brief conversation?"
        )

        conf = min(1.0, decision.composite_score * 0.9)

        return GeneratedAction(
            action_type="linkedin_message",
            target_name="",
            target_title=target,
            target_company=company,
            reason=reason,
            message_subject=None,
            message_body=body,
            timing_label=timing_label,
            expires_at=expires_at,
            confidence=round(conf, 4),
            priority=_TYPE_PRIORITY["linkedin_message"],
            decision_score=decision.composite_score,
            channel_metadata={
                "signal_type": signal.signal_type,
                "platform": "linkedin",
            },
        )

    @staticmethod
    def _email_outreach(
        *,
        company: str,
        role_title: str,
        owner_title: str,
        owner_dept: str,
        reason: str,
        timing_label: str,
        expires_at: datetime | None,
        decision: DecisionScore,
        signal: HiddenSignal,
    ) -> GeneratedAction:
        target = owner_title or "Talent Acquisition"
        subject = (
            f"Re: {role_title} opportunity at {company}"
        )
        body = (
            f"Dear {target},\n\n"
            f"I noticed that {company} is {reason.lower()} "
            f"Based on my background, I believe I could add immediate "
            f"value in a {role_title} capacity.\n\n"
            f"I would welcome the chance to discuss how my experience "
            f"aligns with what you are building. "
            f"Would you have 15 minutes this week?\n\n"
            f"Best regards"
        )

        conf = min(1.0, decision.composite_score * 0.85)

        return GeneratedAction(
            action_type="email_outreach",
            target_name="",
            target_title=target,
            target_company=company,
            reason=reason,
            message_subject=subject,
            message_body=body,
            timing_label=timing_label,
            expires_at=expires_at,
            confidence=round(conf, 4),
            priority=_TYPE_PRIORITY["email_outreach"],
            decision_score=decision.composite_score,
            channel_metadata={
                "signal_type": signal.signal_type,
                "department": owner_dept or "unknown",
                "platform": "email",
            },
        )

    @staticmethod
    def _referral_request(
        *,
        company: str,
        role_title: str,
        owner_title: str,
        reason: str,
        timing_label: str,
        expires_at: datetime | None,
        decision: DecisionScore,
    ) -> GeneratedAction:
        body = (
            f"Hi — I am exploring a {role_title} opportunity at "
            f"{company}. {reason} "
            f"Since you have a connection there, would you be open to "
            f"making a warm introduction to the {owner_title or 'team'}? "
            f"I would really appreciate it."
        )

        # Referrals have highest conversion — boost confidence
        conf = min(1.0, decision.composite_score * 1.1)

        return GeneratedAction(
            action_type="referral_request",
            target_name="",
            target_title="mutual connection",
            target_company=company,
            reason=reason,
            message_subject=None,
            message_body=body,
            timing_label=timing_label,
            expires_at=expires_at,
            confidence=round(conf, 4),
            priority=_TYPE_PRIORITY["referral_request"],
            decision_score=decision.composite_score,
            channel_metadata={
                "platform": "referral",
                "referral_target_title": owner_title or "",
            },
        )

    @staticmethod
    def _follow_up_sequence(
        *,
        company: str,
        role_title: str,
        reason: str,
        timing_label: str,
        expires_at: datetime | None,
        decision: DecisionScore,
    ) -> GeneratedAction:
        body = (
            f"Follow-up plan for {role_title} at {company}:\n"
            f"Day 1: Initial outreach (LinkedIn or email)\n"
            f"Day 3: Share relevant insight or article about "
            f"their industry challenge\n"
            f"Day 7: Follow up with specific value proposition\n"
            f"Day 14: Check in with any new developments"
        )

        conf = min(1.0, decision.composite_score * 0.80)

        return GeneratedAction(
            action_type="follow_up_sequence",
            target_name="",
            target_title="hiring team",
            target_company=company,
            reason=reason,
            message_subject=f"Follow-up sequence: {company}",
            message_body=body,
            timing_label=timing_label,
            expires_at=expires_at,
            confidence=round(conf, 4),
            priority=_TYPE_PRIORITY["follow_up_sequence"],
            decision_score=decision.composite_score,
            channel_metadata={
                "platform": "multi_channel",
                "steps": 4,
            },
        )

    # ── Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _best_role(
        interpretation: SignalInterpretation | None,
    ) -> dict:
        """Extract highest-confidence predicted role from interpretation."""
        if not interpretation:
            return {
                "role": "Senior Role",
                "timeline": "3_6_months",
                "urgency": "likely",
            }

        roles = interpretation.predicted_roles or []
        if not roles:
            return {
                "role": "Senior Role",
                "timeline": "3_6_months",
                "urgency": "likely",
            }

        return max(roles, key=lambda r: r.get("confidence", 0))

    @staticmethod
    def _build_reason(
        signal: HiddenSignal,
        interpretation: SignalInterpretation | None,
    ) -> str:
        """Build a human-readable 'why now' justification."""
        if interpretation and interpretation.business_change:
            parts = []
            if interpretation.business_change:
                parts.append(interpretation.business_change.rstrip("."))
            if interpretation.hiring_reason:
                parts.append(interpretation.hiring_reason.rstrip("."))
            return ". ".join(parts) + "."

        # Fallback to signal reasoning
        if signal.reasoning:
            return signal.reasoning[:300]

        return f"{signal.company_name} shows a {signal.signal_type} signal."
