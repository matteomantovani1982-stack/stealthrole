"""
app/workers/tasks/scout_scan.py

Celery task: daily proactive scout scan for all active users.

Runs as a periodic task (via Celery Beat) — scans market signals
for each user who has job preferences configured, caches results
in scout_results table, and marks previous results as stale.

Users see fresh results when they next open the Scout dashboard.
"""

import uuid
from datetime import UTC, datetime

import structlog
from celery import Task

from app.workers.celery_app import celery
from app.workers.db_utils import get_sync_db

logger = structlog.get_logger(__name__)


@celery.task(
    bind=True,
    name="app.workers.tasks.scout_scan.daily_scout_scan",
    max_retries=0,
    soft_time_limit=900,   # 15 min total for all users
    time_limit=960,
)
def daily_scout_scan(self: Task) -> dict:
    """
    Scan market signals for ALL active users with preferences.

    For each user:
    1. Load their job preferences (roles, regions, sectors)
    2. Run the signal engine
    3. Cache results in scout_results table

    Runs daily via Celery Beat schedule.
    """
    log = logger.bind(task_id=self.request.id)
    log.info("daily_scout_scan_started")

    # Find all users with preferences configured
    with get_sync_db() as db:
        from app.models.candidate_profile import CandidateProfile
        from sqlalchemy import select
        import json as _json

        result = db.execute(
            select(CandidateProfile).where(
                CandidateProfile.global_context.isnot(None),
            )
        )
        profiles = result.scalars().all()

        users_to_scan = []
        for p in profiles:
            try:
                ctx = _json.loads(p.global_context or "{}")
                prefs = ctx.get("__preferences", {})
                # Only scan if they have at least roles or regions set
                if prefs.get("roles") or prefs.get("regions"):
                    users_to_scan.append({
                        "user_id": p.user_id,
                        "profile": {
                            "headline": p.headline or "",
                            "global_context": p.global_context or "",
                        },
                        "preferences": prefs,
                    })
            except Exception:
                continue

    log.info("users_to_scan", count=len(users_to_scan))

    if not users_to_scan:
        return {"status": "no_users", "scanned": 0}

    scanned = 0
    errors = 0

    for user_data in users_to_scan:
        user_id = user_data["user_id"]
        try:
            from app.services.scout.signal_engine import run_signal_engine

            result = run_signal_engine(
                preferences=user_data["preferences"],
                user_profile=user_data["profile"],
                max_results=15,
            )

            # Skip demo results
            if result.get("is_demo"):
                continue

            # Cache result in DB
            with get_sync_db() as db:
                from app.models.scout_result import ScoutResult
                from sqlalchemy import update

                # Mark previous results as stale
                db.execute(
                    update(ScoutResult)
                    .where(ScoutResult.user_id == user_id, ScoutResult.is_stale == False)
                    .values(is_stale=True)
                )

                # Insert new result
                prefs = user_data["preferences"]
                sr = ScoutResult(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    opportunities=result.get("opportunities", []),
                    live_openings=result.get("live_openings", []),
                    signals_detected=result.get("signals_detected", 0),
                    sources_searched=result.get("sources_searched", 0),
                    scored_by=result.get("scored_by", ""),
                    regions=prefs.get("regions", []),
                    roles=prefs.get("roles", []),
                    sectors=prefs.get("sectors", []),
                    is_stale=False,
                )
                db.add(sr)
                db.commit()

            scanned += 1
            log.info("user_scanned", user_id=user_id,
                     signals=result.get("signals_detected", 0),
                     opportunities=len(result.get("opportunities", [])))

            # Send WhatsApp alerts for top opportunities
            _send_wa_alerts(user_id, result.get("opportunities", []), log)

        except Exception as e:
            errors += 1
            log.warning("user_scan_failed", user_id=user_id, error=str(e))

    log.info("daily_scout_scan_complete", scanned=scanned, errors=errors)
    return {"status": "complete", "scanned": scanned, "errors": errors}


