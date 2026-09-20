# =============================================================================
# operations — Application factory & lifespan
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
from app.api.v1.operator import router as operator_router
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


def create_app() -> FastAPI:
    # Fail-fast: this raises (and aborts startup) if the environment is invalid.
    settings = get_settings()
    # A service that cannot witness its own privileged actions must not serve traffic as if it can.
    settings.assert_audit_config_ok()
    settings.assert_subscription_config_ok()
    settings.assert_pii_config_ok()
    settings.assert_cors_config_ok()
    settings.assert_search_config_ok()
    settings.assert_seed_config_ok()
    settings.assert_apps_config_ok()
    settings.assert_billing_plans_config_ok()
    settings.assert_onboarding_config_ok()
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
        # The one-time template seed. Applied ONLY when the table is empty, so an operator's
        # edits are never overwritten on a restart — a console that appears to work while its
        # changes vanish overnight is worse than one that does not exist.
        #
        # A failure here is LOGGED, not fatal. The seed is a convenience for a fresh install; a
        # running platform whose library is already populated must not be taken down because a
        # mounted file went missing.
        try:
            n = await container.templates.seed_from_file(settings.TEMPLATES_SEED_FILE)
            if n:
                logger.info("templates_seeded", extra={"count": n})
        except Exception as exc:                                            # noqa: BLE001
            logger.error("template_seed_failed", extra={"error": str(exc)[:300]})

        # THE PLATFORM'S OWN TEMPLATES (`_platform`) — registered automatically (a local upsert,
        # no Meta call), never submitted automatically (that stays the operator's own console
        # click). See core/platform_templates.py's own docstring for why this never reverts an
        # operator's edit, and why a failure here is logged, not fatal, same as the seed above.
        try:
            from app.core.platform_templates import seed_platform_templates

            stats = await seed_platform_templates(
                container.library, seed_path=settings.PLATFORM_TEMPLATES_SEED_FILE)
            if stats["registered"]:
                logger.info("platform_templates_seeded", extra=stats)
        except Exception as exc:                                            # noqa: BLE001
            logger.error("platform_template_seed_failed", extra={"error": str(exc)[:300]})

        # React to billing-service's own subscription.suspended/renewed events (base-services
        # v0.25.21+) by flipping Meta's own WhatsApp AI switch in real time — see
        # core/meta_agent_rollout_events.py's own docstring. A failure here is logged, not fatal,
        # same posture as the seeds above: the owner's own AI kill switch (staff.py) is unaffected.
        try:
            from app.core.meta_agent_rollout_events import register as register_rollout_events

            await register_rollout_events(container)
        except Exception as exc:                                            # noqa: BLE001
            logger.error("meta_agent_rollout_events_subscribe_failed",
                         extra={"error": str(exc)[:300]})
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
    # The PIN hash is salted with PII_SALT, so the routes need settings. Attached once rather than
    # re-resolved per request through the lru_cache.
    app.state.container_settings = settings
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
    # `as instrumentator_metrics` — NOT `metrics`. That name is already our own `app.api.metrics`
    # module, imported at file scope and used two lines above (`metrics.router`). A local import
    # of the SAME name anywhere in this function makes Python treat every `metrics` reference in
    # the whole function as local — including the one on line 150, which then runs before this
    # line ever assigns it: `UnboundLocalError: cannot access local variable 'metrics'`, on every
    # single app boot, this router included or not. Found by a test suite failing to build the
    # app at all, not by anything about metrics themselves being wrong.
    from prometheus_fastapi_instrumentator import Instrumentator
    from prometheus_fastapi_instrumentator import metrics as instrumentator_metrics
    Instrumentator().add(instrumentator_metrics.default()).instrument(app)
    app.include_router(internal.router)
    app.include_router(v1_router)
    # Operator controls: credentials and policy an operator changes after launch.
    app.include_router(operator_router)

    return app


# ASGI entry point: `uvicorn app.main:app`
app = create_app()
