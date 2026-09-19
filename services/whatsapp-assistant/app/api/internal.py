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
from starlette.responses import JSONResponse

from app.backup_manifest import BACKUP
from app.config import Settings, get_settings
from app.core import backup as _backup
from app.core.inbound_ingest import outbound_allowed
from app.manifest import build_manifest


def _refuse(reason: str, status_code: int = 400) -> JSONResponse:
    """A refusal the CALLER (backup-service) can read — returned, not raised. Fixed 2026-09-12, a
    real gap a QA audit found: `raise HTTPException(400, str(exc))` looked right but the global
    handler (app/api/errors.py's `_http_exc`) strips every `HTTPException.detail` on purpose (CWE-209
    hardening for user-facing responses) and returns only a generic `{"error": "BAD_REQUEST"}` —
    silently discarding the ONE THING that made the 400 actionable: which archive-specific reason
    backup-service should log or retry on. Matches `app/api/v1/operator.py`'s own `_refuse` for the
    identical reason."""
    return JSONResponse({"error": "BAD_REQUEST", "reason": reason}, status_code=status_code)


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


async def require_push_signature(
    request: Request,
    x_job_signature: str | None = Header(default=None, alias="X-Job-Signature"),
    x_job_signature_timestamp: str | None = Header(default=None,
                                                   alias="X-Job-Signature-Timestamp"),
    settings: Settings = Depends(get_settings),
) -> None:
    """A door driven ONLY by job-service's own push dispatch (base-services v0.24.0) — see
    app/core/push_verify.py's own docstring for the scheme. `require_internal_token` alone would
    accept ANY caller that knows the shared fleet secret; this additionally proves the body is
    exactly what job-service sent, at the moment it sent it, never a replay."""
    import time as _time

    from app.core.push_verify import verify as verify_push

    body = await request.body()
    secret = settings.PUSH_SIGNING_SECRET or settings.INTERNAL_SERVICE_TOKEN
    ok = verify_push(secret, x_job_signature_timestamp or "", body, x_job_signature or "",
                     now=_time.time(), max_skew_seconds=settings.PUSH_SIGNATURE_MAX_SKEW_SECONDS)
    if not ok:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="UNAUTHORIZED")


