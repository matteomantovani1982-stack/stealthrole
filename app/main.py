"""
app/main.py

FastAPI application factory and entry point.
All app-level setup lives here: routers, middleware, lifespan events.
Business logic NEVER goes here.
"""

import structlog
from fastapi import FastAPI
from app.monitoring.sentry import init_sentry
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.api.middleware.error_handler import register_error_handlers
from app.api.routes import health
from app.config import settings

logger = structlog.get_logger(__name__)


def create_app() -> FastAPI:
    """
    Application factory.
    Returns a fully configured FastAPI instance.
    """
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "CareerOS API — generates Application Intelligence Packs "
            "by parsing CVs, analysing job descriptions, and calling Claude."
        ),
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
    )

    # ── Middleware ─────────────────────────────────────────────────────────
    from app.api.middleware.cache_control import CacheControlMiddleware
    app.add_middleware(CacheControlMiddleware)
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    # CORS — in dev allow all, in prod use ALLOWED_ORIGINS env var
    if settings.is_production and not settings.allowed_origins.strip():
        logger.warning("cors_wildcard_in_prod", msg="ALLOWED_ORIGINS is empty — CORS will fall back to FRONTEND_URL only")
    _origins = (
        ["*"] if settings.is_development
        else [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]
             or [settings.frontend_url]
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_origins,
        allow_origin_regex=r"^chrome-extension://.*$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Error handlers ─────────────────────────────────────────────────────
    register_error_handlers(app)

    # ── Routers ────────────────────────────────────────────────────────────
    # All routes are versioned under /api/v1 (except health — see /health for liveness)
    app.include_router(health.router)               # /health, /health/ready

    # Auth routes — /api/v1/auth
    from app.api.routes import auth
    app.include_router(auth.router)

    # CV upload routes — /api/v1/cvs
    from app.api.routes import uploads
    app.include_router(uploads.router)

    # Quick Start — /api/v1/quickstart
    from app.api.routes import quickstart
    app.include_router(quickstart.router)

    # Job run routes — /api/v1/jobs
    from app.api.routes import jobs
    app.include_router(jobs.router)

    # CV Builder routes — /api/v1/cv-builder
    from app.api.routes import cv_builder
    app.include_router(cv_builder.router)

    # Billing routes — /api/v1/billing
    from app.api.routes import billing
    app.include_router(billing.router)

    # Candidate profile routes — /api/v1/profiles
    from app.api.routes import profiles
    from app.api.routes import profile_import
    app.include_router(profiles.router)
    app.include_router(profile_import.router)

    from app.api.routes import scout
    app.include_router(scout.router)

    # Shadow Application routes — /api/v1/shadow
    from app.api.routes import shadow
    app.include_router(shadow.router)

    # OpportunityRadar routes — /api/v1/opportunities
    from app.api.routes import opportunities
    app.include_router(opportunities.router)

    # Outreach Generator routes — /api/v1/outreach
    from app.api.routes import outreach
    app.include_router(outreach.router)

    # Analytics routes — /api/v1/analytics
    from app.api.routes import analytics
    app.include_router(analytics.router)

    # Dashboard routes — /api/v1/dashboard
    from app.api.routes import dashboard
    app.include_router(dashboard.router)

    # WhatsApp routes — /api/v1/whatsapp
    from app.api.routes import whatsapp
    app.include_router(whatsapp.router)

    # Admin: cost monitor — /api/v1/admin/costs
    from app.api.routes import admin_costs
    app.include_router(admin_costs.router)

    # Referral routes — /api/v1/referral
    from app.api.routes import referral
    app.include_router(referral.router)

    from app.api.routes import email as email_routes
    app.include_router(
        email_routes.router,
        prefix="/api/v1",
    )

    # Application Tracker routes — /api/v1/applications
    from app.api.routes import applications
    app.include_router(applications.router)

    # Email Integration routes — /api/v1/email-integration
    from app.api.routes import email_integration
    app.include_router(email_integration.router)

    # CRM routes — /api/v1/crm
    from app.api.routes import crm
    app.include_router(crm.router)

    # LinkedIn routes — /api/v1/linkedin
    from app.api.routes import linkedin
    app.include_router(linkedin.router)

    # Relationship Engine routes — /api/v1/relationships
    from app.api.routes import relationships
    app.include_router(relationships.router)

    # Auto-Apply routes — /api/v1/auto-apply
    from app.api.routes import auto_apply
    app.include_router(auto_apply.router)

    # Interview Coach routes — /api/v1/interviews
    from app.api.routes import interviews
    app.include_router(interviews.router)

    # Email Intelligence routes — /api/v1/email-intelligence
    from app.api.routes import email_intelligence as email_intel_routes
    app.include_router(email_intel_routes.router)

    # User Intelligence routes — /api/v1/intelligence
    from app.api.routes import user_intelligence
    app.include_router(user_intelligence.router)

    # Credits routes — /api/v1/credits
    from app.api.routes import credits
    app.include_router(credits.router)

    # Export routes — /api/v1/export
    from app.api.routes import export
    app.include_router(export.router)

    # Action Engine routes — /api/v1/actions
    from app.api.routes import actions
    app.include_router(actions.router)

    # Value / ROI Insights — /api/v1/insights
    from app.api.routes import insights
    app.include_router(insights.router)

    # Quick Start (intelligence) — /api/v1/quick-start
    from app.api.routes import quick_start
    app.include_router(quick_start.router)

    # Extension capture — /api/v1/extension
    from app.api.routes import extension
    app.include_router(extension.router)

    # ── Startup / shutdown events ──────────────────────────────────────────
    @app.on_event("startup")
    async def on_startup() -> None:
        init_sentry()
        logger.info(
            "cvlab_starting",
            env=settings.app_env,
            version=settings.app_version,
        )

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        logger.info("careeros_shutdown")

    return app


# Uvicorn entry point
app = create_app()
