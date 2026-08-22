"""The dashboard's routes — reads only, and one subscription switch.

EVERYTHING HERE READS A SNAPSHOT. No route computes an indicator on the request path: that is the
whole reason the snapshot exists (core/tick.py), and a route that "just recomputes this one" is how
the guarantee is lost one endpoint at a time.

THE PLAN IS CHECKED AT EVERY ROUTE, NOT ONLY IN THE CATALOGUE. The console is a map and never the
authority — a client that stops asking is a client that sees everything.

AND A TENANT WITH NO SNAPSHOT NEVER GETS A BLANK. It gets "أحسب الآن" with the next pass time. An
empty dashboard reads as broken, and an owner who concludes that on his first day does not return
on his second.
"""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.config import get_settings

from app.adapters.peers import DENIED
from app.api.auth import Principal
from app.api.authz import require_capability
from app.api.ratelimit import rate_limit
from app.core import bundles as _bundles
from app.core import next_step
from app.core import plans
from app.core.coverage import blocked, group_by
from app.core.models import Coverage, NEXT_STEP_STATE, PAIRS, SNAPSHOTS, Pair

router = APIRouter(prefix="/insights", tags=["insights"])

_READ = require_capability("insights.read")
_PLATFORM = require_capability("platform.insights")


def _refuse(reason: str, code: int = status.HTTP_400_BAD_REQUEST) -> JSONResponse:
    """A refusal the owner can read — returned, not raised.

    The platform's handler strips `detail` from every HTTPException on purpose (CWE-209), which is
    right for a trace and wrong for a sentence we wrote ourselves. See playbook §4.25.
    """
    return JSONResponse({"error": "BAD_REQUEST", "reason": reason}, status_code=code)


def _tenant(principal: Principal) -> str:
    t = getattr(principal, "tenant", "") or ""
    if not t:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "no establishment on this token")
    return t


# THE PLAN IS NOT ON THE TOKEN — see core/plans.py. It is asked of billing, per request, and a
# failure to reach billing denies. `_keys` is the one place that asks.
async def _keys(c, tenant: str) -> set[str]:
    return await plans.allowed_keys(c.peers, tenant)


LOCKED = "هذه الميزة في باقة أعلى"


async def _snapshot(c, tenant: str, branch_id: str = "") -> dict | None:
    return await c.datastore.get(SNAPSHOTS, f"{tenant}|{branch_id or '_all'}")


