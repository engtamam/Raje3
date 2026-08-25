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

        # ── inbound WhatsApp: the FAST path, and it is NOT the only path ─────────────────────
        #
        # notification-service's EventBus is explicitly at-most-once and non-durable (its own
        # docstring says so). This subscription is a hint that makes a reply faster when it
        # arrives; it is never the only way a message can be learned about, because there is no
        # catch-up read for inbound messages on that peer (only for delivery receipts) — see
        # deploy/services/whatsapp-assistant.values.yaml's ESCALATED note.
        #
        # The mitigation THIS service owns: every event is persisted into inbound_store, keyed by
        # Meta's wamid, BEFORE anything is processed — see app/ports/inbound_store.py. A
        # redelivery of the same wamid (this subscription firing twice, or a future durable
        # replay mechanism landing the same message again) is dropped here, not double-processed.
        async def _on_whatsapp_message(event) -> None:
            payload = getattr(event, "payload", None) or {}
            tenant = str(payload.get("tenant") or "")
            wamid = str(payload.get("wamid") or payload.get("id") or "")
            from_number = str(payload.get("from") or payload.get("from_number") or "")
            if not tenant or not wamid or not from_number:
                return
            is_new = await container.inbound_store.record_if_new(tenant, wamid, payload)
            if not is_new:
                return
            try:
                lookup = await container.customer_lookup.resolve(tenant, from_number)
                subject_ref = str(lookup.get("subject_ref") or "")
                if not subject_ref:
                    # UNKNOWN CUSTOMER. Rather than invent a pseudonym (which would collide with
                    # a real one the day this number does become a customer), the conversation is
                    # keyed on a per-number-per-tenant hash derived the same way core/pii.py
                    # derives subject_ref, so an unrecognised sender can still hold a session.
                    from app.core.pii import subject_ref as derive_ref
                    subject_ref = derive_ref(settings.PII_SALT or "dev-salt", tenant, from_number)

                kind = str(payload.get("kind") or "text")
                if kind in ("button_reply", "list_reply"):
                    reply_id = str(payload.get("reply_id") or payload.get("id_reply") or "")
                    from app.core import points as P

                    plan = await container.engine.handle_button_reply(
                        tenant=tenant, subject_ref=subject_ref, reply_id=reply_id,
                        redeemer=container.points_summary, auditor=_app.state.auditor)
                else:
                    text = str(payload.get("text") or "")
                    await container.engine.on_inbound_text(
                        tenant=tenant, subject_ref=subject_ref, from_number=from_number, text=text)
                    plan = None

                if plan is not None and plan.kind == "text" and plan.text:
                    await container.sender.send_template(
                        tenant=tenant, to=from_number, template_name="wa_assistant_reply",
                        variables=[plan.text], idempotency_key=f"{wamid}:reply")
            except Exception as exc:                                        # noqa: BLE001
                logger.warning("whatsapp_message_handling_failed",
                               extra={"error": str(exc)[:200], "tenant": tenant, "wamid": wamid})
            finally:
                await container.inbound_store.mark_processed(tenant, wamid)

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

    return app


# ASGI entry point: `uvicorn app.main:app`
app = create_app()
