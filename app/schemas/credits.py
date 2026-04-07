"""app/schemas/credits.py"""

import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class CreditBalanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    balance: int
    lifetime_purchased: int
    lifetime_spent: int
    lifetime_earned: int


class CreditTransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    transaction_type: str
    amount: int
    balance_after: int
    action: str | None = None
    reference_id: str | None = None
    description: str | None = None
    created_at: datetime


class AddCreditsRequest(BaseModel):
    amount: int = Field(..., ge=1, le=10000)
    transaction_type: str = "purchase"
    description: str | None = None


class SpendCreditsRequest(BaseModel):
    action: str
    reference_id: str | None = None


class PricingItem(BaseModel):
    action: str
    credits: int
    display: str