@router.get("/dashboard", dependencies=[Depends(rate_limit)])
async def dashboard(request: Request, branch_id: str = "",
                    principal: Principal = Depends(_READ)) -> dict:
    """Everything the panel renders, in one read.

    ONE CALL, because eleven indicators fetched separately is eleven round trips on a phone, and
    the screen would paint itself in pieces.
    """
    c = request.app.state.container
    tenant = _tenant(principal)
    keys = await _keys(c, tenant)

    # ── WHOSE DASHBOARD THIS IS (§12.4) ────────────────────────────────────────────────────────
    # A person assigned to a branch sees THAT branch, and asking for another one does not widen
    # him — the parameter is overruled rather than refused, because a manager who lands on «كل
    # الفروع» from a bookmark should read his own shop, not an error.
    #
    # THE SCOPE COMES FROM OPERATIONS, which is the only service that knows who works where. An
    # unassigned person — the owner, and everybody in a shop that assigns nobody — is unscoped and
    # sees the establishment, exactly as before.
    ask = getattr(c.peers, "branch_scope", None)
    scope = await ask(tenant, getattr(principal, "subject", "")) if ask else ""
    if scope in DENIED:
        # FAIL CLOSED — and it used to fail OPEN, on the one question that decides who sees whose
        # numbers. `_unreadable` means we could not learn which branch this person works at, and
        # the old line turned that into `branch_id = ""`, which is «the whole establishment». So
        # a branch manager, during any operations hiccup, was handed the entire chain's dashboard:
        # every branch's revenue and traffic, from a read that failed.
        #
        # An unknown scope is not an empty scope. Refusing costs him a dashboard for a minute;
        # guessing costs the owner a confidentiality he never agreed to give up.
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content={
            "message": "تعذّر التحقق من صلاحيتك على الفروع الآن. أعد المحاولة بعد قليل."})
    if isinstance(scope, (set, frozenset)):
        # A DASHBOARD IS BUILT FROM ONE BRANCH'S SNAPSHOT, and a man who watches four has no single
        # one. Picking one of them silently would show him a quarter of his work as if it were all
        # of it — the failure this whole change exists to prevent — and widening to the
        # establishment would show him branches he was never granted. So he is told, and «مقارنة
        # الفروع» beside it answers the question he actually has.
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={
            "error": "MANY_BRANCHES",
            "branches": sorted(scope),
            "message": "لوحتك تغطي أكثر من فرع. اختر فرعاً، أو افتح «مقارنة الفروع»."})
    if scope:
        branch_id = scope

    snap = await _snapshot(c, tenant, branch_id)

    if not snap:
        # ── COMPUTED HERE AND NOW, ON THE FIRST OPEN ────────────────────────────────────────
        # THE «تظهر خلال ساعات» MESSAGE WAS THE FIRST THING A NEW SHOP SAW. It was written to
        # prevent a blank dashboard, and it prevented one — by replacing it with a sentence that
        # says the product is not ready yet, on the very screen that is supposed to prove the
        # product works. An owner who has just signed up and recorded his first visits reads it
        # as "nothing was counted".
        #
        # AND THE COST ARGUMENT DOES NOT APPLY TO THE CASE THAT HITS IT. The sweep exists because
        # 26 indicators over years of visits must not run on every page open; a shop with NO
        # snapshot has no years — it is minutes old, its history is a handful of rows, and
        # computing it inline is cheaper than the round trip that fetched nothing.
        #
        # ONLY WHEN THERE IS NOTHING. An existing snapshot is served as it is, however old — the
        # sweep owns refreshing it, and «حدّث الآن» below is how an owner asks for it early.
        try:
            await c.tick.compute(tenant, now=int(time.time()))
            snap = await _snapshot(c, tenant, branch_id)
        except Exception:               # noqa: BLE001 — a failed compute is not a failed screen
            snap = None
        if not snap:
            # A BRANCH WITH NO VISITS IS NOT A COMPUTATION IN PROGRESS.
            #
            # The sweep derives its branch list FROM THE VISITS, so a branch that has never
            # recorded one has no snapshot and never will until it does. Its manager — hired the
            # day the branch opened, which is exactly when this happens — was told «أحسب مؤشرات
            # محلك الآن — حدّث الصفحة بعد قليل» on every open, for ever. The sentence promises work
            # in progress, so he refreshes, and refreshes, and concludes the product is broken on
            # his first day.
            #
            # THE HONEST ANSWER NAMES HIS BRANCH AND WHAT IT IS WAITING FOR — a visit, which he is
            # the one who can record. «لا توجد بيانات» and «أحسب الآن» are different states and
            # collapsing them is the same three-state failure as an empty list standing in for a
            # failed read.
            if branch_id:
                return {"computing": False, "empty_branch": True,
                        "message": "لا توجد زيارات مسجّلة في فرعك بعد — سجّل أول زيارة "
                                   "وتظهر مؤشرات الفرع فوراً.",
                        "values": {}, "as_of": 0}
            return {"computing": True,
                    "message": "أحسب مؤشرات محلك الآن — حدّث الصفحة بعد قليل",
                    "values": {}, "as_of": 0}

    now = int(time.time())
    age_hours = (now - int(snap.get("computed_at") or 0)) // 3600
    values = plans.filter_snapshot(snap.get("values") or {}, keys)

    # The pairs are a paid surface, and the teaser is the ONE deliberate exception to "what a plan
    # does not include is not rendered at all".
    pairs = [_as_pair(r) for r in (snap.get("values", {}).get("associations", {}) or {})
             .get("pairs", [])]
    teaser = plans.teaser(keys, pairs)

    cov = snap.get("coverage") or {}
    not_enabled = []
    for name, raw in cov.items():
        b = blocked(name, coverage=Coverage(total=int(raw.get("total") or 0),
                                            known=int(raw.get("known") or 0)))
        if b:
            not_enabled.append({"indicator": name, **b})
    assoc = (snap.get("values") or {}).get("associations") or {}
    b = blocked("associations", learning=assoc)
    if b and not plans.can_see("associations", keys):
        pass          # a locked surface is not "not enabled" — it is not bought. Two different
                      # sentences, and mixing them tells the owner to fix something he cannot.
    elif b:
        not_enabled.append({"indicator": "associations", **b})

    # ── the audience he already has (spec §8.5) ───────────────────────────────────────────────
    # Shown to a shop WITHOUT campaigns, and to nobody else. It is the truest upgrade motivator in
    # the product because it is his own number — customers who explicitly agreed to receive his
    # offers, sitting there while he cannot send one.
    #
    # And it is only honest because consent is now recorded explicitly (reminders/core/consent.py).
    # Computed from refusals — as it would have been a week ago — this was every customer he had,
    # which sells an upgrade on a premise the first campaign disproves.
    audience = None
    if not plans.can_see("associations", keys):
        count = await c.peers.consented(tenant)
        if count:
            # ZERO SHOWS NOTHING. "0 customers agreed" is not a motivator, it is a verdict on his
            # customer page — and one he cannot act on from this screen.
            audience = {"consented": count,
                        "message": f"{count} عميلاً وافقوا على استقبال عروضك."}

    # ── الخطوة التالية (core/next_step.py) — واحدة تتصدّر، تتغيّر بالأولوية والتبريد ───────────
    ctx = next_step.NextStepCtx(
        values=values, entitlements=keys, audience=audience, teaser=teaser,
        multi_branch=len(values.get("branch_rows") or []) > 1,
        staff_coverage=cov.get("staff_performance") or {})
    state_row = await c.datastore.get(NEXT_STEP_STATE, tenant) or {}
    first_seen = dict(state_row.get("seen") or {})
    picked = next_step.pick(ctx, first_seen, now=now)
    seen_ids = {picked["primary"]["id"]}
    if picked["secondary"]:
        seen_ids.add(picked["secondary"]["id"])
    updated_seen = next_step.next_first_seen(first_seen, seen_ids, now=now)
    if updated_seen != first_seen:
        await c.datastore.put(NEXT_STEP_STATE, tenant, {"seen": updated_seen})

    return {
        "computing": False,
        "values": values,
        "audience": audience,
        "coverage": cov,
        "as_of": int(snap.get("computed_at") or 0),
        # SHOWN, ALWAYS. An owner comparing our number to his till at 2pm must see that ours was
        # computed at 3am, or he stops trusting both.
        "as_of_hours_ago": age_hours,
        # THE SETTING, NOT A LITERAL. `SNAPSHOT_STALE_HOURS` is declared in config.py and in
        # the values file, and this line ignored it: an operator lowering the threshold to
        # see staleness sooner changed nothing, and the number he read was not the number
        # the badge obeyed.
        "stale": age_hours >= get_settings().SNAPSHOT_STALE_HOURS,
        # AND WHETHER THE HISTORY BEHIND THESE NUMBERS WAS COMPLETE. `tick.py` records `partial`
        # when the visit read hit its cap: the snapshot is then computed from a WINDOW of the
        # shop's history rather than from all of it. `Snapshot.partial` says so in its own comment
        # — «the difference is invisible on the screen unless it travels with them» — and it was
        # written to disk on every run and dropped here. So the busiest shops in the product, the
        # only ones that can reach a cap, were the ones shown a figure with no mark on it.
        #
        # `stale` beside it is the same honesty about a different axis: one says the number is old,
        # this says it is narrow. An owner who can see neither compares ours to his till, finds a
        # gap, and stops trusting both — and he is right to.
        "partial": bool(snap.get("partial")),
        "branch_id": branch_id,
        "visits": snap.get("visits", 0),
        "not_enabled": not_enabled,
        "teaser": teaser,
        # WHAT HE HOLDS, not what plan he is on. The console renders a lock from the absence of a
        # key rather than from a plan name it would otherwise have to know the ladder of.
        "entitlements": sorted(keys),
        "next_step": picked,
    }


