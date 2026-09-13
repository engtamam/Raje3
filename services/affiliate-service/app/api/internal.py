# =============================================================================
# affiliate-service — Internal tier (service-to-service, X-Internal-Token)
# -----------------------------------------------------------------------------
# NOT user-facing. Guarded by a shared token compared in CONSTANT TIME
# (CWE-208: observable timing discrepancy). Never a user JWT.
# =============================================================================
from __future__ import annotations

import hmac

from pydantic import BaseModel

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from app.config import Settings, get_settings
from app.core.erasure import AffiliateErasure
from app.core.lead_sourcing import LeadSourcingService
from app.core.leads import LeadSourcingKeys
from app.core.models import JOB_QUEUED, JOB_RUNNING, LEAD_SEARCH_JOBS
from app.core.referrals import ReferralError
from app.core.secret_store import SecretStore
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
    eraser = AffiliateErasure(store=c.datastore, pii_salt=s.PII_SALT,
                             max_scan=s.ERASURE_MAX_SCAN)
    result = await eraser.erase(body.tenant, body.subject)
    # AUDITED — added 2026-09-12, a real gap a QA audit found: this action left no trace anywhere
    # in this service's own append-only chain despite being one of the most legally significant
    # ones it performs. AFTER the act, not before — unlike a write-ahead critical action, an
    # erasure that could not be witnessed must still have happened (the DSAR clock does not wait
    # on the audit sink); the resource is the subject's own pseudonym, never a phone or name.
    await request.app.state.auditor.record(
        "affiliate.subject_erased", actor="", tenant=body.tenant,
        resource=f"subject:{result.get('subject_ref', '')}",
        ip=request.client.host if request.client else "",
        metadata={"erased": result.get("erased") or [], "truncated": bool(result.get("truncated"))})
    return result


class ReferralStampIn(BaseModel):
    tenant: str
    affiliate_id: str
    shop_name: str = ""
    #: The shop owner's own phone — spec §2's anti-self-referral check ("رقم جوال صاحب المحل ≠
    #: رقم جوال المسوّق نفسه"). Optional only for backward compatibility with a caller that
    #: predates this field; core/referrals.py treats an empty value as "cannot check" and stamps
    #: anyway rather than refusing a legitimate referral over a caller that has not been updated.
    shop_owner_phone: str = ""


@router.post("/referrals/stamp", dependencies=[Depends(require_internal_token)])
async def stamp_referral(request: Request, body: ReferralStampIn) -> dict:
    """Called by operations, once, right after a shop it just created finishes signing up —
    the same moment its own core/partners.py stamps a till-company partner. See
    core/referrals.py for why this is a SEPARATE mechanism from that one rather than a shared
    call, and why a bad affiliate id is a 400 the CALLER decides what to do with (operations
    reports it and never fails the owner's own signup over it — the same trade-off it already
    makes for a mistyped partner key)."""
    c = request.app.state.container
    try:
        return await c.referrals.stamp(
            tenant=body.tenant, affiliate_id=body.affiliate_id, shop_name=body.shop_name,
            shop_owner_phone=body.shop_owner_phone)
    except ReferralError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


class CommissionSyncIn(BaseModel):
    tenant: str


@router.post("/commissions/sync", dependencies=[Depends(require_internal_token)])
async def sync_commissions(request: Request, body: CommissionSyncIn) -> dict:
    """Reconcile one tenant's commissions against billing's own paid-invoice history.

    NOT WIRED TO ANY TRIGGER YET — this route exists and is fully tested (core/commission.py),
    but nothing calls it automatically today. The natural next increment (see that module's own
    TODO) is a webhook off billing's payment.succeeded/invoice.paid; until that exists, this is
    reachable only by hand (an admin action, ops using the internal token directly) or a future
    scheduled sweep. Documented here rather than left to be discovered by someone waiting for a
    commission that will never appear on its own."""
    c = request.app.state.container
    out = await c.commissions.sync(body.tenant)
    await request.app.state.auditor.record(
        "affiliate.commissions_synced", actor="", tenant=body.tenant, resource="tenant",
        ip=request.client.host if request.client else "",
        metadata={"created": len(out.get("created") or []), "voided": len(out.get("voided") or []),
                 "reduced": len(out.get("reduced") or [])}
        if out.get("synced") else {"reason": out.get("reason", "")})
    return out


class CommissionsForTenantIn(BaseModel):
    tenant: str


