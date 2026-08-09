# =============================================================================
# loyalty — Internal tier (service-to-service, X-Internal-Token)
# -----------------------------------------------------------------------------
# NOT user-facing. Guarded by a shared token compared in CONSTANT TIME
# (CWE-208: observable timing discrepancy). Never a user JWT.
# =============================================================================
from __future__ import annotations

import hmac

from pydantic import BaseModel

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from app.config import Settings, get_settings
from app.core.erasure import TemplateErasure
from app.core.models import LoyaltyError, Overdraft
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
    eraser = TemplateErasure(store=c.datastore, pii_salt=s.PII_SALT,
                             max_scan=s.ERASURE_MAX_SCAN)
    return await eraser.erase(body.tenant, body.subject)


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


# ── the heartbeat ──────────────────────────────────────────────────────────────────────────────
class TickIn(BaseModel):
    # Empty = every tenant. A value scopes the sweep, which is what a support engineer wants when
    # investigating one shop without touching the rest of the product.
    tenant: str = ""


@router.post("/loyalty/tick", dependencies=[Depends(require_internal_token)])
async def tick(request: Request, body: TickIn) -> dict:
    """Expire what is due, and warn what is about to expire (spec §9.7).

    WITHOUT ITS CRON THIS SERVICE IS INERT AND LOOKS PERFECTLY HEALTHY. Balances accumulate, every
    probe passes, and nothing ever expires — which is the shape of playbook trap §4.1, and the
    reason this endpoint is declared in the manifest alongside its schedule rather than merely
    existing.

    EXPIRY IS COMMITTED FIRST, THE WARNINGS ARE SENT AFTER. A send failure must never leave a
    balance half-expired; and a warning that fails is retried tomorrow, because `mark_warned` is
    only stamped once the send succeeded.
    """
    import time as _time

    c = request.app.state.container
    now = int(_time.time())
    s = get_settings()
    res = await c.expiry.sweep(now=now, tenant=body.tenant, limit=s.EXPIRY_SWEEP_LIMIT)

    sent = failed = 0
    for w in res.get("to_warn", []):
        days = max(1, (w["due_at"] - now) // 86400)
        try:
            out = await c.notifier.expiry_warning(
                tenant=w["tenant"], subject_ref=w["subject_ref"], points=w["points"],
                days=days, cycle_key=f"{w['subject_ref']}:{w['due_at']}")
        except Exception as exc:                                        # noqa: BLE001
            c.telemetry.event("loyalty_warning_failed", tenant=w["tenant"],
                              error=str(exc)[:200])
            failed += 1
            continue
        if out.get("sent"):
            # STAMPED ONLY ON SUCCESS. Stamping before the send would leave a customer silently
            # un-warned until the day his points vanish — the exact outcome the warning exists
            # to prevent.
            await c.expiry.mark_warned(w["tenant"], w["subject_ref"], now)
            sent += 1
        else:
            failed += 1

    return {"expired": res["expired"], "warned_sent": sent, "warned_failed": failed,
            "seen": res["seen"], "more": res["more"]}


# ── earning, from the visit event and from the catch-up ────────────────────────────────────────
class EarnIn(BaseModel):
    tenant: str
    visit_id: str
    subject_ref: str
    service_ids: list[str] = []
    # Invoice mode only, and only for an integrated establishment. Halalas, so no float ever
    # touches money.
    amount_halalas: int = 0
    actor: str = ""


@router.post("/loyalty/earn", dependencies=[Depends(require_internal_token)])
async def earn(request: Request, body: EarnIn) -> dict:
    """Award points for one visit. Idempotent on the visit id.

    Called by the event subscription AND by the catch-up, deliberately through the same route: a
    catch-up with its own calculation is a second earning rule, and the second one drifts from the
    settings screen the first time somebody changes one of them.
    """
    c = request.app.state.container
    return await c.earner.from_visit(
        body.tenant, visit_id=body.visit_id, subject_ref=body.subject_ref,
        service_ids=body.service_ids, amount_halalas=body.amount_halalas, actor=body.actor)


# ── the till (spec §9.8) ───────────────────────────────────────────────────────────────────────
class TillRedeemIn(BaseModel):
    tenant: str
    subject_ref: str
    reward_id: str
    # THEIR transaction reference. The till is the only party that knows whether two calls are the
    # same sale — a key we generated would be new on every retry, which is the doubling this
    # prevents.
    idempotency_key: str
    # The cashier's account, as their system holds it. Recorded AS GIVEN: their system is the
    # account system, and building a second one here would be a login nobody asked for (spec §3.5).
    actor: str = ""


@router.post("/loyalty/redeem", dependencies=[Depends(require_internal_token)])
async def till_redeem(request: Request, body: TillRedeemIn) -> dict:
    """Redeem from an integrated till, and return what the receipt must carry.

    IDENTICAL LEDGER ENTRIES TO THE FIELD PATH. Same shape, same attribution, same customer
    message — the only difference is `channel`. A fallback or a side path that records differently
    is a reporting bug waiting for month end, discovered by an owner reconciling two numbers that
    ought to match.
    """
    c = request.app.state.container
    try:
        rec, is_new = await c.redeemer.redeem(
            body.tenant, body.subject_ref, body.reward_id, actor=body.actor,
            idem_key=body.idempotency_key, channel="till")
    except Overdraft as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except LoyaltyError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    bal = await c.ledger.balance(body.tenant, body.subject_ref)
    if is_new:
        try:
            await c.notifier.receipt(tenant=body.tenant, subject_ref=rec.subject_ref,
                                     redemption_id=rec.id, reward_name=rec.reward_name,
                                     cost=rec.cost, remaining=bal.points)
        except Exception as exc:                                        # noqa: BLE001
            c.telemetry.event("loyalty_receipt_failed", tenant=body.tenant,
                              error=str(exc)[:200])
    return {
        # What the printed receipt carries, so the paper becomes a second trail.
        "transaction_ref": rec.id,
        "discount_halalas": rec.discount_halalas,
        "reward_name": rec.reward_name,
        "cost": rec.cost,
        "balance": bal.points,
        "duplicate": not is_new,
    }


# ── the repair (playbook: a materialised total can drift from its ledger) ──────────────────────
class ReconcileIn(BaseModel):
    tenant: str
    subject_ref: str


@router.post("/loyalty/reconcile", dependencies=[Depends(require_internal_token)])
async def reconcile(request: Request, body: ReconcileIn) -> dict:
    """Recompute one balance from its ledger, and repair it if they disagree.

    Exists because the materialised total CAN drift — a crash between the two writes in
    `Ledger.post`, a restore that replayed one collection and not the other. Drift with no detector
    is the worst version of this bug, because the wrong number stays entirely plausible.
    """
    c = request.app.state.container
    return await c.ledger.reconcile(body.tenant, body.subject_ref)
