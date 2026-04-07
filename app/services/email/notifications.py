"""
app/services/email/notifications.py

Notification dispatcher — checks user preferences before sending.

Called from Celery workers (sync context) after events:
  - Pack completion
  - Shadow application completion
  - Hidden market signal detection
  - Scout digest (periodic)
"""

import structlog
from app.config import settings

logger = structlog.get_logger(__name__)


def notify_pack_complete(user_id: str, job_run_id: str, role_title: str,
                         company_name: str, score: int | None) -> None:
    """Send pack completion notification if user has it enabled."""
    user = _load_user_sync(user_id)
    if not user:
        return

    prefs = _get_prefs(user)
    if not prefs.get("pack_complete_email", True):
        logger.info("notification_skipped", type="pack_complete", user_id=user_id, reason="disabled")
        return

    from app.services.email.service import get_email_service
    svc = get_email_service()
    pack_url = f"{settings.app_base_url}/applications/{job_run_id}"
    svc.send_pack_complete_email(
        to_email=user.email,
        to_name=user.full_name,
        role_title=role_title or "Role",
        company_name=company_name or "Company",
        score=score,
        pack_url=pack_url,
    )


def notify_shadow_complete(user_id: str, shadow_id: str, company: str, role: str) -> None:
    """Send shadow completion notification if user has it enabled."""
    user = _load_user_sync(user_id)
    if not user:
        return

    prefs = _get_prefs(user)
    if not prefs.get("shadow_ready_email", True):
        return

    from app.services.email.service import get_email_service
    svc = get_email_service()
    shadow_url = f"{settings.app_base_url}/shadow/{shadow_id}"
    svc.send_shadow_ready_email(
        to_email=user.email,
        to_name=user.full_name,
        company=company,
        role=role or "Role",
        shadow_url=shadow_url,
    )


def notify_hidden_market(user_id: str, company: str, signal_type: str,
                         likely_roles: list, reasoning: str) -> None:
    """Send hidden market alert if user has it enabled."""
    user = _load_user_sync(user_id)
    if not user:
        return

    prefs = _get_prefs(user)
    if not prefs.get("hidden_market_email", True):
        return

    from app.services.email.service import get_email_service
    svc = get_email_service()
    dashboard_url = f"{settings.app_base_url}/dashboard"
    svc.send_hidden_market_alert(
        to_email=user.email,
        to_name=user.full_name,
        company=company,
        signal_type=signal_type,
        likely_roles=likely_roles or [],
        reasoning=reasoning or "",
        dashboard_url=dashboard_url,
    )


def _load_user_sync(user_id: str):
    """Load user from DB in sync context (Celery workers)."""
    try:
        from app.workers.db_utils import get_sync_db
        from app.models.user import User
        import uuid
        with get_sync_db() as db:
            return db.get(User, uuid.UUID(user_id))
    except Exception as e:
        logger.warning("notification_user_load_failed", user_id=user_id, error=str(e))
        return None


def _get_prefs(user) -> dict:
    """Extract notification preferences from user model."""
    prefs = getattr(user, "notification_preferences", None)
    if isinstance(prefs, dict):
        return prefs
    return {
        "pack_complete_email": True,
        "scout_digest_email": True,
        "hidden_market_email": True,
        "shadow_ready_email": True,
    }
