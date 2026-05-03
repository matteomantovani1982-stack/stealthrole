# CareerOS (StealthRole)

Application Intelligence SaaS — parses CVs, analyses job descriptions via Claude, generates tailored application packs (cover letters, positioning strategies, interview prep).

## Quick Start

```bash
make up        # starts full dev stack (Docker Compose)
make test      # runs pytest suite
make lint      # ruff lint check
make test-cov  # tests with coverage report
```

## Architecture

**Backend:** FastAPI (Python 3.11) with async SQLAlchemy, Alembic migrations, Celery workers, Redis broker.
**Frontend:** Next.js + TypeScript on Vercel.
**Extension:** Chrome extension for LinkedIn job capture.
**Infra:** API on AWS ECS (eu-west-1), PostgreSQL, Redis, S3 for document storage.

## Key Patterns

- **Auth:** Custom JWT (HS256) — access tokens (30 min) + refresh token rotation (30 days). Use `CurrentUser` dependency from `app/dependencies.py` for all authenticated routes.
- **DB Sessions:** Routes use async sessions via `DB = Depends(get_db_session)`. Celery workers use sync sessions via `get_sync_db()` from `app/workers/db_utils.py`. Never use async sessions in Celery.
- **Transaction ownership:** Routes own commits. Services should not call `db.commit()` — let the route layer control transaction boundaries.
- **Error handling:** Global handlers in `app/api/middleware/error_handler.py`. Raise `CareerOSError` subclasses for typed app errors. `HTTPException` for HTTP-level errors.
- **Rate limiting:** Redis-backed per-IP rate limiter on auth endpoints. See `app/api/middleware/rate_limiter.py`.
- **LLM caching:** Deterministic LLM tasks cached in Redis with TTLs. See `app/services/llm/cache.py`.

## Celery Queues

Three queues with separate workers:
- `default` — lightweight tasks (parse CV, status updates, email sync, calendar sync)
- `llm` — Claude API calls (rate-limited to 10/min)
- `rendering` — DOCX generation (CPU-bound)

Workers bake code into Docker image at build time. Always use `docker compose up --build` after code changes.

## Billing

Credit-based system + subscription tiers (Free/Starter/Pro/Unlimited). Stripe integration via httpx. Price IDs configured via env vars (`STRIPE_PRICE_*`). Demo mode (`DEMO_MODE=true`) skips Anthropic API calls.

## Project Structure

```
app/
  api/routes/          # FastAPI route handlers
  api/middleware/      # Error handler, rate limiter, cache control
  config.py            # Pydantic settings (all env vars)
  dependencies.py      # FastAPI dependencies (DB, CurrentUser)
  db/                  # Engine, session factory, migrations
  models/              # SQLAlchemy ORM models
  schemas/             # Pydantic request/response schemas
  services/            # Business logic layer
  workers/             # Celery app, task modules, sync DB utils
  monitoring/          # Sentry init, breadcrumbs
docker/                # Dockerfiles, compose configs
frontend/              # Next.js app
tests/                 # pytest suite
```

## Environment

All config via env vars — see `app/config.py` and `.env.production.example`. Key vars:
- `DATABASE_URL` — must use `postgresql+asyncpg://` driver
- `REDIS_URL` — broker + cache
- `ANTHROPIC_API_KEY` — Claude API
- `DEMO_MODE` — skip LLM calls (returns mock data)
- `SENTRY_DSN` — error monitoring (optional)

## Do Not Touch

- Connection sync, messages inbox, and all related backend/frontend code — active development by another team member.