def _as_pair(row: dict) -> Pair:
    p = Pair(tenant=row.get("tenant", ""), a=row.get("a", ""), b=row.get("b", ""),
             lift_basket=float(row.get("lift_basket") or 0),
             lift_customer=float(row.get("lift_customer") or 0),
             customers=int(row.get("customers") or 0),
             verdict=row.get("verdict", "none"))
    p.id = row.get("id", p.id)
    return p


@router.get("/associations", dependencies=[Depends(rate_limit)])
async def associations(request: Request, principal: Principal = Depends(_READ)):
    """The pairs themselves — a paid surface (spec §15).

    Returns the VERDICT and the customer count, and never the arithmetic. No lift value leaves
    this service: the engine is the product's own IP (core/associations.py).
    """
    c = request.app.state.container
    tenant = _tenant(principal)
    if not plans.can_see("associations", await _keys(c, tenant)):
        return _refuse(LOCKED, status.HTTP_402_PAYMENT_REQUIRED)
    snap = await _snapshot(c, tenant)
    assoc = ((snap or {}).get("values") or {}).get("associations") or {}
    if assoc.get("learning"):
        return {"learning": True, "have": assoc.get("have", 0), "need": assoc.get("need", 0),
                "pairs": []}
    return {"learning": False,
            "pairs": [{"a": p["a"], "b": p["b"], "verdict": p["verdict"],
                       "customers": p["customers"]}
                      for p in assoc.get("pairs", []) if p.get("verdict") != "group"]}


