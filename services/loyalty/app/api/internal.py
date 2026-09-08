# =============================================================================
# loyalty — Internal tier (service-to-service, X-Internal-Token)
# -----------------------------------------------------------------------------
# NOT user-facing. Guarded by a shared token compared in CONSTANT TIME
# (CWE-208: observable timing discrepancy). Never a user JWT.
# =============================================================================
from __future__ import annotations

import hmac

from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.adapters.datastore.drain import drain
from app.config import Settings, get_settings
from app.core.erasure import TemplateErasure
from app.core.licence import NOT_INCLUDED as LICENCE_NOT_INCLUDED
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


async def _tenants_with_balances(c, limit: int = 2000) -> list[str]:
    """Every establishment this service holds points for — the recovery's work list.

    A WHOLE-COLLECTION READ, bounded, on a cron path. The datastore refuses an empty `where` on
    purpose, and there is no per-tenant index of «who has a balance»: the balance rows ARE that
    index. A bounded scan every quarter of an hour is the price of a safety net that can find a
    shop whose very first visit event was the one that was dropped.
    """
    from app.core.models import BALANCES

    rows = await c.datastore.scan_all(BALANCES, limit=limit)
    # dict.fromkeys keeps first-seen order in O(n) — the growing `x not in list` scan this replaced
    # was O(n²) on a collection that is, by design, a whole-collection read.
    tenants = (str(row.get("tenant") or "") for row in rows)
    return list(dict.fromkeys(t for t in tenants if t))


@router.post("/loyalty/recover", dependencies=[Depends(require_internal_token)])
async def recover(request: Request, body: TickIn | None = None) -> dict:
    """Award points for visits the event never brought (the at-most-once safety net).

    THE BUS IS THE FAST PATH AND WAS THE ONLY PATH. A pod restarting through one delivery never
    hears about that visit again, and a customer's points simply never arrive — permanently, with a
    balance that looks correct and nothing anywhere saying otherwise. `Earner.catch_up` was written
    for this and had no caller; the config key naming the read existed and nothing read it.

    NO BODY AND NO TENANT: the clock decides the work list, exactly like every other sweep here.
    """
    c = request.app.state.container
    recovery = getattr(c, "recovery", None)
    if recovery is None:
        return {"ok": False, "reason": "NOT_CONFIGURED"}

    # THE WORK LIST COMES FROM THE VISITS, NOT FROM OUR BALANCES (د-19).
    #
    # A balance row is written by the first point ever awarded. So the shop this repair exists for
    # — the one whose very first visit event was the one that was dropped — has no balance row, is
    # not in the scan, and is invisible to the repair FOR EVER. Its first customers are exactly the
    # people who lost their points, and nothing anywhere would ever say so.
    #
    # `operations` answers with no tenant filter for this reason, and the visits name their own
    # tenant. Our balances are still merged in: a peer we could not reach must narrow the pass, not
    # empty it, and a shop that has points but no recent visits still has expiring windows to walk.
    tenants = await _tenants_with_balances(c)
    feed = getattr(c, "visit_feed", None)
    for tenant in (await feed.tenants() if feed is not None else []):
        if tenant not in tenants:
            tenants.append(tenant)
    read = awarded = 0
    unreadable = 0
    for tenant in tenants:
        out = await recovery.run(tenant)
        read += int(out.get("read") or 0)
        awarded += int(out.get("awarded") or 0)
        unreadable += 1 if out.get("unreadable") else 0
    # UNREADABLE IS REPORTED, NOT ROUNDED TO ZERO. A pass that could not ask anybody must not look
    # like a fleet with nothing to recover.
    return {"ok": True, "tenants": len(tenants), "read": read, "awarded": awarded,
            "unreadable": unreadable}


