# =============================================================================
# whatsapp-assistant — Internal tier (service-to-service, X-Internal-Token)
# -----------------------------------------------------------------------------
# NOT user-facing. Guarded by a shared token compared in CONSTANT TIME
# (CWE-208), exactly as every sibling service's internal.py does it.
# =============================================================================
from __future__ import annotations

import hmac
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.backup_manifest import BACKUP
from app.config import Settings, get_settings
from app.core import backup as _backup
from app.core.inbound_ingest import outbound_allowed
from app.manifest import build_manifest


def _now_iso() -> str:
    import datetime as _dt
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

router = APIRouter(prefix="/internal", tags=["internal"])

_HEADER = "X-Internal-Token"


async def require_internal_token(
    x_internal_token: str | None = Header(default=None, alias=_HEADER),
    settings: Settings = Depends(get_settings),
) -> None:
    expected = settings.INTERNAL_SERVICE_TOKEN
    provided = x_internal_token or ""
    if not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="UNAUTHORIZED")


@router.get("/health", dependencies=[Depends(require_internal_token)])
async def internal_health(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    return {"status": "ok", "service": settings.SERVICE_NAME}


@router.get("/manifest", dependencies=[Depends(require_internal_token)])
async def manifest(request: Request, settings: Settings = Depends(get_settings)) -> dict:
    container = request.app.state.container
    return build_manifest(settings, ports=container.describe())


async def _active_tenants(c: Any, *, limit: int) -> list[str]:
    """Tenants with a conversation row at all, from OUR OWN datastore — same "derive it from our
    own rows rather than ask a peer" shape as services/reminders' `_active_tenants`. A CronJob
    posts no body and cannot be templated per tenant (one fixed TARGET_URL — see
    platform/deploy/chart/templates/cronjob.yaml), so a global sweep must discover its own
    worklist rather than be handed one."""
    from app.core.models import CONVERSATIONS

    rows = await c.datastore.scan_all(CONVERSATIONS, limit)
    seen: list[str] = []
    for r in rows:
        t = r.get("tenant") or ""
        if t and t not in seen:
            seen.append(t)
    return seen


async def _tick_one_tenant(c: Any, settings: Settings, tenant: str, *, now: int, batch: int,
                           auditor: Any) -> dict:
    replied = 0
    due = await c.engine.sweep_due(tenant, now=now, batch=batch)
    for subject_ref in due:
        plan = await c.engine.compose_reply(tenant, subject_ref, now=now)
        if plan.kind == "none":
            continue
        conv = await c.datastore.get("wa_conversations", f"{tenant}|{subject_ref}")
        to = (conv or {}).get("from_number", "")
        if not to:
            continue
        if not await outbound_allowed(c, settings, tenant):
            from app.observability.logging import get_logger
            get_logger("app.internal.tick").warning(
                "whatsapp_outbound_capped", extra={"tenant": tenant})
            continue
        if plan.kind == "text" and plan.text:
            await c.sender.send_template(
                tenant=tenant, to=to, template_name="wa_assistant_reply",
                variables=[plan.text], idempotency_key=f"tick_{tenant}_{subject_ref}_{now}")
            replied += 1
        elif plan.kind == "interactive" and plan.proposal is not None:
            await c.sender.send_interactive(
                tenant=tenant, to=to, body=plan.proposal.body, buttons=plan.proposal.buttons,
                idempotency_key=f"tick_{plan.proposal.proposal_id}")
            replied += 1
        elif plan.kind == "carousel" and plan.carousel is not None:
            await c.sender.send_carousel(
                tenant=tenant, to=to,
                template_name=settings.WHATSAPP_CATALOG_CAROUSEL_TEMPLATE_NAME,
                language=settings.WHATSAPP_CATALOG_CAROUSEL_LANGUAGE,
                cards=plan.carousel.cards, idempotency_key=f"tick_{tenant}_{subject_ref}_{now}")
            replied += 1

    timed_out = await c.engine.sweep_timed_out(tenant, now=now, batch=batch)

    # ── chat data retention — same tick, no separate unmonitored cron ────────────────────────
    # Runs AFTER the reply/timeout sweep above: a conversation must actually be closed (which the
    # sweep just did for anything newly timed out) before retention has anything to consider. See
    # app/core/retention.py for the full pattern and why it belongs here rather than its own cron.
    from app.core.retention import run_retention_tick

    retention = await run_retention_tick(
        tenant, now=now, store=c.datastore, inbound_store=c.inbound_store,
        auditor=auditor,
        retention_days=settings.CHAT_RETENTION_DAYS,
        batch=settings.CHAT_RETENTION_TICK_BATCH_SIZE,
        max_scan_per_subject=settings.ERASURE_MAX_SCAN)

    return {"replied": replied, "closed": len(timed_out), "scanned": len(due),
            "retention_purged_conversations": retention.purged_conversations,
            "retention_purged_messages": retention.purged_messages,
            "retention_truncated": retention.truncated}


@router.post("/whatsapp_assistant/tick", dependencies=[Depends(require_internal_token)])
async def tick(request: Request, settings: Settings = Depends(get_settings)) -> dict:
    """The scheduled sweep: compose debounced replies whose window elapsed, close sessions past
    their silence timeout. Imitates services/reminders' /internal split between the event
    fast-path (subscribed in main.py's lifespan) and this cron-driven tick — the fast path can
    silently miss an event; this cannot silently miss a due conversation, because it scans this
    service's OWN datastore rather than depending on the bus a second time.

    EMPTY BODY (NO `tenant`) MEANS EVERY TENANT WITH A CONVERSATION ROW — the platform's CronJob
    template posts an EMPTY body (no way to template one per tenant, one fixed TARGET_URL), so a
    tick that REQUIRED `tenant` would fail on every single scheduled invocation while every probe
    stayed green: the exact defect reminders' own /reminders/tick already carries this same fix
    for. `tenant` in the body is what an operator uses to unstick one shop by hand.

    Per-tenant, bounded (CONVERSATION_TICK_BATCH_SIZE) — the same reasoning as reminders'
    TICK_BATCH_SIZE: an unbounded sweep is how one busy tenant starves every other one.
    """
    import time as _time

    c = request.app.state.container
    body: dict = {}
    try:
        body = await request.json()
    except Exception:
        body = {}
    tenant = str(body.get("tenant") or "")

    now = int(_time.time())
    batch = settings.CONVERSATION_TICK_BATCH_SIZE
    tenants = [tenant] if tenant else await _active_tenants(c, limit=2000)

    # ── scheduled pricing changes — once per tick, never per-tenant (pricing is platform-wide,
    # same as every other RUNTIME_POLICY knob this service has) ──────────────────────────────────
    # See core/pricing_schedule.py's own docstring for why a pricing change is scheduled rather
    # than instant. Runs even on a tenant-scoped manual tick (an operator unsticking one shop by
    # hand should not also silently suppress a due platform-wide price change from ever landing).
    from app.core.pricing_schedule import apply_due as _apply_due_pricing

    pricing_applied = await _apply_due_pricing(c.datastore, c.runtime_config, now=now)

    replied = closed = scanned = 0
    retention_purged_conversations = retention_purged_messages = 0
    retention_truncated = False
    for t in tenants:
        got = await _tick_one_tenant(c, settings, t, now=now, batch=batch,
                                     auditor=request.app.state.auditor)
        replied += got["replied"]
        closed += got["closed"]
        scanned += got["scanned"]
        retention_purged_conversations += got["retention_purged_conversations"]
        retention_purged_messages += got["retention_purged_messages"]
        retention_truncated = retention_truncated or got["retention_truncated"]

    # ── inbound catch-up sweep — closes the "bus dropped a whatsapp.message event" gap ────────
    # Not tenant-scoped (unlike the reply/timeout sweep above): notification-service's inbound
    # feed is one global cursor across every tenant, so it runs once per tick call regardless of
    # which (or how many) tenants this invocation swept above. Bounded and idempotent (see
    # app/core/inbound_poll.py).
    from app.core.inbound_poll import InboundPoller
    from app.observability.logging import get_logger

    poller = InboundPoller(container=c, settings=settings, logger=get_logger("app.inbound_poll"),
                           max_pages=settings.INBOUND_POLL_MAX_PAGES)
    inbound_poll = await poller.run(auditor=request.app.state.auditor)

    return {"tenant": tenant, "tenants_swept": len(tenants), "replied": replied, "closed": closed,
            "scanned": scanned,
            "retention_purged_conversations": retention_purged_conversations,
            "retention_purged_messages": retention_purged_messages,
            "retention_truncated": retention_truncated,
            "inbound_poll": inbound_poll}


class EraseIn(BaseModel):
    tenant: str
    subject: str


@router.post("/privacy/erase", dependencies=[Depends(require_internal_token)])
async def erase_subject(request: Request, body: EraseIn) -> dict:
    """Erase a data subject's WhatsApp conversation data. Called by compliance-service during a
    DSAR fan-out — see app/core/erasure.py. Runs regardless of CHAT_RETENTION_DAYS: a customer
    asking to be forgotten does not wait for the scheduled purge to agree with them.

    Idempotent — a DSAR retries, so erasing an already-erased subject must not fail.
    """
    c = request.app.state.container
    s = get_settings()
    # WRITE-AHEAD, and critical — see app/core/audit.py. Erasure is irreversible; recording
    # afterwards would leave exactly the case that matters (an erasure that half-succeeded) with
    # no record that it was ever attempted.
    await request.app.state.auditor.record(
        "subject.erased", actor="", tenant=body.tenant, resource="subject",
        ip=request.client.host if request.client else "")

    from app.core.erasure import WhatsAppAssistantErasure

    eraser = WhatsAppAssistantErasure(
        store=c.datastore, inbound_store=c.inbound_store, max_scan=s.ERASURE_MAX_SCAN)
    return await eraser.erase(body.tenant, body.subject)


# ── backup — declared by app/manifest.py's endpoints from day one, so it must actually exist ────
# Mirrors services/loyalty/app/api/internal.py's three routes exactly; app/core/backup.py is a
# verbatim copy of loyalty's generic seal/export/import/verify logic, and app/backup_manifest.py
# is this service's own declaration of what wa_* collections it holds.
class BackupExportIn(BaseModel):
    # Empty tenant = the whole service; a value = just that customer's tenant-scoped rows.
    tenant: str = ""


class BackupImportIn(BaseModel):
    archive: dict
    # Off by default: a restore must not bulldoze rows written after the backup unless the operator
    # driving the restore says so.
    overwrite: bool = False
    # Empty = restore in place. A value REMAPS the restore into that tenant (restore-as-clone):
    # only rows that carry a tenant are reassigned; a global dataset is left alone.
    into_tenant: str = ""


def _sealer(settings: Settings):
    """The backup (seal, unseal) pair, or a 503 when no backup key is configured.

    Refused rather than defaulted: sealing with an empty key would write a plaintext-equivalent
    archive while every check reported it encrypted — the one outcome a backup must never have.
    """
    if not settings.BACKUP_KEK:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "BACKUP_KEK not configured — set this SHARED key (the SAME value backup-service holds) on this service, or its archives cannot be opened")
    return _backup.make_sealer(settings.BACKUP_KEK)