@router.get("/bundles", dependencies=[Depends(rate_limit)])
async def suggested_bundles(request: Request, principal: Principal = Depends(_READ)):
    """The suggested-bundles page (spec §10.6.2.1) — where, never how much."""
    c = request.app.state.container
    tenant = _tenant(principal)
    if not plans.can_see("suggested_bundles", await _keys(c, tenant)):
        return _refuse(LOCKED, status.HTTP_402_PAYMENT_REQUIRED)
    snap = await _snapshot(c, tenant)
    values = (snap or {}).get("values") or {}
    pairs = [_as_pair(r) for r in (values.get("associations") or {}).get("pairs", [])]
    missing: dict[tuple[str, str], int] = {}
    for m in values.get("missed_opportunities") or []:
        k = (m.get("has", ""), m.get("missing", ""))
        missing[k] = missing.get(k, 0) + 1
    cards = _bundles.build(pairs, names=values.get("service_names") or {},
                           missing_counts=missing,
                           min_opportunity=get_settings().INSIGHTS_MIN_OPPORTUNITY)
    return {"bundles": cards, "count": len(cards)}


@router.get("/branches", dependencies=[Depends(rate_limit)])
async def branches(request: Request, principal: Principal = Depends(_READ)):
    """The branch table, with its unspecified row and its ranking rule (spec §10.6.3)."""
    # NO GATE. Everything about branches follows the branch count the establishment bought, not a
    # separate purchase — see core/plans.py. A shop with one branch gets an empty table here and
    # needs nothing else: the switch does not render for it either (core/tick.py).
    c = request.app.state.container
    tenant = _tenant(principal)

    # THE SAME SCOPE THE DASHBOARD APPLIES, and this route did not ask for it at all — which made
    # it the widest hole in the product: the branch COMPARISON table is every branch's revenue and
    # traffic side by side, and a branch-scoped manager read the whole chain's copy of it. The
    # dashboard next door was scoped; this one was not, so the isolation held everywhere except
    # the single screen that exists to compare people.
    ask = getattr(c.peers, "branch_scope", None)
    scope = await ask(tenant, getattr(principal, "subject", "")) if ask else ""
    if scope in DENIED:
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content={
            "message": "تعذّر التحقق من صلاحيتك على الفروع الآن. أعد المحاولة بعد قليل."})

    snap = await _snapshot(c, tenant)
    cov = ((snap or {}).get("coverage") or {}).get("branch_comparison") or {}
    rows = ((snap or {}).get("values") or {}).get("branch_rows") or []
    if scope:
        # HIS OWN ROW, AND NO RANKING. A table of one cannot be ranked, and «الأول من ثلاثة» said
        # to somebody who may not see the other two is a number he cannot check and we should not
        # have shown.
        # MEMBERSHIP, NOT EQUALITY. What a man may SEE is a set — one branch is a set of one, and a
        # supervisor over four is a set of four. An `==` here keeps passing every test written for
        # the single-branch case and then shows him ONE of his four, silently, which is the whole
        # reason this reads as a set.
        visible = scope if isinstance(scope, (set, frozenset)) else {scope}
        rows = [r for r in rows if str(r.get("branch_id") or "") in visible]
        # RANKING NEEDS THE WHOLE FIELD. «الأول من ثلاثة» said to somebody who may not see the other
        # two is a number he cannot check, and that stays true whether he sees one branch or four.
        return {"coverage": cov, "rows": rows, "unknown": 0, "can_rank": False}
    return {"coverage": cov, "rows": rows,
            "unknown": cov.get("unknown", 0),
            "can_rank": bool(((snap or {}).get("values") or {}).get("branch_can_rank"))}