@router.post("/loyalty/replay-free-visits", dependencies=[Depends(require_internal_token)])
async def replay_free_visits(request: Request, body: TickIn | None = None) -> dict:
    """Record the visits that free rewards owed and never got (ز-9).

    A `service` reward is two things at once: points spent, and a visit recorded so the reminder
    cycle restarts from today. The second one ran inside a try/except that wrote telemetry and
    nothing else, and NOBODY EVER REPLAYED IT. So the half-act was permanent: a free wash handed
    over, the points gone, no visit anywhere — and the reminder engine, doing its job perfectly,
    inviting the man back for the service he had just received. He reads that as a shop that does
    not know him, which is the exact opposite of what he is being sold.

    THE RECEIPT IS THE WORK LIST. `visit_recorded` is written on our own row, so the pass is a scan
    of redemptions rather than a question to operations about every reward we ever gave.

    IDEMPOTENT AT THE FAR DOOR: `source=rec.id` is stable, so replaying one that actually landed is
    refused there as a duplicate. That is what makes «absent means not done» the safe reading for
    rows written before the field existed.

    NO BODY AND NO TENANT: the clock decides the work list, exactly like every other sweep here.
    """
    from app.api.v1.loyalty import record_free_visit
    from app.core.models import REDEMPTIONS
    from app.core.redeem import _row_to_redemption

    c = request.app.state.container
    if getattr(c, "visits", None) is None:
        return {"ok": False, "reason": "NOT_CONFIGURED"}

    rows = await c.datastore.scan_all(REDEMPTIONS, limit=2000)
    owed = [r for r in rows
            if str(r.get("reward_type") or "") == "service" and not r.get("visit_recorded")]

    recorded = failed = 0
    for row in owed:
        rec = _row_to_redemption(row)
        if await record_free_visit(c, rec.tenant, rec, rec.actor):
            recorded += 1
        else:
            # COUNTED, NOT SWALLOWED. A pass that could reach nobody must not report the same
            # «0 outstanding» as a fleet with nothing to repair — that is the shape of silence
            # this whole finding is about.
            failed += 1
    return {"ok": True, "owed": len(owed), "recorded": recorded, "failed": failed}


@router.post("/loyalty/tick", dependencies=[Depends(require_internal_token)])
async def tick(request: Request, body: TickIn | None = None) -> dict:
    """Expire what is due, and warn what is about to expire (spec §9.7).

    WITHOUT ITS CRON THIS SERVICE IS INERT AND LOOKS PERFECTLY HEALTHY. Balances accumulate, every
    probe passes, and nothing ever expires — which is the shape of playbook trap §4.1, and the
    reason this endpoint is declared in the manifest alongside its schedule rather than merely
    existing.

    EXPIRY IS COMMITTED FIRST, THE WARNINGS ARE SENT AFTER. A send failure must never leave a
    balance half-expired; and a warning that fails is retried tomorrow, because `mark_warned` is
    only stamped once the send succeeded.
    """
    # THE CRON POSTS NO BODY AT ALL. The platform's scheduled-job template sends an empty payload
    # with a JSON content type, and a REQUIRED model rejects that as a validation error before a
    # line of this function runs — so the heartbeat failed on every schedule while every probe
    # stayed green and every route answered. The failure lived in a Job's exit code and nowhere
    # else. An empty POST now means what a scheduled pass means: all of it.
    body = body or TickIn()

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
    # Invoice mode only — computed by operations from its own priced catalogue now, no till
    # required (spec §9.3, retired 2026-09-08). Halalas, so no float ever touches money.
    amount_halalas: int = 0
    # THE VISIT WAS A REDEMPTION, NOT A SALE (ب-6). Declared here as well as on the visit door,
    # because this is where the event arrives and a field the model does not declare is a field
    # pydantic drops — which is the whole defect this closes.
    free: bool = False
    actor: str = ""
    # WHO ALLOWED IT, when the reward is above the shop's threshold. Empty is the ordinary case —
    # most redemptions are below it — and the core refuses the expensive ones without a name, and
    # refuses a name that is the operator's own.
    approved_by: str = ""
    # Optional, like everything else the till sends about itself. A chain's balance is one across
    # its branches (§12.2) — this does not change that; it answers WHERE, which the owner asks
    # immediately after WHO.
    branch_id: str = ""
    # "" for an ordinary visit. Set when this visit fulfilled a PACKAGE booking — takes over the
    # points calculation entirely (see Earner.from_visit's own docstring); `service_ids` above is
    # still carried for every other reader.
    package_id: str = ""


