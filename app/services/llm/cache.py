"""
app/services/llm/cache.py

Redis-based LLM response cache for deterministic tasks.

Caches responses for tasks where the same input always produces
the same (or functionally equivalent) output:
  - seniority detection
  - sector classification
  - geography mapping
  - CV quality scoring (same parsed CV → same score)

Non-deterministic tasks (outreach, strategy) are NOT cached.

Cache key = sha256(task + model + prompt_content)
TTL = configurable per task type (default 24h, classification 7d)
"""

import hashlib

import structlog

from app.config import settings

logger = structlog.get_logger(__name__)

# Tasks eligible for caching (deterministic output)
_CACHEABLE_TASKS = {
    "classification",
    "scoring",
    "cv_quality",
    "cv_best_practices",
    "jd_extraction",
    "signal_enrichment",
    "signal_scoring",
    "news_tagging",
}

# TTL in seconds per task type
_TASK_TTL = {
    "classification": 7 * 86400,    # 7 days — seniority/sector rarely changes
    "scoring": 24 * 3600,           # 24h — scores may drift with model updates
    "cv_quality": 24 * 3600,        # 24h
    "cv_best_practices": 24 * 3600,
    "jd_extraction": 7 * 86400,     # 7 days — JD text doesn't change
    "signal_enrichment": 6 * 3600,  # 6h — signals are time-sensitive
    "signal_scoring": 6 * 3600,
    "news_tagging": 12 * 3600,      # 12h
}

_DEFAULT_TTL = 24 * 3600  # 24 hours

# Redis client singleton
_redis_client = None


def _get_redis():
    """Lazy-init Redis client. Returns None if Redis unavailable."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    try:
        import redis
        _redis_client = redis.Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        # Test connection
        _redis_client.ping()
        return _redis_client
    except Exception as e:
        logger.debug("llm_cache_redis_unavailable", error=str(e))
        _redis_client = False  # Sentinel: don't retry
        return None


def _make_key(task: str, model: str, prompt_hash: str) -> str:
    """Build Redis key for an LLM cache entry."""
    return f"llm_cache:{task}:{model}:{prompt_hash}"


def _hash_prompt(system_prompt: str, user_prompt: str) -> str:
    """SHA-256 hash of the combined prompt content."""
    content = f"{system_prompt}\n---\n{user_prompt}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def is_cacheable(task: str) -> bool:
    """Check if a task type is eligible for caching."""
    return task in _CACHEABLE_TASKS


def get_cached(task: str, model: str, system_prompt: str, user_prompt: str) -> str | None:
    """
    Look up a cached LLM response.
    Returns the cached content string, or None if not cached.
    """
    if not is_cacheable(task):
        return None

    r = _get_redis()
    if not r:
        return None

    try:
        prompt_hash = _hash_prompt(system_prompt, user_prompt)
        key = _make_key(task, model, prompt_hash)
        cached = r.get(key)
        if cached:
            logger.info("llm_cache_hit", task=task, model=model)
            return cached
    except Exception as e:
        logger.debug("llm_cache_get_error", error=str(e))

    return None


def set_cached(
    task: str, model: str,
    system_prompt: str, user_prompt: str,
    response: str,
) -> None:
    """
    Store an LLM response in cache.
    Only stores for cacheable tasks.
    """
    if not is_cacheable(task):
        return

    r = _get_redis()
    if not r:
        return

    try:
        prompt_hash = _hash_prompt(system_prompt, user_prompt)
        key = _make_key(task, model, prompt_hash)
        ttl = _TASK_TTL.get(task, _DEFAULT_TTL)
        r.setex(key, ttl, response)
        logger.debug("llm_cache_set", task=task, model=model, ttl=ttl)
    except Exception as e:
        logger.debug("llm_cache_set_error", error=str(e))