@router.get("/health", dependencies=[Depends(require_internal_token)])
async def internal_health(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    return {"status": "ok", "service": settings.SERVICE_NAME}


@router.get("/manifest", dependencies=[Depends(require_internal_token)])
async def manifest(request: Request, settings: Settings = Depends(get_settings)) -> dict:
    container = request.app.state.container
    return build_manifest(settings, ports=container.describe())


class CarouselShownIn(BaseModel):
    tenant: str = Field(min_length=1, max_length=128)
    subject_ref: str = Field(min_length=1, max_length=256)
    # THE SAME PSEUDONYM campaigns/reminders already compute (core/pii.py::subject_ref, one
    # shared PII_SALT across the fleet) — never a phone number crossing this boundary.
    item_ids: list[str] = Field(min_length=1, max_length=10)
    # ONLY APPLIED TO A BRAND-NEW CONVERSATION ROW — see register_carousel_shown's own docstring
    # for why an existing one keeps whatever it already fixed from the customer's own number.
    branch_id: str = Field(default="", max_length=64)


@router.post("/carousel-shown", dependencies=[Depends(require_internal_token)])
async def carousel_shown(request: Request, body: CarouselShownIn) -> dict:
    """A campaign's own carousel (services/campaigns, 2026-09-13) was just sent to this customer,
    outside any live conversation this engine ran — see ConversationEngine.register_carousel_shown
    for what this actually writes and why. Called by whichever peer decided the card gets a real
    button at all (campaigns' own Dispatcher._card_button_allowed) — never by an unauthenticated
    caller, same `X-Internal-Token` gate as every other door in this file.

    `{"ok": True}` always — there is no partial failure to report short of an exception, which
    the caller (reminders' sender, best-effort) already treats as "no button" on any error.
    """
    container = request.app.state.container
    await container.engine.register_carousel_shown(
        tenant=body.tenant, subject_ref=body.subject_ref, item_ids=list(body.item_ids),
        branch_id=body.branch_id)
    return {"ok": True}


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
        # ISOLATED PER CONVERSATION, ON PURPOSE — this call is the one real network/LLM round
        # trip in the whole tick, and it is exactly the one that can fail on data this service
        # does not control (a malformed provider response, a transient model-garden outage, one
        # poisoned conversation history). Before this try/except, an exception here propagated
        # out of BOTH loops — this tenant's remaining due conversations AND every tenant still
        # queued behind this one in tick()'s own loop never ran, and since nothing here advances
        # the conversation's due state before compose_reply is called, the exact same poisoned
        # conversation is due again next tick — a single bad reply could wedge the reply pipeline
        # for the entire platform indefinitely. Any wallet hold `compose_reply` reserved is not
        # leaked by skipping it: `self._reserve_llm_hold`'s own contract is that an unconfirmed
        # hold simply expires on wallet-service's HOLD_TTL_SECONDS, never stranded (see
        # core/conversation.py's `compose_reply` docstring at the `confirm(hold_id)` call).
        try:
            plan = await c.engine.compose_reply(tenant, subject_ref, now=now)
        except Exception:
            from app.observability.logging import get_logger
            get_logger("app.internal.tick").exception(
                "whatsapp_compose_reply_failed",
                extra={"tenant": tenant, "subject_ref": subject_ref})
            continue
        if plan.kind == "none":
            continue
        conv = await c.datastore.get("wa_conversations", f"{tenant}|{subject_ref}")
        to = (conv or {}).get("from_number", "")
        if not to:
            continue
        branch_id = (conv or {}).get("branch_id", "")
        if not await outbound_allowed(c, settings, tenant, subject_ref=subject_ref,
                                      branch_id=branch_id):
            from app.observability.logging import get_logger
            get_logger("app.internal.tick").warning(
                "whatsapp_outbound_capped", extra={"tenant": tenant})
            # SEE app/core/inbound_ingest.py's OWN NOTE on this same audit action — a cap trip is a
            # `warning`, which Fluent Bit never ships to error-collector on purpose, so this is the
            # only way an operator ever sees or counts one from the tick path.
            try:
                await auditor.record(
                    "whatsapp_assistant.outbound_capped", actor="whatsapp-assistant",
                    resource=f"subject_ref:{subject_ref}", tenant=tenant,
                    metadata={"subject_ref": subject_ref, "branch_id": branch_id})
            except Exception:                                        # noqa: BLE001
                pass
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
        elif plan.kind == "card" and plan.card is not None:
            await c.sender.send_single_card(
                tenant=tenant, to=to, card=plan.card.card,
                idempotency_key=f"tick_{tenant}_{subject_ref}_{now}")
            replied += 1
        elif plan.kind == "request_location" and plan.text:
            await c.sender.send_location_request(
                tenant=tenant, to=to, body=plan.text,
                idempotency_key=f"tick_{tenant}_{subject_ref}_{now}")
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


class UpcomingRenewalTriggerIn(BaseModel):
    tenant: str = Field(min_length=1, max_length=128)
    subscription_id: str = Field(min_length=1, max_length=128)
    period_end: int = Field(gt=0)


@router.post("/whatsapp/upcoming-renewal/trigger", dependencies=[Depends(require_internal_token)])
async def upcoming_renewal_trigger(request: Request, body: UpcomingRenewalTriggerIn) -> dict:
    """Fire the 2-days-ahead renewal heads-up for ONE subscription — called per row by whatever
    finds subscriptions renewing soon (see app/core/upcoming_renewal_trigger.py's own docstring
    for why this is a proactive notice, never the automatic billing cycle itself, which stays
    completely untouched). `tenant` is always taken from the body, never assumed."""
    import time as _time

    c = request.app.state.container
    sent = await c.upcoming_renewal_trigger.handle(
        tenant=body.tenant, subscription_id=body.subscription_id, period_end=body.period_end,
        now=int(_time.time()))
    return {"sent": sent}


@router.post("/whatsapp_assistant/tick",
            dependencies=[Depends(require_internal_token), Depends(require_push_signature)])
async def tick(request: Request, settings: Settings = Depends(get_settings)) -> dict:
    """The scheduled sweep: compose debounced replies whose window elapsed, close sessions past
    their silence timeout. Imitates services/reminders' /internal split between the event
    fast-path (subscribed in main.py's lifespan) and this cron-driven tick — the fast path can
    silently miss an event; this cannot silently miss a due conversation, because it scans this
    service's OWN datastore rather than depending on the bus a second time.

    DRIVEN BY job-service's PUSH DISPATCH, NOT A K8S CronJob (migrated 2026-09-15 — see
    `deploy/hooks/job-schedule.sh`'s own header for the reasoning and the migration plan for our
    other services' own cron entries) — `require_push_signature` on top of the usual internal
    token means this only ever fires on a genuine, unreplayed push job-service itself sent.

    THE BODY CARRIES `{"job": {...}}` (job-service's own wrapper) rather than a bare `{"tenant":
    ...}` — this route needs no field off it at all (a tick sweeps every tenant with a due
    conversation row regardless of which job fired it), so `tenant` below simply stays empty on
    every real push, exactly as it already did under the old CronJob's empty POST body.

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
        # ISOLATED PER TENANT, ON PURPOSE — mirrors the per-conversation isolation inside
        # `_tick_one_tenant` itself (see its own comment on the `compose_reply` call). This is
        # the outer defence: anything else in that function which can still raise (sweep_due,
        # sweep_timed_out, retention) must not cost every OTHER tenant its tick just because one
        # tenant's data is bad. One tenant simply gets nothing counted this tick and is picked
        # up again next time; every other tenant proceeds normally.
        try:
            got = await _tick_one_tenant(c, settings, t, now=now, batch=batch,
                                         auditor=request.app.state.auditor)
        except Exception:
            from app.observability.logging import get_logger
            get_logger("app.internal.tick").exception(
                "whatsapp_tick_one_tenant_failed", extra={"tenant": t})
            continue
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

    # ── coexistence catch-up sweep — notes every owner-sent echo so the AI goes quiet on that
    # customer for a while (app/core/owner_presence.py). Same global-cursor reasoning as the
    # inbound sweep just above; a no-op ({"configured": False, ...}) when the feature is off.
    from app.core.coexistence_poll import CoexistencePoller

    co_poller = CoexistencePoller(container=c, settings=settings,
                                  logger=get_logger("app.coexistence_poll"),
                                  max_pages=settings.COEXISTENCE_POLL_MAX_PAGES)
    coexistence_poll = await co_poller.run(now=now)

    return {"tenant": tenant, "tenants_swept": len(tenants), "replied": replied, "closed": closed,
            "scanned": scanned,
            "retention_purged_conversations": retention_purged_conversations,
            "retention_purged_messages": retention_purged_messages,
            "retention_truncated": retention_truncated,
            "inbound_poll": inbound_poll,
            "coexistence_poll": coexistence_poll}


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
    # AUTHORITATIVE undo: also delete rows present now but absent from the archive
    # (backup-r2-01). Set only by the undo path; never combined with into_tenant.
    prune: bool = False


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
        return _refuse(str(exc))


@router.post("/backup/import", dependencies=[Depends(require_internal_token)])
async def backup_import(request: Request, body: BackupImportIn,
                        settings: Settings = Depends(get_settings)) -> dict:
    """Restore an archive this service produced. Idempotent; leaves newer rows alone by default."""
    _, unseal = _sealer(settings)
    try:
        return await _backup.import_archive(
            request.app.state.container.datastore, body.archive,
            unseal=unseal, overwrite=body.overwrite, into_tenant=body.into_tenant,
            declaration=BACKUP, prune=body.prune,
            scan_cap=settings.BACKUP_MAX_ROWS_PER_COLLECTION)
    except _backup.BackupError as exc:
        # A bad archive is the caller's problem, not a 500: the checksum failed, the key did not
        # match, or a row had no identity. Say which, so an operator can act. RETURNED, not raised
        # — see `_refuse`'s own docstring for why raising here used to lose this exact detail.
        return _refuse(str(exc))


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