@router.post("/loyalty/earn", dependencies=[Depends(require_internal_token)])
async def earn(request: Request, body: EarnIn) -> dict:
    """Award points for one visit. Idempotent on the visit id.

    Called by the event subscription AND by the catch-up, deliberately through the same route: a
    catch-up with its own calculation is a second earning rule, and the second one drifts from the
    settings screen the first time somebody changes one of them.
    """
    c = request.app.state.container

    # ── has this shop bought the programme? ──────────────────────────────────────────────────
    # THE ONE THAT MATTERS MOST, because nobody presses it: every recorded visit arrives here on
    # the bus. `feature.loyalty` is on the price list and was enforced nowhere, so every shop on
    # every plan has been earning points since the day this route existed.
    #
    # AND IT IS THE GROWING HALF: refusing here stops the debt from increasing. Redemption and
    # every read go around the licence on purpose — a lapsed subscription must not strand points
    # a customer already holds, and his own page (which may not consult billing at all) is showing
    # that balance right now.
    licence = getattr(c, "licence", None)
    if licence is not None and not await licence.allowed(body.tenant):
        # NOT AN ERROR, AND NOT A RETRY. The bus swallows exceptions and the catch-up would call
        # this again for ever; `earned: 0` with a reason is a fact the caller can record.
        return {"earned": 0, "balance": 0, "repeated": False,
                "reason": LICENCE_NOT_INCLUDED}

    return await c.earner.from_visit(
        body.tenant, visit_id=body.visit_id, subject_ref=body.subject_ref,
        service_ids=body.service_ids, amount_halalas=body.amount_halalas,
        free=body.free, actor=body.actor,
        branch_id=body.branch_id, package_id=body.package_id)


class RatingBonusIn(BaseModel):
    tenant: str
    visit_id: str
    subject_ref: str
    # THE SHOP'S CONFIGURED RATING INCENTIVE, PASSED IN — never recomputed here. `reminders` is the
    # one service that owns `rating_settings.py` and `feature.rating` entitlement; asking this
    # service to re-derive "how many points a rating is worth" would be a second copy of that rule,
    # and the second copy is the one that drifts the day someone changes the setting.
    points: int = Field(ge=0)
    actor: str = ""
    branch_id: str = ""


@router.post("/loyalty/rating-bonus", dependencies=[Depends(require_internal_token)])
async def rating_bonus(request: Request, body: RatingBonusIn) -> dict:
    """Credit points for one SUBMITTED rating — the incentive `rating_cta.py`'s message text
    already promises. Idempotent on the visit id, same shape as `earn` above.

    A DISTINCT `source` FROM THE VISIT'S OWN `earn` ENTRY, ON PURPOSE. `Ledger.already_posted` is
    keyed on (tenant, source, reason) — both this call and the visit's regular earn use
    reason="earn", so `source=f"rating:{visit_id}"` (never the bare `visit_id`) is what keeps the
    two from colliding: one visit legitimately produces both an ordinary earn AND a rating bonus,
    and they must not look like the same movement retried.

    ZERO POINTS CREDITS NOTHING, NOT A ZERO ROW. `Ledger.post` already refuses a zero-delta
    movement (see its own docstring — it would stamp `last_movement_at` for a customer who gained
    nothing), so a disabled or unconfigured incentive simply produces no ledger entry at all here,
    matching the "never show/promise zero" discipline the rest of the rating app holds.
    """
    c = request.app.state.container

    # SAME GATE AS `earn`, SAME REASON. A lapsed licence must not grow a debt further — see that
    # route's own comment; redemption and reads still go around it, this credit does not.
    licence = getattr(c, "licence", None)
    if licence is not None and not await licence.allowed(body.tenant):
        return {"earned": 0, "balance": 0, "reason": LICENCE_NOT_INCLUDED}

    if body.points <= 0 or not body.subject_ref or not body.visit_id:
        return {"earned": 0, "reason": "nothing to credit"}

    entry = await c.ledger.post(
        tenant=body.tenant, subject_ref=body.subject_ref, delta=body.points, reason="earn",
        source=f"rating:{body.visit_id}", actor=body.actor, rule_level="rating",
        branch_id=body.branch_id)
    if entry is None:
        return {"earned": 0, "duplicate": True, "reason": "already credited for this rating"}

    await request.app.state.auditor.record(
        "loyalty.rating_bonus_credited", actor=body.actor or "operations", tenant=body.tenant,
        resource=f"visit:{body.visit_id}", ip=request.client.host if request.client else "",
        metadata={"points": body.points})
    return {"earned": body.points, "balance": entry.balance_after, "entry_id": entry.id}


