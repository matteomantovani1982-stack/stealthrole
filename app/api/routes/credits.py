"""
app/api/routes/credits.py

Credit system endpoints.

Routes:
  GET    /api/v1/credits/balance        Current balance
  GET    /api/v1/credits/transactions   Transaction history
  POST   /api/v1/credits/add            Add credits (purchase/bonus)
  POST   /api/v1/credits/spend          Spend credits on an action
  GET    /api/v1/credits/pricing        Credit costs per action
"""

from fastapi import APIRouter, HTTPException, Query, status

from app.dependencies import DB, CurrentUserId
from app.schemas.credits import (
    AddCreditsRequest,
    CreditBalanceResponse,
    CreditTransactionResponse,
    PricingItem,
    SpendCreditsRequest,
)
from app.services.billing.credit_service import CreditService, InsufficientCreditsError

router = APIRouter(prefix="/api/v1/credits", tags=["Credits"])


def _svc(db: DB) -> CreditService:
    return CreditService(db=db)


@router.get("/balance", response_model=CreditBalanceResponse, summary="Get credit balance")
async def get_balance(db: DB, user_id: CurrentUserId) -> CreditBalanceResponse:
    bal = await _svc(db).get_balance(user_id)
    await db.commit()  # Commit if new balance was auto-provisioned
    return CreditBalanceResponse.model_validate(bal)


@router.get("/transactions", response_model=list[CreditTransactionResponse], summary="Transaction history")
async def get_transactions(
    db: DB,
    user_id: CurrentUserId,
    limit: int = Query(default=50, ge=1, le=500, description="Max items to return"),
    offset: int = Query(default=0, ge=0, description="Items to skip"),
) -> list[CreditTransactionResponse]:
    txs = await _svc(db).get_transactions(user_id, limit=limit, offset=offset)
    return [CreditTransactionResponse.model_validate(t) for t in txs]


@router.post(
    "/add",
    response_model=CreditTransactionResponse,
    summary="Add credits (dev/admin only)",
    include_in_schema=False,
)
async def add_credits(
    payload: AddCreditsRequest, db: DB, user_id: CurrentUserId
) -> CreditTransactionResponse:
    from app.config import settings
    if not getattr(settings, "demo_mode", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Credit grants are only available in demo mode.",
        )
    tx = await _svc(db).add_credits(
        user_id, payload.amount, payload.transaction_type, payload.description,
    )
    await db.commit()
    return CreditTransactionResponse.model_validate(tx)


@router.post("/spend", response_model=CreditTransactionResponse, summary="Spend credits on an action")
async def spend_credits(
    payload: SpendCreditsRequest, db: DB, user_id: CurrentUserId
) -> CreditTransactionResponse:
    try:
        tx = await _svc(db).check_and_spend(user_id, payload.action, payload.reference_id)
    except InsufficientCreditsError as e:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient credits: need {e.required}, have {e.available}",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await db.commit()
    return CreditTransactionResponse.model_validate(tx)


@router.get("/pricing", response_model=list[PricingItem], summary="Credit costs per action")
async def get_pricing(db: DB, user_id: CurrentUserId) -> list[PricingItem]:
    return [PricingItem(**p) for p in _svc(db).get_pricing()]
