"""
app/models/hidden_signal.py

Hidden Market signal — detected before a job is posted.

Signal types:
  - funding: company raised capital
  - leadership: C-suite change
  - expansion: new office/market
  - product_launch: new product = new team
  - hiring_surge: spike in postings
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class HiddenSignal(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "hidden_signals"

    user_id: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True,
    )
    company_name: Mapped[str] = mapped_column(
        String(255), nullable=False,
    )
    signal_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
    )
    confidence: Mapped[float] = mapped_column(
        Float, nullable=False,
    )
    likely_roles: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]",
    )
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    source_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Phase 2: structured enrichment data
    signal_data: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment="Structured enrichment: funding_amount, investors, person_name, etc.",
    )
    evidence_tier: Mapped[str | None] = mapped_column(
        String(20), nullable=True, default="medium", server_default="medium",
        comment="Signal evidence quality: strong | medium | weak | speculative",
    )
    provider: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
        comment="Data provider: crunchbase | magnitt | serper | adzuna",
    )

    is_dismissed: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false",
    )

    # ── Signal Quality Filter (Phase 1 — Signal Intelligence Layer) ───────
    quality_score: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="Composite quality score (0.0–1.0). Null for pre-feature signals.",
    )
    quality_confidence: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="Confidence component of quality score",
    )
    quality_recency: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="Recency component of quality score",
    )
    quality_relevance: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="User-specific relevance component of quality score",
    )
    quality_historical: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="Historical success rate component (blended user + global)",
    )
    quality_gate_result: Mapped[str | None] = mapped_column(
        String(20), nullable=True,
        comment="pass | conditional | store_only | reject",
    )
    quality_computed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="When quality score was computed",
    )

    # ── Prediction tracking ───────────────────────────────────────────────
    prediction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True,
        comment="FK to predicted_opportunities when signal generates prediction",
    )
    outcome_tracked: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false",
        comment="Whether this signal has been connected to a terminal outcome",
    )
    outcome_result: Mapped[str | None] = mapped_column(
        String(20), nullable=True,
        comment="interview | hire | rejection | no_response | null",
    )

    def __repr__(self) -> str:
        return (
            f"<HiddenSignal id={self.id} company={self.company_name} "
            f"type={self.signal_type} conf={self.confidence}>"
        )
