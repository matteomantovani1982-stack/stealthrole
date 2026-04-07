"""
app/services/billing/credit_service.py

Credit system — balance management, spending, purchasing, enforcement.
"""

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.credits import CreditBalance, CreditTransaction, CreditAction

logger = structlog.get_logger(__name__)

# ── Credit costs per action ───────────────────────────────────────────────────

ACTION_COSTS: dict[str, int] = {
    CreditAction.GENERATE_CV: 1,
    CreditAction.INTELLIGENCE_PACK: 2,
    CreditAction.HIDDEN_OPPORTUNITY: 3,
    CreditAction.AUTO_APPLY: 2,
    CreditAction.SHADOW_APPLICATION: 3,
    CreditAction.OUTREACH_GENERATE: 1,
    CreditAction.DEEP_EMAIL_SCAN: 2,
}


class InsufficientCreditsError(Exception):
    def __init__(self, required: int, available: int):
        self.required = required
        self.available = available
        super().__init__(f"Need {required} credits, have {available}")


class CreditService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_balance(self, user_id: str) -> CreditBalance:
        result = await self.db.execute(
            select(CreditBalance).where(CreditBalance.user_id == user_id)
        )
        bal = result.scalar_one_or_none()
        if not bal:
            bal = CreditBalance(user_id=user_id, balance=3)  # 3 free credits for new users
            self.db.add(bal)
            await self.db.flush()
            await self.db.commit()
            await self.db.refresh(bal)
        return bal

    async def check_and_spend(
        self, user_id: str, action: str, reference_id: str | None = None
    ) -> CreditTransaction:
        """
        Check balance and deduct credits for an action.
        Raises InsufficientCreditsError if not enough.
        """
        cost = ACTION_COSTS.get(action)
        if cost is None:
            raise ValueError(f"Unknown credit action: {action}")

        bal = await self.get_balance(user_id)
        if bal.balance < cost:
            raise InsufficientCreditsError(required=cost, available=bal.balance)

        bal.balance -= cost
        bal.lifetime_spent += cost

        tx = CreditTransaction(
            user_id=user_id,
            transaction_type="spend",
            amount=-cost,
            balance_after=bal.balance,
            action=action,
            reference_id=reference_id,
            description=f"Spent {cost} credit(s) on {action}",
        )
        self.db.add(tx)
        await self.db.flush()
        await self.db.commit()
        await self.db.refresh(tx)
        return tx

    async def add_credits(
        self, user_id: str, amount: int,
        transaction_type: str = "purchase",
        description: str | None = None,
        reference_id: str | None = None,
    ) -> CreditTransaction:
        """Add credits (purchase, subscription allocation, bonus, refund)."""
        bal = await self.get_balance(user_id)
        bal.balance += amount

        if transaction_type == "purchase":
            bal.lifetime_purchased += amount
        else:
            bal.lifetime_earned += amount

        tx = CreditTransaction(
            user_id=user_id,
            transaction_type=transaction_type,
            amount=amount,
            balance_after=bal.balance,
            description=description or f"Added {amount} credits ({transaction_type})",
            reference_id=reference_id,
        )
        self.db.add(tx)
        await self.db.flush()
        await self.db.commit()
        await self.db.refresh(tx)
        return tx

    async def refund(
        self, user_id: str, action: str, reference_id: str | None = None
    ) -> CreditTransaction:
        """Refund credits for a failed action."""
        cost = ACTION_COSTS.get(action, 1)
        return await self.add_credits(
            user_id, cost,
            transaction_type="refund",
            description=f"Refund {cost} credit(s) for failed {action}",
            reference_id=reference_id,
        )

    async def get_transactions(
        self, user_id: str, limit: int = 50
    ) -> list[CreditTransaction]:
        result = await self.db.execute(
            select(CreditTransaction)
            .where(CreditTransaction.user_id == user_id)
            .order_by(CreditTransaction.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_cost(self, action: str) -> int:
        return ACTION_COSTS.get(action, 0)

    def get_pricing(self) -> list[dict]:
        return [
            {"action": k, "credits": v, "display": k.replace("_", " ").title()}
            for k, v in ACTION_COSTS.items()
        ]
