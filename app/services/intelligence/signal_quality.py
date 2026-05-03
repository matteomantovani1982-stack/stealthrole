"""
app/services/intelligence/signal_quality.py

Signal Quality Filter — Phase 2 of Signal Intelligence Layer.

Scores every HiddenSignal with a composite quality metric before it
enters the prediction / interpretation pipeline.

Formula
-------
quality_score = confidence(35%) + recency(25%) + relevance(25%)
              + historical_success(15%)

Each component is normalised to 0.0–1.0 before weighting.

Gate thresholds
---------------
  pass        ≥ 0.60  →  proceed to interpretation + prediction
  conditional 0.40–0.59 → proceed with reduced priority
  store_only  0.20–0.39 → persist for analytics, skip prediction
  reject      < 0.20   → discard (do not persist)

Stacking bonus
--------------
When multiple signals exist for the same company, each additional
distinct signal type adds a bonus (capped at +0.15).

Usage
-----
    from app.services.intelligence.signal_quality import (
        SignalQualityFilter,
    )

    qf = SignalQualityFilter(db)
    result = await qf.score_signal(signal, user_id)
    # result.gate == "pass" | "conditional" | "store_only" | "reject"

    # Batch scoring after a scan:
    results = await qf.score_batch(signals, user_id)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import func, select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.hidden_signal import HiddenSignal

logger = structlog.get_logger(__name__)

# ── Weights ──────────────────────────────────────────────────────────────────
W_CONFIDENCE = 0.35
W_RECENCY = 0.25
W_RELEVANCE = 0.25
W_HISTORICAL = 0.15

# ── Gate thresholds ──────────────────────────────────────────────────────────
GATE_PASS = 0.60
GATE_CONDITIONAL = 0.40
GATE_STORE_ONLY = 0.20
# Below GATE_STORE_ONLY → reject

# ── Stacking bonus per additional signal type on the same company ────────────
STACK_BONUS_PER_TYPE = 0.05
STACK_BONUS_CAP = 0.15

# ── Recency decay: half-life in days (signal value halves every N days) ──────
RECENCY_HALF_LIFE_DAYS = 30

# ── Evidence tier → base confidence floor ────────────────────────────────────
_TIER_FLOOR: dict[str, float] = {
    "strong": 0.70,
    "medium": 0.50,
    "weak": 0.30,
    "speculative": 0.10,
}

# ── Signal types with strong hiring correlation ──────────────────────────────
_HIGH_RELEVANCE_TYPES = frozenset({
    "funding", "leadership", "expansion", "ma_activity",
    "board_change", "hiring_surge",
})
_MEDIUM_RELEVANCE_TYPES = frozenset({
    "product_launch", "velocity", "pain_signal", "structural",
})


@dataclass(frozen=True, slots=True)
class QualityResult:
    """Immutable result of a quality scoring pass."""

    quality_score: float
    confidence_component: float
    recency_component: float
    relevance_component: float
    historical_component: float
    gate: str  # pass | conditional | store_only | reject
    stacking_bonus: float


class SignalQualityFilter:
    """Score and gate hidden-market signals."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Public API ───────────────────────────────────────────────────────

    async def score_signal(
        self,
        signal: HiddenSignal,
        user_id: str,
        *,
        company_signal_count: int | None = None,
    ) -> QualityResult:
        """Score a single signal and persist the quality columns.

        Parameters
        ----------
        signal:
            The HiddenSignal ORM instance to score.
        user_id:
            Owner of the signal (used for relevance lookup).
        company_signal_count:
            Pre-computed count of distinct signal types for the same
            company.  When ``None`` the filter queries the database.
        """
        # Component: confidence (0–1)
        confidence = self._score_confidence(signal)

        # Component: recency (0–1)
        recency = self._score_recency(signal)

        # Component: relevance (0–1)
        relevance = await self._score_relevance(signal, user_id)

        # Component: historical success (0–1)
        historical = await self._score_historical(
            signal.signal_type, user_id,
        )

        # Stacking bonus
        if company_signal_count is None:
            company_signal_count = await self._count_company_signals(
                signal.company_name, user_id,
            )
        stack_bonus = min(
            STACK_BONUS_CAP,
            max(0, company_signal_count - 1) * STACK_BONUS_PER_TYPE,
        )

        # Composite
        raw = (
            W_CONFIDENCE * confidence
            + W_RECENCY * recency
            + W_RELEVANCE * relevance
            + W_HISTORICAL * historical
            + stack_bonus
        )
        quality_score = round(min(1.0, max(0.0, raw)), 4)

        gate = self._apply_gate(quality_score)

        result = QualityResult(
            quality_score=quality_score,
            confidence_component=round(confidence, 4),
            recency_component=round(recency, 4),
            relevance_component=round(relevance, 4),
            historical_component=round(historical, 4),
            gate=gate,
            stacking_bonus=round(stack_bonus, 4),
        )

        # Persist to signal columns
        self._persist(signal, result)

        logger.debug(
            "signal_quality_scored",
            signal_id=str(signal.id),
            score=quality_score,
            gate=gate,
            conf=confidence,
            rec=recency,
            rel=relevance,
            hist=historical,
            stack=stack_bonus,
        )

        return result

    async def score_batch(
        self,
        signals: list[HiddenSignal],
        user_id: str,
    ) -> list[QualityResult]:
        """Score a list of signals, pre-computing stacking counts."""
        # Pre-compute company signal counts in one pass
        company_counts: dict[str, int] = {}
        for sig in signals:
            key = sig.company_name.lower().strip()
            company_counts[key] = company_counts.get(key, 0) + 1

        # Also count existing signals per company from the database
        existing = await self._count_company_signals_batch(
            list(company_counts.keys()), user_id,
        )
        for key, count in existing.items():
            company_counts[key] = company_counts.get(key, 0) + count

        results: list[QualityResult] = []
        for sig in signals:
            key = sig.company_name.lower().strip()
            result = await self.score_signal(
                sig, user_id,
                company_signal_count=company_counts.get(key, 1),
            )
            results.append(result)

        return results

    # ── Component scorers ────────────────────────────────────────────────

    @staticmethod
    def _score_confidence(signal: HiddenSignal) -> float:
        """Confidence component based on signal's own confidence +
        evidence tier floor."""
        raw = signal.confidence or 0.5
        tier = signal.evidence_tier or "medium"
        floor = _TIER_FLOOR.get(tier, 0.30)
        return max(floor, min(1.0, raw))

    @staticmethod
    def _score_recency(signal: HiddenSignal) -> float:
        """Exponential decay from creation date with configurable
        half-life."""
        created = signal.created_at
        if created is None:
            return 0.3  # unknown age → conservative

        now = datetime.now(timezone.utc)
        if created.tzinfo is None:
            # Assume UTC for naive datetimes
            age_days = (now.replace(tzinfo=None) - created).days
        else:
            age_days = (now - created).days

        if age_days <= 0:
            return 1.0

        # Exponential decay: score = 2^(-age/half_life)
        decay = math.pow(2, -age_days / RECENCY_HALF_LIFE_DAYS)
        return round(max(0.0, min(1.0, decay)), 4)

    async def _score_relevance(
        self,
        signal: HiddenSignal,
        user_id: str,
    ) -> float:
        """Relevance component: signal type weight + user preference
        alignment."""
        # Base: signal type relevance
        sig_type = signal.signal_type or ""
        if sig_type in _HIGH_RELEVANCE_TYPES:
            base = 0.80
        elif sig_type in _MEDIUM_RELEVANCE_TYPES:
            base = 0.55
        else:
            base = 0.35

        # Boost if signal's likely_roles overlap user's target roles
        pref_boost = await self._preference_boost(signal, user_id)
        return min(1.0, base + pref_boost)

    async def _preference_boost(
        self,
        signal: HiddenSignal,
        user_id: str,
    ) -> float:
        """Check if signal's likely_roles or sector overlap user
        preferences. Returns 0.0–0.20 boost."""
        try:
            from app.services.profile.profile_service import (
                ProfileService,
            )

            svc = ProfileService(self._db)
            profile = await svc.get_active_profile(user_id)
            if not profile or not profile.preferences:
                return 0.0

            prefs = profile.preferences
            boost = 0.0

            # Role overlap
            target_roles = [
                r.lower() for r in prefs.get("roles", [])
            ]
            likely_roles = signal.likely_roles or []
            if target_roles and likely_roles:
                for role in likely_roles:
                    role_lower = (
                        role.lower()
                        if isinstance(role, str)
                        else str(role).lower()
                    )
                    if any(tr in role_lower or role_lower in tr
                           for tr in target_roles):
                        boost += 0.10
                        break

            # Sector overlap
            target_sectors = [
                s.lower() for s in prefs.get("sectors", [])
            ]
            signal_data = signal.signal_data or {}
            sig_sector = (
                signal_data.get("sector", "") or ""
            ).lower()
            if target_sectors and sig_sector:
                if any(ts in sig_sector or sig_sector in ts
                       for ts in target_sectors):
                    boost += 0.10

            return min(0.20, boost)

        except Exception as exc:
            logger.warning(
                "quality_preference_boost_failed",
                error=str(exc),
            )
            return 0.0

    async def _score_historical(
        self,
        signal_type: str,
        user_id: str,
    ) -> float:
        """Historical success rate for this signal type from the
        user's learning profile. Falls back to a neutral 0.50 when
        no data exists."""
        try:
            from app.models.user_intelligence import UserIntelligence

            q = select(UserIntelligence).where(
                UserIntelligence.user_id == user_id,
            )
            row = (await self._db.execute(q)).scalar_one_or_none()
            if not row or not row.learning_profile:
                return 0.50  # neutral prior

            sig_eff = row.learning_profile.get(
                "signal_effectiveness", {},
            )
            entry = sig_eff.get(signal_type)
            if not entry:
                return 0.50

            rate = entry.get("success_rate", 0.50)
            count = entry.get("sample_count", 0)
            if count < 3:
                # Not enough data — blend toward neutral
                weight = count / 3
                return 0.50 * (1 - weight) + rate * weight

            return max(0.0, min(1.0, rate))

        except Exception as exc:
            logger.warning(
                "quality_historical_failed", error=str(exc),
            )
            return 0.50

    # ── Stacking helpers ─────────────────────────────────────────────────

    async def _count_company_signals(
        self,
        company_name: str,
        user_id: str,
    ) -> int:
        """Count distinct signal types for a company in the user's
        recent signals (last 90 days)."""
        from datetime import timedelta

        from app.models.hidden_signal import HiddenSignal

        cutoff = datetime.now(timezone.utc) - timedelta(days=90)
        q = (
            select(
                func.count(func.distinct(HiddenSignal.signal_type)),
            )
            .where(
                func.lower(HiddenSignal.company_name)
                == company_name.lower().strip(),
                HiddenSignal.user_id == user_id,
                HiddenSignal.created_at >= cutoff,
                HiddenSignal.is_dismissed.is_(False),
            )
        )
        result = await self._db.execute(q)
        return result.scalar() or 1

    async def _count_company_signals_batch(
        self,
        company_keys: list[str],
        user_id: str,
    ) -> dict[str, int]:
        """Batch version of _count_company_signals."""
        if not company_keys:
            return {}

        from datetime import timedelta

        from app.models.hidden_signal import HiddenSignal

        cutoff = datetime.now(timezone.utc) - timedelta(days=90)
        q = (
            select(
                func.lower(HiddenSignal.company_name),
                func.count(
                    func.distinct(HiddenSignal.signal_type),
                ),
            )
            .where(
                func.lower(HiddenSignal.company_name).in_(
                    company_keys,
                ),
                HiddenSignal.user_id == user_id,
                HiddenSignal.created_at >= cutoff,
                HiddenSignal.is_dismissed.is_(False),
            )
            .group_by(func.lower(HiddenSignal.company_name))
        )
        rows = (await self._db.execute(q)).all()
        return {row[0]: row[1] for row in rows}

    # ── Gate ─────────────────────────────────────────────────────────────

    @staticmethod
    def _apply_gate(score: float) -> str:
        """Map composite score to gate tier."""
        if score >= GATE_PASS:
            return "pass"
        if score >= GATE_CONDITIONAL:
            return "conditional"
        if score >= GATE_STORE_ONLY:
            return "store_only"
        return "reject"

    # ── Persistence ──────────────────────────────────────────────────────

    @staticmethod
    def _persist(signal: HiddenSignal, result: QualityResult) -> None:
        """Write quality scores back to the signal's ORM columns.

        The caller (route or service) owns the ``db.commit()``.
        """
        signal.quality_score = result.quality_score
        signal.quality_confidence = result.confidence_component
        signal.quality_recency = result.recency_component
        signal.quality_relevance = result.relevance_component
        signal.quality_historical = result.historical_component
        signal.quality_gate_result = result.gate
        signal.quality_computed_at = datetime.now(timezone.utc)
