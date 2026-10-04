# =============================================================================
# reminders — Internal tier (service-to-service, X-Internal-Token)
# -----------------------------------------------------------------------------
# NOT user-facing. Guarded by a shared token compared in CONSTANT TIME
# (CWE-208: observable timing discrepancy). Never a user JWT.
# =============================================================================
from __future__ import annotations

import asyncio
import time

import hmac

from typing import Any

from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from app.adapters.datastore.drain import drain
from app.config import Settings, get_settings
from app.core.erasure import RemindersErasure
from app.core.models import key_of
from app.api.v1.prefs import PrefsIn
from app.core.stores import ScheduleStore, SendLogStore
from app.core.tick import _CLAIM_LOCKS, CLAIM_LOCK_TTL_SECONDS
from app.core import backup as _backup
from app.core import offer_text as OT
from app.core import rendering as R
from app.backup_manifest import BACKUP
from app.manifest import build_manifest

router = APIRouter(prefix="/internal", tags=["internal"])


def _now_iso() -> str:
    import datetime as _dt
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

_HEADER = "X-Internal-Token"

# THE OWNER'S FREE TEXT, ONE CEILING FOR BOTH CALLERS. A campaign's line is short by design; the
# weekly digest is a whole report and was silently 422'd against a limit written for the campaign.
# insights holds the same number in `core/digest.py` and trims to it before posting, so the ceiling
# is enforced on the side that can still do something about it — and again here, because a rule
# enforced on one side of a boundary is a rule the other side can bypass.
OWNER_TEXT_MAX = 700


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
    from app.core.push_verify import verify as verify_push

    body = await request.body()
    secret = settings.PUSH_SIGNING_SECRET or settings.INTERNAL_SERVICE_TOKEN
    ok = verify_push(secret, x_job_signature_timestamp or "", body, x_job_signature or "",
                     now=time.time(), max_skew_seconds=settings.PUSH_SIGNATURE_MAX_SKEW_SECONDS)
    if not ok:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="UNAUTHORIZED")


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


@router.post("/reminders/tick",
            dependencies=[Depends(require_internal_token), Depends(require_push_signature)])