@router.post("/commissions/for-tenant", dependencies=[Depends(require_internal_token)])
async def commissions_for_tenant(request: Request, body: CommissionsForTenantIn) -> dict:
    """Every commission this ONE REFERRED SHOP ever generated — for the ops-mcp case-timeline
    tool's financial-dispute report, answering "did this shop's business ever pay an affiliate a
    commission" without needing to know which affiliate. Read-only; `CommissionEngine.for_tenant`
    already did the real work (see that method's own docstring for why it's a genuinely different
    question from `of_affiliate`, the one every other reader of this store already uses)."""
    c = request.app.state.container
    rows = await c.commissions.for_tenant(body.tenant)
    return {"commissions": [r.to_dict() for r in rows], "count": len(rows)}


@router.post("/commissions/sweep", dependencies=[Depends(require_internal_token)])
async def sweep_commissions(request: Request, settings: Settings = Depends(get_settings)) -> dict:
    """The DURABLE backstop for the event-driven fast path (app/main.py's own subscriber) — meant
    to run on a schedule (see the deploy values' cronJobs), so a missed event costs latency, not
    a lost commission. Bounded (Settings.AFFILIATE_SWEEP_MAX) and reports `truncated` loudly
    rather than silently sweeping only part of a referral history past that cap."""
    c = request.app.state.container
    referrals = await c.referrals.all_referred(limit=settings.AFFILIATE_SWEEP_MAX)
    synced = 0
    created = 0
    voided = 0
    for r in referrals:
        out = await c.commissions.sync(r.tenant)
        if out.get("synced"):
            synced += 1
            created += len(out.get("created") or [])
            voided += len(out.get("voided") or [])
    out = {"referrals_checked": len(referrals), "synced": synced, "created": created,
          "voided": voided, "truncated": len(referrals) >= settings.AFFILIATE_SWEEP_MAX}
    await request.app.state.auditor.record(
        "affiliate.commissions_swept", actor="", tenant="", resource="sweep",
        ip=request.client.host if request.client else "", metadata=out)
    return out


def _lead_sourcing(request: Request, settings: Settings) -> LeadSourcingService | None:
    """None (never raises) when SECRETS_KEK is unconfigured — the cron caller should see 'nothing
    to tick, misconfigured' as a normal, quiet tick rather than the CronJob itself failing every
    minute over a deploy that has not wired lead sourcing yet."""
    if not settings.SECRETS_KEK:
        return None
    c = request.app.state.container
    secret_store = SecretStore(c.datastore, settings.SECRETS_KEK,
                               rotation_window_s=settings.SECRETS_ROTATION_WINDOW_SECONDS)
    keys = LeadSourcingKeys(secret_store=secret_store,
                            fallback_api_key=settings.LEADS_PLACES_API_KEY_FALLBACK)
    return LeadSourcingService(store=c.datastore, keys=keys, onboarding=c.onboarding,
                               sectors=c.sectors)


@router.post("/leads/tick", dependencies=[Depends(require_internal_token)])
async def tick_leads(request: Request, settings: Settings = Depends(get_settings)) -> dict:
    """The resumable engine behind §6's search jobs (core/lead_sourcing.py's own module
    docstring) — advances up to Settings.LEADS_TICK_UNITS (point, keyword) units across the
    OLDEST non-terminal job, then returns. Meant for a k3s CronJob (see the deploy values'
    cronJobs, same shape as commissions-sweep) rather than a person; a full search is hours, so
    this is what turns that into many small, safely-interruptible calls."""
    svc = _lead_sourcing(request, settings)
    if svc is None:
        return {"ticked": False, "reason": "leads_not_configured"}

    c = request.app.state.container
    running, _ = await c.datastore.find(
        LEAD_SEARCH_JOBS, {"status": JOB_RUNNING}, limit=1, sort=("created_at", "asc"))
    if not running:
        running, _ = await c.datastore.find(
            LEAD_SEARCH_JOBS, {"status": JOB_QUEUED}, limit=1, sort=("created_at", "asc"))
    if not running:
        return {"ticked": False, "reason": "no_pending_job"}

    job_id = running[0]["id"]
    units = 0
    for _ in range(settings.LEADS_TICK_UNITS):
        out = await svc.step(job_id)
        units += 1
        if out.get("done"):
            break
    return {"ticked": True, "job_id": job_id, "units": units}


@router.post("/tickets/escalation-sweep", dependencies=[Depends(require_internal_token)])
async def sweep_ticket_escalations(request: Request) -> dict:
    """§13's auto-escalation (core/escalation.py's own module docstring) — a no-response timeout
    or a suspended marketer moves a shop's ticket to his manager automatically. Meant for a k3s
    CronJob (see the deploy values' cronJobs), same bounded shape as commissions/sweep."""
    out = await request.app.state.container.escalation.sweep()
    if out.get("swept") and out.get("tickets_escalated"):
        await request.app.state.auditor.record(
            "affiliate.tickets_escalation_swept", actor="", tenant="", resource="sweep",
            ip=request.client.host if request.client else "", metadata=out)
    return out


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
