"""
app/api/routes/health.py

Health check endpoints for liveness, readiness, and deep system status.
"""

from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import settings, should_skip_anthropic_api
from app.db.session import AsyncSessionLocal

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", summary="Liveness probe")
async def health_check() -> dict:
    payload: dict = {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    # Expose internal details only in non-production environments
    if not settings.is_production:
        payload["env"] = settings.app_env
        payload["demo_mode"] = should_skip_anthropic_api()
        payload["demo_setting_raw"] = settings.demo_mode
    return payload


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


@router.get("/deep", summary="Deep system check", include_in_schema=not settings.is_production)
async def deep_check() -> dict:
    # Production: require a simple shared secret to prevent info leakage
    # In non-prod this is wide open for convenience
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


@router.delete(
    "/reset-user-data",
    summary="Wipe all data for a user (dev/testing)",
    include_in_schema=False,
)
async def reset_user_data(
    email: str,
    confirm: str = "",
):
    """Delete all application data for a user. Dev/testing only. Requires confirm=YES."""
    if settings.is_production:
        return JSONResponse(
            status_code=403,
            content={"detail": "This endpoint is disabled in production."},
        )
    if confirm != "YES":
        raise HTTPException(status_code=400, detail="Pass ?confirm=YES to actually delete")

    from app.db.session import AsyncSessionLocal
    from app.models.user import User

    async with AsyncSessionLocal() as session:
        # Find user
        from sqlalchemy import select
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail=f"User {email} not found")

        uid = str(user.id)

        from app.services.user_data_wipe import wipe_application_and_network_data

        deleted = await wipe_application_and_network_data(
            session, uid, include_intelligence=True,
        )
        await session.commit()

        return {
            "status": "wiped",
            "user_id": uid,
            "email": email,
            "deleted": deleted,
        }
