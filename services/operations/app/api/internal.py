# =============================================================================
# operations — Internal tier (service-to-service, X-Internal-Token)
# -----------------------------------------------------------------------------
# NOT user-facing. Guarded by a shared token compared in CONSTANT TIME
# (CWE-208: observable timing discrepancy). Never a user JWT.
# =============================================================================
from __future__ import annotations

import hmac

from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from app.config import Settings, get_settings
from app.core.erasure import OperationsErasure
from app.core.operations import OperationError
from app.core.sectors import SectorError
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
    # Write-ahead, and CRITICAL. Erasure is irreversible and this service holds the phone number
    # itself — after it runs, nothing else can show that it did. Recording afterwards would leave
    # the one case that matters unrecorded: the erasure that half-succeeded.
    await request.app.state.auditor.record(
        "subject.erased", actor="", tenant=body.tenant, resource="subject",
        ip=request.client.host if request.client else "")
    eraser = OperationsErasure(store=c.datastore, pii_salt=s.PII_SALT,
                               max_scan=s.ERASURE_MAX_SCAN)
    return await eraser.erase(body.tenant, body.subject)


class BatchVisitIn(BaseModel):
    """One visit inside a drained batch, as an integration SDK sends it."""
    tenant: str = Field(min_length=1, max_length=128)
    phone: str = Field(min_length=3, max_length=32)
    service_ids: list[str] = Field(min_length=1, max_length=20)
    name: str = Field(default="", max_length=128)
    plate: str = Field(default="", max_length=32)
    operator_id: str = Field(default="", max_length=64)
    branch_id: str = Field(default="", max_length=64)
    meter: int = Field(default=0, ge=0, le=10_000_000)
    note: str = Field(default="", max_length=1000)
    # REQUIRED here, unlike the interactive route. A batch is by definition a replay, and a replay
    # without a stable key is how one lost reply becomes two visits, two reminders and doubled
    # revenue. The device cannot know whether we saved the first attempt — only we can.
    idempotency_key: str = Field(min_length=8, max_length=128)
    # The device's clock, which may be days out. Kept ALONGSIDE our own receive time rather than
    # instead of it: reminders schedule from the visit time, so a device running two days fast
    # would otherwise produce a reminder that arrives before it should.
    occurred_at: int = Field(default=0, ge=0)


class BatchIn(BaseModel):
    # Small on purpose. The SDK drains oldest-first in modest batches with a randomised gap, so a
    # city's network returning does not put a thousand devices on us in the same second.
    visits: list[BatchVisitIn] = Field(min_length=1, max_length=50)


@router.post("/operations/visits/batch", dependencies=[Depends(require_internal_token)])
async def record_visits_batch(request: Request, body: BatchIn) -> dict:
    """Accept a drained batch from an integration, and report the outcome PER ITEM.

    THE FAILURE THIS EXISTS TO PREVENT — and it is the one everybody who writes an offline queue by
    hand walks into. An all-or-nothing batch containing a single permanently-invalid visit (a
    service id that was deleted, say) fails, is retried, fails again, forever. Everything behind it
    stops moving, and the shop believes its data is syncing while the queue has not advanced in a
    week. Nothing errors anywhere a human is looking.

    So each element gets its own verdict: `accepted`, `duplicate`, or `rejected` with a reason the
    SDK can act on. A rejected item is the client's to dead-letter locally after a bounded number
    of attempts; it must never block the queue behind it.

    THE TENANT IS ON EACH ITEM here, unlike the user-tier route where it comes off the token. This
    is the internal tier, called by a service that already authenticated the establishment, and one
    batch could in principle carry more than one — so it is per item rather than per request, and
    every item is scoped to its own.
    """
    svc = request.app.state.container.operations
    results: list[dict] = []
    accepted = 0

    for item in body.visits:
        # Audited per item, write-ahead, exactly as the interactive route is. A visit arriving
        # through an integration is not a lesser visit — the same reminders, points and revenue
        # derive from it.
        await request.app.state.auditor.record(
            "visit.recorded", actor="integration", tenant=item.tenant, resource="visit",
            ip=request.client.host if request.client else "")
        try:
            res = await svc.record_visit(
                tenant=item.tenant, phone=item.phone, service_ids=item.service_ids,
                name=item.name, plate=item.plate, operator_id=item.operator_id,
                branch_id=item.branch_id, meter=item.meter, note=item.note,
                idempotency_key=item.idempotency_key, occurred_at=item.occurred_at)
        except OperationError as exc:
            # REJECTED, not retryable. The reason travels back so the SDK can dead-letter it with
            # something a support engineer can read, instead of retrying it into eternity.
            results.append({"idempotency_key": item.idempotency_key, "status": "rejected",
                            "reason": str(exc)})
            continue

        if res.duplicate:
            results.append({"idempotency_key": item.idempotency_key, "status": "duplicate",
                            "visit_id": res.visit.id})
            continue

        results.append({"idempotency_key": item.idempotency_key, "status": "accepted",
                        "visit_id": res.visit.id})
        accepted += 1
        # The seams run per accepted visit, after it is durable — same rule as the interactive
        # path. Inline here rather than as a background task: a batch is not on anybody's screen,
        # so there is no five-second budget to protect, and doing it inline means the caller's
        # 200 genuinely reflects the work being done.
        await request.app.state.container.seams.after_visit(res)

    return {"accepted": accepted, "total": len(body.visits), "results": results}


class SeedTenantIn(BaseModel):
    tenant: str = Field(min_length=1, max_length=128)
    sector: str = Field(min_length=1, max_length=64)


@router.post("/operations/seed-tenant", dependencies=[Depends(require_internal_token)])
async def seed_tenant(request: Request, body: SeedTenantIn) -> dict:
    """Give a new establishment its service catalogue.

    Called once, by the provisioning path, at the moment a tenant is created. Internal tier because
    it is service-to-service by nature — the establishment is not signed in yet, so there is no
    user token to carry, and minting a platform-capable one for this would put a very powerful
    credential in the signup flow.

    IDEMPOTENT: seeding twice adds nothing. A retried provisioning step must not produce a
    catalogue with every service listed twice, which is a mess the owner has to clean by hand on
    their first day.
    """
    sectors = request.app.state.container.sectors
    try:
        created = await sectors.seed_tenant(tenant=body.tenant, sector_key=body.sector)
    except SectorError as exc:
        # 400 and the list of valid sectors: a caller that sent a typo can fix it from the
        # response, without reading our source.
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    return {"tenant": body.tenant, "sector": body.sector, "services_created": created,
            "fields": await sectors.fields_for(body.sector),
            "tracks_vehicle": await sectors.tracks_vehicle(body.sector)}


@router.get("/operations/sectors", dependencies=[Depends(require_internal_token)])
async def list_sectors(request: Request) -> dict:
    """The sectors this deployment knows, with the fields each one renders.

    The signup screen reads this instead of carrying its own copy — a second list is a second thing
    to keep in step, and it will not be kept in step.
    """
    sectors = request.app.state.container.sectors
    out = []
    for row in await sectors.list():
        # ACTIVE ONLY on this route. It feeds the signup screen, and offering a sector we have
        # retired would let an establishment choose something that will not seed a catalogue.
        if not row.get("active", True):
            continue
        key = row.get("key", "")
        out.append({"key": key, "name": row.get("name", key),
                    "fields": await sectors.fields_for(key),
                    "tracks_vehicle": row.get("asset") == "vehicle"})
    return {"sectors": out}


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