def _send_wa_alerts(user_id: str, opportunities: list, log):
    """Send WhatsApp alerts for high-match opportunities."""
    from app.models.user import User
    from app.config import settings

    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        return

    with get_sync_db() as db:
        from sqlalchemy import select
        user = db.execute(select(User).where(User.id == uuid.UUID(user_id))).scalar_one_or_none()
        if not user or not user.whatsapp_verified or not user.whatsapp_number:
            return
        if user.whatsapp_alert_mode == "OFF":
            return

        # Determine alert limit
        limits = {"CASUAL": 1, "MODERATE": 3, "ACTIVE": 5, "UNLIMITED": 999}
        max_alerts = limits.get(user.whatsapp_alert_mode, 1)

        # Filter by minimum threshold (default 70%)
        threshold = 70
        top = [o for o in opportunities if o.get("fit_score", 0) >= threshold][:max_alerts]

        if not top:
            return

        try:
            from twilio.rest import Client
            client = Client(settings.twilio_account_sid, settings.twilio_auth_token)

            for opp in top:
                score = opp.get("fit_score", 0)
                fire = "🔥" if score >= 85 else "⚡" if score >= 70 else "📋"
                signals = opp.get("signals", [])
                signal_types = list(set(s.get("signal_type", "") for s in signals if isinstance(s, dict)))

                app_base = getattr(settings, "app_base_url", "http://localhost:3000") or "http://localhost:3000"
                msg = (
                    f"{fire} *Hidden opportunity detected*\n\n"
                    f"*{opp.get('suggested_role', 'Role')}*\n"
                    f"📍 {opp.get('company', '?')}\n"
                    f"🎯 Match: *{score}%*\n"
                )
                if len(signal_types) > 1:
                    msg += f"📡 {len(signal_types)} signals: {' + '.join(t.replace('_',' ').title() for t in signal_types)}\n"
                msg += f"\n👉 View & generate Intelligence Pack:\n{app_base}/scout\n"
                msg += f"\n_1 pack = 3 credits — tailored CV, strategy, salary, contacts_"

                # Normalize phone number to E.164
                phone = user.whatsapp_number.replace(" ", "").replace("-", "")
                if phone.startswith("0") and not phone.startswith("00"):
                    phone = "+971" + phone[1:]
                if not phone.startswith("+"):
                    phone = "+" + phone

                client.messages.create(
                    body=msg,
                    from_=settings.twilio_whatsapp_from,
                    to=f"whatsapp:{phone}",
                )
                log.info("wa_alert_sent", user_id=user_id, company=opp.get("company"), score=score)

            # Track quota
            user.whatsapp_weekly_quota_used = (user.whatsapp_weekly_quota_used or 0) + len(top)
            db.commit()

        except Exception as e:
            log.warning("wa_alerts_failed", user_id=user_id, error=str(e))


@celery.task(
    bind=True,
    name="app.workers.tasks.scout_scan.send_realtime_wa_alert",
    max_retries=2,
    soft_time_limit=60,
    time_limit=90,
)
def send_realtime_wa_alert(self: Task, user_id: str, opportunities: list) -> dict:
    """
    Send a real-time WhatsApp alert when a user runs Unleash the Scout
    and new opportunities are found.

    Throttle: only send if no alert sent in the last 2 hours
    (prevents spam if user clicks Unleash multiple times).
    """
    from sqlalchemy import select
    from datetime import timedelta
    from app.config import settings
    from app.models.user import User

    log = logger.bind(user_id=user_id, task="realtime_wa_alert")

    if not (settings.twilio_account_sid and settings.twilio_auth_token):
        log.info("twilio_not_configured")
        return {"sent": 0, "reason": "no_twilio"}

    if not opportunities:
        return {"sent": 0, "reason": "no_opportunities"}

    with get_sync_db() as db:
        user = db.execute(select(User).where(User.id == uuid.UUID(user_id))).scalar_one_or_none()
        if not user or not user.whatsapp_verified or not user.whatsapp_number:
            return {"sent": 0, "reason": "no_verified_number"}
        if user.whatsapp_alert_mode == "OFF":
            return {"sent": 0, "reason": "alerts_off"}

        # Throttle via Redis: skip if we sent an alert in the last 2 hours
        try:
            import redis
            r = redis.Redis.from_url(settings.redis_url, decode_responses=True)
            throttle_key = f"wa_alert_throttle:{user_id}"
            if r.get(throttle_key):
                return {"sent": 0, "reason": "throttled"}
        except Exception:
            r = None  # Continue without throttle if Redis unavailable

        # Send the top 3 opportunities only
        top = opportunities[:3]
        if not top:
            return {"sent": 0, "reason": "no_top"}

        try:
            from twilio.rest import Client
            client = Client(settings.twilio_account_sid, settings.twilio_auth_token)

            # Normalize phone
            phone = user.whatsapp_number.replace(" ", "").replace("-", "")
            if phone.startswith("0") and not phone.startswith("00"):
                phone = "+971" + phone[1:]
            if not phone.startswith("+"):
                phone = "+" + phone

            # Build a single combined message with all top opportunities
            app_base = getattr(settings, "app_base_url", "https://stealthrole.com") or "https://stealthrole.com"
            lines = ["🔥 *New opportunities detected*\n"]
            for i, opp in enumerate(top, 1):
                score = opp.get("fit_score") or opp.get("radar_score") or 0
                role = opp.get("suggested_role") or opp.get("role") or "Senior role"
                company = opp.get("company", "Unknown")
                lines.append(f"{i}. *{role}* at {company} — {score}% match")
            lines.append(f"\n👉 View & generate Intelligence Pack:\n{app_base}/scout")

            client.messages.create(
                body="\n".join(lines),
                from_=settings.twilio_whatsapp_from,
                to=f"whatsapp:{phone}",
            )

            # Set throttle in Redis (2 hours)
            try:
                if r:
                    r.setex(throttle_key, 7200, "1")
                user.whatsapp_weekly_quota_used = (user.whatsapp_weekly_quota_used or 0) + 1
                db.commit()
            except Exception:
                pass

            log.info("realtime_wa_alert_sent", count=len(top))
            return {"sent": len(top)}

        except Exception as e:
            log.warning("realtime_wa_alert_failed", error=str(e))
            return {"sent": 0, "error": str(e)}
