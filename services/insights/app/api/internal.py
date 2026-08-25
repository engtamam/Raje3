# =============================================================================
# insights — Internal tier (service-to-service, X-Internal-Token)
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
    # WRITE-AHEAD, and critical. Erasure is irreversible: after it runs, nothing here can show
    # that it did. Recording afterwards would leave the one case that matters — the erasure that
    # half-succeeded — as the one case with no record.
    await request.app.state.auditor.record(
        "subject.erased", actor="", tenant=body.tenant, resource="subject",
        ip=request.client.host if request.client else "")
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
    # EVERY FIELD HAS A DEFAULT AND THE BODY ITSELF IS OPTIONAL — see the routes below for the
    # eighteen hours of "أحسب الآن" that taught us the difference.
    # Empty = every tenant the data knows about. A value scopes the pass, which is what a support
    # engineer wants when investigating one shop without recomputing the product.
    tenant: str = ""
    since: int = 0


@router.post("/insights/tick", dependencies=[Depends(require_internal_token)])
async def tick(request: Request, body: TickIn | None = None) -> dict:
    """Compute snapshots (spec §10.6.1).

    WITHOUT ITS CRON THIS SERVICE IS INERT AND LOOKS HEALTHY — every probe green, every route
    answering, and every dashboard saying "أحسب الآن" for ever. Playbook trap §4.1, which is why
    the schedule is declared beside this endpoint in the manifest rather than left to a deployer.
    """
    # THE CRON POSTS NO BODY AT ALL. The platform's scheduled-job template sends an empty payload
    # with a JSON content type, and a REQUIRED model rejects that as a validation error before a
    # line of this function runs — so the job failed every night, the snapshot was never computed,
    # and every dashboard said «أحسب مؤشرات محلك الآن» for ever. Exactly the trap the values file
    # warns about, arriving through the one door nobody watched: every probe green, every route
    # answering, the failure visible only in a Job's exit code.
    #
    # OPTIONAL BODY, DEFAULTS INSIDE. An empty POST now means "every tenant", which is what a
    # nightly pass is; a body still scopes it for a support engineer looking at one shop.
    body = body or TickIn()

    import time as _time

    c = request.app.state.container
    s = get_settings()
    now = int(_time.time())
    tenants = [body.tenant] if body.tenant else await c.peers.tenants(since=body.since)
    return await c.tick.run(now=now, tenants=tenants, since=body.since)


@router.post("/insights/platform-rollup", dependencies=[Depends(require_internal_token)])
async def platform_rollup(request: Request, body: TickIn | None = None) -> dict:
    """The admin panel's cross-tenant summary (spec: admin plan phase 11.1-11.4).

    RUNS AFTER TICK, NOT INSTEAD OF IT — it only reads snapshots tick already wrote (see
    `core/rollup.py`'s own module note), so scheduling it right after a tick pass means it reads
    freshly-updated numbers rather than racing the sweep. `body.tenant` is accepted for symmetry
    with `tick`/`digest` but ignored beyond narrowing the tenant list to one — a rollup scoped to
    a single tenant is really just a check that ONE tenant's snapshot got picked up.
    """
    body = body or TickIn()

    import time as _time

    c = request.app.state.container
    now = int(_time.time())
    tenants = [body.tenant] if body.tenant else await c.peers.tenants(since=body.since)
    return await c.rollup.run(now=now, tenants=tenants)


@router.post("/insights/digest", dependencies=[Depends(require_internal_token)])
async def digest(request: Request, body: TickIn | None = None) -> dict:
    """The weekly report, through reminders' gate.

    Sends NOTHING for a tenant with no snapshot or no visits: a message reading "0 visits" is our
    failure wearing the owner's numbers, and it says his shop is dead.
    """
    from app.core.digest import build as build_digest
    from app.core.models import SNAPSHOTS

    # Optional for the same reason as the tick above: the cron posts no body.
    body = body or TickIn()

    import time as _time

    c = request.app.state.container
    tenants = [body.tenant] if body.tenant else await c.peers.tenants()
    # The week this report covers. Passed to the peers so "points redeemed" means THIS WEEK rather
    # than all time — a lifetime total in a weekly report is a number that never changes visibly.
    week_ago = int(_time.time()) - 7 * 86400
    sent = skipped = 0
    for tenant in tenants:
        snap = await c.datastore.get(SNAPSHOTS, f"{tenant}|_all")
        # Each of these may fail on its own and cost exactly one line. See peers.digest_extras.
        extras = await c.peers.digest_extras(tenant, since=week_ago)
        # Whether he can already send offers decides which of two lines he gets — the audience he
        # has, or nothing. Asked once per tenant per week, so the cost is irrelevant.
        from app.core import plans

        extras["can_campaign"] = await c.peers.entitled(tenant, plans.ENGINE) or             await c.peers.entitled(tenant, "feature.campaigns")
        msg = build_digest(snapshot=snap or {}, **extras)
        if not msg:
            skipped += 1
            continue
        for subject in await c.subscriptions.recipients(tenant):
            res = await c.peers.send(
                tenant=tenant, subject_ref=subject, template_type=msg["template_type"],
                cls=msg["cls"], owner_text=msg["text"],
                # The week, so a retry inside the same week sends once.
                idempotency_key=f"insights:digest:{tenant}:{subject}:"
                                f"{int(snap.get('computed_at', 0)) // 604800}")
            if res.get("sent"):
                sent += 1
            else:
                # THE REASON WAS BEING THROWN AWAY, and that is why a whole class of shops lost
                # their weekly report without anyone knowing. `send` returns why it failed; the
                # route counted the successes and dropped the rest on the floor, so «sent: 0»
                # meant «nothing to send» and «every send was refused» in the same word.
                c.telemetry.event("insights_digest_not_sent", tenant=tenant,
                                  reason=str(res.get("reason") or "")[:200])
    return {"sent": sent, "skipped": skipped, "tenants": len(tenants)}


