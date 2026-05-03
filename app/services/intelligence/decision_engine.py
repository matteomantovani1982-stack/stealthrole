"""
app/services/intelligence/decision_engine.py

Decision Engine — Phase 7 of Signal Intelligence Layer.

The final recommendation scorer that produces a composite score
blending user-specific learning, global intelligence, and signal
quality into a single recommendation priority.

Composite formula
-----------------
  raw = profile_fit(30%) + signal_strength(20%)
      + company_responsiveness(15%) + access_strength(15%)
      + timing(10%) + recency(10%)

Hybrid blending
---------------
The ``signal_strength`` and ``company_responsiveness`` components
use a blended weight from user-specific and global learning:

  BLENDED = (user_weight × user_rate) + (global_weight × global_rate)

Weight schedule (by user's learning_sample_count):
  Tier 0:  0-4 samples   → 0% user, 100% global
  Tier 1:  5-9 samples   → 20% user, 80% global
  Tier 2: 10-19 samples  → 50% user, 50% global
  Tier 3: 20-49 samples  → 80% user, 20% global
  Tier 4: 50+ samples    → 95% user, 5% global

User overrides
--------------
If the user's learning_profile has an ``overrides`` entry for a
dimension:key, the global adjustment is ignored and the user's
own rate is used at 100% weight.

Fast feedback
-------------
When the user's ``short_term_memory`` contains recent positive
outcomes for a signal_type or company, a fast-feedback boost
(+0.10) is applied.

Usage
-----
    engine = DecisionEngine(db)
    score = await engine.score_opportunity(
        signal=signal,
        user_id=user_id,
        profile_fit=0.75,
        access_strength=0.60,
    )
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.hidden_signal import HiddenSignal

logger = structlog.get_logger(__name__)

# ── Composite weights ────────────────────────────────────────────────
W_PROFILE_FIT = 0.30
W_SIGNAL_STRENGTH = 0.20
W_COMPANY_RESP = 0.15
W_ACCESS = 0.15
W_TIMING = 0.10
W_RECENCY = 0.10

# ── Blend weight schedule ────────────────────────────────────────────
_BLEND_TIERS: list[tuple[int, float, float]] = [
    # (min_samples, user_weight, global_weight)
    (50, 0.95, 0.05),
    (20, 0.80, 0.20),
    (10, 0.50, 0.50),
    (5, 0.20, 0.80),
    (0, 0.00, 1.00),
]

# Fast feedback boost
FAST_FEEDBACK_BOOST = 0.10
FAST_FEEDBACK_WINDOW_HOURS = 72


@dataclass(frozen=True, slots=True)
class DecisionScore:
    """Immutable result of a decision engine scoring pass."""

    composite_score: float
    profile_fit: float
    signal_strength: float
    company_responsiveness: float
    access_strength: float
    timing: float
    recency: float
    fast_feedback_boost: float
    blend_tier: int
    user_weight: float
    global_weight: float


class DecisionEngine:
    """Final recommendation scorer with hybrid blending."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def score_opportunity(
        self,
        signal: HiddenSignal,
        user_id: str,
        *,
        profile_fit: float = 0.50,
        access_strength: float = 0.50,
    ) -> DecisionScore:
        """Score a single signal/opportunity for recommendation
        priority.

        Parameters
        ----------
        signal : HiddenSignal
        user_id : str
        profile_fit : float
            Pre-computed profile fit from radar scorer (0–1).
        access_strength : float
            How strong the user's access path is (warm intro,
            direct connection, etc.). 0–1.
        """
        # Load user intelligence
        ui = await self._load_user_intelligence(user_id)
        learning = ui.get("learning_profile", {}) if ui else {}
        sample_count = (
            ui.get("learning_sample_count", 0) if ui else 0
        )
        stm = ui.get("short_term_memory", []) if ui else []

        # Determine blend weights
        tier, u_weight, g_weight = _get_blend_weights(
            sample_count,
        )

        # Signal strength (blended)
        sig_type = signal.signal_type or ""
        user_sig_rate = _user_rate(
            learning, "signal_effectiveness", sig_type,
        )
        global_sig_adj = await self._get_global_rate(
            "signal_type", sig_type,
        )

        # Check user override
        overrides = learning.get("overrides", {})
        override_key = f"signal_type:{sig_type}"
        if overrides.get(override_key):
            sig_strength = user_sig_rate
        else:
            sig_strength = _blend(
                user_sig_rate, global_sig_adj,
                u_weight, g_weight,
            )

        # Company responsiveness (blended)
        company = (signal.company_name or "").lower().strip()
        user_co_rate = _user_rate(
            learning, "contact_type", "any",
        )
        global_co_adj = await self._get_global_rate(
            "company", company,
        )
        co_override = f"company:{company}"
        if overrides.get(co_override):
            company_resp = user_co_rate
        else:
            company_resp = _blend(
                user_co_rate, global_co_adj,
                u_weight, g_weight,
            )

        # Timing
        timing = self._score_timing(signal)

        # Recency
        recency = self._score_recency(signal)

        # Fast feedback boost
        fb_boost = _fast_feedback_boost(
            stm, sig_type, company,
        )

        # Composite
        raw = (
            W_PROFILE_FIT * profile_fit
            + W_SIGNAL_STRENGTH * sig_strength
            + W_COMPANY_RESP * company_resp
            + W_ACCESS * access_strength
            + W_TIMING * timing
            + W_RECENCY * recency
            + fb_boost
        )
        composite = round(
            min(1.0, max(0.0, raw)), 4,
        )

        return DecisionScore(
            composite_score=composite,
            profile_fit=round(profile_fit, 4),
            signal_strength=round(sig_strength, 4),
            company_responsiveness=round(company_resp, 4),
            access_strength=round(access_strength, 4),
            timing=round(timing, 4),
            recency=round(recency, 4),
            fast_feedback_boost=round(fb_boost, 4),
            blend_tier=tier,
            user_weight=u_weight,
            global_weight=g_weight,
        )

    async def score_batch(
        self,
        signals: list[HiddenSignal],
        user_id: str,
        *,
        profile_fits: dict | None = None,
        access_strengths: dict | None = None,
    ) -> list[DecisionScore]:
        """Score a batch of signals. Pre-loads user intelligence
        once for efficiency."""
        results: list[DecisionScore] = []
        for sig in signals:
            sig_id = str(sig.id)
            pf = (
                profile_fits.get(sig_id, 0.50)
                if profile_fits
                else 0.50
            )
            acc = (
                access_strengths.get(sig_id, 0.50)
                if access_strengths
                else 0.50
            )
            score = await self.score_opportunity(
                sig, user_id,
                profile_fit=pf,
                access_strength=acc,
            )
            results.append(score)
        return results

    # ── Helpers ──────────────────────────────────────────────────────

    async def _load_user_intelligence(
        self, user_id: str,
    ) -> dict | None:
        """Load user intelligence as a dict."""
        from app.models.user_intelligence import UserIntelligence

        q = select(UserIntelligence).where(
            UserIntelligence.user_id == user_id,
        )
        row = (
            await self._db.execute(q)
        ).scalar_one_or_none()

        if row is None:
            return None

        return {
            "learning_profile": row.learning_profile or {},
            "learning_sample_count": (
                row.learning_sample_count or 0
            ),
            "short_term_memory": row.short_term_memory or [],
        }

    async def _get_global_rate(
        self,
        dimension: str,
        key: str,
    ) -> float:
        """Get effective global adjustment for dimension/key."""
        try:
            from app.services.intelligence.propagation_engine import (
                PropagationEngine,
            )

            engine = PropagationEngine(self._db)
            adj = await engine.get_effective_adjustment(
                dimension, key,
            )
            # Convert adjustment to a rate-like value (0–1)
            # Adjustments are deltas (-0.50 to +0.50),
            # shift to 0.50 baseline
            return max(0.0, min(1.0, 0.50 + adj))
        except Exception:
            return 0.50  # neutral

    @staticmethod
    def _score_timing(signal: HiddenSignal) -> float:
        """Score based on signal quality gate and confidence."""
        gate = signal.quality_gate_result or "conditional"
        gate_score = {
            "pass": 0.90,
            "conditional": 0.60,
            "store_only": 0.30,
            "reject": 0.10,
        }.get(gate, 0.50)

        conf = signal.confidence or 0.5
        return (gate_score * 0.6) + (conf * 0.4)

    @staticmethod
    def _score_recency(signal: HiddenSignal) -> float:
        """Recency score with 30-day half-life."""
        import math

        created = signal.created_at
        if created is None:
            return 0.30

        now = datetime.now(timezone.utc)
        if created.tzinfo is None:
            age_days = (now.replace(tzinfo=None) - created).days
        else:
            age_days = (now - created).days

        if age_days <= 0:
            return 1.0

        return round(
            max(0.0, min(1.0, math.pow(2, -age_days / 30))),
            4,
        )


