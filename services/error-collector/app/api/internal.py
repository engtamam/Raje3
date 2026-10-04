# =============================================================================
# error-collector — Internal tier (service-to-service, X-Internal-Token)
# -----------------------------------------------------------------------------
# NOT user-facing. Guarded by a shared token compared in CONSTANT TIME
# (CWE-208: observable timing discrepancy). Never a user JWT.
# =============================================================================
from __future__ import annotations

import hmac

from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from app.config import Settings, get_settings
from app.core.erasure import TemplateErasure
from app.core import backup as _backup
from app.core.signals import SignalIn, SignalStore
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
    tenant: str = Field(min_length=1, max_length=128)
    subject: str = Field(min_length=1, max_length=256)


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
    from app.api.deps import get_runtime_config

    # THE ACK NAMES THE EFFECTIVE RETENTION, NOT THE DEPLOY'S DEFAULT — same fix as
    # _signal_store's own read above: an owner who raised SIGNAL_RETENTION_DAYS through the panel
    # needs the DSAR receipt to state the number that is actually true, not the env value it
    # started as.
    retention_days = await get_runtime_config(request).get(
        tenant="", key="SIGNAL_RETENTION_DAYS", default=s.SIGNAL_RETENTION_DAYS)
    eraser = TemplateErasure(store=c.datastore, pii_salt=s.PII_SALT,
                             max_scan=s.ERASURE_MAX_SCAN,
                             retention_days=retention_days)
    result = await eraser.erase(body.tenant, body.subject)
    # AUDITED — fixed 2026-09-12, a real gap a QA audit found: this action left no trace anywhere
    # in this service's own append-only chain despite being one of the most legally significant
    # ones it performs. AFTER the act, not before — an erasure that could not be witnessed must
    # still have happened (the DSAR clock does not wait on the audit sink); the resource is the
    # subject's own pseudonym, never the raw phone/identifier.
    await request.app.state.auditor.record(
        "error-collector.subject_erased", actor="", tenant=body.tenant,
        resource=f"subject:{result.get('subject_ref', '')}",
        ip=request.client.host if request.client else "",
        metadata={"erased": result.get("erased") or [], "truncated": bool(result.get("truncated"))})
    return result


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
            unseal=unseal, token=secrets.token_hex(8), declaration=BACKUP)
    except _backup.BackupError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.post("/backup/import", dependencies=[Depends(require_internal_token)])
async def backup_import(request: Request, body: BackupImportIn,
                        settings: Settings = Depends(get_settings)) -> dict:
    """Restore an archive this service produced. Idempotent; leaves newer rows alone by default."""
    _, unseal = _sealer(settings)
    try:
        result = await _backup.import_archive(
            request.app.state.container.datastore, body.archive,
            unseal=unseal, overwrite=body.overwrite, into_tenant=body.into_tenant,
            prune=body.prune, scan_cap=settings.BACKUP_MAX_ROWS_PER_COLLECTION,
            declaration=BACKUP)
    except _backup.BackupError as exc:
        # A bad archive is the caller's problem, not a 500: the checksum failed, the key did not
        # match, or a row had no identity. Say which, so an operator can act.
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    await request.app.state.auditor.record(
        "error_collector.backup_imported", actor="", tenant=body.into_tenant,
        resource="backup:import",
        ip=request.client.host if request.client else "",
        metadata={"overwrite": body.overwrite, "prune": body.prune,
                 "into_tenant": body.into_tenant})
    return result


# ── the signal stream's own two internal routes ───────────────────────────────────────────────
# INGEST IS INTERNAL-TOKEN, NOT A JWT, because its caller is a DaemonSet. Fluent Bit tails every
# pod's stdout on every node and has no identity on this platform beyond the shared service token
# every other service already carries (deploy/k3s/fluent-bit.yaml). A route the console's users
# could reach would be a route anybody's browser could fill the store through; a route only
# in-cluster infrastructure can reach is what this is.


async def _signal_store(request: Request, settings: Settings) -> SignalStore:
    """RETENTION/REAP NOW RESOLVE THROUGH RuntimeConfig — same fix, same reasoning as
    api/v1/signals.py's own `_store`; see its docstring for the full context (a QA audit found the
    operator config panel advertised these as its only two settings while nothing actually read
    an override)."""
    from app.api.deps import get_runtime_config

    rc = get_runtime_config(request)
    retention_days = await rc.get(tenant="", key="SIGNAL_RETENTION_DAYS",
                                  default=settings.SIGNAL_RETENTION_DAYS)
    reap_limit = await rc.get(tenant="", key="SIGNAL_REAP_LIMIT",
                              default=settings.SIGNAL_REAP_LIMIT)
    return SignalStore(request.app.state.container.datastore,
                       retention_days=retention_days, reap_limit=reap_limit)


@router.post("/signals/ingest", dependencies=[Depends(require_internal_token)])
async def ingest_signal(request: Request, body: SignalIn | list[SignalIn],
                        settings: Settings = Depends(get_settings)) -> dict:
    """Signals, from anything inside the cluster.

    THE SAME PYDANTIC MODEL THE BROWSER ROUTE VALIDATES — see app/core/signals.py. One contract,
    two doors; the only difference here is that this one may arrive as a LIST.

    A LIST, BECAUSE THE CALLER IS A LOG SHIPPER AND LOG SHIPPERS BATCH. Fluent Bit's http output
    flushes a JSON ARRAY of records — that is not configurable away, and a route declaring a single
    object answers 422 to every flush. Nothing would fail: the DaemonSet is Running, the collector
    is Ready, and the screen is empty in exactly the way «no errors» looks. So the batch is accepted
    explicitly, each element validated against the same model, rather than discovered in production.

    STRICT ABOUT SHAPE, on purpose: a RAW tail record does not match this contract, so the lua
    filter in deploy/k3s/fluent-bit.yaml must reshape it before the output fires. A collector that
    quietly accepted anything would fill with rows no screen can render and no filter can narrow.

    NOT AUDITED, and no tenant is taken. A signal is not an action by a person and carries no
    verified subject; an audit row per log line would be a second, larger log.
    """
    items = body if isinstance(body, list) else [body]
    store = await _signal_store(request, settings)
    ids = [(await store.record(item))["id"] for item in items]
    return {"stored": len(ids), "ids": ids}


class ReapIn(BaseModel):
    """DEFAULTED THROUGHOUT, so an EMPTY POST is a valid request (playbook §4.41).

    The platform's scheduled-job template posts an empty body with a JSON content type, and a route
    with a required body answers 422 before a line of its own code runs — every probe green, every
    dashboard healthy, and the store growing without bound. `ci/check_cron_bodies.py` reads the
    `cronJobs` entry in this service's own values file and fails the build on exactly that.
    """

    # A ceiling on ONE pass, not on the sweep. Zero means "this service's configured budget".
    limit: int = Field(default=0, ge=0, le=50_000)


@router.post("/signals/reap", dependencies=[Depends(require_internal_token)])
async def reap_signals(request: Request, body: ReapIn = ReapIn(),
                       settings: Settings = Depends(get_settings)) -> dict:
    """Delete signals past the retention window. Returns how many went.

    BOUNDED PER CALL AND RE-INVOKED UNTIL IT ANSWERS 0 — the shape every sweep on this platform
    uses (whatsapp-assistant's `purge_for_subject`, reminders' `_delete_where`). `0` means the
    store is inside its window; anything else means there is more to do, and the caller — the daily
    cron, or an operator during an incident — simply calls again.
    """
    limit = body.limit or None
    store = await _signal_store(request, settings)
    removed = await store.reap(limit=limit)
    return {"removed": removed}
