"""
app/services/email_integration/scan_service.py

Orchestrates email account management, syncing, and signal extraction.
"""

import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.email_account import EmailAccount, SyncStatus
from app.models.email_scan import EmailScan
from app.models.application import Application
from app.schemas.email_integration import (
    EmailAccountResponse,
    EmailScanList,
    EmailScanResponse,
)
from app.services.email_integration.crypto import encrypt_token, decrypt_token
from app.services.email_integration.extractor import extract_signal
from app.services.email_integration.providers import get_provider, OAuthTokens

logger = structlog.get_logger(__name__)


class EmailIntegrationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Account management ────────────────────────────────────────────────

    async def connect_account(
        self,
        user_id: str,
        provider: str,
        tokens: OAuthTokens,
        email_address: str,
    ) -> EmailAccountResponse:
        """Store a newly connected email account with encrypted tokens."""
        # Check for existing account (upsert)
        result = await self.db.execute(
            select(EmailAccount).where(
                EmailAccount.user_id == user_id,
                EmailAccount.provider == provider,
            )
        )
        account = result.scalar_one_or_none()

        if account:
            # Update existing
            account.access_token_encrypted = encrypt_token(tokens.access_token)
            if tokens.refresh_token:
                account.refresh_token_encrypted = encrypt_token(tokens.refresh_token)
            account.token_expires_at = tokens.expires_at
            account.email_address = email_address
            account.is_active = True
            account.last_sync_error = None
        else:
            account = EmailAccount(
                user_id=user_id,
                provider=provider,
                email_address=email_address,
                access_token_encrypted=encrypt_token(tokens.access_token),
                refresh_token_encrypted=(
                    encrypt_token(tokens.refresh_token) if tokens.refresh_token else None
                ),
                token_expires_at=tokens.expires_at,
            )
            self.db.add(account)

        await self.db.flush()
        await self.db.commit()
        await self.db.refresh(account)
        return EmailAccountResponse.model_validate(account)

    async def list_accounts(self, user_id: str) -> list[EmailAccountResponse]:
        result = await self.db.execute(
            select(EmailAccount)
            .where(EmailAccount.user_id == user_id)
            .order_by(EmailAccount.created_at)
        )
        return [EmailAccountResponse.model_validate(a) for a in result.scalars().all()]

    async def disconnect_account(self, account_id: uuid.UUID, user_id: str) -> bool:
        result = await self.db.execute(
            select(EmailAccount).where(
                EmailAccount.id == account_id,
                EmailAccount.user_id == user_id,
            )
        )
        account = result.scalar_one_or_none()
        if not account:
            return False
        account.is_active = False
        try:
            account.access_token_encrypted = encrypt_token("revoked")
        except (RuntimeError, Exception):
            account.access_token_encrypted = "revoked"
        account.refresh_token_encrypted = None
        await self.db.commit()
        return True

    # ── Sync ──────────────────────────────────────────────────────────────

    async def sync_account(self, account_id: uuid.UUID) -> int:
        """
        Sync a single email account: fetch new emails, extract signals.
        Returns number of new signals found.
        """
        result = await self.db.execute(
            select(EmailAccount).where(EmailAccount.id == account_id)
        )
        account = result.scalar_one_or_none()
        if not account or not account.is_active:
            return 0

        # Update status
        account.sync_status = SyncStatus.SYNCING
        await self.db.flush()

        try:
            # Refresh token if needed
            access_token = await self._ensure_valid_token(account)

            # Fetch messages
            provider = get_provider(account.provider)
            messages, new_cursor = await provider.fetch_messages(
                access_token=access_token,
                cursor=account.sync_cursor,
                max_results=100,
            )

            # Process each message
            new_signals = 0
            for msg in messages:
                # Check for duplicate (already scanned this message)
                existing = await self.db.execute(
                    select(EmailScan).where(
                        EmailScan.email_account_id == account.id,
                        EmailScan.message_id == msg.message_id,
                    )
                )
                if existing.scalar_one_or_none():
                    continue

                # Extract signal
                signal = extract_signal(msg)
                if signal is None:
                    continue

                scan = EmailScan(
                    email_account_id=account.id,
                    message_id=msg.message_id,
                    email_from=msg.sender,
                    email_subject=msg.subject,
                    email_date=msg.date,
                    email_snippet=msg.snippet,
                    company=signal.company,
                    role=signal.role,
                    detected_stage=signal.detected_stage,
                    confidence=signal.confidence,
                )
                self.db.add(scan)
                new_signals += 1

            # Update account state
            account.sync_status = SyncStatus.IDLE
            account.last_synced_at = datetime.now(UTC)
            account.last_sync_error = None
            if new_cursor:
                account.sync_cursor = new_cursor
            account.total_scanned += len(messages)
            account.total_signals += new_signals

            await self.db.flush()
            await self.db.commit()

            logger.info(
                "email_sync_complete",
                account_id=str(account.id),
                messages=len(messages),
                signals=new_signals,
            )
            return new_signals

        except Exception as e:
            account.sync_status = SyncStatus.FAILED
            account.last_sync_error = str(e)[:500]
            await self.db.commit()
            logger.error(
                "email_sync_failed",
                account_id=str(account.id),
                error=str(e),
            )
            raise

    async def _ensure_valid_token(self, account: EmailAccount) -> str:
        """Check if access token is expired, refresh if needed."""
        now = datetime.now(UTC)

        if account.token_expires_at and account.token_expires_at > now:
            return decrypt_token(account.access_token_encrypted)

        # Token expired — refresh
        if not account.refresh_token_encrypted:
            raise ValueError("Access token expired and no refresh token available")

        refresh_token = decrypt_token(account.refresh_token_encrypted)
        provider = get_provider(account.provider)
        new_tokens = await provider.refresh_access(refresh_token)

        account.access_token_encrypted = encrypt_token(new_tokens.access_token)
        if new_tokens.refresh_token:
            account.refresh_token_encrypted = encrypt_token(new_tokens.refresh_token)
        account.token_expires_at = new_tokens.expires_at
        await self.db.flush()

        return new_tokens.access_token

    # ── Scans ─────────────────────────────────────────────────────────────

    async def list_scans(
        self, user_id: str, include_dismissed: bool = False,
    ) -> EmailScanList:
        """List extracted signals for a user's connected accounts."""
        # Get user's account IDs
        accounts_result = await self.db.execute(
            select(EmailAccount.id).where(EmailAccount.user_id == user_id)
        )
        account_ids = [row[0] for row in accounts_result.all()]
        if not account_ids:
            return EmailScanList(scans=[], total=0, unlinked=0)

        query = (
            select(EmailScan)
            .where(EmailScan.email_account_id.in_(account_ids))
        )
        if not include_dismissed:
            query = query.where(EmailScan.is_dismissed == False)  # noqa: E712

        query = query.order_by(EmailScan.email_date.desc())
        result = await self.db.execute(query)
        scans = result.scalars().all()

        unlinked = sum(1 for s in scans if s.application_id is None and not s.is_dismissed)

        return EmailScanList(
            scans=[EmailScanResponse.model_validate(s) for s in scans],
            total=len(scans),
            unlinked=unlinked,
        )

    async def link_scan_to_application(
        self,
        scan_id: uuid.UUID,
        user_id: str,
        application_id: uuid.UUID | None = None,
    ) -> EmailScanResponse | None:
        """
        Link a scan to an Application. If application_id is None,
        create a new Application from the scan data.
        """
        # Verify scan belongs to user
        scan = await self._get_user_scan(scan_id, user_id)
        if not scan:
            return None

        if application_id is None:
            # Auto-create Application from scan
            app = Application(
                user_id=user_id,
                company=scan.company or "Unknown",
                role=scan.role or "Unknown",
                date_applied=scan.email_date,
                source_channel="email",
                stage=scan.detected_stage if scan.detected_stage != "unknown" else "applied",
            )
            self.db.add(app)
            await self.db.flush()
            application_id = app.id

        scan.application_id = application_id
        await self.db.flush()
        await self.db.commit()
        await self.db.refresh(scan)
        return EmailScanResponse.model_validate(scan)

    async def dismiss_scan(
        self, scan_id: uuid.UUID, user_id: str, dismissed: bool = True,
    ) -> EmailScanResponse | None:
        scan = await self._get_user_scan(scan_id, user_id)
        if not scan:
            return None
        scan.is_dismissed = dismissed
        await self.db.flush()
        await self.db.commit()
        await self.db.refresh(scan)
        return EmailScanResponse.model_validate(scan)

    async def _get_user_scan(self, scan_id: uuid.UUID, user_id: str) -> EmailScan | None:
        """Get a scan that belongs to one of the user's accounts."""
        result = await self.db.execute(
            select(EmailScan)
            .join(EmailAccount, EmailScan.email_account_id == EmailAccount.id)
            .where(
                EmailScan.id == scan_id,
                EmailAccount.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()