@router.get("/insights/associated-services", dependencies=[Depends(require_internal_token)])
async def associated_services(request: Request, tenant: str, service_id: str) -> dict:
    """A peer-safe read of core/associations.py's verdicts for ONE anchor service — for
    whatsapp-assistant's cross-sell suggestion tool, so the assistant proposes only what the
    engine already calls `real` (a genuine relationship, not the `group` false-positive the
    engine exists to filter out), never inventing a recommendation of its own.

    THE SAME PLAN GATE AS THE USER-FACING ROUTE, not a bypass of it (api/v1/insights.py's
    `associations` route: `plans.can_see("associations", keys)`). A peer service calling
    `/internal/*` is not a loophole around a paid surface — the tenant that has not paid for
    associations sees none here either, same as on the dashboard.

    NEVER THE LIFT VALUE OR THE FORMULA (see core/associations.py's own docstring on why) — only
    the other anchor's id, exactly what the v1 route already exposes to the shop's own owner.
    """
    from app.core import plans
    from app.core.models import PAIRS, SNAPSHOTS

    c = request.app.state.container
    keys = await plans.allowed_keys(c.peers, tenant)
    if not plans.can_see("associations", keys):
        return {"related": []}
    snap = await c.datastore.get(SNAPSHOTS, f"{tenant}|_all")
    assoc = ((snap or {}).get("values") or {}).get("associations") or {}
    if assoc.get("learning"):
        return {"related": []}
    related = []
    for p in assoc.get("pairs", []) or []:
        if p.get("verdict") != "real":
            continue
        a, b = p.get("a"), p.get("b")
        if a == service_id:
            related.append(b)
        elif b == service_id:
            related.append(a)
    return {"related": related[:5]}


@router.get("/insights/engine-reserve", dependencies=[Depends(require_internal_token)])
async def engine_reserve(request: Request, tenant: str) -> dict:
    """How many of today's messages the automatic engine needs kept back for itself (§8.4.3).

    FOR CAMPAIGNS, which must subtract it before promising an owner that his campaign reaches
    everyone in five days. Without it that promise is made against the shop's WHOLE allowance, and
    the reminders it displaces are the confirmations and service reminders the product exists for.

    THE NUMBER IS ALREADY COMPUTED — it sits in the establishment's snapshot, derived from the
    visits this service holds — so this is a read, not a second calculation. A second one made in
    campaigns from data it does not have would be a guess dressed as a figure.

    ZERO WHEN THERE IS NO SNAPSHOT YET, and that is the honest answer for a shop whose first sweep
    has not run: nothing is reserved because nothing is known about its traffic. campaigns treats a
    peer that cannot answer the same way, so a new shop is not held back by a number nobody has.
    """
    from app.core.models import SNAPSHOTS

    snap = await request.app.state.container.datastore.get(SNAPSHOTS, f"{tenant}|_all")
    values = (snap or {}).get("values") or {}
    # THE INDICATOR IS A JUDGEMENT, NOT A NUMBER (ج-2). `indicators.engine_reserve` answers
    # `{"reserve", "basis", "weekday", "samples"}` — the number AND how it was arrived at — and the
    # snapshot stores that whole answer, deliberately. This route read it as if it were the number:
    # `int({...})` raises TypeError, the route 500s, and campaigns swallows the failure into a
    # zero. So the reserve was never once subtracted, on any shop, since it was built: a campaign
    # took 250 where 210 was its share and ate the reminders' allowance to do it.
    #
    # AND THE FIELD IS NAMED HERE. `reserved` is what campaigns asks for; `reserve` is what the
    # indicator calls it. One translation, at the boundary, rather than two vocabularies loose in
    # both services.
    got = values.get("engine_reserve")
    reserve = got.get("reserve") if isinstance(got, dict) else got
    return {"reserved": int(reserve or 0),
            # HOW IT WAS ARRIVED AT, carried rather than dropped: «floor» on a shop with no
            # history is a different fact from a percentile of eight real weeks, and the caller
            # that promises an owner his campaign reaches everyone should be able to say which.
            "basis": str((got or {}).get("basis") or "") if isinstance(got, dict) else ""}