@router.post("/backup/export", dependencies=[Depends(require_internal_token)])
async def backup_export(request: Request, body: BackupExportIn,
                        settings: Settings = Depends(get_settings)) -> dict:
    """Produce a sealed, checksummed archive of this service's declared data.

    Called by backup-service, on a schedule, over the internal token. What this service holds is
    declared in app/backup_manifest.py; how it is read lives in core/backup.py. The orchestrator
    stores the archive and never sees the plaintext.
    """
    seal, _ = _sealer(settings)
    return await _backup.export(
        request.app.state.container.datastore, BACKUP,
        service=settings.SERVICE_NAME, version=settings.SERVICE_VERSION,
        taken_at=_now_iso(), seal=seal, tenant=body.tenant,
        scan_cap=settings.BACKUP_MAX_ROWS_PER_COLLECTION)


class BackupVerifyIn(BaseModel):
    archive: dict


@router.post("/backup/verify", dependencies=[Depends(require_internal_token)])
async def backup_verify(request: Request, body: BackupVerifyIn,
                        settings: Settings = Depends(get_settings)) -> dict:
    """Prove an archive restores, by test-restoring it into a throwaway namespace and comparing.

    backup-service calls this after it stores an archive. This service is the only party that can
    unseal its own archive and knows its own schema, so verification lives here; the orchestrator
    only records the verdict. The throwaway namespace is torn down before this returns.
    """
    import secrets
    _, unseal = _sealer(settings)
    try:
        return await _backup.verify_restore(
            request.app.state.container.datastore, body.archive,
            unseal=unseal, token=secrets.token_hex(8), declaration=BACKUP)
    except _backup.BackupError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.post("/backup/import", dependencies=[Depends(require_internal_token)])
