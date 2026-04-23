"""
app/api/routes/health.py

Health check endpoints for liveness, readiness, and deep system status.
"""

from datetime import UTC, datetime

import structlog
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import settings
from app.db.session import AsyncSessionLocal

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", summary="Liveness probe")
async def health_check() -> dict:
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
        "env": settings.app_env,
        "deploy_marker": "2026-04-22-v4-discover-people",
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/ready", summary="Readiness probe (DB + Redis)")
async def readiness_check():
    checks: dict = {}

    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = {"status": "ok"}
    except Exception as e:
        checks["database"] = {"status": "error", "error": str(e)}
        logger.error("health_db_failed", error=str(e))

    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.redis_url, socket_connect_timeout=2)
        await r.ping()
        await r.aclose()
        checks["redis"] = {"status": "ok"}
    except Exception as e:
        checks["redis"] = {"status": "error", "error": str(e)}

    overall = "ok" if all(c["status"] == "ok" for c in checks.values()) else "degraded"
    return JSONResponse(
        status_code=200 if overall == "ok" else 503,
        content={"status": overall, "checks": checks, "timestamp": datetime.now(UTC).isoformat()},
    )


@router.get("/deep", summary="Deep system check")
async def deep_check() -> dict:
    checks: dict = {}

    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public'")
            )
            checks["database"] = {"status": "ok", "tables": result.scalar()}
    except Exception as e:
        checks["database"] = {"status": "error", "error": str(e)}

    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.redis_url, socket_connect_timeout=2)
        info = await r.info("server")
        await r.aclose()
        checks["redis"] = {"status": "ok", "version": info.get("redis_version")}
    except Exception as e:
        checks["redis"] = {"status": "error", "error": str(e)}

    try:
        import redis as sync_redis
        r = sync_redis.from_url(settings.redis_url, socket_connect_timeout=2)
        checks["celery_queues"] = {
            "status": "ok",
            "lengths": {q: r.llen(q) for q in ["default", "llm", "rendering"]},
        }
        r.close()
    except Exception as e:
        checks["celery_queues"] = {"status": "error", "error": str(e)}

    checks["sentry"] = {
        "status": "configured" if settings.sentry_dsn else "not_configured",
        "environment": settings.sentry_environment or settings.app_env,
    }

    critical_ok = all(
        checks.get(k, {}).get("status") == "ok" for k in ("database", "redis")
    )
    return {
        "status": "ok" if critical_ok else "degraded",
        "version": settings.app_version,
        "env": settings.app_env,
        "checks": checks,
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.delete("/reset-user-data", summary="Wipe all data for a user (dev/testing)")
async def reset_user_data(
    email: str,
    confirm: str = "",
):
    """Delete all application data for a user. Requires confirm=YES."""
    if confirm != "YES":
        return {"error": "Pass ?confirm=YES to actually delete"}

    from app.db.session import AsyncSessionLocal
    from app.models.user import User

    async with AsyncSessionLocal() as session:
        # Find user
        from sqlalchemy import select, delete
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if not user:
            return {"error": f"User {email} not found"}

        uid = str(user.id)

        # Delete all user data (order matters for foreign keys)
        tables_to_clear = [
            "warm_intros", "mutual_connections", "application_timeline",
            "application_events", "interview_rounds", "compensation_benchmarks",
            "scout_results", "hidden_signals", "saved_jobs",
            "linkedin_conversations", "linkedin_messages",
            "linkedin_connections", "applications",
        ]

        deleted = {}
        for table in tables_to_clear:
            try:
                r = await session.execute(
                    text(f"DELETE FROM {table} WHERE user_id = :uid"),
                    {"uid": uid},
                )
                deleted[table] = r.rowcount
            except Exception as e:
                deleted[table] = f"error: {str(e)}"

        await session.commit()

        return {
            "status": "wiped",
            "user_id": uid,
            "email": email,
            "deleted": deleted,
        }
