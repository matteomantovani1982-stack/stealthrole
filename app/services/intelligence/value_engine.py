"""
app/services/intelligence/value_engine.py

Value / ROI Engine — makes the system visibly valuable by analysing
outcomes, signals, and actions to surface insights and recommendations.

Responsibilities
----------------
  - Success rate per signal type
  - Success rate per action type
  - Best-performing paths (warm intro vs direct apply vs recruiter)
  - Time-to-response metrics
  - Personalised recommendations based on user's history

Integrates with
---------------
  - outcome_tracker: raw outcome data
  - learning_updater: per-user learning profile
  - action_recommendations: action lifecycle data

Usage
-----
    engine = ValueEngine(db)
    insights = await engine.compute_insights(user_id)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import case, func, select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from app.models.action_recommendation import ActionRecommendation
from app.models.hidden_signal import HiddenSignal

logger = structlog.get_logger(__name__)

# ── Insight types ────────────────────────────────────────────────────
INSIGHT_SIGNAL_EFFECTIVENESS = "signal_effectiveness"
INSIGHT_ACTION_EFFECTIVENESS = "action_effectiveness"
INSIGHT_PATH_PERFORMANCE = "path_performance"
INSIGHT_TIMING = "timing"
INSIGHT_RECOMMENDATION = "recommendation"


class ValueEngine:
    """Analyses outcomes to surface ROI insights."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def compute_insights(
        self,
        user_id: str,
    ) -> dict:
        """Compute comprehensive value insights for a user.

        Returns a dict with signal effectiveness, action
        effectiveness, best paths, timing data, and
        recommendations.
        """
        signal_stats = await self._signal_effectiveness(user_id)
        action_stats = await self._action_effectiveness(user_id)
        path_stats = await self._path_performance(user_id)
        timing_stats = await self._timing_insights(user_id)
        summary = self._build_summary(
            signal_stats, action_stats, path_stats,
        )
        recommendations = self._generate_recommendations(
            signal_stats, action_stats, path_stats,
        )

        return {
            "user_id": user_id,
            "computed_at": (
                datetime.now(timezone.utc).isoformat()
            ),
            "signal_effectiveness": signal_stats,
            "action_effectiveness": action_stats,
            "path_performance": path_stats,
            "timing": timing_stats,
            "summary": summary,
            "recommendations": recommendations,
        }

    # ── Signal effectiveness ─────────────────────────────────────────

    async def _signal_effectiveness(
        self,
        user_id: str,
    ) -> list[dict]:
        """Success rate per signal type.

        Groups signals by type, counts outcomes, and computes
        the positive outcome rate (interview + hire).
        """
        q = (
            select(
                HiddenSignal.signal_type,
                func.count().label("total"),
                func.count(
                    case(
                        (
                            HiddenSignal.outcome_result.in_(
                                ["interview", "hire"],
                            ),
                            1,
                        ),
                    ),
                ).label("positive"),
                func.count(
                    case(
                        (
                            HiddenSignal.outcome_result == "hire",
                            1,
                        ),
                    ),
                ).label("hires"),
            )
            .where(
                HiddenSignal.user_id == user_id,
                HiddenSignal.outcome_tracked.is_(True),
            )
            .group_by(HiddenSignal.signal_type)
            .order_by(func.count().desc())
        )
        rows = (await self._db.execute(q)).all()

        results = []
        for row in rows:
            total = row.total or 1
            results.append({
                "signal_type": row.signal_type,
                "total_signals": total,
                "positive_outcomes": row.positive or 0,
                "hires": row.hires or 0,
                "success_rate": round(
                    (row.positive or 0) / total, 4,
                ),
                "hire_rate": round(
                    (row.hires or 0) / total, 4,
                ),
            })
        return results

    # ── Action effectiveness ─────────────────────────────────────────

    async def _action_effectiveness(
        self,
        user_id: str,
    ) -> list[dict]:
        """Success rate per action type.

        Measures how often each action type leads to a response.
        """
        q = (
            select(
                ActionRecommendation.action_type,
                func.count().label("total"),
                func.count(
                    case(
                        (
                            ActionRecommendation.status
                            == "responded",
                            1,
                        ),
                    ),
                ).label("responded"),
                func.count(
                    case(
                        (
                            ActionRecommendation.status == "sent",
                            1,
                        ),
                    ),
                ).label("sent"),
                func.count(
                    case(
                        (
                            ActionRecommendation.status
                            == "dismissed",
                            1,
                        ),
                    ),
                ).label("dismissed"),
            )
            .where(
                ActionRecommendation.user_id == user_id,
            )
            .group_by(ActionRecommendation.action_type)
            .order_by(func.count().desc())
        )
        rows = (await self._db.execute(q)).all()

        results = []
        for row in rows:
            total = row.total or 1
            sent = row.sent or 0
            responded = row.responded or 0
            results.append({
                "action_type": row.action_type,
                "total_generated": total,
                "sent": sent,
                "responded": responded,
                "dismissed": row.dismissed or 0,
                "response_rate": round(
                    responded / max(sent + responded, 1),
                    4,
                ),
                "execution_rate": round(
                    (sent + responded) / total, 4,
                ),
            })
        return results

    # ── Path performance ─────────────────────────────────────────────

    async def _path_performance(
        self,
        user_id: str,
    ) -> list[dict]:
        """Best-performing paths from action channel metadata."""
        from app.models.user_intelligence import UserIntelligence

        q = select(UserIntelligence).where(
            UserIntelligence.user_id == user_id,
        )
        row = (
            await self._db.execute(q)
        ).scalar_one_or_none()

        if not row or not row.learning_profile:
            return []

        path_data = row.learning_profile.get(
            "path_success", {},
        )
        results = []
        for path_name, stats in path_data.items():
            if not isinstance(stats, dict):
                continue
            results.append({
                "path": path_name,
                "success_rate": stats.get(
                    "success_rate", 0.0,
                ),
                "sample_count": stats.get(
                    "sample_count", 0,
                ),
            })

        results.sort(
            key=lambda x: x["success_rate"], reverse=True,
        )
        return results

    # ── Timing insights ──────────────────────────────────────────────

    async def _timing_insights(
        self,
        user_id: str,
    ) -> dict:
        """Compute average time from signal to action to response."""
        # Average time from action created to sent
        sent_q = (
            select(
                func.avg(
                    func.extract(
                        "epoch",
                        ActionRecommendation.sent_at
                        - ActionRecommendation.created_at,
                    ),
                ).label("avg_to_send"),
            )
            .where(
                ActionRecommendation.user_id == user_id,
                ActionRecommendation.sent_at.isnot(None),
            )
        )
        sent_row = (await self._db.execute(sent_q)).one()
        avg_to_send = sent_row.avg_to_send

        # Average time from sent to responded
        resp_q = (
            select(
                func.avg(
                    func.extract(
                        "epoch",
                        ActionRecommendation.responded_at
                        - ActionRecommendation.sent_at,
                    ),
                ).label("avg_to_respond"),
            )
            .where(
                ActionRecommendation.user_id == user_id,
                ActionRecommendation.responded_at.isnot(None),
            )
        )
        resp_row = (await self._db.execute(resp_q)).one()
        avg_to_respond = resp_row.avg_to_respond

        return {
            "avg_hours_to_send": (
                round(avg_to_send / 3600, 1)
                if avg_to_send
                else None
            ),
            "avg_hours_to_respond": (
                round(avg_to_respond / 3600, 1)
                if avg_to_respond
                else None
            ),
        }

    # ── Summary ──────────────────────────────────────────────────────

    @staticmethod
    def _build_summary(
        signal_stats: list[dict],
        action_stats: list[dict],
        path_stats: list[dict],
    ) -> dict:
        """Build a high-level summary from component stats."""
        total_signals = sum(
            s["total_signals"] for s in signal_stats
        )
        total_positive = sum(
            s["positive_outcomes"] for s in signal_stats
        )
        total_hires = sum(
            s["hires"] for s in signal_stats
        )
        total_actions = sum(
            a["total_generated"] for a in action_stats
        )
        total_responses = sum(
            a["responded"] for a in action_stats
        )

        best_signal = (
            max(
                signal_stats,
                key=lambda s: s["success_rate"],
            )["signal_type"]
            if signal_stats
            else None
        )
        best_path = (
            path_stats[0]["path"]
            if path_stats
            else None
        )

        return {
            "total_signals_tracked": total_signals,
            "total_positive_outcomes": total_positive,
            "total_hires": total_hires,
            "overall_success_rate": round(
                total_positive / max(total_signals, 1), 4,
            ),
            "total_actions_generated": total_actions,
            "total_responses": total_responses,
            "best_signal_type": best_signal,
            "best_path": best_path,
        }

    # ── Recommendations ──────────────────────────────────────────────

    @staticmethod
    def _generate_recommendations(
        signal_stats: list[dict],
        action_stats: list[dict],
        path_stats: list[dict],
    ) -> list[dict]:
        """Generate actionable recommendations from the data."""
        recs: list[dict] = []

        # Recommend best signal type
        if signal_stats:
            best = max(
                signal_stats,
                key=lambda s: s["success_rate"],
            )
            if best["success_rate"] > 0:
                recs.append({
                    "type": INSIGHT_RECOMMENDATION,
                    "title": (
                        f"Focus on {best['signal_type']}"
                        " signals"
                    ),
                    "detail": (
                        f"{best['signal_type']} signals have "
                        f"a {best['success_rate']:.0%} success "
                        f"rate — your best performing type."
                    ),
                    "priority": "high",
                })

        # Recommend best action type
        if action_stats:
            active = [
                a for a in action_stats
                if a["responded"] > 0
            ]
            if active:
                best_action = max(
                    active,
                    key=lambda a: a["response_rate"],
                )
                recs.append({
                    "type": INSIGHT_RECOMMENDATION,
                    "title": (
                        f"Use more "
                        f"{best_action['action_type']}"
                        " actions"
                    ),
                    "detail": (
                        f"{best_action['action_type']} "
                        f"has a "
                        f"{best_action['response_rate']:.0%}"
                        f" response rate."
                    ),
                    "priority": "high",
                })

        # Recommend best path
        if path_stats and path_stats[0]["success_rate"] > 0:
            best_path = path_stats[0]
            recs.append({
                "type": INSIGHT_RECOMMENDATION,
                "title": (
                    f"Prioritise "
                    f"{best_path['path']} path"
                ),
                "detail": (
                    f"Your {best_path['path']} path has "
                    f"a {best_path['success_rate']:.0%} "
                    f"success rate based on "
                    f"{best_path['sample_count']} "
                    f"outcomes."
                ),
                "priority": "medium",
            })

        # Low-performing signal warning
        for sig in signal_stats:
            if (
                sig["total_signals"] >= 5
                and sig["success_rate"] < 0.10
            ):
                recs.append({
                    "type": INSIGHT_RECOMMENDATION,
                    "title": (
                        f"Reconsider "
                        f"{sig['signal_type']} signals"
                    ),
                    "detail": (
                        f"{sig['signal_type']} signals "
                        f"have a low "
                        f"{sig['success_rate']:.0%} "
                        f"success rate across "
                        f"{sig['total_signals']} tracked "
                        f"signals."
                    ),
                    "priority": "low",
                })

        return recs