async def backup_import(request: Request, body: BackupImportIn,
                        settings: Settings = Depends(get_settings)) -> dict:
    """Restore an archive this service produced. Idempotent; leaves newer rows alone by default."""
    _, unseal = _sealer(settings)
    try:
        return await _backup.import_archive(
            request.app.state.container.datastore, body.archive,
            unseal=unseal, overwrite=body.overwrite, into_tenant=body.into_tenant,
            declaration=BACKUP)
    except _backup.BackupError as exc:
        # A bad archive is the caller's problem, not a 500: the checksum failed, the key did not
        # match, or a row had no identity. Say which, so an operator can act.
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


# ── pricing — the smallest honest caller for a genuinely staged module ──────────────────────────
# app/core/pricing.py computed a price nothing ever asked for (ci/check_dead_core.py flagged it):
# no billing peer exists yet to charge a shop for this service. Following docs/adding-a-new-app.md
# §3c's own precedent (bookings' /internal/availability/check, pulled forward for the same reason)
# this is the smallest real, callable, tested interface — token counts and period context in the
# request body rather than read from a store that does not exist yet — and it becomes the exact
# route a future billing/insights peer calls once one exists. Nothing about price_conversation's
# own signature changes later; only where its inputs come from does.
class PriceIn(BaseModel):
    # ge=0 ADDED 2026-09-07 — a QA audit found this had no floor: a negative value reached
    # pricing.usage_based() and could produce a negative halalas result with nothing clamping it.
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    # THIS PERIOD'S conversation count / first-of-period flag — the caller's to track (it is the
    # one that knows the billing period), not this service's; see core/pricing.py's own docstring
    # for why: a business number frozen into this service would be a rewrite waiting to happen.
    conversations_this_period: int = 0
    is_first_conversation_this_period: bool = False


