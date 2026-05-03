"""
app/services/entry/quick_start_engine.py

Quick Start Engine — accepts minimal input (CV text, LinkedIn
URL, or target role) and returns immediate actionable output
bypassing the full setup flow.

Keyword-based ranking
---------------------
When cv_text, linkedin_url, or target_role are provided, the
engine extracts role/seniority/industry/location keywords and
uses them to rank signals by relevance before scoring through
the decision engine.

Returns
-------
  - Top matching signals (existing or freshly scored)
  - Top 3 action recommendations
  - Summary with next steps

Usage
-----
    engine = QuickStartEngine(db)
    result = await engine.quick_start(
        user_id=user_id,
        cv_text="...",
        target_role="Senior Backend Engineer",
    )
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hidden_signal import HiddenSignal
from app.services.action.action_generator import (
    ActionGenerator,
)
from app.services.intelligence.decision_engine import (
    DecisionEngine,
)

logger = structlog.get_logger(__name__)

# Max items returned in quick-start
_MAX_SIGNALS = 5
_MAX_ACTIONS = 3

# Fetch more signals when we need to rank by keywords
_FETCH_POOL = 30

# ── Keyword extraction helpers ────────────────────────────

# Common stop words to exclude from keyword extraction
_STOP_WORDS: set[str] = {
    "a", "an", "the", "and", "or", "but", "in", "on",
    "at", "to", "for", "of", "with", "by", "from", "as",
    "is", "was", "are", "were", "been", "be", "have",
    "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "shall", "can",
    "i", "me", "my", "we", "our", "you", "your", "he",
    "she", "it", "they", "them", "this", "that", "these",
    "those", "not", "no", "so", "if", "about", "up",
    "out", "just", "also", "very", "more", "most",
    "into", "over", "such", "than", "other", "some",
    "all", "any", "each", "every", "both", "few", "many",
    "how", "what", "which", "who", "when", "where", "why",
    "am", "its", "etc", "via",
}

# Seniority/role keywords that boost matching
_SENIORITY_TERMS: set[str] = {
    "junior", "mid", "senior", "lead", "staff",
    "principal", "head", "director", "vp", "cto",
    "ceo", "cfo", "coo", "founder", "manager",
    "intern", "entry", "executive", "chief",
}

# Industry keywords
_INDUSTRY_TERMS: set[str] = {
    "fintech", "healthtech", "edtech", "saas", "ai",
    "ml", "blockchain", "crypto", "ecommerce",
    "logistics", "biotech", "cleantech", "proptech",
    "insuretech", "martech", "adtech", "agritech",
    "deeptech", "cybersecurity", "gaming", "media",
    "consulting", "banking", "insurance", "pharma",
    "automotive", "aerospace", "defence", "energy",
    "telecom", "retail", "manufacturing", "healthcare",
}

_TOKEN_RE = re.compile(r"[a-z0-9+#]+", re.IGNORECASE)


def _tokenise(text: str) -> list[str]:
    """Extract lowercase alpha-numeric tokens."""
    return [
        t.lower()
        for t in _TOKEN_RE.findall(text)
        if len(t) >= 2 and t.lower() not in _STOP_WORDS
    ]


def _extract_keywords(
    cv_text: str | None,
    linkedin_url: str | None,
    target_role: str | None,
    target_companies: list[str] | None,
) -> dict[str, set[str]]:
    """Extract categorised keywords from user input.

    Returns dict with keys:
      role — role/title keywords (highest weight)
      seniority — seniority level terms
      industry — industry/domain terms
      company — company name keywords
      general — everything else
    """
    keywords: dict[str, set[str]] = {
        "role": set(),
        "seniority": set(),
        "industry": set(),
        "company": set(),
        "general": set(),
    }

    all_tokens: list[str] = []

    if target_role:
        role_tokens = _tokenise(target_role)
        all_tokens.extend(role_tokens)
        # All target_role tokens go into role bucket
        keywords["role"].update(role_tokens)

    if cv_text:
        cv_tokens = _tokenise(cv_text)
        all_tokens.extend(cv_tokens)

    if linkedin_url:
        # Extract useful parts from LinkedIn URL
        # e.g. linkedin.com/in/john-doe-backend-eng
        url_tokens = _tokenise(linkedin_url)
        # Filter out common URL noise
        url_noise = {
            "linkedin", "com", "in", "www", "https",
            "http", "pub", "profile",
        }
        url_tokens = [
            t for t in url_tokens
            if t not in url_noise
        ]
        all_tokens.extend(url_tokens)

    if target_companies:
        for company in target_companies:
            comp_tokens = _tokenise(company)
            keywords["company"].update(comp_tokens)

    # Classify remaining tokens
    for token in all_tokens:
        if token in keywords["role"]:
            continue
        if token in _SENIORITY_TERMS:
            keywords["seniority"].add(token)
        elif token in _INDUSTRY_TERMS:
            keywords["industry"].add(token)
        else:
            keywords["general"].add(token)

    return keywords


def _score_signal_relevance(
    signal: HiddenSignal,
    keywords: dict[str, set[str]],
) -> float:
    """Score how relevant a signal is to the keywords.

    Weights:
      company match  — 3.0 per token
      role match     — 2.0 per token
      seniority      — 1.5 per token
      industry       — 1.5 per token
      general        — 1.0 per token

    Searches: company_name, signal_type, likely_roles,
    reasoning, signal_data.
    """
    score = 0.0

    # Build a searchable text blob from the signal
    parts: list[str] = [
        signal.company_name or "",
        signal.signal_type or "",
        signal.reasoning or "",
    ]

    # Extract role names from likely_roles JSONB
    roles = signal.likely_roles or []
    if isinstance(roles, list):
        for entry in roles:
            if isinstance(entry, dict):
                parts.append(
                    entry.get("role", ""),
                )
            elif isinstance(entry, str):
                parts.append(entry)

    # Extract values from signal_data JSONB
    data = signal.signal_data or {}
    if isinstance(data, dict):
        for val in data.values():
            if isinstance(val, str):
                parts.append(val)

    blob = " ".join(parts).lower()
    blob_tokens = set(_tokenise(blob))

    # Score each keyword category
    weights = {
        "company": 3.0,
        "role": 2.0,
        "seniority": 1.5,
        "industry": 1.5,
        "general": 1.0,
    }

    for category, cat_keywords in keywords.items():
        w = weights.get(category, 1.0)
        for kw in cat_keywords:
            if kw in blob_tokens or kw in blob:
                score += w

    return score


class QuickStartEngine:
    """Instant entry — minimal input, immediate value."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def quick_start(
        self,
        user_id: str,
        *,
        cv_text: str | None = None,
        linkedin_url: str | None = None,
        target_role: str | None = None,
        target_companies: list[str] | None = None,
    ) -> dict:
        """Run quick-start flow and return instant results.

        Steps
        -----
        1. Extract keywords from user input
        2. Fetch candidate signals for the user
        3. Rank signals by keyword relevance
        4. Score top signals through the decision engine
        5. Generate actions for the best opportunities
        6. Return a summary with next steps
        """
        # 1 — Extract keywords from all inputs
        keywords = _extract_keywords(
            cv_text=cv_text,
            linkedin_url=linkedin_url,
            target_role=target_role,
            target_companies=target_companies,
        )
        has_keywords = any(
            bool(v) for v in keywords.values()
        )

        logger.info(
            "quick_start_keywords",
            user_id=user_id,
            keyword_counts={
                k: len(v) for k, v in keywords.items()
            },
            has_keywords=has_keywords,
        )

        # 2 — Fetch candidate signals
        signals = await self._fetch_top_signals(
            user_id,
            target_companies,
            fetch_more=has_keywords,
        )

        if not signals:
            return self._empty_result(
                user_id, target_role,
            )

        # 3 — Rank by keyword relevance if we have input
        if has_keywords:
            signals = self._rank_by_relevance(
                signals, keywords,
            )

        # 4 — Score and generate actions
        decision_engine = DecisionEngine(self._db)
        generator = ActionGenerator(self._db)

        scored: list[dict] = []
        all_actions: list[dict] = []

        for signal in signals[:_MAX_SIGNALS]:
            decision = (
                await decision_engine.score_opportunity(
                    signal, user_id,
                )
            )
            scored.append({
                "signal_id": str(signal.id),
                "company": signal.company_name,
                "signal_type": signal.signal_type,
                "confidence": signal.confidence,
                "decision_score": (
                    decision.composite_score
                ),
                "quality_gate": (
                    signal.quality_gate_result
                    or "unknown"
                ),
            })

            # Generate actions for high-scoring signals
            if decision.composite_score >= 0.35:
                actions = (
                    await generator.generate_actions(
                        signal=signal,
                        interpretation=None,
                        decision=decision,
                        user_id=user_id,
                    )
                )
                for a in actions[:_MAX_ACTIONS]:
                    all_actions.append({
                        "action_type": a.action_type,
                        "target_company": (
                            a.target_company
                        ),
                        "reason": a.reason,
                        "timing": a.timing_label,
                        "confidence": a.confidence,
                        "message_preview": (
                            a.message_body[:200]
                        ),
                    })

        # Sort actions by confidence, take top N
        all_actions.sort(
            key=lambda x: x["confidence"],
            reverse=True,
        )
        top_actions = all_actions[:_MAX_ACTIONS]

        return {
            "user_id": user_id,
            "computed_at": (
                datetime.now(timezone.utc).isoformat()
            ),
            "signals": scored,
            "actions": top_actions,
            "summary": self._build_summary(
                scored, top_actions, target_role,
            ),
        }

    async def _fetch_top_signals(
        self,
        user_id: str,
        target_companies: list[str] | None = None,
        *,
        fetch_more: bool = False,
    ) -> list[HiddenSignal]:
        """Fetch candidate signals for ranking.

        When fetch_more is True (keywords available),
        fetches a larger pool so keyword ranking can
        surface the most relevant signals.
        """
        pool_size = (
            _FETCH_POOL if fetch_more
            else _MAX_SIGNALS * 2
        )

        q = (
            select(HiddenSignal)
            .where(
                HiddenSignal.user_id == user_id,
                HiddenSignal.is_dismissed.is_(False),
            )
            .order_by(
                HiddenSignal.confidence.desc(),
                HiddenSignal.created_at.desc(),
            )
            .limit(pool_size)
        )

        if target_companies:
            q = q.where(
                HiddenSignal.company_name.in_(
                    target_companies,
                ),
            )

        result = await self._db.execute(q)
        return list(result.scalars().all())

    @staticmethod
    def _rank_by_relevance(
        signals: list[HiddenSignal],
        keywords: dict[str, set[str]],
    ) -> list[HiddenSignal]:
        """Re-rank signals by keyword relevance score.

        Combines keyword relevance with the original
        confidence to produce a blended ranking.
        Signals with no keyword matches keep their
        original confidence-based position but rank
        below keyword-matched signals.
        """
        scored_pairs: list[
            tuple[float, float, HiddenSignal]
        ] = []

        for signal in signals:
            relevance = _score_signal_relevance(
                signal, keywords,
            )
            # Blend: 60% keyword relevance, 40% confidence
            # Normalise relevance to 0–1 range (cap at 10)
            norm_relevance = min(relevance / 10.0, 1.0)
            blended = (
                0.6 * norm_relevance
                + 0.4 * (signal.confidence or 0.0)
            )
            scored_pairs.append(
                (blended, relevance, signal),
            )

        # Sort by blended score descending
        scored_pairs.sort(
            key=lambda x: x[0], reverse=True,
        )

        logger.debug(
            "quick_start_ranked",
            top_scores=[
                {
                    "company": s.company_name,
                    "relevance": rel,
                    "blended": bl,
                }
                for bl, rel, s in scored_pairs[:5]
            ],
        )

        return [s for _, _, s in scored_pairs]

    @staticmethod
    def _build_summary(
        scored: list[dict],
        actions: list[dict],
        target_role: str | None,
    ) -> dict:
        """Build a human-readable quick-start summary."""
        top_company = (
            scored[0]["company"] if scored else None
        )
        top_action = (
            actions[0]["action_type"] if actions else None
        )

        next_steps: list[str] = []
        if actions:
            next_steps.append(
                f"Review your top action: {top_action}"
                f" at {actions[0].get('target_company', '')}"
            )
        if len(scored) > 1:
            next_steps.append(
                f"Explore {len(scored)} active signals"
            )
        next_steps.append(
            "Complete your profile for better matching"
        )

        return {
            "total_signals": len(scored),
            "total_actions": len(actions),
            "top_company": top_company,
            "recommended_action": top_action,
            "target_role": target_role,
            "next_steps": next_steps,
        }

    @staticmethod
    def _empty_result(
        user_id: str,
        target_role: str | None = None,
    ) -> dict:
        """Return when no signals are available."""
        return {
            "user_id": user_id,
            "computed_at": (
                datetime.now(timezone.utc).isoformat()
            ),
            "signals": [],
            "actions": [],
            "summary": {
                "total_signals": 0,
                "total_actions": 0,
                "top_company": None,
                "recommended_action": None,
                "target_role": target_role,
                "next_steps": [
                    "Upload your CV to get started",
                    "Add target companies to track",
                ],
            },
        }