# ── the customer's own page ────────────────────────────────────────────────────────────────────
@router.get("/loyalty/portal/balance", dependencies=[Depends(require_internal_token)])
async def portal_balance(request: Request, tenant: str, subject_ref: str) -> dict:
    """What the CUSTOMER sees of his own points, read by portal on his behalf.

    AN INTERNAL ROUTE, NOT THE OWNER'S. The customer holds no token — he opened a link from a
    WhatsApp message — so the page is composed server-side by portal using its internal
    credential. Reusing the owner-facing route would mean minting an owner's token for a member of
    the public, which is not a thing to be clever about.

    THE SAME NUMBERS THE COUNTER SEES. It is deliberately the same call the field screen makes:
    two balance calculations would disagree the first time a rule changed, and the disagreement
    would be between what he reads at home and what he is told at the till.

    NO NAME, NO NUMBER, EVER. Everything here is keyed by the pseudonym; this service has never
    held a phone number and this route does not become the first place one appears.
    """
    c = request.app.state.container
    bal = await c.ledger.balance(tenant, subject_ref)
    catalogue = await c.rewards.list(tenant)
    affordable = await c.rewards.affordable(tenant, bal.points, catalogue=catalogue)
    all_costs = [r.cost for r in catalogue]
    from app.api.v1.loyalty import _threshold
    from app.core.notify import to_next_reward
    from app.core.redeem import needs_approval
    threshold = await _threshold(c, tenant)
    return {
        # DOES THIS SHOP RUN A PROGRAMME AT ALL — asked here, because only this service can
        # answer it, and said out loud because the readers cannot infer it (هـ-1).
        #
        # Every key below has a value for a shop that runs nothing: zero points, no rewards, a
        # threshold of zero. So the dictionary is never empty, and portal's «show the section if
        # we got points back» was a condition that could not be false — a customer of a car wash
        # with no loyalty programme opened his page and read «0 نقطة», which is a shop advertising
        # something it does not have and a balance nobody can ever spend.
        #
        # REWARDS ARE THE PROGRAMME. Not the licence: reads deliberately go around billing (see
        # `award` above) so a lapsed subscription never strands points a customer already holds.
        # A shop with nothing to redeem has nothing to show him, whatever it is paying for.
        "has_programme": bool(all_costs),
        "points": bal.points,
        "manager_threshold": threshold,
        # WHAT EACH REWARD STILL NEEDS BEFORE IT CAN BE HANDED OVER (د-14أ). Affordable is not the
        # same question as allowed: a shop with a manager threshold has rewards the balance covers
        # and the counter may not give away alone. Offering those as available and refusing at the
        # tap is the worst order to discover it in — the customer is already holding out his hand.
        # One rule, read from `core.redeem` so the offer and the refusal cannot drift.
        "rewards": [{**r.to_dict(),
                     "needs_approval": needs_approval(r.cost, threshold)} for r in affordable],
        # Zero means "say nothing" — either he can afford everything or the shop has no rewards.
        "to_next_reward": to_next_reward(bal.points, all_costs),
        "expires_at": c.expiry.due_at(bal.to_dict()),
    }


@router.get("/loyalty/history", dependencies=[Depends(require_internal_token)])
async def loyalty_history(request: Request, tenant: str, subject_ref: str, limit: int = 100
                          ) -> dict:
    """EVERY movement and EVERY redemption for one member — for the ops-mcp case-timeline
    investigation tool, never a customer- or portal-facing surface. `portal_balance` above is
    deliberately the shop's own numbers with no history attached (a customer's own page shows a
    current balance, not a ledger); this route is the opposite trade, made for a different reader.

    TWO READS, BOTH ALREADY READ-ONLY AND SUBJECT-SCOPED — `Ledger.history` (every points
    movement: earn, redeem, expire, correction) and `Redeemer.history` (the redemption RECEIPTS,
    with the reward's own name/cost snapshotted onto them — see `Redemption`'s own docstring on
    why that is a separate, richer fact than the ledger entry that moved the points). Returned
    together since a case investigation reads them as one story, not two.
    """
    c = request.app.state.container
    movements = await c.ledger.history(tenant, subject_ref, limit=limit)
    redemptions = await c.redeemer.history(tenant, subject_ref, limit=limit)
    return {"movements": movements, "redemptions": redemptions}


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
    # THE MANAGER WHO ALLOWED IT — and the route READ THIS FIELD BEFORE THE MODEL DECLARED IT.
    # `getattr(body, "approved_by", "")` cannot fail, so the default won every time and FastAPI
    # dropped the key a till did send, because a schema that does not declare a field does not
    # accept it. Every reward above the shop's threshold was refused at the one door where a
    # manager is standing right there, with no way on earth to satisfy the refusal.
    approved_by: str = ""
    # WHICH BRANCH handed the reward over. A shop with three branches that knows who spent a
    # customer's points and not where knows half of what it asked. Optional: a till that does not
    # send it records a redemption with no branch rather than failing — the same rule visits
    # already follow on /internal/operations/visits/batch.
    branch_id: str = ""