async def tick(request: Request, body: TickIn | None = None) -> dict:
    """The heartbeat. DRIVEN BY job-service's PUSH DISPATCH, NOT A K8S CronJob (migrated
    2026-09-16, following whatsapp-assistant's own tick — see deploy/hooks/job-schedule.sh's own
    header for the full migration plan) — `require_push_signature` on top of the usual internal
    token means this only ever fires on a genuine, unreplayed push job-service itself sent.

    WITHOUT A LIVE SCHEDULE + REGISTERED PUSH TARGET THIS SERVICE IS INERT AND LOOKS HEALTHY:
    visits arrive, schedules are created, every probe is green, and not one message is ever sent.
    That is why a guard checks that this path exists — the failure has no symptom until an owner
    asks why nobody is coming back.

    Runs the catch-up read FIRST, then the send pass. In that order because the bus is
    at-most-once: a visit the event missed should be scheduled and sent in the same tick, not in
    the next one.
    """
    # THE CRON POSTS NO BODY AT ALL. The platform's scheduled-job template sends an empty payload
    # with a JSON content type, and a REQUIRED model rejects that as a validation error before a
    # line of this function runs — so the heartbeat failed on every schedule while every probe
    # stayed green and every route answered. The failure lived in a Job's exit code and nowhere
    # else. An empty POST now means what a scheduled pass means: all of it.
    body = body or TickIn()

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
            # THE CONFIG IS A RESOLVER, NOT `{}` (ج-5). Discovery reads across every tenant from
            # one global cursor, so it has no single shop to look a config up for — and `{}` meant
            # every service fell back to the default cycle. It runs FIRST and consumes the visit,
            # writing the «seen» mark, so the per-tenant catch-up below — the only caller with the
            # real configuration — then found it `duplicate` and changed nothing. A car wash on a
            # 10-day cycle had its first reminder scheduled at 90 days and locked there.
            #
            # Asked per visit, by the tenant on the visit — exactly as `confirm_visits` already is.
            got = await c.ingest.discover(now=now,
                                          service_config=lambda t: _service_config(c, t),
                                          confirm_visits=lambda t: _confirms_visits(c, t),
                                          rating_eligible=lambda t: _rating_eligible(c, t),
                                          message_delay_seconds=lambda t: _message_delay_seconds(c, t))
            caught["read"] += got.get("read", 0)
            caught["scheduled"] += got.get("scheduled", 0)
        except Exception as exc:                                            # noqa: BLE001
            c.telemetry.event("discover_failed", error=str(exc)[:200])

    tenants = [body.tenant] if body.tenant else await _active_tenants(c)
    sent = suppressed = deferred = failed = 0
    reasons: dict[str, int] = {}

    # ONCE PER TICK, NOT ONCE PER TENANT. `Reach.prune()` scans the whole `reached_24h` table —
    # there is no tenant filter to scope it by, because it is housekeeping for one shared table,
    # not a per-shop answer. `Tick.run()` used to call it from inside the per-tenant loop below,
    # which re-ran that same unscoped up-to-5000-row scan once per tenant with due work — up to
    # `TICK_MAX_TENANTS` times per tick for a job that only needs to happen once.
    await c.tick.prune_reach(now=now)

    tick_deadline = time.monotonic() + s.TICK_TIME_BUDGET_SECONDS
    tenants_processed = 0
    for tenant in tenants[:s.TICK_MAX_TENANTS]:
        if time.monotonic() >= tick_deadline:
            # FAIL SHORT, NOT LONG — a widespread peer slowdown must never let this tick still be
            # running when the next one fires. The remaining tenants are caught up next tick.
            c.telemetry.event("tick_time_budget_exceeded", tenants_remaining=len(tenants) - tenants_processed)
            break
        tenants_processed += 1
        cfg = await _service_config(c, tenant)
        try:
            got = await c.ingest.catch_up(tenant, now=now, service_config=cfg,
                                          confirm_visits=await _confirms_visits(c, tenant),
                                          rating_eligible=await _rating_eligible(c, tenant),
                                          message_delay_seconds=await _message_delay_seconds(c, tenant))
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
        from app.core.reason_choices import ChoiceStore
        res = await c.tick.run(
            tenant, now=now, library=await _library(c, tenant),
            # `or k`, NOT `get(…, k)` — the config now always carries the key and its value is
            # blank when the catalogue does not list the service. The identifier remains the last
            # resort for that one case, and it is a worse message rather than no message: a shop
            # holding a rule for a service its catalogue has dropped still has customers waiting.
            service_names={k: v.get("name") or k for k, v in cfg.items()},
            establishment=shop.name, customer_names={}, tone=shop.tone,
            # ONE READ PER TENANT PER PASS, beside the library and the approved set — thirteen
            # small answers that cannot change while this loop runs.
            choices=await ChoiceStore(c.datastore).load(tenant))
        sent += res.sent
        suppressed += res.suppressed
        deferred += res.deferred
        failed += res.failed
        for k, v in res.reasons.items():
            reasons[k] = reasons.get(k, 0) + v

    return {"tenants": len(tenants), "tenants_processed": tenants_processed,
            "caught_up": caught, "sent": sent,
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


@router.get("/reminders/ceiling-pressure", dependencies=[Depends(require_internal_token)])
async def ceiling_pressure(request: Request, limit: int = 200) -> dict:
    """Establishments whose WhatsApp ceiling has cost them customers — who is worth a call.

    THIS IS THE WHOLE REASON THE ROW EXISTS. We decided not to message the owner about it: a
    notice to him is itself a business-initiated message, out of the same ceiling and onto the
    same bill, sent at exactly the moment there is none left (core/ceiling_notice.py). So the fact
    is recorded and READ — by his dashboard, and by us before we pick up the phone.

    WE REACH OUT; WE DO NOT WAIT ON A BUTTON (spec §6.2.2). An owner losing customers to a ceiling
    he does not know exists will not open a support form about it — he will conclude the product
    is quiet and stop looking at it.

    NEWEST FIRST, because pressure that started today is a call worth making today. And bounded,
    because an operator panel that fetches every establishment gets slower every month until
    somebody stops opening it.
    """
    from app.core.ceiling_notice import NOTICES

    store = request.app.state.container.datastore
    rows = await store.scan_all(NOTICES, max(1, min(1000, limit)))
    rows = sorted(rows or [], key=lambda r: int(r.get("at") or 0), reverse=True)
    return {"establishments": rows, "count": len(rows)}


@router.get("/reminders/effect", dependencies=[Depends(require_internal_token)])
async def effect(request: Request, tenant: str, since: int = 0, limit: int = 5000) -> dict:
    """What the engine sent, and what it cost — the two facts only this service holds (proofs 3, 4).

    ONE READ FOR TWO INDICATORS, deliberately. «كم زيارة عادت بعد تذكير» needs the moment each
    reminder went out; «كم إيقافاً لكل ألف رسالة» needs the count of sends and of stops over the
    same window. Two endpoints over one collection would be two scans, two paginations and two
    chances for the numbers under one screen to disagree about the same week.

    THE SENDS COME BACK AS (customer, when), AND NOTHING ELSE. insights joins them against visits
    it already holds; sending it the template, the text or the reason would be handing another
    service a copy of the message log to keep in step with this one.

    BOUNDED, AND IT SAYS SO. `truncated` is not decoration: an indicator computed over the first
    five thousand rows of a busier week is a number that quietly describes a different period than
    its label claims, and the caller must be able to tell.
    """
    from app.core.stores import SEND_LOG

    # TENANT-FILTERED AT THE STORE, not after. A scan of the whole collection would read every
    # shop's log to answer one shop's question — the shape of query that is fine on the pilot and
    # is the outage on the hundredth establishment.
    store = request.app.state.container.datastore
    capped = max(1, min(20_000, limit))
    rows, _ = await store.find(SEND_LOG, {"tenant": tenant}, limit=capped, sort=("at", "desc"))
    rows = [r for r in (rows or []) if int(r.get("at") or 0) >= since]

    sends: list[dict] = []
    opt_outs = 0
    for r in rows:
        outcome = str(r.get("outcome") or "")
        if outcome == "opt_out":
            opt_outs += 1
        elif outcome == "sent":
            sends.append({"subject_ref": str(r.get("subject_ref") or ""),
                          "at": int(r.get("at") or 0),
                          "cls": str(r.get("cls") or "")})
    return {
        "tenant": tenant,
        "sends": sends,
        "sent_count": len(sends),
        "opt_outs": opt_outs,
        "truncated": len(rows) >= capped,
    }


@router.get("/reminders/sends-for-subject", dependencies=[Depends(require_internal_token)])
async def sends_for_subject(request: Request, tenant: str, subject_ref: str) -> dict:
    """The FULL send-log row for one member — every field, unlike `effect` right above
    (deliberately "(customer, when), and nothing else" — that route feeds insights' aggregate
    counters, and handing it the template/reason would be giving a peer service a copy of the
    message log to keep in step with this one). This route is for an internal-only investigation
    tool (ops-mcp's `case_timeline`), never a peer aggregate, so that same restraint would only
    hide the exact evidence a complaint needs: WHICH template went out, WHEN, whether it was
    actually SENT or SUPPRESSED and why (`reason` — e.g. a quiet-hours refusal or a withdrawn
    consent, see core/gate.py), and whether it was ever read or clicked.

    Same safe, already-existing, already subject-scoped store read `SendLogStore.since` already
    makes for the cap-checking logic in core/gate.py — `since=0` here simply means "everything".
    """
    from app.core.stores import SendLogStore

    store = request.app.state.container.datastore
    rows = await SendLogStore(store).since(tenant, subject_ref, since=0)
    return {"sends": rows, "count": len(rows)}


class RedemptionIn(BaseModel):
    tenant: str = Field(min_length=1, max_length=128)
    subject_ref: str = Field(min_length=8, max_length=128)
    reward_name: str = Field(min_length=1, max_length=80)
    cost: int = Field(ge=0, le=1_000_000)
    remaining: int = Field(ge=0, le=100_000_000)


@router.post("/reminders/redemption", dependencies=[Depends(require_internal_token)])
async def redemption(request: Request, body: RedemptionIn) -> dict:
    """Fold a redemption into the confirmation that has not gone out yet (§9.6).

    THE DECISION THIS SERVES, IN THE OWNER'S WORDS: «تأكيد الاستبدال تكون ضمن رسالة تأكيد الزيارة
    بحيث ما نرسل رسايل كثير». Before this, a redemption sent its own receipt — a second message
    minutes after the first, from a product whose whole discipline is not sending many.

    AND THE TEN-MINUTE DELAY IS WHAT MAKES IT POSSIBLE. The confirmation waits on purpose (a
    message arriving while he is still at the counter is about something he is watching happen),
    and that same window is exactly when a reward is handed over. So the merge is not a trick: it
    is the two events being genuinely simultaneous.

    RETURNS `merged: false` RATHER THAN FAILING when there is no pending confirmation — a
    redemption without a visit is a real case (the owner correcting something, a portal
    redemption), and the caller then falls back to its own receipt. Silence would be worse than a
    second message: the customer would learn nothing about points he just spent.
    """
    c = request.app.state.container
    store = ScheduleStore(c.datastore)
    pending = await store.pending_for_subject(body.tenant, body.subject_ref)
    row = next((r for r in pending if r.get("kind") == "visit_confirmation"), None)
    if row is None:
        return {"merged": False, "reason": "no pending visit confirmation"}

    # SAME LOCK `Tick._claim()` TAKES ON THIS ROW — fixed 2026-09-12, a real gap a QA audit found.
    # This handler used to read the pending row and blind-upsert it back with no coordination at
    # all, racing the exact claim lock `_claim()` added for this same read-modify-write shape: a
    # tick could claim (`state: sending`) and send this row between our read and our write, and
    # our upsert would then either stomp its claim mid-send or, worse, revert an already-`sent` row
    # back to a stale pending copy the customer already received. Keyed identically to `_claim()`
    # (`tenant|natural key`, in `_CLAIM_LOCKS`) so the two paths serialise against each other, not
    # just against themselves.
    now = int(time.time())
    lock_key = f"{body.tenant}|{_sched_key(row)}"
    took = await c.datastore.claim(
        _CLAIM_LOCKS, lock_key, {"tenant": body.tenant, "row": _sched_key(row)},
        ttl_seconds=CLAIM_LOCK_TTL_SECONDS, now=now)
    if not took:
        # A tick is deciding this exact row's claim right now. Not an error — the caller's own
        # docstring already treats "no pending confirmation" as a legitimate outcome, and this is
        # the same shape: the row is mid-flight, so there is nothing safe to merge into right now.
        return {"merged": False, "reason": "row is being claimed"}
    try:
        # RE-READ UNDER THE LOCK, NOT THE COPY FROM BEFORE IT. The claim above only tells us we
        # now hold exclusive access — it says nothing about whether a tick's `_claim()` already
        # moved the row to `sending` (or further) in the gap between our first read and this lock.
        fresh = await store._get(_sched_key(row))
        if fresh is None or fresh.get("state") != "pending":
            return {"merged": False, "reason": "no pending visit confirmation"}
        row = fresh

        # A TEMPLATE VARIANT, NOT AN EXTRA SENTENCE. WhatsApp has no optional part, so a
        # confirmation with three unused slots is not a thing that can exist — the row moves to
        # the template that declares five and the send engine chooses it by type, exactly as it
        # does for every other.
        row["template_type"] = "svc_visit_redeemed"
        row["redeemed_name"] = body.reward_name
        row["redeemed_cost"] = int(body.cost)
        row["redeemed_remaining"] = int(body.remaining)
        row["updated"] = now
        # THE NATURAL KEY, NEVER THE ID. The store writes under whatever key it is handed, and the
        # id is not that key — passing it created a SECOND row carrying the same id, one on the
        # old template and one on the new. The customer would then be holding two pending
        # confirmations for one visit, which is the exact duplication the natural key exists to
        # prevent (tenant|subject|service|kind — see models.Schedule.key).
        await store.upsert(body.tenant, _sched_key(row), row)
        return {"merged": True, "schedule": row.get("id", ""), "template_type": row["template_type"]}
    finally:
        await c.datastore.delete(_CLAIM_LOCKS, lock_key)


_sched_key = key_of


@router.post("/reminders/receipts/pull",
            dependencies=[Depends(require_internal_token), Depends(require_push_signature)])
async def pull_receipts(request: Request) -> dict:
    """Walk the notification peer's delivery receipts forward and write them onto the send log.

    DRIVEN BY job-service's PUSH DISPATCH, NOT A K8S CronJob (migrated 2026-09-16, same as the
    tick above) — without a live schedule + registered push target the whole path is inert while
    looking healthy.

    NOT A WEBHOOK. Meta's status callback lands on notification-service, which owns the number and
    the verify token; this service reads what that peer persisted. One door for Meta, one reader
    per consumer, and no second signature to verify in a service that holds no credentials.

    THE ANSWER NAMES ITS OWN LIMITS: `configured: false` when no peer is wired, `unreadable: true`
    when the peer could not be asked. Neither is «no receipts», and a zero with no reason would
    read as «every message accounted for».
    """
    from app.core.receipts import Receipts

    c = request.app.state.container
    out = await Receipts(store=c.datastore, log=SendLogStore(c.datastore),
                         feed=getattr(c, "receipt_feed", None),
                         telemetry=getattr(c, "telemetry", None)).run()
    return out


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
    # DRAINED. The two thousand soonest-due pending schedules, cursor discarded — so a platform
    # with more than that pending simply did not list the tenants whose reminders fell later, and
    # the tick walks this list. The reminders did not fail; they were never looked at.
    rows = await drain(c.datastore, "schedules", {"state": "pending"}, sort=("due_at", "asc"))
    seen: list[str] = []
    for r in rows:
        t = r.get("tenant") or ""
        if t and t not in seen:
            seen.append(t)
    return seen


async def _confirms_visits(c, tenant: str) -> bool:
    """Does this establishment still answer the customer on the day of the visit?

    IT IS THE `visit_recorded` TRIGGER'S SWITCH, and not a setting of its own. It was a key in the
    settings tree for a day — which meant two switches for one behaviour the moment the reason
    registry arrived, and two switches for one behaviour is one of them that quietly does nothing.

    ASKED HERE RATHER THAN AT SEND TIME, and this reason alone: switched off it must not CREATE a
    row at all (§5.5.1). A row created and then suppressed sits in «رسائلي» as «بانتظار» and reads,
    to the owner who threw the switch, exactly like a switch that did not work.
    """
    from app.core.reason_choices import ChoiceStore
    if not tenant:
        return True
    return (await ChoiceStore(c.datastore).load(tenant)).enabled("visit_recorded")


async def _rating_eligible(c, tenant: str) -> bool:
    """Does this shop get the rating app's message instead of the plain confirmation right now?

    TWO FACTS, BOTH MUST HOLD. Owning the app (billing) says nothing about whether the shop has
    switched it ON (rating_settings.py) — a shop that paused it keeps the plain confirmation, same
    as one that never bought the app at all. `False` on either an outage or a genuine "no" — a
    missed rating message for one visit costs nothing a retry would fix, unlike the base licence's
    own refusal, which is why this asks no LicenceError-style question at all.
    """
    if not tenant:
        return False
    owns = await c.app_entitlement.allowed(tenant, "feature.rating")
    if not owns:
        return False
    from app.core.rating_settings import RatingSettingsStore
    settings_row = await RatingSettingsStore(c.datastore).load(tenant)
    return settings_row.enabled


async def _message_delay_seconds(c, tenant: str) -> int:
    """This shop's own configured delay for the post-visit message, in seconds — asked of EVERY
    tenant regardless of `_rating_eligible` (product decision: one "بعد كم دقيقة" answer governs
    both the plain confirmation and the rating request, not a platform-wide constant any more, and
    not gated behind owning the rating app — a shop with no interest in ratings can still want its
    confirmation sooner or later than the 10-minute default)."""
    from app.core.rating_settings import RatingSettingsStore
    settings_row = await RatingSettingsStore(c.datastore).load(tenant)
    return settings_row.delay_minutes * 60


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

    # HIS CATALOGUE, WHICH IS WHERE THE REAL CYCLES LIVE. The tree answers with OUR default when
    # the owner never set anything — and that default (90 days) was being applied to every service
    # of every shop, including a car wash whose catalogue says 10. So the catalogue is read here
    # and consulted where the tree is silent.
    #
    # AND IT ADDS SERVICES THE TREE HAS NEVER HEARD OF. `known` is built from configured services
    # and live rules, so a shop that configured nothing produced an EMPTY config — every service
    # falling through to the default. A service the owner sells is a service the engine must know
    # the cycle of.
    cycles: dict[str, float] = {}
    names: dict[str, str] = {}
    try:
        cycles = await c.catalogue.cycles(tenant) if tenant else {}
    except Exception:                                                        # noqa: BLE001
        cycles = {}
    # HIS WORDS FOR HIS OWN SERVICES (أ-5), from the same cached read. The tick renders every
    # message from this config — `service_names={k: v.get("name") or k …}` — and nothing ever put a
    # name in it, so the fallback WAS the behaviour: «تذكير بخصوص svc_7f3a…» went to every customer
    # of every shop. A name arriving in the answer and being dropped one line later is the whole
    # defect; it is read here, beside the cycle it travelled with.
    #
    # ITS OWN TRY, AND THAT IS NOT TIDINESS. Sharing one with the cycles above meant a failure
    # while fetching the words DISCARDED the cycles that had already arrived — every service in
    # the shop falling back to our 90 days, which is the defect the line above exists to close.
    # Losing a name costs a worse sentence; losing a cycle costs the schedule.
    try:
        names = await c.catalogue.names(tenant) if tenant else {}
    except Exception:                                                        # noqa: BLE001
        names = {}
    # ZERO IS NOT A CYCLE, and it is filtered HERE as well as in the reader. A service with no
    # natural rhythm (a puncture repair) must not be added to the known set — added, it resolves to
    # our default and starts reminding people about a repair that never repeats.
    cycles = {sid: days for sid, days in cycles.items() if days > 0}
    known |= set(cycles)

    out: dict[str, dict] = {}
    for sid in sorted(x for x in known if x):
        v = tree.effective(sid)
        # THE ORDER, AND IT IS THE WHOLE FIX. `resolve` already reports WHERE each value came
        # from: "service", "group:…" and "general" are the owner's own decisions and outrank
        # everything. Only "default" means «nobody said» — and that is precisely where his
        # catalogue must answer instead of our 90.
        chosen = tree.resolve(sid, "interval_days")
        # NO SECOND FALLBACK ONCE THE OWNER HAS SPOKEN. `chosen.source != "default"` means a real
        # decision at the service/group/general level — including an explicit zero, "this service
        # has no cycle" — and `cycle or v.get("interval_days")` used to silently reintroduce a
        # nonzero value from the tree's own separately-resolved read exactly when that decision was
        # zero. Only the "nobody said" (default) case still falls back, catalogue first.
        if chosen.source == "default":
            cycle = float(cycles.get(sid) or 0) or float(v.get("interval_days") or 0)
        else:
            cycle = float(chosen.value or 0)
        out[sid] = {
            "cycle_days": cycle,
            "lead_days": v.get("lead_days") or 0,
            "follow_up_days": v.get("follow_up_days") or 0,
            # A service switched off schedules nothing NEW. Existing schedules are left alone: the
            # owner turned off future reminders, not the one already promised to a customer this
            # week, and silently cancelling those would be a decision they did not make.
            "enabled": bool(v.get("enabled", True)),
            # EMPTY, NEVER THE IDENTIFIER. A service the catalogue does not list has no name we
            # can honestly print, and the reader decides what to do with that — putting `sid` here
            # would push our primary key one step closer to a customer's screen.
            "name": names.get(sid, ""),
        }
    return out


async def _library(c, tenant: str) -> list:
    """The platform's texts. THE TENANT IS NOT A FILTER — every shop sends the same 81.

    It read a `tenant_cache` row that nothing in the fleet ever wrote, so it answered `[]` for
    every tenant on every tick and `choose()` refused every message with «لا يوجد قالب فعّال».
    The engine has never had a library. `tenant` stays in the signature because the per-shop
    approval set is what actually differs, and that is read separately (ApprovedTemplates).
    """
    return await c.library.all()


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
    # REQUIRED, WITH NO DEFAULT. Both callers — campaigns and insights — always send it, so the
    # default only ever fired for a caller that FORGOT, and «marketing» is not a safe thing to
    # guess: it decides the mandatory stop link, the consent required, the quiet window and the
    # monthly cap. A guess in either direction is wrong, and a 422 naming the missing field is a
    # better answer than a message sent under a class nobody chose.
    cls: str = Field(alias="class", min_length=1, max_length=32)

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

    # THE CONSENT RECORD, READ HERE TOO — and the reason this line is not optional.
    #
    # `gate.evaluate` defaults `marketing_consent` to "never_asked", and its own rule is that a
    # MARKETING message needs "granted". This route never passed it, so every marketing eligibility
    # question was answered «no» no matter what the customer had actually agreed to: the campaign
    # audience resolved to zero, the preview said the campaign would reach nobody, and the owner
    # concluded the feature did not work. The send path (core/tick.py) reads consent correctly —
    # which is precisely why nothing here ever looked wrong in a test of the gate itself.
    from app.core.consent import Consent

    consent = await Consent(c.datastore).state(body.tenant, body.subject_ref)
    prefs = await PrefsStore(c.datastore).get(body.tenant, body.subject_ref) or {}
    eng = await EngagementStore(c.datastore).get(body.tenant, body.subject_ref) or {}
    recent = await SendLogStore(c.datastore).since(body.tenant, body.subject_ref,
                                                   since=now - 31 * 86400)
    d = G.evaluate(
        cls=body.cls, template_type="", now=now, marketing_consent=consent,
        limits=G.Limits(window_start_hour=s.SEND_WINDOW_START_HOUR,
                        window_end_hour=s.SEND_WINDOW_END_HOUR,
                        daily_service_cap=s.DAILY_SERVICE_CAP,
                        monthly_marketing_cap=s.MONTHLY_MARKETING_CAP,
                        marketing_cooldown_hours=s.MARKETING_COOLDOWN_HOURS,
                        daily_total_cap=s.DAILY_TOTAL_CAP),
        prefs_stopped=prefs.get("stopped") or {},
        engagement_score=float(eng.get("score") or 0.0),
        engagement_at=int(eng.get("scored_at") or 0),
        recent_sends=recent,
        # ── THE HOLDOUT, WHICH THIS ROUTE SILENTLY LEFT OUT ────────────────────────────────────
        #
        # `evaluate` decides the holdout from the SUBJECT — `tenant`, `subject_ref` and the share
        # together — and every one of those has a default that fails OPEN: no tenant, no subject,
        # `holdout_enabled=False`. So this route answered «yes, reachable» for the 10% the engine
        # deliberately withholds, while the send path correctly withheld them.
        #
        # The consequence is the exact promise three paragraphs above: «so the preview's number is
        # the number that goes out». It was not. The owner was shown 340 and the report said 306,
        # with 34 unexplained — and the control group is the whole of our proof that the messages
        # work (§ the holdout), so a preview that ignores it teaches the owner our figures drift.
        #
        # ONE SOURCE FOR THE SHARE, and it is settings — the tick reads the same two values, and a
        # second number here would be a second holdout with a different membership.
        tenant=body.tenant, subject_ref=body.subject_ref,
        holdout_enabled=s.HOLDOUT_ENABLED, holdout_share=s.HOLDOUT_SHARE_PERCENT,
        # `class_enabled` IS DELIBERATELY LEFT AT ITS DEFAULT, and the reason is stated rather than
        # implied: it asks whether the shop has a template of a TYPE, and this route is asked about
        # a CLASS — `template_type` arrives empty. Passing a computed False here would refuse
        # everybody for a question nobody asked.
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
    # REQUIRED, WITH NO DEFAULT. Both callers — campaigns and insights — always send it, so the
    # default only ever fired for a caller that FORGOT, and «marketing» is not a safe thing to
    # guess: it decides the mandatory stop link, the consent required, the quiet window and the
    # monthly cap. A guess in either direction is wrong, and a 422 naming the missing field is a
    # better answer than a message sent under a class nobody chose.
    cls: str = Field(alias="class", min_length=1, max_length=32)
    # The owner's ONE free-text field. Sanitised by the caller AND here — a rule enforced on one
    # side of a boundary is a rule the other side can bypass.
    #
    # 200 WAS THE CAMPAIGN'S NUMBER, and this field has a second caller. insights posts the weekly
    # digest through here — a header plus up to nine `label: value` lines, 250-350 characters for a
    # shop with a full week. FastAPI answered 422, the caller turned it into {"sent": false}, and
    # the route counted it as nothing. So the busiest shops — the ones with the most lines — were
    # exactly the ones that never received the one report they do not have to log in to read.
    # OWNER_TEXT_MAX is the shared ceiling now, declared once and checked on both sides.
    owner_text: str = Field(default="", max_length=OWNER_TEXT_MAX)
    idempotency_key: str = Field(min_length=8, max_length=256)
    # WHICH BRANCH THIS CAMPAIGN IS FOR — empty for every shop that runs one number, which is most.
    #
    # IT DECIDES WHICH NUMBER THE MESSAGE LEAVES FROM. `tick._sending_identity` reads `branch_id`
    # off the schedule row and returns `tenant:branch`; a campaign schedule never carried one, so
    # a chain that had moved to a number per branch (§12.4) sent every campaign message from the
    # CENTRAL number — and the customer of the Jeddah branch replied to Riyadh, to a team that
    # knows nothing about his car.
    #
    # AND IT IS THE SEND LOG'S BRANCH TOO. Without it «من راسلنا ومن أيّ فرع» had no answer for a
    # single campaign message: the ledger recorded an empty branch on every row.
    branch_id: str = Field(default="", max_length=64)
    # WHEN THIS OFFER STOPS BEING TRUE, carried from the campaign so it lands in the send log.
    #
    # That log is the record of who is entitled to what: the customer who received the message
    # holds the offer until this moment, and the customer who did not never held it. Without the
    # date it would be an entitlement with no end — and the operator at the counter, the customer's
    # own page and its countdown would all have nothing to read.
    #
    # ZERO IS VALID AND MEANS "NOT AN OFFER". Most sends carry nothing to expire.
    offer_expires_at: int = Field(default=0, ge=0)
    # Which services the offer covers. Empty is "the whole shop".
    offer_services: list[str] = Field(default_factory=list, max_length=100)
    # ── the typed part of an offer ────────────────────────────────────────────────────────────
    # A discount is «20%» or «50 ريال» and nothing else. It travels as its own field rather than
    # inside the owner's sentence, because a template slot declared `amount` is validated at
    # render and a sentence is not.
    offer_value: str = Field(default="", max_length=32)
    # THE SAME DISCOUNT, STRUCTURED (2026-10-04) — `offer_value` above is display text composed by
    # campaigns; these are the integers a downstream system can actually enforce. Empty `reward_kind`
    # means this send carries no discount at all.
    reward_kind: str = Field(default="", max_length=16)
    reward_amount: int = Field(default=0, ge=0)
    # The services the offer covers, NAMED — this service holds ids, and «خصم على svc_9f2» is not
    # a message. The caller owns the catalogue, so the caller sends the words.
    service_names: list[str] = Field(default_factory=list, max_length=100)
    # THE UNIFIED SINGLE-ITEM QUICK-REPLY BUTTON (core/shape.py, 2026-09-13) — for a campaign of
    # one of the three non-booking types that names exactly one service/package: a
    # "carousel:{kind}:{id}" quick-reply button on an otherwise flat send (the payload prefix
    # whatsapp-assistant's own tap handler recognises — coined for the multi-card carousel send
    # this service used to also offer, deleted 2026-09-13, and kept here because this button
    # mechanism shares the exact same prefix and handler). Empty means no button, omitted from
    # the wire body entirely when meaningless — same posture every optional field here follows.
    button_item_id: str = Field(default="", max_length=64)
    button_kind: str = Field(default="service", max_length=16)
    # WHICH OF THREE REWARDS THIS CAMPAIGN GIVES (occasion pilot, 2026-09-13) — "discount" is the
    # default so every existing caller that has never heard of this field keeps sending exactly
    # what it always sent. See rendering.campaign_slots's own "reward" branch for what each value
    # composes.
    reward_type: str = Field(default="discount", max_length=16)
    reward_points: int = Field(default=0, ge=0)
    # THE CAMPAIGN'S OWN ID (2026-09-14) — carried onto the send log so a redeemed offer at the
    # till can later be attributed back to the campaign that sent it. "" is a real answer (no
    # campaign — an ordinary reminder never goes through this route in the first place, but a
    # future caller of this same route might not be one).
    campaign_id: str = Field(default="", max_length=64)

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
        # READ BY `_sending_identity` AND BY THE SEND LOG — see CampaignSendIn.branch_id.
        "branch_id": body.branch_id,
        "also_services": [],
        # THE OFFER'S OWN WORDS AND ITS END, so the send log records both. The text IS the owner's
        # text — the one field he wrote and the one the customer read. Copying anything else here
        # would be showing the operator a sentence the customer never received.
        # THE ENTITLEMENT, AND IT NO LONGER DEPENDS ON A FIELD THE TEMPLATES NEVER ASK FOR (أ-6).
        # This used to be `body.owner_text if body.offer_expires_at else ""` — and the three offer
        # templates declare no `owner` fill, so the screen never asked, the owner never wrote, and
        # the log recorded a blank. Every reader skips a blank: the campaign sends four hundred
        # correct messages and then the till says «لا يوجد عرضٌ ساري» to the customer holding one.
        "offer_text": OT.compose(owner_text=body.owner_text, value=body.offer_value,
                                 service_names=list(body.service_names),
                                 has_expiry=bool(body.offer_expires_at)),
        "offer_expires_at": body.offer_expires_at,
        "offer_services": list(body.offer_services),
        "offer_value": body.offer_value,
        "reward_kind": body.reward_kind,
        "reward_amount": body.reward_amount,
        "reward_type": body.reward_type,
        "reward_points": body.reward_points,
        "button_item_id": body.button_item_id,
        "button_kind": body.button_kind,
        "campaign_id": body.campaign_id,
    }
    library = await _library(c, body.tenant)
    # THE APPROVED SET, WHICH THIS PATH NEVER READ. The reminder tick has always preferred a
    # template Meta approved; the campaign path did not, so it chose by `active` alone and the
    # send failed at notification-service — one wasted resolution of a phone number per recipient,
    # and a run report full of a failure the shop could do nothing about.
    approved = await c.approved_templates.names(body.tenant)
    names = {sid: name for sid, name in
             zip(body.offer_services, body.service_names, strict=False)}
    from app.core.reason_choices import ChoiceStore
    res = await c.tick.send_one(body.tenant, schedule, now=now, library=library,
                                service_names=names, establishment=shop.name, tone=shop.tone,
                                approved=approved,
                                choices=await ChoiceStore(c.datastore).load(body.tenant))
    return res


@router.get("/reminders/orders/active-discount", dependencies=[Depends(require_internal_token)])
async def active_discount(request: Request, tenant: str, subject_ref: str) -> dict:
    """The live, UNREDEEMED discount a phone number is holding, for WhatsApp Direct Ordering
    (services/operations::OrderService.create) — never consulted for bookings/visits, which keep
    their own, older §5.6.2 mechanism untouched (see `SendLogStore.find_unredeemed_discount`'s own
    docstring for why this is a separate, simpler flag rather than that mechanism reused).

    `ref` IN THE RESPONSE IS THE SEND-LOG ROW ID — the same thing `confirm_payment` later hands
    back to `/reminders/orders/redeem` once, and only once, the order is actually paid.
    """
    from app.core.stores import SendLogStore

    row = await SendLogStore(request.app.state.container.datastore).find_unredeemed_discount(
        tenant, subject_ref, now=int(time.time()))
    if row is None:
        return {"discount": None}
    return {"discount": {
        "ref": str(row.get("id") or ""),
        "reward_kind": str(row.get("reward_kind") or ""),
        "reward_amount": int(row.get("reward_amount") or 0),
        "scope_service_ids": list(row.get("offer_services") or []),
        "expires_at": int(row.get("offer_expires_at") or 0),
    }}


class RedeemDiscountIn(BaseModel):
    tenant: str = Field(min_length=1, max_length=128)
    ref: str = Field(min_length=1, max_length=128)
    redeemed_by: str = Field(min_length=1, max_length=128)


@router.post("/reminders/orders/redeem", dependencies=[Depends(require_internal_token)])
async def redeem_discount(request: Request, body: RedeemDiscountIn) -> dict:
    """Spend one discount, exactly once — called ONLY from `OrderService.confirm_payment`, never
    from `create()`. An order that is cancelled or never paid must never reach this route, so the
    same discount is still there for the customer's next attempt.
    """
    from app.core.stores import SendLogStore

    ok = await SendLogStore(request.app.state.container.datastore).mark_redeemed(
        body.tenant, body.ref, redeemed_by=body.redeemed_by, now=int(time.time()))
    return {"redeemed": ok}


class ChooseOfferIn(BaseModel):
    tenant: str = Field(min_length=1, max_length=128)
    subject_ref: str = Field(min_length=8, max_length=128)
    # WHAT THE CUSTOMER ACTUALLY TOOK. A scoped offer applies only when one of its services is on
    # the visit — the text persuades and the scope applies (§5.6.2).
    service_ids: list[str] = Field(default_factory=list, max_length=50)


@router.post("/reminders/offer/choose", dependencies=[Depends(require_internal_token)])
async def choose_offer(request: Request, body: ChooseOfferIn) -> dict:
    """WHICH offer a visit would apply — and it applies nothing (§5.6.2).

    THE PREDECESSOR OF THIS ROUTE SPENT THE OFFER, by stamping `offer_used_at` onto the send-log
    row. The spec says in as many words why that cannot be: «دفتر الإرسال يُضاف إليه ولا يُعدَّل
    بقرار — وكل حدود 5.8 تُحتسب عليه». A ledger something edits is not a ledger, and every message
    cap this product enforces is counted against that one.

    SO THE ACT MOVED AND THE JUDGEMENT STAYED. `operations` records the spend on the visit — the
    thing that happened at the counter, and the place «one per visit» can actually be enforced —
    and calls this to ask which offer applies, because only this service knows what was sent, to
    whom, with what scope and what expiry.

    INTERNAL, NOT USER-TIER. Its only caller is another service, and the answer names an offer for
    a pseudonym: exposed to a token it would be a way to ask "is this customer holding anything",
    one guess at a time.
    """
    from app.core.stores import SendLogStore

    used = await _spent_or_empty(body.tenant, body.subject_ref)
    if used is None:
        # NOTHING IS CHOSEN WHEN WE CANNOT KNOW WHAT WAS SPENT. The alternative is spending one
        # twice, and a double discount on one invoice is money the owner never agreed to.
        return {"offer": None, "reason": "تعذّر التحقق من العروض المستهلَكة"}

    row = await SendLogStore(request.app.state.container.datastore).choose_offer(
        body.tenant, body.subject_ref, service_ids=list(body.service_ids),
        used_refs=used, now=int(time.time()))
    if row is None:
        # NOT AN ERROR, AND THE SENTENCE SAYS WHY. He may hold nothing, or hold one whose scope
        # this visit does not touch — and the operator at the counter needs to tell those apart.
        return {"offer": None, "reason": "لا يوجد عرضٌ ساري يشمل هذه الزيارة"}
    return {"offer": {"ref": str(row.get("id") or ""),
                      "text": row.get("offer_text", ""),
                      # THE AMOUNT, so the till states the discount rather than reading it off a
                      # sentence — or, when the owner wrote his own line, not at all. An operator
                      # who cannot see the value takes the customer's word for it.
                      "value": row.get("offer_value", ""),
                      "expires_at": int(row.get("offer_expires_at") or 0),
                      # WHICH CAMPAIGN SENT IT — "" for an ordinary reminder, real for a campaign
                      # send (2026-09-14). Lets the till attribute a redemption back to the
                      # campaign that produced it.
                      "campaign_id": row.get("campaign_id", "")}}


async def _spent_or_empty(tenant: str, subject_ref: str) -> set[str] | None:
    """What operations says was spent, or None when it could not be asked — two different facts."""
    from app.config import get_settings
    from app.core.spent import SpentUnknown, spent_refs

    cfg = get_settings()
    try:
        return await asyncio.to_thread(
            spent_refs, operations_url=cfg.OPERATIONS_SERVICE_URL,
            token=cfg.INTERNAL_SERVICE_TOKEN, tenant=tenant, subject_ref=subject_ref)
    except SpentUnknown:
        return None


@router.get("/portal/offers", dependencies=[Depends(require_internal_token)])
async def portal_offers(request: Request, tenant: str, subject_ref: str) -> dict:
    """The offers a customer is holding, for his own page.

    READ BY PORTAL ON HIS BEHALF, never by him: the page is public and carries no token, so the
    only thing that reaches this route is a service that already resolved his reference. A public
    route here would be a way to ask "does this shop hold an offer for this pseudonym", one guess
    at a time.

    EXPIRED ONES ARE ABSENT, not flagged. The link sits in a chat for days and is opened twice —
    the second reading can fall on the other side of an expiry the first did not, and a page that
    shows a dead offer contradicts the shop that sent it.

    THE END TIME TRAVELS, NEVER A DURATION. "Three days left" computed here is wrong by the time it
    renders and frozen wrong while the page stays open; the countdown needs the moment itself.
    """
    from app.core.stores import SendLogStore

    # SPENT ONES ARE ABSENT TOO, and operations is who knows (§5.6.2). If it cannot be asked the
    # page shows no offers rather than possibly-spent ones: a customer told on his own page that
    # he still holds something he used last week will walk in expecting it.
    used = await _spent_or_empty(tenant, subject_ref)
    if used is None:
        return {"offers": []}

    rows = await SendLogStore(request.app.state.container.datastore).live_offers(
        tenant, subject_ref, used_refs=used, now=int(time.time()))
    return {"offers": [{"text": r.get("offer_text", ""),
                        "expires_at": int(r.get("offer_expires_at") or 0),
                        "sent_at": int(r.get("at") or 0),
                        # THE WORDS, AND WHETHER IT IS SCOPED AT ALL (أ-4). This route used to emit
                        # `offer_services` — our identifiers — straight onto a customer's page,
                        # which read «على: svc_9f2a…». The two facts are separate on purpose:
                        # empty names with `scoped` true is «we know it is limited and cannot name
                        # the services», which is neither «the whole shop» nor a gap. Only an
                        # offer recorded before the names were kept can be in that state.
                        "services": list(r.get("offer_service_names") or []),
                        "scoped": bool(r.get("offer_services")),
                        "value": str(r.get("offer_value") or "")}
                       for r in rows]}


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
        return await _backup.import_archive(
            request.app.state.container.datastore, body.archive,
            unseal=unseal, overwrite=body.overwrite, into_tenant=body.into_tenant,
            prune=body.prune, scan_cap=settings.BACKUP_MAX_ROWS_PER_COLLECTION,
            declaration=BACKUP)
    except _backup.BackupError as exc:
        # A bad archive is the caller's problem, not a 500: the checksum failed, the key did not
        # match, or a row had no identity. Say which, so an operator can act.
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.get("/reminders/room", dependencies=[Depends(require_internal_token)])
async def room(request: Request, tenant: str) -> dict:
    """Today's WhatsApp ceiling for this shop, and how much of it the engine has already spent.

    THE TWO NUMBERS CAMPAIGNS COULD NOT GET, and their absence is why «this will reach everyone in
    five days» has never once appeared on an owner's screen: `campaigns` builds its share from a
    ceiling and an engine load, its peer builder returned neither key, and the container fell back
    to "unknown" on every request — silently, for ever, with the sentence simply not rendering.

    BOTH FROM THE SERVICE THAT OWNS THEM. The ceiling is Meta's, read through notification-service
    by this service's own Ceiling; `used` is the count of people this engine has already reached in
    the current window, which is the only place that number exists. Computing either inside
    campaigns would be a second version of somebody else's figure, drifting from it quietly — the
    thing the container's own docstring says it refuses to do.

    THE WINDOW IS THE CONFIGURED ONE, not the default. `/today` builds its own `Reach()` and gets
    `DEFAULT_WINDOW`; a deployment that tunes REACH_WINDOW_SECONDS therefore shows the owner one
    number and gates his sends on another. Reading it off settings here keeps this answer and the
    tick's answer the same answer.

    `limit` KEEPS notification-service's SHAPE: -1 unlimited, 0 unknown. campaigns' share.compute
    reads exactly those two sentinels, and translating them here would put the meaning of "unknown"
    in two places.
    """
    from app.core.reach import Reach

    c = request.app.state.container
    s = get_settings()
    ceiling = await c.ceiling.read(tenant)
    now = int(time.time())
    used, truncated = await Reach(c.datastore, window=s.REACH_WINDOW_SECONDS).count(tenant, now=now)
    return {"limit": int(getattr(ceiling, "limit", 0) or 0),
            "tier": str(getattr(ceiling, "tier", "") or ""),
            "used": int(used or 0), "truncated": truncated}


# ── the customer's five switches, on the tier the caller actually is ────────────────────────────
#
# THE SAME TWO HANDLERS, ON A DOOR WITH NO PER-CALLER LIMIT. portal read and wrote these through
# `/api/v1/prefs/{ref}`, which carries `Depends(rate_limit)`. portal presents no bearer token, only
# X-Internal-Token — so the limiter had no subject and keyed on the IP it could see: the PORTAL
# POD's. Every customer page view of every establishment spent one unit of ONE 600/60s bucket.
#
# WHAT THAT COSTS ON A BUSY EVENING: past the bucket, reminders answers 429. The switches section
# renders «تعذّرت القراءة» for customers who did nothing, and — the part that matters — a customer
# tapping the one-tap unsubscribe gets `saved: False` and no confirmation that his stop was
# recorded. The code's own comment says what he does next: he blocks the number.
#
# NOT A HIGHER LIMIT, A CORRECT TIER. A number tuned for one pod is a number that is wrong again at
# the next customer. The internal token IS the authentication here, and every other portal→reminders
# read (`/internal/portal/offers`) was already on this side of the wall.
#
# DELEGATED, NEVER COPIED. Both routes call the very same handlers the public tier calls — a second
# implementation of an audited, consent-writing action is a second version of what «stop» means.
@router.get("/portal/prefs/{ref}", dependencies=[Depends(require_internal_token)])
async def portal_prefs(request: Request, ref: str) -> dict:
    from app.api.v1.prefs import get_prefs
    return await get_prefs(request, ref)


@router.put("/portal/prefs/{ref}", dependencies=[Depends(require_internal_token)])
async def portal_set_prefs(request: Request, ref: str, body: PrefsIn) -> dict:
    from app.api.v1.prefs import set_prefs
    return await set_prefs(request, ref, body)


@router.get("/reminders/sendable", dependencies=[Depends(require_internal_token)])
async def sendable(request: Request, tenant: str) -> dict:
    """For each template type, the row THIS shop would actually send — or nothing.

    THE ANSWER CAMPAIGNS HAS BEEN GUESSING. Its template peer took a `tenant` argument and threw it
    away: it fetched the platform library once, cached it PROCESS-WIDE, and returned the first row
    of the asked-for type. Three facts that differ per establishment were absent from a call whose
    docstring promised all three —

      · THE TONE. The library carries every type in three registers. Ignoring the shop's meant the
        preview showed one wording and the customer received another.
      · META'S APPROVAL, which is per (tenant, name): the same text is approved for one shop and
        pending for another. A goal card read «متاح» for a shop whose library was still under
        review, he launched, and every recipient failed at the delivery layer for a reason he could
        do nothing about.
      · HIS OWN TEXT, if he re-wrote the message and Meta approved it. The preview never showed it.

    ONE READ PER TENANT, RESOLVED BY `rendering.choose` — the same function the tick calls, so the
    preview and the send cannot disagree. Computing any of this inside campaigns would be a second
    version of a fact this service owns.

    `kind="campaign"` because that is what the caller is: `candidates` maps the type to the reasons
    a campaign message could belong to, which is how his own re-written text is found.
    """
    from app.core import reasons as TR
    from app.core.custom_templates import CustomTemplateStore
    from app.core.reason_choices import ChoiceStore
    from app.core.tick import _own_template

    c = request.app.state.container
    library = await _library(c, tenant)
    shop = await _establishment(c, tenant)
    tone = str(getattr(shop, "tone", "") or "")
    approved = await c.approved_templates.names(tenant)
    # THE SAME BADGE reasons/OWN screen SHOWS, for campaigns' own goal cards — one status word
    # per type (see rendering.type_status), not the collapsed approved/not-approved `blocked`
    # dict below alone, which cannot tell a REJECTED template from one still under review.
    statuses_by_name = await c.approved_templates.statuses(tenant)
    choices = await ChoiceStore(c.datastore).load(tenant)
    customs = CustomTemplateStore(c.datastore)

    out: dict[str, dict] = {}
    # A SEPARATE ANSWER FROM `out`, DELIBERATELY (2026-09-13) — `out`/`types`/`count` are THE
    # SENDABLE CONTRACT this route has always kept (`test_sendable.py`'s own name for it): a type
    # missing from them means the send itself refuses it, and more than one caller (campaigns'
    # `create()`, the reasons screen) trusts that absence as the whole answer. Widening `out`
    # itself to include a not-yet-approved fallback broke exactly that — an unapproved type came
    # back inside `templates`/`types`, which is the one thing this endpoint must never say. The
    # preview screen's own need (show the words even before Meta approves them) is answered here
    # instead, in a field nothing else reads.
    preview_only: dict[str, dict] = {}
    blocked: dict[str, str] = {}
    statuses: dict[str, str] = {}
    for template_type in sorted({str(t.get("type") or "") for t in library} - {""}):
        statuses[template_type] = R.type_status(
            template_type, library=library, statuses=statuses_by_name)
        own_name = _own_template(choices, list(TR.candidates("campaign", template_type)))
        own_row = await customs.get(tenant, own_name) if own_name else None
        try:
            row = R.choose(template_type=template_type, tone=tone, library=library,
                           approved=approved, own=own_name, own_row=own_row)
        except R.RenderError as exc:
            # NOTHING SENDABLE OF THIS TYPE FOR THIS SHOP — which is an ANSWER, and the one the
            # goal card needs in order to lock itself honestly. `choose` already distinguishes
            # «still under review» from «never seeded»: one resolves itself in an hour and the
            # other is ours to fix, and the owner is entitled to know which he is waiting on.
            blocked[template_type] = str(exc)
            # STILL HANDED OVER FOR A PREVIEW, under its own name — an owner composing a campaign
            # whose template is still under Meta's review (or never submitted at all) is entitled
            # to see the exact words it will use the moment it is approved, and to fill in his own
            # blanks and see the count of people it reaches, while the one thing this status
            # actually forbids — pressing launch — stays refused (campaigns' own `create()` reads
            # `blocked`/`meta_approved`, never this field). `approved=None` skips the approval
            # filter entirely, so this is any active library row in the shop's tone, the same one
            # the send will use once approval lands — never invented text. `own` is deliberately
            # left OUT of this fallback: a shop's own re-written wording that Meta has not (yet)
            # approved is not ours to preview as if it were about to go out under his name.
            try:
                preview_row = R.choose(template_type=template_type, tone=tone, library=library,
                                       approved=None)
                preview_only[template_type] = preview_row
            except R.RenderError:
                pass
            continue
        if row:
            out[template_type] = row
    return {"templates": out, "types": sorted(out), "blocked": blocked, "count": len(out),
            "statuses": statuses, "preview_only": preview_only}


class RhythmsIn(BaseModel):
    tenant: str = Field(min_length=1, max_length=128)
    # Empty means "his rhythm for anything" — the most recently updated row per customer. A
    # campaign that names a service asks about THAT service; one that does not is asking how often
    # this person comes at all.
    service_id: str = Field(default="", max_length=128)
    limit: int = Field(default=5000, ge=1, le=5000)


@router.post("/reminders/rhythms", dependencies=[Depends(require_internal_token)])
async def rhythms(request: Request, body: RhythmsIn) -> dict:
    """What we have LEARNED about each customer's rhythm — the number campaigns targets by.

    THE JOIN THAT WAS NEVER MADE. `campaigns` reads `interval_days` off every audience row and
    operations' customer read does not carry it — its own docstring says «campaigns joins the
    learned interval from reminders», and nothing ever did. So every win-back campaign in the
    product's life has measured every customer against one 90-day default: the per-customer rhythm
    this service exists to learn was computed, stored, and never used by the one screen that sells
    it.

    PER CUSTOMER PER SERVICE, because that is what is stored (core/models.py RuleState) and what
    the product promises: «the customer who returns every two months is reminded every two
    months». Collapsing it to a shop average here would hand campaigns exactly the number the
    adaptive engine was built to replace.

    OBSERVATIONS TRAVEL WITH IT. Below two, the estimate is the service's own default wearing a different
    hat — and a caller that cannot tell a learned 45 from a defaulted 45 will present a guess as a
    measurement.

    PSEUDONYMS ONLY, like every other cross-service read here.

    FOUND BROKEN 2026-09-07, building `/reminders/rhythm-for-subject` right beside it: this route
    imported `RULES` from `app.core.models` (never defined there — it lives in `app.core.stores`),
    an ImportError on every single call, zero test coverage anywhere in this service to have ever
    caught it. Every campaign audience join this route was meant to serve has failed at this line
    since the day it was written. Fixed here, alongside its sibling below.
    """
    from app.core.stores import RULES

    c = request.app.state.container
    where = {"tenant": body.tenant}
    if body.service_id:
        where["service_id"] = body.service_id
    rows, _ = await c.datastore.find(RULES, where, limit=body.limit, sort=("updated", "desc"))

    # NEWEST WINS, and the sort above is what makes that true without a second pass: for a caller
    # that named no service, the first row seen for a customer is his most recently updated rhythm.
    out: dict[str, dict] = {}
    for r in rows or []:
        ref = str(r.get("subject_ref") or "")
        if not ref or ref in out:
            continue
        out[ref] = {"interval_days": float(r.get("interval_days") or 0.0),
                    "last_visit": int(r.get("last_visit_at") or 0),
                    "observations": int(r.get("observations") or 0)}
    return {"rhythms": out, "count": len(out)}


@router.get("/reminders/rhythm-for-subject", dependencies=[Depends(require_internal_token)])
async def rhythm_for_subject(request: Request, tenant: str, subject_ref: str) -> dict:
    """The SAME learned rhythm `rhythms` above already computes — POST /reminders/rhythms exists
    for campaigns' bulk audience join (one tenant, thousands of customers, filtered by service_id
    at most); this route is the OTHER shape a caller needs: one specific customer, every service he
    has a rhythm for at once, no tenant-wide scan. whatsapp-assistant's own personalization tool
    (spec: "خدمات مستحقة قريباً"/"خدمات توقف عنها") is exactly that caller — a mid-conversation
    lookup for ONE customer must not pay the cost of a 5000-row tenant scan to answer it.

    Same GET-with-query-params shape as `sends-for-subject` right above, for the same reason: this
    is a read keyed by (tenant, subject_ref), not a body worth a POST.

    `is_learned` TRAVELS WITH EACH ROW, not left for the caller to recompute — see `rhythms`'s own
    docstring on why presenting a defaulted estimate as learned is a lie a caller two services away
    should never have to know to avoid. Uses AdaptiveConfig's own default warmup (2 observations);
    this route carries no per-tenant tuning today because nothing has needed it yet.
    """
    from app.core.adaptive import AdaptiveConfig, is_learned
    from app.core.stores import RULES

    c = request.app.state.container
    rows, _ = await c.datastore.find(
        RULES, {"tenant": tenant, "subject_ref": subject_ref}, limit=200, sort=("updated", "desc"))
    cfg = AdaptiveConfig()
    out = []
    for r in rows or []:
        observations = int(r.get("observations") or 0)
        out.append({
            "service_id": str(r.get("service_id") or ""),
            "interval_days": float(r.get("interval_days") or 0.0),
            "last_visit_at": int(r.get("last_visit_at") or 0),
            "observations": observations,
            "is_learned": is_learned(observations, cfg),
        })
    return {"rhythms": out, "count": len(out)}


class EvidenceIn(BaseModel):
    """One establishment, one window. Nothing about a single customer — see below."""

    tenant: str = Field(min_length=1, max_length=128)
    # INCLUSIVE FROM, EXCLUSIVE TO, both epoch seconds. A window rather than "everything" because
    # the question is always about a period — a complaint, an audit, a dispute — and a file that
    # answers "everything" is a file nobody can read and a disclosure larger than the question.
    since: int = Field(default=0, ge=0)
    until: int = Field(default=0, ge=0)
    limit: int = Field(default=1000, ge=1, le=5000)


@router.post("/reminders/evidence", dependencies=[Depends(require_internal_token)])
async def evidence(request: Request, body: EvidenceIn) -> dict:
    """What this service can prove about one establishment: consent, and what went out.

    WHY IT IS ASSEMBLED RATHER THAN RECONSTRUCTED. Both halves are already written at the moment
    they happen and never updated: a consent transition records the statement TEXT the customer
    actually saw (not a pointer to a document we can edit later), and the send log records every
    message and every suppression with its reason. This route does no interpretation at all — it
    reads two append-only ledgers and returns them. A file we reason our way to is a file the other
    side can reason its way out of.

    PSEUDONYMS, NEVER NUMBERS. Every row here is keyed by `subject_ref`. An evidence file is a
    document that leaves this system — to a regulator, to a lawyer, to a support ticket — and it
    must not be the place a customer's phone number travels to. Whoever needs to tie a pseudonym
    to a person can do it deliberately, once, through the customer's own record.

    THE COUNT AND THE CAP ARE BOTH RETURNED, and `truncated` says so out loud. A file that silently
    stops at a thousand rows is worse than no file: it looks complete, and the gap is invisible
    exactly where it matters.
    """
    from app.core.consent import CONSENT
    from app.core.stores import SEND_LOG

    c = request.app.state.container
    until = body.until or (int(time.time()) + 1)

    def _window(rows: list[dict], field_name: str) -> list[dict]:
        return [r for r in rows
                if body.since <= int(r.get(field_name) or 0) < until]

    consent_rows, _ = await c.datastore.find(
        CONSENT, {"tenant": body.tenant}, limit=body.limit, sort=("seq", "asc"))
    sends, _ = await c.datastore.find(
        SEND_LOG, {"tenant": body.tenant}, limit=body.limit, sort=("at", "asc"))

    kept_consent = _window(consent_rows, "at")
    kept_sends = _window(sends, "at")

    return {
        "tenant": body.tenant,
        "since": body.since,
        "until": until,
        "consent": {
            # EVERY FIELD THAT MAKES IT DEFENSIBLE: what they saw, which version, who recorded it,
            # and the sequence that orders two events inside the same second.
            "records": [{"subject_ref": r.get("subject_ref", ""), "state": r.get("state", ""),
                         "source": r.get("source", ""), "statement": r.get("statement", ""),
                         "statement_version": r.get("statement_version", ""),
                         "actor": r.get("actor", ""), "at": int(r.get("at") or 0),
                         "seq": int(r.get("seq") or 0)} for r in kept_consent],
            "count": len(kept_consent),
            "truncated": len(consent_rows) >= body.limit,
        },
        "messages": {
            # WHY IT WENT, NOT ONLY THAT IT WENT. `cls` is the lawful basis in practice — a service
            # reminder rides a visit, a marketing message rides consent — and `reason` is what a
            # suppression was for. Both are the answer to «why did you message my customer».
            "records": [{"subject_ref": r.get("subject_ref", ""), "cls": r.get("cls", ""),
                         "template_name": r.get("template_name", ""),
                         "branch_id": r.get("branch_id", ""),
                         "outcome": r.get("outcome", ""), "reason": r.get("reason", ""),
                         "at": int(r.get("at") or 0),
                         "offer_text": r.get("offer_text", ""),
                         "offer_expires_at": int(r.get("offer_expires_at") or 0)}
                        for r in kept_sends],
            "count": len(kept_sends),
            "truncated": len(sends) >= body.limit,
        },
    }


class RatingExpediteIn(BaseModel):
    tenant: str = Field(min_length=1, max_length=128)
    subject_ref: str = Field(min_length=8, max_length=128)
    asset_id: str = Field(default="", max_length=64)


@router.post("/reminders/rating-request/expedite", dependencies=[Depends(require_internal_token)])
async def expedite_rating_request(request: Request, body: RatingExpediteIn) -> dict:
    """Move an already-scheduled rating request to "due now" — the till's own
    `POST /till/rating-request` (2026-09-14, this session's till-integration audit follow-up).

    REUSED, NOT REIMPLEMENTED. Building a second send path here — its own gating, its own consent
    check, its own quiet-hours/ceiling logic — is exactly the mistake this codebase's own comments
    warn against elsewhere (till.py's visit route: "a second copy here is a second set of rules
    and the second one is always the one missing a check"). The row this schedules the SAME way
    `core/scheduling.py` already schedules a rating request at visit time; all this does is pull
    its `due_at` to now, so the next ordinary tick pass sends it through the one real path, with
    every gate that path already has — consent, the quiet window, the daily cap, whether this shop
    even has the rating app.

    NOT INSTANT. The standing tick runs on its own cadence (a few minutes, not a route's response
    time) — "expedited", never "sent synchronously". `sent: True` here means "moved to the front
    of the queue", not "delivered".
    """
    from app.core.models import schedule_key

    key = schedule_key(tenant=body.tenant, subject_ref=body.subject_ref,
                       asset_id=body.asset_id, service_id="", kind="rating_request")
    store = ScheduleStore(request.app.state.container.datastore)
    row = await store.get(key)
    if row is None or row.get("state") != "pending":
        return {"ok": False,
               "reason": "لا يوجد طلب تقييم بانتظار الإرسال لهذه الزيارة — إما أُرسل بالفعل، أو "
                         "لا يملك هذا المحل تطبيق التقييم مفعَّلاً."}
    row["due_at"] = int(time.time())
    await store.upsert(body.tenant, key, row)
    return {"ok": True}


# ── the hosted rating page's own two calls ([[task-service-procedure-checklists]] phase 2) ──────
# portal's public `/r/{ref}` page is the customer-facing half; these are the internal-token-holding
# half it calls server-to-server, mirroring the split every other portal-facing route in this
# product already follows (see reminders' own `/internal/reminders/prefs/{ref}` for the pattern).

@router.get("/reminders/rating/{ref}", dependencies=[Depends(require_internal_token)])
async def rating_anchor(request: Request, ref: str) -> dict:
    """What the page needs BEFORE the customer answers anything: which tenant, which visit —
    read-only, never consumes the anchor (see `RatingRequestStore.get`'s own docstring for why a
    page LOAD must not spend the same single-use token `resolve()` is for).

    `found: false` for an unknown or already-consumed ref — same "no oracle, no 404" posture
    operations' own `record_visit_rating` route already documents for the identical shape of
    problem: an internal-token holder gets a plain fact, never a distinction between "never
    existed" and "already used", which would let a caller map the ref space.
    """
    pending = await request.app.state.container.rating_requests.get(ref)
    if pending is None:
        return {"found": False}
    return {"found": True, "tenant": pending.tenant, "visit_id": pending.visit_id}


class RatingSubmitIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    feedback_text: str = Field(default="", max_length=2000)
    rating_issue_step_ids: list[str] = Field(default_factory=list, max_length=200)


@router.post("/reminders/rating/{ref}/submit", dependencies=[Depends(require_internal_token)])
async def rating_submit(request: Request, ref: str, body: RatingSubmitIn) -> dict:
    """The real answer — CONSUMES the anchor (see `RatingRequestStore.resolve`), same single-use
    guarantee the old Flow-reply bus consumer held, now reached by a synchronous call from
    portal's own form POST instead of an inbound WhatsApp message.

    POINTS COMPUTED HERE, FRESH — the exact same `rating_points_for` callable
    `RatingConsumer.handle` already uses, so the bus path (still live for any deployment mid-
    migration) and this page path can never answer "what is this rating worth right now"
    differently. See that callable's own docstring (container.py) for why fresh-at-reply-time is
    the deliberate design, not a shortcut.

    `found: false, reason: "..."` for an unknown/already-consumed ref (expired link, or a
    duplicate submit) — portal renders this as "already recorded, thank you" rather than an error,
    since the ordinary reason a ref is gone is that it was already answered.
    """
    c = request.app.state.container
    pending = await c.rating_requests.resolve(ref)
    if pending is None:
        return {"recorded": False, "reason": "expired or already submitted"}
    points = await c.rating_points_for(pending.tenant) if c.rating_points_for else 0
    ok = await c.rating_writer.write(
        tenant=pending.tenant, visit_id=pending.visit_id, rating=body.rating,
        feedback_text=body.feedback_text, subject_ref=pending.subject_ref,
        rating_points=points, rating_issue_step_ids=body.rating_issue_step_ids)
    return {"recorded": ok, "visit_id": pending.visit_id if ok else ""}
