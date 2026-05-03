"""
app/api/middleware/rate_limiter.py

Redis-backed rate limiter for sensitive endpoints (auth, billing).
Uses a sliding-window counter per IP address.

Usage as a FastAPI dependency:

    from app.api.middleware.rate_limiter import rate_limit

    @router.post("/login")
    async def login(
        request: Request,
        _rl: None = Depends(rate_limit("login", max_calls=10, window_seconds=60)),
    ):
        ...

No extra pip dependency — uses the redis client already in requirements.
"""

from __future__ import annotations

import time

import structlog
from fastapi import HTTPException, Request, status

logger = structlog.get_logger(__name__)

# Lazy-init redis client (avoids import-time connection)
_redis_client = None


def _get_redis():
    global _redis_client
    if _redis_client is None:
        import redis
        from app.config import settings
        _redis_client = redis.from_url(
            settings.redis_url,
            socket_connect_timeout=2,
            socket_timeout=1,
            decode_responses=True,
        )
    return _redis_client


def rate_limit(
    scope: str,
    max_calls: int = 10,
    window_seconds: int = 60,
):
    """
    FastAPI dependency that enforces a per-IP rate limit.

    Args:
        scope: Unique name for this limit bucket (e.g. "login", "register").
        max_calls: Maximum requests allowed within the window.
        window_seconds: Sliding window size in seconds.

    Raises HTTPException 429 if the limit is exceeded.
    Degrades gracefully — if Redis is unavailable, requests are allowed through
    (fail-open) so that auth doesn't break when Redis goes down.
    """

    async def _check(request: Request) -> None:
        # Extract client IP (trust X-Forwarded-For behind a proxy)
        forwarded = request.headers.get("x-forwarded-for")
        client_ip = forwarded.split(",")[0].strip() if forwarded else (
            request.client.host if request.client else "unknown"
        )

        key = f"rl:{scope}:{client_ip}"
        now = time.time()

        try:
            r = _get_redis()
            pipe = r.pipeline()
            # Remove entries outside the window
            pipe.zremrangebyscore(key, 0, now - window_seconds)
            # Add current request
            pipe.zadd(key, {str(now): now})
            # Count requests in window
            pipe.zcard(key)
            # Set expiry so keys don't linger forever
            pipe.expire(key, window_seconds + 10)
            results = pipe.execute()
            current_count = results[2]

            if current_count > max_calls:
                logger.warning(
                    "rate_limit_exceeded",
                    scope=scope,
                    ip=client_ip,
                    count=current_count,
                    max=max_calls,
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Too many requests. Try again in {window_seconds} seconds.",
                    headers={"Retry-After": str(window_seconds)},
                )
        except HTTPException:
            raise
        except Exception as e:
            # Fail open — don't block auth if Redis is down
            logger.warning("rate_limiter_redis_error", error=str(e), scope=scope)

    return _check
