# =============================================================================
# reminders — Internal tier (service-to-service, X-Internal-Token)
# -----------------------------------------------------------------------------
# NOT user-facing. Guarded by a shared token compared in CONSTANT TIME
# (CWE-208: observable timing discrepancy). Never a user JWT.
# =============================================================================
from __future__ import annotations

import time

import hmac

from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from app.config import Settings, get_settings
from app.core.erasure import RemindersErasure
from app.core import backup as _backup
from app.backup_manifest import BACKUP
from app.manifest import build_manifest

router = APIRouter(prefix="/internal", tags=["internal"])


def _now_iso() -> str:
    import datetime as _dt
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

_HEADER = "X-Internal-Token"


async def require_internal_token(
    x_internal_token: str | None = Header(default=None, alias=_HEADER),
    settings: Settings = Depends(get_settings),
) -> None:
    """Deny unless the caller presents the exact internal token (timing-safe)."""
    expected = settings.INTERNAL_SERVICE_TOKEN
    provided = x_internal_token or ""
    # hmac.compare_digest is constant-time and length-safe.
    if not hmac.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="UNAUTHORIZED"
        )


@router.get("/health", dependencies=[Depends(require_internal_token)])
async def internal_health(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    return {"status": "ok", "service": settings.SERVICE_NAME}


@router.get("/manifest", dependencies=[Depends(require_internal_token)])
async def internal_manifest(
    request: Request, settings: Settings = Depends(get_settings)
) -> dict:
    container = getattr(request.app.state, "container", None)
    ports = container.describe() if container is not None else []
    manifest = build_manifest(settings, ports=ports)
    guard = getattr(request.app.state, "cwe_guard", None)
    if guard is not None:
        manifest["security"] = {"cwe_guard": guard.report()}
    return manifest


class EraseIn(BaseModel):
    tenant: str
    subject: str


@router.post("/privacy/erase", dependencies=[Depends(require_internal_token)])
async def erase_subject(request: Request, body: EraseIn) -> dict:
    """Erase a data subject. Called by compliance-service during a DSAR fan-out.

    Returns the ack: what was erased, and what was RETAINED with its legal basis. Idempotent — a
    DSAR retries, so erasing an already-erased subject must not fail. Wire this service into the
    fan-out by adding it to PRIVACY_TARGETS in compliance-service's values file; the
    safety:privacy-wiring gate fails if you implement this and forget.
    """
    c = request.app.state.container
    s = get_settings()
    # WRITE-AHEAD, and critical. Erasure is irreversible; recording afterwards would leave exactly
    # the case that matters — the erasure that half-succeeded — with no record that it was tried.
    await request.app.state.auditor.record(
        "subject.erased", actor="", tenant=body.tenant, resource="subject",
        ip=request.client.host if request.client else "")
    # NO pii_salt. This service never receives a raw identifier, so it has nothing to hash — the
    # `subject` it is handed is already the pseudonym operations published. Passing a salt here
    # would imply a capability we deliberately do not have.
    eraser = RemindersErasure(store=c.datastore, max_scan=s.ERASURE_MAX_SCAN)
    return await eraser.erase(body.tenant, body.subject)


class TickIn(BaseModel):
    # Empty = every tenant with pending work. A value = just that one, which is what an operator
    # uses to unstick a single establishment without re-running the fleet.
    tenant: str = Field(default="", max_length=128)


@router.post("/reminders/tick", dependencies=[Depends(require_internal_token)])
async def tick(request: Request, body: TickIn) -> dict:
    """The heartbeat. A CronJob in the values file drives this.

    WITHOUT THE CRON THIS SERVICE IS INERT AND LOOKS HEALTHY: visits arrive, schedules are created,
    every probe is green, and not one message is ever sent. That is why the cron is declared in the
    values file and why a guard checks that this path exists — the failure has no symptom until an
    owner asks why nobody is coming back.

    Runs the catch-up read FIRST, then the send pass. In that order because the bus is
    at-most-once: a visit the event missed should be scheduled and sent in the same tick, not in
    the next one.
    """
    c = request.app.state.container
    s = get_settings()
    now = int(time.time())
    caught = {"read": 0, "scheduled": 0}

    # DISCOVERY FIRST, and before the tenant list is computed. An establishment whose first visit
    # event was missed has no pending schedule, so it would not be in that list — and would never
    # be caught up, for ever. Running discovery first means the schedule it creates is in the list
    # by the time the list is read.
    if not body.tenant:
        try:
            got = await c.ingest.discover(now=now, service_config={})
            caught["read"] += got.get("read", 0)
            caught["scheduled"] += got.get("scheduled", 0)
        except Exception as exc:                                            # noqa: BLE001
            c.telemetry.event("discover_failed", error=str(exc)[:200])

    tenants = [body.tenant] if body.tenant else await _active_tenants(c)
    sent = suppressed = deferred = failed = 0
    reasons: dict[str, int] = {}

    for tenant in tenants[:s.TICK_MAX_TENANTS]:
        cfg = await _service_config(c, tenant)
        try:
            got = await c.ingest.catch_up(tenant, now=now, service_config=cfg)
            caught["read"] += got.get("read", 0)
            caught["scheduled"] += got.get("scheduled", 0)
        except Exception as exc:                                            # noqa: BLE001
            # A catch-up failure must not skip the send pass: the schedules already in the
            # datastore are due regardless of whether operations is reachable right now.
            c.telemetry.event("catch_up_failed", tenant=tenant, error=str(exc)[:200])

        shop = await _establishment(c, tenant)
        if not shop.usable:
            # DEFER, DO NOT SEND. A message with a blank shop name is worse than a late one: the
            # customer reads it, and the owner cannot explain it. The next tick retries, and a
            # stale cached name is accepted precisely so this is rare.
            c.telemetry.event("tick_skipped_no_identity", tenant=tenant)
            reasons["no establishment identity"] = reasons.get("no establishment identity", 0) + 1
            continue
        res = await c.tick.run(
            tenant, now=now, library=await _library(c, tenant),
            service_names={k: v.get("name", k) for k, v in cfg.items()},
            establishment=shop.name, customer_names={}, tone=shop.tone)
        sent += res.sent
        suppressed += res.suppressed
        deferred += res.deferred
        failed += res.failed
        for k, v in res.reasons.items():
            reasons[k] = reasons.get(k, 0) + v

    return {"tenants": len(tenants), "caught_up": caught, "sent": sent,
            "suppressed": suppressed, "deferred": deferred, "failed": failed,
            # The reason counts, not just the totals. "312 suppressed" is an alarm; "312
            # suppressed, all outside the window" is a working system doing its job.
            "reasons": reasons}


class ReceiptIn(BaseModel):
    """A delivery fact from notification-service: the customer read it, or tapped the button."""
    tenant: str = Field(min_length=1, max_length=128)
    subject_ref: str = Field(min_length=8, max_length=128)
    # "read" or "click". Anything else is ignored rather than rejected — a peer that grows a new
    # receipt type must not start failing against us.
    event: str = Field(min_length=1, max_length=32)


@router.post("/reminders/receipt", dependencies=[Depends(require_internal_token)])
async def receipt(request: Request, body: ReceiptIn) -> dict:
    """Credit an engagement signal.

    THE ABSENCE OF A RECEIPT IS NOT A ZERO — it means we have not heard, which is different from
    ignored, and the score treats it that way by simply decaying. So there is no "unread" event and
    nothing to call here when a message goes unopened.
    """
    from app.core.engagement import EngagementConfig, add, points_for
    from app.core.stores import EngagementStore
    c = request.app.state.container
    s = get_settings()
    cfg = EngagementConfig(half_life_days=s.ENGAGEMENT_HALF_LIFE_DAYS,
                           full_threshold=s.ENGAGEMENT_FULL_THRESHOLD,
                           minimal_threshold=s.ENGAGEMENT_MINIMAL_THRESHOLD)
    points = points_for(body.event, cfg)
    if points <= 0:
        return {"credited": 0.0, "ignored": body.event}
    now = int(time.time())
    store = EngagementStore(c.datastore)
    row = await store.get(body.tenant, body.subject_ref) or {
        "id": f"eng_{body.subject_ref}", "tenant": body.tenant,
        "subject_ref": body.subject_ref, "score": 0.0, "scored_at": now}
    score, at = add(float(row.get("score") or 0.0), scored_at=int(row.get("scored_at") or now),
                    points=points, now=now, cfg=cfg)
    row["score"], row["scored_at"], row["updated"] = score, at, now
    await store.put(body.tenant, body.subject_ref, row)
    return {"credited": points, "score": score}


async def _active_tenants(c) -> list[str]:
    """Tenants with pending schedules.

    Derived from our own rows rather than asked of tenant-service: this must keep working when a
    peer is down, and a tenant with no pending schedule has nothing for the tick to do anyway.
    """
    rows, _ = await c.datastore.find("schedules", {"state": "pending"}, limit=2000,
                                     sort=("due_at", "asc"))
    seen: list[str] = []
    for r in rows:
        t = r.get("tenant") or ""
        if t and t not in seen:
            seen.append(t)
    return seen


async def _service_config(c, tenant: str) -> dict:
    """What each service's schedule should look like — resolved through the settings tree.

    REPLACES a `tenant_cache` lookup that nothing ever wrote, so every service fell back to the
    platform default and an owner who changed a cycle saw no effect. The tree answers per service:
    the service's own value if it has one, else its group's, else the tenant's general setting,
    else ours (spec §10.8.1).

    Returns the shape the scheduler already expects, so nothing downstream changes: the settings
    tree is a source of values, not a new concept for the engine to learn.
    """
    from app.config import get_settings
    from app.core.settings_tree import SettingsStore
    s = get_settings()
    tree = await SettingsStore(c.datastore, defaults={
        "interval_days": s.DEFAULT_INTERVAL_DAYS,
        "lead_days": s.DEFAULT_LEAD_DAYS,
        "follow_up_days": 0,
        "enabled": True}).load(tenant)

    # Every service the tenant has touched at any level, plus the ones with a live rule. A service
    # nobody configured needs no entry — the scheduler falls back to the same defaults the tree
    # would have returned, so an empty entry and a missing one mean the same thing.
    known = set(tree.services) | set(tree.service_group)
    rows, _ = await c.datastore.find("rules", {"tenant": tenant}, limit=500,
                                     sort=("updated", "desc")) if tenant else ([], None)
    known |= {r.get("service_id", "") for r in rows if r.get("service_id")}

    out: dict[str, dict] = {}
    for sid in sorted(x for x in known if x):
        v = tree.effective(sid)
        out[sid] = {
            "cycle_days": v.get("interval_days") or 0,
            "lead_days": v.get("lead_days") or 0,
            "follow_up_days": v.get("follow_up_days") or 0,
            # A service switched off schedules nothing NEW. Existing schedules are left alone: the
            # owner turned off future reminders, not the one already promised to a customer this
            # week, and silently cancelling those would be a decision they did not make.
            "enabled": bool(v.get("enabled", True)),
        }
    return out


async def _library(c, tenant: str) -> list:
    row = await c.datastore.get("tenant_cache", f"{tenant}|templates")
    return (row or {}).get("templates") or []


async def _establishment(c, tenant: str):
    """The shop, from tenant-service. Read once per tenant per tick and passed down.

    Replaces a `tenant_cache` lookup that nothing ever wrote — so every rendered message carried a
    blank where the establishment name belongs. Found by reading the code that reads it, not by a
    test: an empty string is a valid string.
    """
    return await c.identity.get(tenant)


class EligibilityIn(BaseModel):
    tenant: str = Field(min_length=1, max_length=128)
    subject_ref: str = Field(min_length=8, max_length=128)
    cls: str = Field(default="marketing", alias="class", max_length=32)

    model_config = {"populate_by_name": True}


@router.post("/reminders/eligibility", dependencies=[Depends(require_internal_token)])
async def eligibility(request: Request, body: EligibilityIn) -> dict:
    """Would the gate let this message through right now?

    ASKED BEFORE A CAMPAIGN COUNTS SOMEBODY, so the preview's number is the number that goes out. A
    campaign that counted 47 and delivered 31 would teach an owner that our figures are decoration.

    IT IS AN OPINION, NOT A RESERVATION. Nothing is held: the same subject asked twice gets the
    same answer, and the real decision is made again at send time by the same function. A
    reservation would have to be released by something, and whatever releases it is the bug.
    """
    from app.core import engagement as E
    from app.core import gate as G
    from app.core.stores import EngagementStore, PrefsStore, SendLogStore
    c = request.app.state.container
    s = get_settings()
    now = int(time.time())

    prefs = await PrefsStore(c.datastore).get(body.tenant, body.subject_ref) or {}
    eng = await EngagementStore(c.datastore).get(body.tenant, body.subject_ref) or {}
    recent = await SendLogStore(c.datastore).since(body.tenant, body.subject_ref,
                                                   since=now - 31 * 86400)
    d = G.evaluate(
        cls=body.cls, template_type="", now=now,
        limits=G.Limits(window_start_hour=s.SEND_WINDOW_START_HOUR,
                        window_end_hour=s.SEND_WINDOW_END_HOUR,
                        daily_service_cap=s.DAILY_SERVICE_CAP,
                        monthly_marketing_cap=s.MONTHLY_MARKETING_CAP,
                        monthly_awareness_cap=s.MONTHLY_AWARENESS_CAP,
                        marketing_cooldown_hours=s.MARKETING_COOLDOWN_HOURS,
                        daily_total_cap=s.DAILY_TOTAL_CAP),
        prefs_stopped=prefs.get("stopped") or {},
        engagement_score=float(eng.get("score") or 0.0),
        engagement_at=int(eng.get("scored_at") or 0),
        recent_sends=recent,
        eng_cfg=E.EngagementConfig(half_life_days=s.ENGAGEMENT_HALF_LIFE_DAYS,
                                   full_threshold=s.ENGAGEMENT_FULL_THRESHOLD,
                                   minimal_threshold=s.ENGAGEMENT_MINIMAL_THRESHOLD))
    # THE WINDOW IS EXCLUDED FROM THIS ANSWER, deliberately. A campaign previewed at 11pm would
    # otherwise report reaching nobody — when in truth everyone is reached, tomorrow morning. The
    # preview says WHEN separately; this says WHETHER.
    allowed = d.allowed or bool(d.retry_at)
    return {"allowed": allowed, "reason": "" if allowed else d.reason, "tier": d.tier}


class CampaignSendIn(BaseModel):
    tenant: str = Field(min_length=1, max_length=128)
    subject_ref: str = Field(min_length=8, max_length=128)
    template_type: str = Field(min_length=3, max_length=128)
    cls: str = Field(default="marketing", alias="class", max_length=32)
    # The owner's ONE free-text field. Sanitised by the caller AND here — a rule enforced on one
    # side of a boundary is a rule the other side can bypass.
    owner_text: str = Field(default="", max_length=200)
    idempotency_key: str = Field(min_length=8, max_length=256)

    model_config = {"populate_by_name": True}


@router.post("/reminders/send", dependencies=[Depends(require_internal_token)])
async def campaign_send(request: Request, body: CampaignSendIn) -> dict:
    """Send one campaign message — THE ONLY WAY campaigns sends anything.

    It goes through the same gate, the same template selection, the same sanitiser and the same
    ledger as a reminder. There is no campaign-shaped shortcut, because a second path is a second
    set of rules and the second one is always the one missing a check.

    Returns `{"sent": bool, "reason": str}` — and the reason is the gate's own sentence, carried
    into the campaign's run report verbatim.
    """
    c = request.app.state.container
    s = get_settings()
    now = int(time.time())

    shop = await c.identity.get(body.tenant)
    if not shop.usable:
        # A message with a blank shop name is worse than a late one: the customer reads it and the
        # owner cannot explain it.
        return {"sent": False, "reason": "تعذّر تحديد اسم المنشأة — لم تُرسَل."}

    schedule = {
        "tenant": body.tenant, "subject_ref": body.subject_ref, "cls": body.cls,
        "template_type": body.template_type, "service_id": "_campaign",
        "kind": "campaign", "owner_text": body.owner_text,
        "idempotency_key": body.idempotency_key, "id": body.idempotency_key,
        "also_services": [],
    }
    library = await _library(c, body.tenant)
    res = await c.tick.send_one(body.tenant, schedule, now=now, library=library,
                                service_names={}, establishment=shop.name, tone=shop.tone)
    return res


class ConsentCountIn(BaseModel):
    tenant: str = Field(min_length=1, max_length=128)


@router.post("/reminders/consent/count", dependencies=[Depends(require_internal_token)])
async def consent_count(request: Request, body: ConsentCountIn) -> dict:
    """How many customers currently allow this establishment's offers (spec §8.5).

    A COUNT, AND DELIBERATELY NOTHING ELSE. The owner is shown a number — "340 عميلاً وافقوا على
    استقبال عروضك" — and a route that returned WHO consented would be a customer list export
    wearing a different name. There is no `limit`, no cursor and no shape here that could grow
    into one.

    Counted from the NEWEST record per person, not by counting grants: somebody who granted and
    later withdrew has two rows and must not be counted, and somebody who granted twice is one
    person.
    """
    from app.core.consent import Consent

    c = request.app.state.container
    return {"tenant": body.tenant,
            "granted": await Consent(c.datastore).count_granted(body.tenant)}


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

    backup-service calls this after it stores an archive (passing back the bytes it read FROM the
    store, so corruption at rest is caught too). This service is the only party that can unseal its
    own archive and knows its own schema, so verification lives here; the orchestrator only records
    the verdict. The throwaway namespace is torn down before this returns — nothing is left behind,
    and live data is never touched.
    """
    import secrets
    _, unseal = _sealer(settings)
    try:
        return await _backup.verify_restore(
            request.app.state.container.datastore, body.archive,
            unseal=unseal, token=secrets.token_hex(8))
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
            unseal=unseal, overwrite=body.overwrite, into_tenant=body.into_tenant)
    except _backup.BackupError as exc:
        # A bad archive is the caller's problem, not a 500: the checksum failed, the key did not
        # match, or a row had no identity. Say which, so an operator can act.
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
