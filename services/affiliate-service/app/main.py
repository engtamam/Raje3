# =============================================================================
# affiliate-service — Application factory & lifespan
# -----------------------------------------------------------------------------
# Builds the FastAPI app: validated config (fail-fast), structured logging,
# hardened middleware, safe error handlers, and the three endpoint tiers
# (public / internal / user).
#
# Middleware nesting (outermost -> innermost), so every response — including
# errors and timeouts — is tagged and hardened:
#     RequestId  ->  SecurityHeaders  ->  Timeout  ->  BodyLimit  ->  app
# Starlette runs the LAST-added middleware outermost, so we add them in the
# reverse of that order below.
# =============================================================================
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import health, internal, metrics
from app.api.errors import register_error_handlers
from app.api.health import register_readiness_check
from app.api.v1 import router as v1_router
from app.api.v1.admin import router as affiliates_admin_router
from app.api.v1.admin_employment import router as affiliates_admin_employment_router
from app.api.v1.admin_leads import router as affiliates_admin_leads_router
from app.api.v1.admin_sectors import router as affiliates_admin_sectors_router
from app.api.v1.admin_payouts import router as affiliates_admin_payouts_router
from app.api.v1.admin_wafa import router as affiliates_admin_wafa_router
from app.api.v1.affiliate_self import router as affiliates_self_router
from app.api.v1.outreach import router as affiliates_outreach_router
from app.api.v1.operator import router as operator_router
from app.api.v1.public import router as affiliates_public_router
from app.config import get_settings
from app.core.audit import build_auditor
from app.container import build_container
from app.middleware import (
    BodyLimitMiddleware,
    RequestIdMiddleware,
    SecurityHeadersMiddleware,
    TimeoutMiddleware,
)
from app.observability.logging import configure_logging, get_logger
from app.security.catalog import get_catalog
from app.security.checks import build_checks
from app.security.cwe_guard import CweGuard
from app.security.step_map import load_step_map


def _commission_sync_handler(container, logger):
    """One handler, reused for every subscribed topic — billing's payment_payload() puts `tenant`
    on every event type this service subscribes to, so there is nothing topic-specific to branch
    on. Exceptions are swallowed here on purpose: the event bus already swallows a subscriber's
    exceptions per-publish (so one bad handler cannot break the publisher), but logging it once
    ourselves is the difference between a silent miss and a miss somebody can find in the logs —
    and it still costs nothing but latency, since the sweep is the actual backstop."""
    async def handler(event) -> None:
        tenant = (event.payload or {}).get("tenant", "") if isinstance(event.payload, dict) else ""
        if not tenant:
            return
        try:
            await container.commissions.sync(tenant)
        except Exception as exc:                                             # noqa: BLE001
            logger.warning("commission_sync_from_event_failed",
                           extra={"tenant": tenant, "topic": event.type,
                                 "error": type(exc).__name__})
    return handler