class NextStepDismissIn(BaseModel):
    id: str = Field(min_length=1, max_length=64)


@router.post("/next-step/dismiss", dependencies=[Depends(rate_limit)])
async def dismiss_next_step(request: Request, body: NextStepDismissIn,
                            principal: Principal = Depends(_READ)) -> dict:
    """«مو الآن» — this one rule stops leading the card for a while, starting now.

    SAME CAPABILITY AS `set_digest` ABOVE, for the same reason: this changes nothing the shop
    OWNS, only which of several true sentences he is shown first — closer to a per-person
    preference than to data.
    """
    c = request.app.state.container
    tenant = _tenant(principal)
    state_row = await c.datastore.get(NEXT_STEP_STATE, tenant) or {}
    first_seen = dict(state_row.get("seen") or {})
    updated = next_step.dismiss(first_seen, body.id, now=int(time.time()))
    await c.datastore.put(NEXT_STEP_STATE, tenant, {"seen": updated})
    return {"ok": True}


class DigestIn(BaseModel):
    on: bool
    # Empty = the caller themselves. A manager subscribing himself is the common case, and making
    # him type his own id would be a form nobody fills.
    subject: str = Field(default="", max_length=128)


@router.get("/digest", dependencies=[Depends(rate_limit)])
async def get_digest(request: Request, principal: Principal = Depends(_READ)) -> dict:
    """Is this person subscribed to the weekly report?

    THE READ THAT DID NOT EXIST. The switch was `useState(true)`: hardcoded on, because there was
    nothing to ask. An owner who turned the report off saw it ON again on his next visit to the
    screen, and could not tell whether his choice had been saved. The setting was real; only its
    reflection was missing, which is the harder version to notice — everything works, and the
    person using it is the only one who knows something is wrong.

    `decided: false` says «he has never chosen», so the screen can show the default (subscribed)
    without pretending to have read a decision.
    """
    c = request.app.state.container
    subject = str(getattr(principal, "subject", "") or "")
    if not subject:
        return {"on": True, "decided": False}
    state = await c.subscriptions.state_for(_tenant(principal), subject)
    return {"on": True if state is None else state, "decided": state is not None}


@router.put("/digest", dependencies=[Depends(rate_limit)])
async def set_digest(request: Request, body: DigestIn,
                     principal: Principal = Depends(_READ)) -> dict:
    """Subscribe to the weekly report — PER PERSON, not per establishment.

    A manager may want it and the owner may not; one flag on the establishment forces them to
    agree, and makes unsubscribing an act that silently switches a colleague off.
    """
    c = request.app.state.container
    subject = body.subject or str(getattr(principal, "subject", "") or "")
    if not subject:
        return _refuse("لا يمكن تحديد المشترك")
    return await c.subscriptions.set(_tenant(principal), subject, on=body.on)


