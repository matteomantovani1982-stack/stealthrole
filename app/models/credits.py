"""
app/models/credits.py

Credit-based monetization system.

Users buy credit packs or earn through subscriptions.
Each action costs credits. Balance is enforced before execution.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class CreditAction(StrEnum):
    """Actions that cost credits."""
    GENERATE_CV = "generate_cv"             # 1 credit
    INTELLIGENCE_PACK = "intelligence_pack"  # 2 credits
    HIDDEN_OPPORTUNITY = "hidden_opportunity"  # 3 credits
    AUTO_APPLY = "auto_apply"               # 2 credits
    SHADOW_APPLICATION = "shadow_application"  # 3 credits
    OUTREACH_GENERATE = "outreach_generate"   # 1 credit
    DEEP_EMAIL_SCAN = "deep_email_scan"       # 2 credits


class TransactionType(StrEnum):
    PURCHASE = "purchase"       # Bought credits
    SUBSCRIPTION = "subscription"  # Monthly allocation
    SPEND = "spend"             # Used on an action
    REFUND = "refund"           # Action failed, credits returned
    BONUS = "bonus"             # Referral, promo, etc.


class CreditBalance(Base, UUIDMixin, TimestampMixin):
    """User's current credit balance."""
    __tablename__ = "credit_balances"

    user_id: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True,
    )
    balance: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
        comment="Current credit balance",
    )
    lifetime_purchased: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
    )
    lifetime_spent: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
    )
    lifetime_earned: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
        comment="From referrals, bonuses, subscription allocations",
    )

    def __repr__(self) -> str:
        return f"<CreditBalance user={self.user_id} balance={self.balance}>"


class CreditTransaction(Base, UUIDMixin, TimestampMixin):
    """Immutable ledger of all credit transactions."""
    __tablename__ = "credit_transactions"

    user_id: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True,
    )
    transaction_type: Mapped[str] = mapped_column(
        String(30), nullable=False,
        comment="purchase | subscription | spend | refund | bonus",
    )
    amount: Mapped[int] = mapped_column(
        Integer, nullable=False,
        comment="Positive = credit added, negative = credit spent",
    )
    balance_after: Mapped[int] = mapped_column(
        Integer, nullable=False,
        comment="Balance after this transaction",
    )
    action: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
        comment="Which action consumed credits (for spend type)",
    )
    reference_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        comment="Job run ID, submission ID, etc.",
    )
    description: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
    )

    def __repr__(self) -> str:
        return f"<CreditTransaction type={self.transaction_type} amount={self.amount}>"