@router.post("/loyalty/redeem", dependencies=[Depends(require_internal_token)])
async def till_redeem(request: Request, body: TillRedeemIn) -> dict:
    """Redeem from an integrated till, and return what the receipt must carry.

    IDENTICAL LEDGER ENTRIES TO THE FIELD PATH. Same shape, same attribution, same customer
    message — the only difference is `channel`. A fallback or a side path that records differently
    is a reporting bug waiting for month end, discovered by an owner reconciling two numbers that
    ought to match.
    """
    c = request.app.state.container

    # THE SHOP'S OWN THRESHOLD, ON THIS PATH TOO — and it was passed on neither.
    #
    # `manager_threshold` defaults to 0, which means «no approval needed for anything». The owner
    # sets it on his screen, the field route reads it, and this one did not: so the counter he set
    # the rule FOR — the integrated till, where neither he nor the customer is looking at our
    # screen — was the one place it did not apply. A control that holds everywhere except the
    # place it was written for is not a control.
    from app.api.v1.loyalty import _after_redeem, _threshold

    try:
        rec, is_new = await c.redeemer.redeem(
            body.tenant, body.subject_ref, body.reward_id, actor=body.actor,
            idem_key=body.idempotency_key, channel="till", branch_id=body.branch_id,
            approved_by=body.approved_by,
            manager_threshold=await _threshold(c, body.tenant))
    # RETURNED, NOT RAISED — and the reader here is a cashier with a customer in front of him.
    #
    # `Overdraft` says «الرصيد 30 نقطة، والمكافأة 100 — لا يكفي». Raised, the platform's handler
    # strips `detail` (CWE-209 by design) and the body becomes {"error": "CONFLICT"}. operations'
    # `LoyaltyDesk` then reads `payload["detail"] or payload["reason"]`, finds neither, and the till
    # prints «تعذّر الاستبدال.» — so the cashier cannot tell an insufficient balance from a retired
    # reward from a duplicate key, and tells the customer nothing.
    #
    # THE STATUS IS KEPT, so every existing caller behaves as before; only the sentence survives.
    # The desk already reads `reason`, which is the whole reason this shape was chosen.
    except Overdraft as exc:
        return JSONResponse({"error": "CONFLICT", "reason": str(exc)},
                            status_code=status.HTTP_409_CONFLICT)
    except LoyaltyError as exc:
        return JSONResponse({"error": "BAD_REQUEST", "reason": str(exc)},
                            status_code=status.HTTP_400_BAD_REQUEST)

    bal = await c.ledger.balance(body.tenant, body.subject_ref)
    if is_new:
        # THE WHOLE TAIL, NOT THE RECEIPT ALONE — and this path had copied only the receipt.
        #
        # `_after_redeem` carries a second seam: a `service` reward is also RECORDED AS A VISIT, so
        # the reminder cycle restarts from the free wash the customer just had. Reimplementing half
        # of it here meant a reward redeemed at the till left no trace in operations: the customer
        # received the service and was then reminded, days later, to come in for it — on the very
        # counter where nobody from the shop is looking at our screen to notice.
        #
        # The docstring above says these two paths differ only in `channel`. Calling the same
        # function is the only way that stays true when the tail grows a third seam.
        await _after_redeem(c, body.tenant, rec, bal.points, body.actor)
    return {
        # What the printed receipt carries, so the paper becomes a second trail.
        "transaction_ref": rec.id,
        "discount_halalas": rec.discount_halalas,
        "reward_name": rec.reward_name,
        "cost": rec.cost,
        "balance": bal.points,
        "duplicate": not is_new,
    }


# ── what the programme did, for a peer's report ───────────────────────────────────────────────
class ReportIn(BaseModel):
    tenant: str
    # Empty = all time. A window makes "this week" answerable without the caller filtering rows it
    # is not allowed to see.
    since: int = 0