# HOW OFTEN AN OWNER MAY ASK FOR A FRESH ONE. Long enough that the button cannot be used as a
# denial-of-service against our own datastore, short enough to cover "I just recorded five visits
# and want to see them" — which is the only reason anybody presses it.
REFRESH_COOLDOWN_SECONDS = 15 * 60


@router.post("/refresh", dependencies=[Depends(rate_limit)])
async def refresh(request: Request, principal: Principal = Depends(_READ)) -> dict:
    """Recompute THIS establishment's snapshot now.

    THE OWNER COULD NOT ASK. Recomputing existed as a support route that needs a platform
    capability, so the answer to «سجّلت زيارات اليوم وما ظهرت» was "wait for the sweep" — for a
    number the shop can see with its own eyes at the counter. This is the same computation,
    scoped to the tenant in the token, and it names its own limit rather than failing silently.
    """
    c = request.app.state.container
    tenant = _tenant(principal)
    now = int(time.time())

    snap = await _snapshot(c, tenant)
    computed_at = int((snap or {}).get("computed_at") or 0)
    waited = now - computed_at
    if snap and waited < REFRESH_COOLDOWN_SECONDS:
        minutes = max(1, (REFRESH_COOLDOWN_SECONDS - waited) // 60)
        # A REFUSAL THAT IS RETURNED, NOT RAISED, and that says when rather than "later".
        return {"ok": False, "computed_at": computed_at,
                "message": f"حُدّثت قبل قليل — جرّب بعد {minutes} دقيقة."}

    # A PEER'S REFUSAL IS NOT A CRASH, AND THE OWNER MUST NOT READ ONE.
    #
    # This was an unguarded call, so the day operations answered 422 — its `limit` ceiling was
    # 1000 while this service asked for 5000 — the owner pressing «حدّث الآن» got a bare 500 and
    # the console logged `POST /api/v1/insights/refresh 500`. Nothing on the screen said what had
    # happened, and the same 422 was silently failing every nightly computation as well.
    #
    # The number is one shared declaration now (VISITS_PAGE_MAX / SNAPSHOT_VISIT_LIMIT, paired in
    # ci/check_paired_config.py) so this exact cause cannot return. This guard is for the NEXT
    # one: whatever a peer refuses, he is told we could not refresh — a sentence he can act on by
    # waiting — rather than shown our stack trace's status code.
    try:
        fresh = await c.tick.compute(tenant, now=now)
    except Exception:                                  # noqa: BLE001 — any peer failure, one answer
        c.telemetry.event("insights_refresh_failed", tenant=tenant)
        return {"ok": False, "computed_at": computed_at,
                "message": "تعذّر التحديث الآن — والخلل عندنا. أرقامك محفوظة، جرّب بعد قليل."}
    return {"ok": True, "computed_at": fresh.computed_at, "visits": fresh.visits}


@router.post("/platform/recompute", dependencies=[Depends(rate_limit)])
async def platform_recompute(request: Request, principal: Principal = Depends(_PLATFORM)) -> dict:
    """Recompute one establishment's snapshot now — OURS, for support.

    The tenant comes off the body here, which is why the route is separate and why it needs a
    platform capability: support is answering a question about a shop that is not theirs.
    """
    body = await request.json()
    tenant = str((body or {}).get("tenant") or "")
    if not tenant:
        return _refuse("tenant is required")
    c = request.app.state.container
    await request.app.state.auditor.record(
        "insights.recomputed", actor=getattr(principal, "subject", ""), tenant=tenant,
        resource="snapshot", ip=request.client.host if request.client else "")
    snap = await c.tick.compute(tenant, now=int(time.time()))
    return {"tenant": tenant, "computed_at": snap.computed_at, "visits": snap.visits}
