# =============================================================================
# whatsapp-assistant — Application factory & lifespan
# -----------------------------------------------------------------------------
# Builds the FastAPI app: validated config (fail-fast), structured logging,
# hardened middleware, safe error handlers, and subscribes to notification-
# service's whatsapp.message / whatsapp.status bus events — the FAST path in,
# imitating services/reminders/app/main.py's `_on_visit` subscription exactly.
# =============================================================================
from __future__ import annotations

import time

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import health, internal, metrics
from app.api.v1 import router as v1_router
from app.api.v1.operator import router as operator_router
from app.api.errors import register_error_handlers
from app.api.health import register_readiness_check
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
    settings = get_settings()
    settings.assert_audit_config_ok()
    settings.assert_pii_config_ok()
    settings.assert_cors_config_ok()
    settings.assert_llm_config_ok()
    settings.assert_consent_config_ok()
    configure_logging(settings.SERVICE_NAME, settings.ENV, settings.LOG_LEVEL)
    logger = get_logger("app.main")

    container = build_container(settings)

    cwe_guard = CweGuard(
        catalog=get_catalog(), step_map=load_step_map(settings.CWE_STEP_MAP_FILE),
        checks=build_checks(settings), enabled=settings.CWE_GUARD_ENABLED)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        logger.info("startup", extra={"service": settings.SERVICE_NAME,
                                      "version": settings.SERVICE_VERSION,
                                      "ports": container.describe()})

        # ── inbound WhatsApp: the FAST path, and it is DELIBERATELY not the only path ─────────
        #
        # notification-service's EventBus is explicitly at-most-once and non-durable (its own
        # docstring says so): a pod restarting through this subscription hears a message never,
        # with no symptom anywhere. We keep it anyway, for latency — a customer who just messaged
        # a shop should not wait for a poll cadence to get a reply. What closes the missed-event
        # gap is api/internal.py's tick-driven sweep against notification-service's durable
        # GET /internal/whatsapp/inbound (platform v0.16.38, commit 31e556e): same message, same
        # dedup, just found later if the bus ever drops it. Both paths call
        # core/inbound_ingest.py::ingest_inbound_message, which persists into inbound_store keyed
        # by Meta's wamid BEFORE anything is processed — whichever path sees a wamid first wins;
        # the other finds `record_if_new` already False and stops. A message delivered by BOTH the
        # bus and the catch-up sweep is therefore processed exactly once, not twice.
        async def _on_whatsapp_message(event) -> None:
            payload = getattr(event, "payload", None) or {}
            tenant = str(payload.get("tenant") or "")
            wamid = str(payload.get("wamid") or payload.get("id") or "")
            from_number = str(payload.get("from") or payload.get("from_number") or "")
            kind = str(payload.get("kind") or "")
            text = str(payload.get("text") or "")
            reply_id = str(payload.get("reply_id") or payload.get("id_reply") or "")
            if not kind and isinstance(payload.get("message"), dict):
                # notification-service's real bus payload carries Meta's RAW message object under
                # `message`, not pre-flattened fields — see core/inbound_parse.py.
                from app.core.inbound_parse import parse_message
                kind, text, reply_id = parse_message(payload["message"])
                wamid = wamid or str(payload["message"].get("id") or "")
                from_number = from_number or str(payload["message"].get("from") or "")
            kind = kind or "text"

            from app.core.inbound_ingest import ingest_inbound_message
            await ingest_inbound_message(
                container=container, logger=logger, settings=settings,
                auditor=_app.state.auditor, tenant=tenant, wamid=wamid, from_number=from_number,
                kind=kind, text=text, reply_id=reply_id, raw_payload=payload)

        try:
            await container.event_bus.subscribe("whatsapp.message", _on_whatsapp_message)
            await container.event_bus.subscribe("whatsapp.status", lambda e: None)
            logger.info("subscribed", extra={"topic": "whatsapp.message"})
        except Exception as exc:                                            # noqa: BLE001
            logger.warning("subscribe_failed", extra={"error": str(exc)[:200]})

        yield
        await container.close()
        logger.info("shutdown", extra={"service": settings.SERVICE_NAME})

    app = FastAPI(
        title=settings.SERVICE_NAME, version=settings.SERVICE_VERSION, lifespan=lifespan,
        docs_url=None if settings.is_production else "/docs", redoc_url=None,
        openapi_url=None if settings.is_production else "/openapi.json")
    app.state.container = container
    app.state.auditor = build_auditor(settings, container)
    # Wired here rather than in build_container(): the Auditor needs the CONTAINER to build, so
    # the engine cannot hold it at construction time — see ConversationEngine.__init__'s comment.
    container.engine.set_auditor(app.state.auditor)
    app.state.cwe_guard = cwe_guard

    for name, probe in container.health_probes().items():
        register_readiness_check(name, probe)

    app.add_middleware(BodyLimitMiddleware, max_bytes=settings.BODY_LIMIT_BYTES)
    app.add_middleware(TimeoutMiddleware, timeout_ms=settings.REQUEST_TIMEOUT_MS)
    app.add_middleware(SecurityHeadersMiddleware, frame_ancestors=settings.ALLOWED_FRAME_ANCESTORS,
                       is_production=settings.is_production)
    app.add_middleware(RequestIdMiddleware)

    if settings.cors_origins:
        from fastapi.middleware.cors import CORSMiddleware
        app.add_middleware(
            CORSMiddleware, allow_origins=settings.cors_origins,
            allow_credentials=settings.CORS_ALLOW_CREDENTIALS, allow_methods=settings.cors_methods,
            allow_headers=settings.cors_headers, max_age=settings.CORS_MAX_AGE_SECONDS)

    register_error_handlers(app)

    from app.api.ratelimit import build_policy, register_ratelimit_refund
    app.state.ratelimit_policy = build_policy(settings)
    register_ratelimit_refund(app)

    app.include_router(health.router)
    app.include_router(metrics.router)
    app.include_router(internal.router)
    # NEVER MOUNTED UNTIL NOW — /whoami and /admin/ping were live routes on paper (defined,
    # imported by nothing) since whichever commit added app/api/v1/__init__.py. Found while wiring
    # operator.router in for GEMINI_API_KEY rotation: the operator route needed v1's own auth
    # dependencies to mean anything, and testing that path is what surfaced the missing include.
    app.include_router(v1_router)
    app.include_router(operator_router)

    return app


# ASGI entry point: `uvicorn app.main:app`
app = create_app()
