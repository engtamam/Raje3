# =============================================================================
# campaigns — Internal tier (service-to-service, X-Internal-Token)
# -----------------------------------------------------------------------------
# NOT user-facing. Guarded by a shared token compared in CONSTANT TIME
# (CWE-208: observable timing discrepancy). Never a user JWT.
# =============================================================================
from __future__ import annotations

import hmac

from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from app.adapters.datastore.drain import drain
from app.config import Settings, get_settings
from app.core.erasure import CampaignsErasure
from app.core.tick import TickResult
from app.core import backup as _backup
from app.core import service_due_settings as SDS
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
    # No salt: this service never receives a raw identifier — the subject it is handed is already
    # the pseudonym operations published.
    eraser = CampaignsErasure(store=c.datastore, max_scan=s.ERASURE_MAX_SCAN)
    return await eraser.erase(body.tenant, body.subject)


@router.get("/campaigns/service-due-settings", dependencies=[Depends(require_internal_token)])
async def service_due_settings(request: Request, tenant: str = "") -> dict:
    """What reminders needs, at send time, for every «حان وقت الخدمة» / «لم يستجب» send.

    THE DEFAULT IS THE WHOLE POINT: a shop that never opened this settings screen gets
    `active=True` — exactly today's plain reminder, unchanged, forever (`SDS.DEFAULTS`). Called by
    reminders' own peer client (`HttpServiceDueSettings`/`NullServiceDueSettings`), never by the
    console directly — the owner's OWN read/write of this one field is the public
    `/campaigns/service-due-settings` route above, guarded by a user token; this one is guarded by
    the internal token, the same pattern every other service-to-service read in this file already
    follows.
    """
    settings = await SDS.load(request.app.state.container.datastore, tenant)
    return settings.as_dict()


class TickIn(BaseModel):
    tenant: str = Field(default="", max_length=128)


@router.post("/campaigns/tick", dependencies=[Depends(require_internal_token)])
async def tick(request: Request, body: TickIn | None = None) -> dict:
    """The heartbeat. A CronJob in the values file drives this.

    WITHOUT IT THIS SERVICE IS INERT AND LOOKS HEALTHY: campaigns exist, every probe passes, and
    nothing ever fires. There is no symptom until an owner asks why the win-back campaign they set
    up in March has never sent anything.
    """
    # THE CRON POSTS NO BODY AT ALL. The platform's scheduled-job template sends an empty payload
    # with a JSON content type, and a REQUIRED model rejects that as a validation error before a
    # line of this function runs — so the heartbeat failed on every schedule while every probe
    # stayed green and every route answered. The failure lived in a Job's exit code and nowhere
    # else. An empty POST now means what a scheduled pass means: all of it.
    body = body or TickIn()

    import time
    c = request.app.state.container
    s = get_settings()
    now = int(time.time())
    tenants = [body.tenant] if body.tenant else await _active_tenants(c)
    fired = evaluated = sent = suppressed = skipped = 0
    reasons: dict = {}
    for tenant in tenants[:s.TICK_MAX_TENANTS]:
        res = await c.tick.run(tenant, now=now)
        fired += res.fired
        evaluated += res.evaluated
        sent += res.sent
        suppressed += res.suppressed
        skipped += res.skipped
        for k, v in res.reasons.items():
            reasons[k] = reasons.get(k, 0) + v
    return {"tenants": len(tenants), "evaluated": evaluated, "fired": fired,
            "sent": sent, "suppressed": suppressed, "skipped": skipped,
            # The reason counts, not just the totals: "312 suppressed" is an alarm, "312
            # suppressed, all outside the window" is a working system doing its job.
            "reasons": reasons}


@router.post("/campaigns/jobs/run", dependencies=[Depends(require_internal_token)])
async def run_jobs(request: Request) -> dict:
    """job-service's own claim loop, from this service's side — a CronJob drives THIS at a much
    tighter cadence than `/campaigns/tick` above (every minute, not every 15), and it can afford
    to: it claims only what job-service says is actually due right now (an indexed read, never a
    scan of every campaign this tenant or any other holds), so a tight cadence costs nothing extra
    here the way it would scanning this service's own datastore that often.

    ONE JOB TYPE TODAY — `campaigns.fire`, a campaign whose owner gave it a future `fire_at`
    (any goal now, not only «مناسبة عميلك» — 2026-09-12). `NullJobService.claim()` always returns
    `[]`, so this route is a harmless no-op wherever `JOB_SERVICE_URL` is unset.
    """
    import time
    c = request.app.state.container
    now = int(time.time())
    claimed = await c.jobs.claim(worker=f"campaigns-{now}", queue="campaigns", batch=20)
    fired = requeued = failed = 0
    for job in claimed:
        job_id, lease_token = job.get("id", ""), job.get("lease_token", "")
        payload = job.get("payload") or {}
        tenant, campaign_id = job.get("tenant", ""), payload.get("campaign_id", "")
        try:
            row = await c.datastore.get("campaigns", f"{tenant}|{campaign_id}")
            if row is None or row.get("state") != "active":
                # Paused/deleted/already-done between scheduling and now — not a failure, just
                # nothing left to do. Acked so it never retries a campaign that no longer exists.
                await c.jobs.ack(job_id, lease_token, {"skipped": "not_active"})
                continue
            res = TickResult()
            finished = await c.tick._fire(row, now=now, res=res)   # same gate/window/audience path
            fired += res.fired
            if finished:
                await c.jobs.ack(job_id, lease_token, {"sent": res.sent, "finished": True})
            else:
                # A LARGE AUDIENCE'S FIRST PASS DID NOT FINISH — same bounded-pass shape
                # dispatch.py already documents. Acked (the attempt itself succeeded) and a follow-
                # up job takes over the rest shortly, rather than nacking into job-service's own
                # backoff/retry ladder, which is for FAILURES, not ordinary multi-pass campaigns.
                await c.jobs.ack(job_id, lease_token, {"sent": res.sent, "finished": False})
                await c.jobs.enqueue(queue="campaigns", tenant=tenant, type="campaigns.fire",
                                     payload={"campaign_id": campaign_id}, delay_seconds=900,
                                     unique_key=f"cmp-fire-cont:{campaign_id}:{now // 900}")
                requeued += 1
        except Exception as exc:                                  # noqa: BLE001
            failed += 1
            await c.jobs.nack(job_id, lease_token, str(exc)[:200])
    return {"claimed": len(claimed), "fired": fired, "requeued": requeued, "failed": failed}


async def _active_tenants(c) -> list:
    """Tenants with an active campaign.

    Derived from our own rows rather than asked of tenant-service: this must keep working when a
    peer is down, and a tenant with no active campaign has nothing for the tick to do.
    """
    # DRAINED. This used to read the two thousand OLDEST active campaigns and discard the cursor,
    # so once the platform held more than that, the tenants whose campaigns were created most
    # recently were simply not in the list — and the tick, which walks exactly this list, never
    # touched them. A new shop's first campaign would be the one that never sends.
    rows = await drain(c.datastore, "campaigns", {"state": "active"}, sort=("created", "asc"))
    seen = []
    for r in rows:
        t = r.get("tenant") or ""
        if t and t not in seen:
            seen.append(t)
    return seen


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
            unseal=unseal, overwrite=body.overwrite, into_tenant=body.into_tenant,
            prune=body.prune, scan_cap=settings.BACKUP_MAX_ROWS_PER_COLLECTION)
    except _backup.BackupError as exc:
        # A bad archive is the caller's problem, not a 500: the checksum failed, the key did not
        # match, or a row had no identity. Say which, so an operator can act.
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