def _get_blend_weights(
    sample_count: int,
) -> tuple[int, float, float]:
    """Return (tier, user_weight, global_weight) based on
    the user's sample count."""
    for i, (min_n, uw, gw) in enumerate(_BLEND_TIERS):
        if sample_count >= min_n:
            return len(_BLEND_TIERS) - 1 - i, uw, gw
    return 0, 0.0, 1.0


def _user_rate(
    learning: dict,
    dimension: str,
    key: str,
) -> float:
    """Extract user's success rate for a dimension/key."""
    section = learning.get(dimension, {})
    if key == "any":
        # Average across all entries
        rates = [
            e.get("success_rate", 0.5)
            for e in section.values()
            if isinstance(e, dict)
        ]
        return sum(rates) / len(rates) if rates else 0.50

    entry = section.get(key, {})
    if isinstance(entry, dict):
        return entry.get("success_rate", 0.50)
    return 0.50


def _blend(
    user_rate: float,
    global_rate: float,
    user_weight: float,
    global_weight: float,
) -> float:
    """Blend user and global rates."""
    return (user_weight * user_rate) + (
        global_weight * global_rate
    )


def _fast_feedback_boost(
    stm: list,
    signal_type: str,
    company: str,
) -> float:
    """Check short-term memory for recent positive outcomes
    matching this signal type or company.

    Returns FAST_FEEDBACK_BOOST if a positive match is found
    within the window, else 0.0.
    """
    if not stm:
        return 0.0

    cutoff = datetime.now(timezone.utc) - timedelta(
        hours=FAST_FEEDBACK_WINDOW_HOURS,
    )

    for event in reversed(stm):
        # Parse timestamp
        ts_str = event.get("timestamp", "")
        if not ts_str:
            continue
        try:
            ts = datetime.fromisoformat(ts_str)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue

        if ts < cutoff:
            continue

        outcome = event.get("outcome", "")
        if outcome not in ("interview", "hire"):
            continue

        # Match by signal type or company
        ev_sig = event.get("signal_type", "")
        ev_co = (event.get("company", "") or "").lower()

        if (
            (signal_type and ev_sig == signal_type)
            or (company and ev_co and company in ev_co)
            or (company and ev_co and ev_co in company)
        ):
            return FAST_FEEDBACK_BOOST

    return 0.0
