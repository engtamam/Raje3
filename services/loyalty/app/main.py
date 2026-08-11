# =============================================================================
# loyalty — Application factory & lifespan
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
    settings.assert_pii_config_ok()
    settings.assert_cors_config_ok()
    # A programme that deducts points and tells nobody has no audit (spec §9.6).
    settings.assert_peers_config_ok()
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
        # ── the visit event: where every point in this service comes from ────────────────────
        #
        # THE BUG THIS CLOSES. `Earner.from_visit` was written, tested and reachable at
        # /internal/loyalty/earn, and NOTHING CALLED IT. A visit was recorded and no point was
        # awarded — so the rewards table, the redemption sheet and «نقاطي» all stood on a balance
        # that was zero for ever, and every test in this service passed the whole time. Fourth
        # instance of the same shape in this codebase: complete in the depth, cut at the door.
        #
        # A SUBSCRIPTION, NOT A CALL FROM operations. `operations` publishes and deliberately does
        # not know who consumes a visit — a service that knows its consumers has to change every
        # time one is added. So the wire belongs on this end.
        #
        # AND IT IS THE FAST PATH, NOT THE RELIABLE ONE. The bus is at-most-once by contract, so a
        # pod that is rolling out simply misses the event and nothing records that it did.
        # `Earner.catch_up` exists for exactly that and reads the same function — a catch-up with
        # its own arithmetic is a second earning rule, and the second one drifts from the settings
        # screen the first time somebody edits it.
        async def _on_visit(event) -> None:
            payload = getattr(event, "payload", None) or {}
            try:
                await container.earner.from_visit(
                    str(payload.get("tenant") or ""),
                    # Idempotent BY visit_id: the ledger refuses a second entry from the same
                    # source, so a redelivered event awards nothing twice.
                    visit_id=str(payload.get("visit_id") or ""),
                    subject_ref=str(payload.get("subject_ref") or ""),
                    service_ids=list(payload.get("service_ids") or []),
                    amount_halalas=int(payload.get("amount_halalas") or 0),
                    actor=str(payload.get("operator_id") or ""),
                    branch_id=str(payload.get("branch_id") or ""))
            except Exception as exc:                                        # noqa: BLE001
                # NEVER RAISES INTO THE BUS. The visit already happened and is not ours to undo;
                # a handler that throws here would, on some drivers, redeliver for ever.
                logger.warning("earn_from_visit_failed",
                               extra={"error": str(exc)[:200],
                                      "visit": str(payload.get("visit_id") or "")})

        try:
            await container.event_bus.subscribe("operations.visit.recorded", _on_visit)
            logger.info("subscribed", extra={"topic": "operations.visit.recorded"})
        except Exception as exc:                                            # noqa: BLE001
            # NOT fatal — the catch-up covers it, and refusing to start over a subscription would
            # turn a degraded fast path into a total outage.
            logger.warning("subscribe_failed", extra={"error": str(exc)[:200]})

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
    app.include_router(internal.router)
    app.include_router(v1_router)
    # Operator controls: credentials and policy an operator changes after launch.
    app.include_router(operator_router)

    return app


# ASGI entry point: `uvicorn app.main:app`
app = create_app()