@router.post("/whatsapp_assistant/price", dependencies=[Depends(require_internal_token)])
async def price(body: PriceIn, request: Request, settings: Settings = Depends(get_settings)) -> dict:
    """What ONE conversation would cost under the configured PRICING_STRATEGY.

    Every constant behind this is zero in config today (see core/pricing.py's module docstring) —
    this computes the SHAPE, not a real charge, until the business sets real numbers. Resolved
    through RuntimeConfig (`from_runtime`, not `from_settings`) — a scheduled pricing change that
    has landed (core/pricing_schedule.py) must be reflected here on the very next call, the same
    "no redeploy" contract every other RUNTIME_POLICY knob already has.
    """
    from app.core.pricing import ConversationCost, PricingConfig, price_conversation

    container = getattr(request.app.state, "container", None)
    runtime_config = getattr(container, "runtime_config", None) if container is not None else None
    cfg = await PricingConfig.from_runtime(runtime_config, settings)
    cost = ConversationCost(input_tokens=body.input_tokens, output_tokens=body.output_tokens)
    try:
        halalas = price_conversation(
            cfg, cost, conversations_this_period=body.conversations_this_period,
            is_first_conversation_this_period=body.is_first_conversation_this_period)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return {"strategy": cfg.strategy, "halalas": halalas}


# ── PHASE 5 — the WhatsApp Flow booking channel ──────────────────────────────────────────────
class FlowBookingIn(BaseModel):
    """The platform's own HttpBookingBackend adapter's fixed shape (notification-service's
    services/notification-service/app/adapters/booking/http.py) — one op, one tenant, and
    whichever of `dimension`/`chosen`/`date`/`selection`/`idempotency_key` that op needs. Kept
    permissive (no per-op required-field split) because the platform is the one enforcing which
    op sends what; a stricter model here would just be a second, possibly-drifting copy of that
    contract."""
    op: str
    tenant: str = ""
    customer: str = ""
    dimension: str = ""
    chosen: dict[str, Any] = Field(default_factory=dict)
    date: str = ""
    selection: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str = ""


@router.post("/whatsapp-flow/booking", dependencies=[Depends(require_internal_token)])
async def whatsapp_flow_booking(body: FlowBookingIn, request: Request) -> dict:
    """Answers the platform's generic booking_flow.py engine (v0.18.54+) — see
    core/flow_booking_backend.py's own module docstring for the full contract and the
    single-branch-shops-only limitation. 404s (via a plain refusal, never a stack trace) when
    WHATSAPP_FLOW_BOOKING_ENABLED is off, so an unconfigured deployment's Flow simply cannot
    reach a backend rather than crash one that half-exists.
    """
    container = getattr(request.app.state, "container", None)
    backend = getattr(container, "flow_booking_provider", None) if container is not None else None
    if backend is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "WhatsApp Flow booking is not enabled")

    if body.op == "options":
        options = await backend.options(tenant=body.tenant, dimension=body.dimension,
                                        chosen=body.chosen, customer=body.customer)
        return {"options": options}
    if body.op == "calendar":
        return await backend.calendar(tenant=body.tenant, chosen=body.chosen,
                                      customer=body.customer)
    if body.op == "slots":
        slots = await backend.slots(tenant=body.tenant, chosen=body.chosen, date=body.date,
                                    customer=body.customer)
        return {"slots": slots}
    if body.op == "reserve":
        return await backend.reserve(tenant=body.tenant, selection=body.selection,
                                     idempotency_key=body.idempotency_key, customer=body.customer)
    raise HTTPException(status.HTTP_400_BAD_REQUEST, f"unknown op {body.op!r}")
