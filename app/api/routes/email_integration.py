"""
app/api/routes/email_integration.py

Email Integration endpoints — connect Gmail/Outlook, sync, view extracted signals.

Routes:
  POST   /api/v1/email-integration/connect         Get OAuth URL
  POST   /api/v1/email-integration/callback         OAuth callback (exchange code)
  GET    /api/v1/email-integration/accounts         List connected accounts
  DELETE /api/v1/email-integration/accounts/{id}    Disconnect account
  POST   /api/v1/email-integration/accounts/{id}/sync   Trigger manual sync
  GET    /api/v1/email-integration/scans            List extracted signals
  POST   /api/v1/email-integration/scans/{id}/link  Link signal to application
  POST   /api/v1/email-integration/scans/{id}/dismiss  Dismiss false positive
"""

import uuid

import structlog
from fastapi import APIRouter, HTTPException, status

from app.dependencies import DB, CurrentUserId
from app.config import settings
from app.schemas.email_integration import (
    DismissScanRequest,
    EmailAccountList,
    EmailAccountResponse,
    EmailCallbackRequest,
    EmailConnectRequest,
    EmailConnectResponse,
    EmailScanList,
    EmailScanResponse,
    LinkScanRequest,
    SyncResponse,
)
from app.services.email_integration.scan_service import EmailIntegrationService
from app.services.email_integration.providers import get_provider

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/api/v1/email-integration",
    tags=["Email Integration"],
)


def _svc(db: DB) -> EmailIntegrationService:
    return EmailIntegrationService(db=db)


def _redirect_uri() -> str:
    """Build the OAuth redirect URI — points to frontend callback page.
    Must NOT include query params — Google requires exact match with registered URI.
    """
    return f"{settings.app_base_url}/auth/callback"


# ── OAuth flow ────────────────────────────────────────────────────────────────

@router.post(
    "/connect",
    response_model=EmailConnectResponse,
    summary="Get OAuth URL to connect an email account",
)
async def connect_email(
    payload: EmailConnectRequest,
    user_id: CurrentUserId,
) -> EmailConnectResponse:
    # Validate provider credentials are configured
    if payload.provider == "gmail" and not settings.google_client_id:
        raise HTTPException(
            status_code=501,
            detail="Gmail integration not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.",
        )
    if payload.provider == "outlook" and not settings.microsoft_client_id:
        raise HTTPException(
            status_code=501,
            detail="Outlook integration not configured. Set MICROSOFT_CLIENT_ID and MICROSOFT_CLIENT_SECRET.",
        )

    provider = get_provider(payload.provider)
    redirect_uri = _redirect_uri()
    # Encode provider in state so callback knows which provider to use
    state = f"{user_id}:{payload.provider}"
    auth_url = provider.get_auth_url(redirect_uri=redirect_uri, state=state)

    return EmailConnectResponse(auth_url=auth_url, provider=payload.provider)


@router.post(
    "/callback",
    response_model=EmailAccountResponse,
    summary="Complete OAuth flow — exchange code for tokens",
)
async def oauth_callback(
    payload: EmailCallbackRequest,
    db: DB,
    user_id: CurrentUserId,
) -> EmailAccountResponse:
    provider = get_provider(payload.provider)
    redirect_uri = _redirect_uri()

    try:
        tokens = await provider.exchange_code(
            code=payload.code,
            redirect_uri=redirect_uri,
        )
    except Exception as e:
        logger.error("oauth_exchange_failed", provider=payload.provider, error=str(e))
        raise HTTPException(
            status_code=400,
            detail=f"Failed to complete OAuth: {e}",
        )

    # Get the user's email address from the provider
    try:
        email_address = await provider.get_user_email(tokens.access_token)
    except Exception as e:
        logger.error("email_fetch_failed", error=str(e))
        raise HTTPException(status_code=400, detail="Failed to retrieve email address")

    # Store the account
    service = _svc(db)
    account = await service.connect_account(
        user_id=user_id,
        provider=payload.provider,
        tokens=tokens,
        email_address=email_address,
    )

    # Auto-trigger sync + deep scan
    try:
        from app.workers.tasks.email_sync import sync_email_account
        sync_email_account.delay(str(account.id))
        logger.info("auto_sync_triggered", account_id=str(account.id))
    except Exception as e:
        logger.warning("auto_sync_trigger_failed", error=str(e))

    try:
        from app.workers.tasks.email_intelligence import run_deep_scan
        run_deep_scan.delay(user_id)
        logger.info("auto_deep_scan_triggered", user_id=user_id)
    except Exception as e:
        logger.warning("auto_deep_scan_trigger_failed", error=str(e))

    return account


# ── Account management ───────────────────────────────────────────────────────

@router.get(
    "/accounts",
    response_model=EmailAccountList,
    summary="List connected email accounts",
)
async def list_accounts(
    db: DB,
    user_id: CurrentUserId,
) -> EmailAccountList:
    accounts = await _svc(db).list_accounts(user_id=user_id)
    return EmailAccountList(accounts=accounts, total=len(accounts))


@router.delete(
    "/accounts/{account_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Disconnect an email account",
)
async def disconnect_account(
    account_id: uuid.UUID,
    db: DB,
    user_id: CurrentUserId,
) -> None:
    deleted = await _svc(db).disconnect_account(account_id=account_id, user_id=user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Account not found")


# ── Sync ──────────────────────────────────────────────────────────────────────

@router.post(
    "/accounts/{account_id}/sync",
    response_model=SyncResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger manual email sync",
)
async def trigger_sync(
    account_id: uuid.UUID,
    db: DB,
    user_id: CurrentUserId,
) -> SyncResponse:
    # Verify account belongs to user
    service = _svc(db)
    accounts = await service.list_accounts(user_id=user_id)
    if not any(a.id == account_id for a in accounts):
        raise HTTPException(status_code=404, detail="Account not found")

    # Dispatch Celery task
    from app.workers.tasks.email_sync import sync_email_account
    task = sync_email_account.delay(str(account_id))

    return SyncResponse(
        message="Sync started",
        account_id=account_id,
        task_id=task.id,
    )


# ── Scans (extracted signals) ────────────────────────────────────────────────

@router.get(
    "/scans",
    response_model=EmailScanList,
    summary="List extracted application signals from emails",
)
async def list_scans(
    db: DB,
    user_id: CurrentUserId,
    include_dismissed: bool = False,
) -> EmailScanList:
    return await _svc(db).list_scans(
        user_id=user_id,
        include_dismissed=include_dismissed,
    )


@router.post(
    "/scans/{scan_id}/link",
    response_model=EmailScanResponse,
    summary="Link an email signal to an application (or auto-create one)",
)
async def link_scan(
    scan_id: uuid.UUID,
    payload: LinkScanRequest,
    db: DB,
    user_id: CurrentUserId,
) -> EmailScanResponse:
    result = await _svc(db).link_scan_to_application(
        scan_id=scan_id,
        user_id=user_id,
        application_id=payload.application_id,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Scan not found")
    return result


@router.post(
    "/scans/{scan_id}/dismiss",
    response_model=EmailScanResponse,
    summary="Dismiss a scan as a false positive",
)
async def dismiss_scan(
    scan_id: uuid.UUID,
    payload: DismissScanRequest,
    db: DB,
    user_id: CurrentUserId,
) -> EmailScanResponse:
    result = await _svc(db).dismiss_scan(
        scan_id=scan_id,
        user_id=user_id,
        dismissed=payload.is_dismissed,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Scan not found")
    return result