@router.post("/loyalty/report", dependencies=[Depends(require_internal_token)])
async def internal_report(request: Request, body: ReportIn) -> dict:
    """The same totals the owner's screen shows, for `insights` to put one line in the weekly
    digest.

    AGGREGATES ONLY, and that is the whole reason this is separate from the ledger: it answers
    "how many points were redeemed" and never "by whom". A peer building a report has no business
    receiving a list of customers, and a route that returned one would be a customer export
    wearing a different name.
    """
    from app.core.report import build as build_report

    c = request.app.state.container
    rep = await build_report(c.datastore, body.tenant)
    if body.since:
        # DRAINED. Ten thousand newest redemptions, cursor discarded, then filtered by `since` —
        # so a shop with more than that many redemptions newer than the window reported a number
        # smaller than the truth, and the report gave no sign of it.
        rows = await drain(c.datastore, "loyalty_redemptions", {"tenant": body.tenant},
                           sort=("created_at", "desc"))
        recent = [r for r in (rows or []) if int(r.get("created_at") or 0) >= body.since]
        rep["redeemed_since"] = sum(int(r.get("cost") or 0) for r in recent)
        rep["redemptions_since"] = len(recent)
    return rep


# ── the table a shop starts with (spec §10.8) ─────────────────────────────────────────────────
class SeedRewardIn(BaseModel):
    name: str
    cost: int
    type: str
    # Already resolved by the caller. A seed row could only name a service, and a service id belongs
    # to one establishment — so the lookup happens where that shop's catalogue is.
    service_id: str = ""
    discount_halalas: int = 0


class SeedRewardsIn(BaseModel):
    tenant: str
    rewards: list[SeedRewardIn]


@router.post("/loyalty/seed-rewards", dependencies=[Depends(require_internal_token)])
async def seed_rewards(request: Request, body: SeedRewardsIn) -> dict:
    """Give a new establishment its rewards table. Returns how many were created.

    WHY THIS EXISTS AT ALL. «نقاطي» once told owners the table "arrives filled for your trade — contact
    us if it stays empty", and nothing in this product ever filled it: there was no seeding code in
    any service. The screen was accusing the system of a fault that had no implementation behind
    it, and every shop was told to call support on its first day.

    IDEMPOTENT BY NAME, exactly like the service catalogue. A retried provisioning step must not
    hand the owner two of every reward to delete by hand on day one.

    IT REFUSES NOTHING AND CREATES WHAT IT CAN. A single malformed entry — a service reward whose
    service was not seeded, a discount with no amount — skips itself and the rest still land. The
    alternative is a shop with no rewards at all because one row of ours was wrong, which is our
    mistake charged to the owner.
    """
    c = request.app.state.container
    existing = {r.name for r in await c.rewards.list(body.tenant, active_only=False)}
    created = 0
    for entry in body.rewards:
        if entry.name in existing:
            continue
        try:
            await c.rewards.create(
                body.tenant, name=entry.name, cost=entry.cost, type=entry.type,
                service_id=entry.service_id, discount_halalas=entry.discount_halalas)
        except LoyaltyError:
            continue
        created += 1
    return {"created": created}


# ── the repair (playbook: a materialised total can drift from its ledger) ──────────────────────
class ReconcileIn(BaseModel):
    tenant: str
    subject_ref: str
    # THE SAME REQUIREMENT AS THE USER-TIER ROUTE, AND FOR THE SAME REASON. «Internal» here means
    # the caller holds a service token — but the thing that reaches for this route is a person
    # running a playbook, and a repair he cannot explain later is one nobody can argue with.
    reason: str = Field(min_length=3, max_length=280)


@router.post("/loyalty/reconcile", dependencies=[Depends(require_internal_token)])
async def reconcile(request: Request, body: ReconcileIn) -> dict:
    """Recompute one balance from its ledger, and repair it if they disagree.

    Exists because the materialised total CAN drift — a crash between the two writes in
    `Ledger.post`, a restore that replayed one collection and not the other. Drift with no detector
    is the worst version of this bug, because the wrong number stays entirely plausible.

    AUDITED, AND IT WAS NOT. This route rewrote the total of any customer's ledger in any
    establishment and left no record at all — not who, not why, not what the number had been.
    §8.3 asks for all three; this asked for none.
    """
    c = request.app.state.container
    await request.app.state.auditor.record(
        "loyalty.reconciled", actor="playbook", tenant=body.tenant,
        resource=f"balance:{body.subject_ref}", ip="", metadata={"reason": body.reason})
    out = await c.ledger.reconcile(body.tenant, body.subject_ref)
    await request.app.state.auditor.record(
        "loyalty.reconcile_result", actor="playbook", tenant=body.tenant,
        resource=f"balance:{body.subject_ref}", ip="",
        metadata={"was": out.get("was"), "now": out.get("ledger"),
                  "drift": out.get("drift"), "repaired": out.get("repaired")})
    return out
