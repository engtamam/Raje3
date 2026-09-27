# =============================================================================
# coworking — Internal tier (service-to-service, X-Internal-Token)
# -----------------------------------------------------------------------------
# NOT user-facing. Guarded by a shared token compared in CONSTANT TIME
# (CWE-208: observable timing discrepancy). Never a user JWT.
# =============================================================================
from __future__ import annotations

import hmac

from pydantic import BaseModel

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from app.backup_manifest import BACKUP
from app.config import Settings, get_settings
from app.core import backup as _backup
from app.core.erasure import CoworkingErasure
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
    if not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="UNAUTHORIZED")


async def require_push_signature(
    request: Request,
    x_job_signature: str | None = Header(default=None, alias="X-Job-Signature"),
    x_job_signature_timestamp: str | None = Header(default=None,
                                                   alias="X-Job-Signature-Timestamp"),
    settings: Settings = Depends(get_settings),
) -> None:
    """A door driven ONLY by job-service's own push dispatch — kept here for parity with every
    other service even though this service has no scheduled job today; a future CronJob (e.g. a
    sweep that auto-expires stale pending join requests) can reuse it with no new plumbing."""
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
async def internal_manifest(request: Request, settings: Settings = Depends(get_settings)) -> dict:
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
    """Erase a data subject (a freelancer's own phone number). Called by compliance-service
    during a DSAR fan-out. Idempotent — a DSAR retries, so erasing an already-erased subject must
    not fail. See `core/erasure.py`'s own module doc for why this service's identity model makes
    that lookup different from every other service's own erasure.py."""
    c = request.app.state.container
    s = get_settings()
    eraser = CoworkingErasure(store=c.datastore, pii_salt=s.PII_SALT, max_scan=s.ERASURE_MAX_SCAN)
    result = await eraser.erase(body.tenant, body.subject)
    await request.app.state.auditor.record(
        "coworking.subject_erased", actor="", tenant=body.tenant,
        resource=f"subject:{result.get('subject_ref', '')}",
        ip=request.client.host if request.client else "",
        metadata={"erased": result.get("erased") or [], "truncated": bool(result.get("truncated"))})
    return result


class BackupExportIn(BaseModel):
    tenant: str = ""


class BackupImportIn(BaseModel):
    archive: dict
    overwrite: bool = False
    into_tenant: str = ""
    prune: bool = False


def _sealer(settings: Settings):
    if not settings.BACKUP_KEK:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "BACKUP_KEK not configured — set this SHARED key (the SAME value backup-service holds) on this service, or its archives cannot be opened")
    return _backup.make_sealer(settings.BACKUP_KEK)


@router.post("/backup/export", dependencies=[Depends(require_internal_token)])
async def backup_export(request: Request, body: BackupExportIn,
                        settings: Settings = Depends(get_settings)) -> dict:
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
    _, unseal = _sealer(settings)
    try:
        return await _backup.import_archive(
            request.app.state.container.datastore, body.archive,
            unseal=unseal, overwrite=body.overwrite, into_tenant=body.into_tenant,
            prune=body.prune, scan_cap=settings.BACKUP_MAX_ROWS_PER_COLLECTION)
    except _backup.BackupError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