def create_app() -> FastAPI:
    # Fail-fast: this raises (and aborts startup) if the environment is invalid.
    settings = get_settings()
    # A service that cannot witness its own privileged actions must not serve traffic as if it can.
    settings.assert_audit_config_ok()
    settings.assert_pii_config_ok()
    settings.assert_cors_config_ok()
    settings.assert_onboarding_config_ok()
    settings.assert_receipt_config_ok()
    configure_logging(settings.SERVICE_NAME, settings.ENV, settings.LOG_LEVEL)
    logger = get_logger("app.main")

    # Composition root: wire ports -> adapters from config (fail-fast on bad driver).
    container = build_container(settings)

    # CWE self-guard: pre/post-step checks referencing the bundled MITRE catalog.
    cwe_guard = CweGuard(
        catalog=get_catalog(),
        step_map=load_step_map(settings.CWE_STEP_MAP_FILE),
        checks=build_checks(settings),
        enabled=settings.CWE_GUARD_ENABLED,
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        logger.info(
            "startup",
            extra={
                "service": settings.SERVICE_NAME,
                "version": settings.SERVICE_VERSION,
                "ports": container.describe(),
            },
        )
        # THE FAST PATH ONLY — see Settings.AFFILIATE_COMMISSION_SYNC_TOPICS and
        # app/ports/event_bus.py's own contract. sync() itself (reading billing's durable
        # invoice history) is what actually creates/confirms a commission correctly; this just
        # makes it happen sooner than the sweep (POST /internal/commissions/sweep, on a
        # schedule) would on its own. A missed event costs latency, never correctness.
        for topic in settings.affiliate_commission_sync_topics:
            await container.event_bus.subscribe(topic, _commission_sync_handler(container, logger))
        # THE OUTBOUND CONVERSION PLAYBOOK'S SEED DATA — see core/outreach_seed.py's own
        # docstring for why this runs on every boot and is still safe: it only ever fills in a
        # stage/template that has never existed, and never touches one a manager already has
        # (even a deactivated one), so a fresh install gets the starting playbook and a live
        # server with a manager's own edits is never silently reset.
        from app.core.outreach_seed import seed as seed_outreach

        await seed_outreach(stages=container.outreach_stages, templates=container.templates,
                            stat_citations=container.stat_citations)
        yield
        await container.close()
        logger.info("shutdown", extra={"service": settings.SERVICE_NAME})

    app = FastAPI(
        title=settings.SERVICE_NAME,
        version=settings.SERVICE_VERSION,
        lifespan=lifespan,
        # Docs off by default in production (reduce surface); on elsewhere.
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production else "/openapi.json",
    )
    app.state.container = container
    # Validated at boot: a malformed declaration stops the service rather than surfacing months
    # later as a hole in the log.
    app.state.auditor = build_auditor(settings, container)
    app.state.cwe_guard = cwe_guard

    # Readiness reflects real dependency health for the wired adapters.
    for name, probe in container.health_probes().items():
        register_readiness_check(name, probe)

    # ── Middleware (added inner -> outer; see header note) ──────────────────
    app.add_middleware(BodyLimitMiddleware, max_bytes=settings.BODY_LIMIT_BYTES)
    app.add_middleware(TimeoutMiddleware, timeout_ms=settings.REQUEST_TIMEOUT_MS)
    app.add_middleware(
        SecurityHeadersMiddleware,
        frame_ancestors=settings.ALLOWED_FRAME_ANCESTORS,
        is_production=settings.is_production,
    )
    app.add_middleware(RequestIdMiddleware)

    # CORS is added LAST so it is the OUTERMOST middleware: a preflight must be answered before
    # the body limit, the timeout or anything else can reject it, and a rejected preflight is an
    # error the browser reports as a CORS failure rather than as the real reason.
    if settings.cors_origins:
        from fastapi.middleware.cors import CORSMiddleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
            allow_methods=settings.cors_methods,
            allow_headers=settings.cors_headers,
            max_age=settings.CORS_MAX_AGE_SECONDS,
        )

    # ── Error handlers (safe, generic) ──────────────────────────────────────
    register_error_handlers(app)

    from app.api.ratelimit import build_policy, register_ratelimit_refund
    app.state.ratelimit_policy = build_policy(settings)
    register_ratelimit_refund(app)

    # ── Routers: public -> internal -> user ─────────────────────────────────
    app.include_router(health.router)
    app.include_router(metrics.router)
    # RED metrics (Rate/Errors/Duration) — grouped by ROUTE TEMPLATE, never the raw path (the
    # library's own default, and the reason: `/bookings/{id}` is one label value regardless of
    # which id, so cardinality stays bounded no matter how many bookings exist). Unhandled paths
    # (404s from probing/scanning) are excluded by the same default, so they cannot inflate the
    # metric set either.
    #
    # .add(metrics.default()) IS NOT OPTIONAL — Instrumentator() alone starts with ZERO
    # instrumentations registered (confirmed live: instrument()-only ran with no error, no crash,
    # and produced not one http_* metric — a silent no-op, the worst kind of bug to ship, because
    # it looks wired and isn't). .default() is what actually registers the request-count and
    # duration-histogram collectors this whole effort is for.
    #
    # This only calls .instrument() — never .expose() — because metrics.router above already
    # serves /metrics off the same default prometheus_client registry Instrumentator writes into;
    # a second .expose() would just be a second route fighting the first for the path. Verified
    # live end to end: a real request through an included router (the exact shape that crashes on
    # 7.x — see the pyproject.toml pin note) produces http_requests_total and
    # http_request_duration_seconds on /metrics, grouped by handler, with no error.
    from prometheus_fastapi_instrumentator import Instrumentator, metrics
    Instrumentator().add(metrics.default()).instrument(app)
    app.include_router(internal.router)
    app.include_router(v1_router)
    app.include_router(affiliates_public_router)
    app.include_router(affiliates_self_router)
    app.include_router(affiliates_outreach_router)
    app.include_router(affiliates_admin_router)
    app.include_router(affiliates_admin_payouts_router)
    app.include_router(affiliates_admin_wafa_router)
    app.include_router(affiliates_admin_employment_router)
    app.include_router(affiliates_admin_sectors_router)
    app.include_router(affiliates_admin_leads_router)
    # Operator controls: credentials and policy an operator changes after launch.
    app.include_router(operator_router)

    return app


# ASGI entry point: `uvicorn app.main:app`
app = create_app()
