"""The loyalty routes — the field screen's three, and the owner's settings.

THE FIELD SCREEN'S PATH IS THE ONE WITH A BUDGET. `GET /loyalty/balance/{subject_ref}` is called on
every customer lookup inside the five-second journey (spec §4.7), so it reads a materialised total
and the rewards this balance can afford, in two reads, and returns nothing else.

REDEMPTION IS A POST WITH AN IDEMPOTENCY KEY, and the key is REQUIRED rather than optional. The
caller is a phone in a service lane on a network that drops; without a key, a retry is a second
spend and the customer's receipt says so. Making it optional would mean the well-behaved clients
are safe and the one written in a hurry is not.

EVERY RULE ENFORCED IN THE CORE IS REACHED THROUGH A ROUTE BY AT LEAST ONE TEST. That is the rule
that came out of `fills` being enforced in the core and dropped by the pydantic model, so the
endpoint returned 200 while doing nothing (playbook §4.20).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.api.auth import Principal
from app.api.authz import require_capability
from app.adapters.branch_scope import DENIED
from app.api.ratelimit import rate_limit
from app.core.licence import NOT_INCLUDED as LICENCE_NOT_INCLUDED
from app.core.models import REDEMPTIONS, LoyaltyError, Overdraft
from app.core.notify import to_next_reward
from app.core.spend_lock import SpendBusy, SpendLock

router = APIRouter(prefix="/loyalty", tags=["loyalty"])

_READ = require_capability("loyalty.read")
_REDEEM = require_capability("loyalty.redeem")
_MANAGE = require_capability("loyalty.manage")
# OURS. Repairing a balance is a support action, never an establishment's: a shop able
# to rewrite its own ledger totals is a shop able to erase a customer's points and
# call it a correction.
_PLATFORM = require_capability("platform.loyalty")


def _refuse(reason: str, status_code: int = status.HTTP_400_BAD_REQUEST) -> JSONResponse:
    """A refusal the OWNER can read — returned, not raised.

    The platform's error handler strips `detail` from every HTTPException on purpose (CWE-209:
    information exposure through error messages), which is right for a stack trace and wrong for
    this: our refusals are sentences WE wrote, naming a rule ("the name is longer than 40
    characters"), never anything the caller sent back at them. Raised, they arrive as
    `{"error": "BAD_REQUEST"}` — and an owner told only that his input is invalid tries again,
    fails again, and calls support.

    So these are returned as a response the handler never sees. `reason` must stay author-written
    text: the moment it interpolates caller input it becomes a reflection, and the handler was
    right after all.
    """
    return JSONResponse({"error": "BAD_REQUEST", "reason": reason}, status_code=status_code)


def _tenant(principal: Principal) -> str:
    # NEVER from the body. The tenant comes off the token and only off the token — a body-supplied
    # tenant is a cross-establishment write waiting for somebody to try it.
    t = getattr(principal, "tenant", "") or ""
    if not t:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "no establishment on this token")
    return t


# ── the field screen ───────────────────────────────────────────────────────────────────────────

async def _may_grow(request: Request, principal: Principal) -> JSONResponse | None:
    """Refuse to GROW the programme when the shop has not bought it — and only to grow it.

    `feature.loyalty` is on the price list and nothing ever checked it: every plan earned points
    and edited rewards. The check lives here rather than on a decorator because the line is not
    "loyalty routes" — it is «ما يجعل المحل يَدين بأكثر»: earning, adjusting, and editing the
    rewards or the rules. Reading a balance and REDEEMING what is already owed never ask; a debt
    is paid whether or not the shop renewed this month, and his customer's own page — which may
    not consult billing at all — is showing that balance right now.

    RETURNED, NEVER RAISED: the platform strips `detail` off HTTPException (CWE-209), so a raised
    refusal reaches the screen empty.
    """
    licence = getattr(request.app.state.container, "licence", None)
    if licence is None:
        return None
    if await licence.allowed(_tenant(principal)):
        return None
    return _refuse(LICENCE_NOT_INCLUDED, status.HTTP_402_PAYMENT_REQUIRED)


@router.get("/balance/{subject_ref}", dependencies=[Depends(rate_limit)])
async def balance(request: Request, subject_ref: str,
                  principal: Principal = Depends(_READ)) -> dict:
    """The balance, and ONLY what it can buy (spec §9.5).

    Not the full menu with the unaffordable greyed out: showing a customer standing at the counter
    a reward he cannot have is a worse moment than his not knowing it exists, and the operator
    holding the phone is the one who has to manage it.
    """
    c = request.app.state.container
    tenant = _tenant(principal)
    bal = await c.ledger.balance(tenant, subject_ref)
    catalogue = await c.rewards.list(tenant)
    affordable = await c.rewards.affordable(tenant, bal.points, catalogue=catalogue)
    all_costs = [r.cost for r in catalogue]
    return {
        "subject_ref": subject_ref,
        "points": bal.points,
        "rewards": [r.to_dict() for r in affordable],
        # Zero means "say nothing" — either he can afford everything or the shop has no rewards.
        # "0 points to your next reward" is a sentence that means nothing to the person reading it.
        "to_next_reward": to_next_reward(bal.points, all_costs),
        "expires_at": c.expiry.due_at(bal.to_dict()),
    }


class RedeemIn(BaseModel):
    subject_ref: str = Field(min_length=8, max_length=128)
    reward_id: str = Field(min_length=1, max_length=128)
    # REQUIRED. See the module docstring: a field phone retries, and a retry without a key is a
    # second spend the customer has a receipt for.
    idempotency_key: str = Field(min_length=4, max_length=128)
    # NO BRANCH ON THE BODY. Where the spend happened is resolved from the person's own operator
    # row, exactly as the visit path resolves it (spec 12.2) — this service holds no staff list,
    # so anything a caller sent here would be written unchecked, and «أيّ فرع يصرف أكثر؟» is a
    # question an owner closes a place on.


@router.post("/redeem", dependencies=[Depends(rate_limit)])
async def redeem(request: Request, body: RedeemIn,
                 principal: Principal = Depends(_REDEEM)) -> dict:
    """Spend points. The operator does this, not the manager (spec §9.5).

    THE RECEIPT IS SENT AFTER THE COMMIT, ALWAYS. A message announcing a redemption that then
    failed to commit is worse than no message: the customer holds proof of a spend that did not
    happen, and his balance disagrees with the paper in his hand.
    """
    c = request.app.state.container
    tenant = _tenant(principal)
    actor = getattr(principal, "subject", "") or ""

    # HIS BRANCH, FROM HIS ROW — asked before anything is written, and refused if it cannot be
    # had. Filing a spend under the wrong branch is not a display detail: the branch comparison is
    # what an owner closes a place on.
    branch_id = ""
    resolver = getattr(c, "branch_scope", None)
    if resolver is not None:
        scope = await resolver.scope(tenant, actor)
        if scope in DENIED:
            return _refuse("تعذّر التحقق من فرعك الآن. أعد المحاولة بعد قليل.",
                           status.HTTP_503_SERVICE_UNAVAILABLE)
        # A SUPERVISOR OVER SEVERAL BRANCHES RESOLVES TO A `frozenset`, NOT A SINGLE ID —
        # `BranchScope.scope()`'s own docstring says so (`branches.py`'s multi-branch reading), but
        # this route used to assign it straight into `branch_id: str` unchanged. It then flowed
        # into `Redemption`/`Ledger.post`, both plain dataclasses Python does not enforce the type
        # of, all the way to `store.put(...)` — which cannot JSON-serialize a frozenset, crashing
        # AFTER the ledger had already deducted the points, with no redemption receipt ever
        # written (a QA audit found this, 2026-09-12). There is no single "right" branch to guess
        # for a multi-branch redemption with nothing else naming one, so it files as unscoped —
        # the same "" a shop with no branches at all already gets — rather than crashing or
        # silently attributing the spend to one branch out of several.
        branch_id = scope if isinstance(scope, str) else ""

    await request.app.state.auditor.record(
        "loyalty.redeemed", actor=actor, tenant=tenant, resource="redemption",
        ip=request.client.host if request.client else "")

    try:
        rec, is_new = await c.redeemer.redeem(
            tenant, body.subject_ref, body.reward_id, actor=actor,
            idem_key=body.idempotency_key, channel="field", branch_id=branch_id)
    except Overdraft as exc:
        # A SECOND, CORRECTIVE ENTRY — fixed 2026-09-12, a real gap a QA audit found: the
        # write-ahead record above claimed a redemption that never actually happened (insufficient
        # balance).
        await request.app.state.auditor.record(
            "loyalty.redeemed", actor=actor, tenant=tenant, resource="redemption",
            ip=request.client.host if request.client else "",
            metadata={"outcome": "refused", "reason": str(exc)})
        return _refuse(str(exc), status.HTTP_409_CONFLICT)
    except LoyaltyError as exc:
        await request.app.state.auditor.record(
            "loyalty.redeemed", actor=actor, tenant=tenant, resource="redemption",
            ip=request.client.host if request.client else "",
            metadata={"outcome": "refused", "reason": str(exc)})
        return _refuse(str(exc))

    bal = await c.ledger.balance(tenant, body.subject_ref)
    if is_new:
        # After the commit. And only when new — a retry must not produce a second receipt for one
        # reward, which is exactly what a customer would read as being charged twice.
        await _after_redeem(c, tenant, rec, bal.points, actor)
    return {"redemption": rec.to_dict(), "balance": bal.points, "duplicate": not is_new}


async def _after_redeem(c, tenant: str, rec, remaining: int, actor: str) -> None:
    """The two seams that follow a redemption — each in its own try, neither able to undo it.

    The points are spent and the customer has his reward. Failing here must not raise: refusing a
    redemption because a message did not send would take back something already handed over.
    """
    try:
        await c.notifier.receipt(tenant=tenant, subject_ref=rec.subject_ref,
                                 redemption_id=rec.id, reward_name=rec.reward_name,
                                 cost=rec.cost, remaining=remaining)
    except Exception as exc:                                            # noqa: BLE001
        c.telemetry.event("loyalty_receipt_failed", tenant=tenant, error=str(exc)[:200])

    if rec.reward_type == "service":
        # THE JOIN EVERYBODY FORGETS. A free wash that is not recorded as a visit means the
        # reminder cycle is never restarted, so the customer is reminded to come in for the
        # service he just received.
        await record_free_visit(c, tenant, rec, actor)


async def record_free_visit(c, tenant: str, rec, actor: str) -> bool:
    """Record the visit a service reward IS, and mark the receipt when it lands.

    FAILING SOFT WAS ONLY HALF A DESIGN (ز-9). This could not raise — the points are spent and the
    customer is holding his reward, so refusing here would take back something already handed over
    — but the failure was written to telemetry and then forgotten by everything. Nothing replayed
    it. So the half-act was permanent: points gone, no visit, and the reminder engine cheerfully
    inviting the man back for the wash he just had.

    THE MARK IS WHAT MAKES THE REPAIR POSSIBLE. Without it, a sweep would have to ask operations
    about every redemption ever made to find the few that are missing; with it, the work list is a
    field on our own rows. And `source=rec.id` keeps the far door idempotent, so replaying one that
    actually landed changes nothing.
    """
    try:
        reward = await c.rewards.get(tenant, rec.reward_id)
        await c.visits.record(tenant=tenant, subject_ref=rec.subject_ref,
                              service_id=reward.service_id, actor=actor, source=rec.id)
    except Exception as exc:                                            # noqa: BLE001
        c.telemetry.event("loyalty_free_visit_failed", tenant=tenant, error=str(exc)[:200])
        return False

    rec.visit_recorded = True
    try:
        await c.redeemer.store.put(REDEMPTIONS, rec.id, rec.to_dict())
    except Exception as exc:                                            # noqa: BLE001
        # THE VISIT IS RECORDED AND THE MARK IS NOT. The repair will replay this one, the far door
        # will refuse it as a duplicate, and the mark will be written then — so the cost of this
        # failure is one wasted call, never a second visit.
        c.telemetry.event("loyalty_visit_mark_failed", tenant=tenant, error=str(exc)[:200])
    return True


# ── the customer's own history ─────────────────────────────────────────────────────────────────
@router.get("/history/{subject_ref}", dependencies=[Depends(rate_limit)])
async def history(request: Request, subject_ref: str, limit: int = 25,
                  principal: Principal = Depends(_READ)) -> dict:
    c = request.app.state.container
    tenant = _tenant(principal)
    return {"entries": await c.ledger.history(tenant, subject_ref, limit=min(limit, 100))}


# ── the rewards catalogue ──────────────────────────────────────────────────────────────────────
class RewardIn(BaseModel):
    # Bounded here AS WELL as validated in core. The model is the door: a rule enforced only in
    # the core is a rule pydantic can drop on the way in, and the route then returns 200 having
    # done nothing (playbook §4.20).
    name: str = Field(min_length=2, max_length=40)
    cost: int = Field(gt=0, le=1_000_000)
    type: str = Field(min_length=4, max_length=16)
    service_id: str = Field(default="", max_length=64)
    discount_halalas: int = Field(default=0, ge=0, le=100_000_000)


@router.get("/rewards", dependencies=[Depends(rate_limit)])
async def list_rewards(request: Request, include_retired: bool = False,
                       principal: Principal = Depends(_READ)) -> dict:
    c = request.app.state.container
    rows = await c.rewards.list(_tenant(principal), active_only=not include_retired)
    return {"rewards": [r.to_dict() for r in rows]}


class AdjustIn(BaseModel):
    subject_ref: str = Field(min_length=8, max_length=128)
    # POSITIVE COMPENSATES, NEGATIVE CORRECTS. Zero is refused rather than accepted as a no-op: a
    # zero here is a slip on the way to a number, and writing an entry that moves nothing turns
    # the ledger into a place where mistakes leave litter.
    delta: int = Field(ge=-100_000, le=100_000)
    # REQUIRED, AND THAT IS THE POINT. An adjustment without a reason is unexplainable the moment
    # anybody asks — including the customer, six months later, whose balance it changed. The note
    # travels with the entry into the history the counter reads out loud.
    note: str = Field(min_length=3, max_length=280)
    # A REPEATED PRESS IS ONE INTENTION. Without it a slow network turns a 50-point apology into
    # a hundred, and neither the owner nor the customer can tell which press was real.
    idempotency_key: str = Field(min_length=4, max_length=128)


@router.post("/adjust", dependencies=[Depends(rate_limit)])
async def adjust(request: Request, body: AdjustIn,
                 principal: Principal = Depends(_MANAGE)) -> dict:
    """Grant or take back points by hand — the apology the product could not make (spec §9.1).

    THE LEDGER HAS ALWAYS KNOWN THIS MOVEMENT. `reason="adjust"` is in REASONS, and `post()`
    reasons about it explicitly — an adjustment does NOT restart the expiry clock, «otherwise a
    shop tidying its books would silently extend every balance it touched». Nothing called it.
    A machine had gone wrong, a customer had been shorted, and the only repair available to the
    owner was to invent a fake visit.

    THE MANAGER, NOT THE OPERATOR. `loyalty.manage`, deliberately: an operator who can mint points
    at the counter is a control the shop cannot audit — and the person who compensates a customer
    is the person who decides what the shop owes.

    AUDITED BEFORE THE WRITE. A balance moved by hand with no record of who moved it is the one
    entry in this ledger nobody can defend.
    """
    # GROWS THE PROGRAMME: minting points by hand is the shop owing more.
    refusal = await _may_grow(request, principal)
    if refusal is not None:
        return refusal
    c = request.app.state.container
    tenant = _tenant(principal)
    actor = getattr(principal, "subject", "") or ""

    if body.delta == 0:
        return {"ok": False, "reason": "لا يمكن أن يكون التعديل صفراً"}

    # THE SAME LANE `redeem`/`earn` ALREADY HOLD — fixed 2026-09-12, a real gap a QA audit found.
    # `Ledger.post` is a read-then-write with no compare-and-set (its own docstring says so
    # plainly); `adjust` used to call it with no lock at all, so a manager correcting a balance at
    # the exact moment that SAME customer's phone was earning or redeeming (a different lane)
    # could interleave with that lane's own locked read+write — whichever read the balance first
    # had its delta silently overwritten by the other's final write, rather than being additive.
    try:
        async with SpendLock(c.cache, tenant, body.subject_ref):
            # NEVER BELOW ZERO, read INSIDE the lock — an unlocked read here would be exactly
            # the same race one layer up: another writer's balance change landing between this
            # check and `post()` below.
            bal = await c.ledger.balance(tenant, body.subject_ref)
            if body.delta < 0 and bal.points + body.delta < 0:
                return {"ok": False,
                        "reason": f"رصيده {bal.points} نقطة — لا يمكن خصم أكثر من ذلك"}

            await request.app.state.auditor.record(
                "loyalty.adjusted", actor=actor, tenant=tenant,
                resource=f"subject:{body.subject_ref}",
                ip=request.client.host if request.client else "",
                metadata={"delta": body.delta, "note": body.note[:120]})

            entry = await c.ledger.post(
                tenant=tenant, subject_ref=body.subject_ref, delta=body.delta, reason="adjust",
                source=body.idempotency_key, actor=actor, note=body.note)
    except SpendBusy as exc:
        return _refuse(str(exc), status.HTTP_409_CONFLICT)

    if entry is None:
        # ALREADY DONE, NOT FAILED. The same key twice is one intention; report the balance as it
        # stands so the screen agrees with the ledger either way.
        return {"ok": True, "balance": (await c.ledger.balance(tenant, body.subject_ref)).points,
                "repeated": True}

    return {"ok": True, "balance": entry.balance_after, "repeated": False}


@router.post("/rewards", dependencies=[Depends(rate_limit)])
async def create_reward(request: Request, body: RewardIn,
                        principal: Principal = Depends(_MANAGE)) -> dict:
    # GROWS THE PROGRAMME: a new reward is a new promise.
    refusal = await _may_grow(request, principal)
    if refusal is not None:
        return refusal
    c = request.app.state.container
    try:
        r = await c.rewards.create(_tenant(principal), name=body.name, cost=body.cost,
                                   type=body.type, service_id=body.service_id,
                                   discount_halalas=body.discount_halalas)
    except LoyaltyError as exc:
        # The reason NAMED, and returned rather than raised — see `_refuse`.
        return _refuse(str(exc))
    return r.to_dict()


class RewardPatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=40)
    cost: int | None = Field(default=None, gt=0, le=1_000_000)
    active: bool | None = None
    discount_halalas: int | None = Field(default=None, ge=0, le=100_000_000)


@router.patch("/rewards/{reward_id}", dependencies=[Depends(rate_limit)])
async def update_reward(request: Request, reward_id: str, body: RewardPatch,
                        principal: Principal = Depends(_MANAGE)) -> dict:
    # EDITS THE PROMISE. Retiring one is also an edit — and a lapsed shop keeps what it has.
    refusal = await _may_grow(request, principal)
    if refusal is not None:
        return refusal
    c = request.app.state.container
    changes = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        r = await c.rewards.update(_tenant(principal), reward_id, **changes)
    except LoyaltyError as exc:
        return _refuse(str(exc))
    return r.to_dict()


# ── the earning tree (spec §9.2) ───────────────────────────────────────────────────────────────
class GeneralIn(BaseModel):
    points: int = Field(ge=0, le=100_000)


class GroupIn(BaseModel):
    group: str = Field(min_length=1, max_length=64)
    points: int = Field(ge=0, le=100_000)
    service_ids: list[str] = Field(default_factory=list, max_length=200)


class ServiceIn(BaseModel):
    points: int = Field(ge=0, le=100_000)


class PackageIn(BaseModel):
    points: int = Field(ge=0, le=100_000)


class ConfigIn(BaseModel):
    mode: str = Field(min_length=4, max_length=16)
    points_per_riyal: int = Field(default=1, ge=0, le=1000)


@router.get("/settings", dependencies=[Depends(rate_limit)])
async def read_settings(request: Request, principal: Principal = Depends(_READ)) -> dict:
    """The whole tree, with every level visible.

    The screen cannot say "this service is customised — tap to follow again" unless the API says
    where each number came from. A resolver that returned only numbers would force the console to
    re-derive the answer, and the two would disagree the first time the resolution order changed.
    """
    c = request.app.state.container
    tree = await c.earn_settings.load(_tenant(principal))
    return {"general": tree.general, "groups": tree.groups,
            "service_group": tree.service_group, "services": tree.services,
            "packages": tree.packages,
            "defaults": tree.defaults, "config": tree.config.to_dict()}


@router.put("/settings/general", dependencies=[Depends(rate_limit)])
async def set_general(request: Request, body: GeneralIn,
                      principal: Principal = Depends(_MANAGE)) -> dict:
    # CHANGES THE EARNING RULE — how fast the shop starts owing.
    refusal = await _may_grow(request, principal)
    if refusal is not None:
        return refusal
    c = request.app.state.container
    tenant = _tenant(principal)
    tree = await c.earn_settings.set_general(tenant, {"points": body.points})
    return {"general": tree.general}


@router.put("/settings/group", dependencies=[Depends(rate_limit)])
async def set_group(request: Request, body: GroupIn,
                    principal: Principal = Depends(_MANAGE)) -> dict:
    # CHANGES THE EARNING RULE for several services at once.
    refusal = await _may_grow(request, principal)
    if refusal is not None:
        return refusal
    c = request.app.state.container
    tree = await c.earn_settings.set_group(_tenant(principal), body.group,
                                           {"points": body.points}, body.service_ids)
    return {"groups": tree.groups, "service_group": tree.service_group}


@router.put("/settings/service/{service_id}", dependencies=[Depends(rate_limit)])
async def set_service(request: Request, service_id: str, body: ServiceIn,
                      principal: Principal = Depends(_MANAGE)) -> dict:
    # CHANGES THE EARNING RULE for one service.
    refusal = await _may_grow(request, principal)
    if refusal is not None:
        return refusal
    c = request.app.state.container
    tree = await c.earn_settings.set_service(_tenant(principal), service_id,
                                             {"points": body.points})
    return {"services": tree.services}


@router.delete("/settings/service/{service_id}", dependencies=[Depends(rate_limit)])
async def follow_again(request: Request, service_id: str,
                       principal: Principal = Depends(_MANAGE)) -> dict:
    """"Tap to follow again" — DELETES the override rather than writing today's general value.

    Writing it would look identical now and diverge later: the service would have stopped
    following, and the NEXT general edit would skip it — a bug appearing a month afterwards with
    nothing connecting it to this button.
    """
    # ALSO AN EARNING-RULE EDIT — removing an override changes what a visit is worth.
    refusal = await _may_grow(request, principal)
    if refusal is not None:
        return refusal
    c = request.app.state.container
    tree = await c.earn_settings.follow_again(_tenant(principal), service_id)
    return {"services": tree.services}


@router.put("/settings/package/{package_id}", dependencies=[Depends(rate_limit)])
async def set_package(request: Request, package_id: str, body: PackageIn,
                      principal: Principal = Depends(_MANAGE)) -> dict:
    """A package's own point value — always explicit, no group and no general rate to follow (see
    core/earning.py's own EarnTree.packages docstring for why this has no "follow again" delete,
    unlike a service). The console prefills `points` with the sum of the components' current
    resolved points when the package is first created; this route is what actually stores whatever
    number ends up in that field, whether the owner kept the suggestion or changed it."""
    refusal = await _may_grow(request, principal)
    if refusal is not None:
        return refusal
    c = request.app.state.container
    tree = await c.earn_settings.set_package(_tenant(principal), package_id, body.points)
    return {"packages": tree.packages}


@router.put("/settings/mode", dependencies=[Depends(rate_limit)])
async def set_mode(request: Request, body: ConfigIn,
                   principal: Principal = Depends(_MANAGE)) -> dict:
    """The earning switch (spec §9.3). Two states, never both.

    Refused with the reason when `invoice` is asked for by an establishment with a service that
    is not yet priced: `operations` computes the invoice amount from the catalogue's own prices
    now (no till required, retired 2026-09-08), so an unpriced service is the one thing that would
    make the mode silently undercount.
    """
    # SWITCHES THE PROGRAMME'S MODE — visits or invoices (§9.3).
    refusal = await _may_grow(request, principal)
    if refusal is not None:
        return refusal
    c = request.app.state.container
    # ASKED LIVE, ONLY WHEN IT MATTERS — a switch back to `services` mode, or one that stays on
    # it, has no business paying for a network call whose answer it will not use.
    services_priced = True
    if body.mode == "invoice":
        services_priced = await c.services_pricing(_tenant(principal))
    try:
        tree = await c.earn_settings.set_config(_tenant(principal), mode=body.mode,
                                                points_per_riyal=body.points_per_riyal,
                                                services_priced=services_priced)
    except LoyaltyError as exc:
        return _refuse(str(exc))
    return {"config": tree.config.to_dict()}


# ── what the owner sees (spec §9.10) ───────────────────────────────────────────────────────────
@router.get("/report", dependencies=[Depends(rate_limit)])
async def report(request: Request, principal: Principal = Depends(_READ)) -> dict:
    from app.core.report import build

    c = request.app.state.container
    return await build(c.datastore, _tenant(principal))


# ── ours (spec §9.1: the obligation is real money, so its repair is not self-service) ──────────
class ReconcileIn(BaseModel):
    tenant: str = Field(min_length=1, max_length=128)
    subject_ref: str = Field(min_length=8, max_length=128)
    # REQUIRED, AND IT HAD NO FIELD AT ALL. §8.3 promises three things about a repair: «باسم من
    # أصلحه، ومعه ما كان قبله، وبسببٍ مكتوب. ومن غير سببٍ لا يُنفَّذ». One of the three was kept.
    #
    # And the omission was exactly backwards. The owner's own `adjust` — which moves one balance
    # in his own shop — has required a `note` from the day it was written, with a comment saying
    # an adjustment without a reason is unexplainable the moment anybody asks. THIS route lets
    # support rewrite the total of any ledger in any establishment, and asked for nothing. The
    # lower-risk action carried the higher bar.
    reason: str = Field(min_length=3, max_length=280)


@router.post("/platform/reconcile", dependencies=[Depends(rate_limit)])
async def platform_reconcile(request: Request, body: ReconcileIn,
                             principal: Principal = Depends(_PLATFORM)) -> dict:
    """Recompute one balance from its ledger and repair it — the answer to "my points vanished".

    THE TENANT COMES OFF THE BODY HERE, and that is the whole reason this route is separate from
    every other one in this file. Support is answering a question about a shop that is not theirs;
    a platform capability is exactly the thing that permits it, and `platform.loyalty` is checked
    by the dependency above rather than assumed from the caller being internal.
    """
    c = request.app.state.container
    ip = request.client.host if request.client else ""
    actor = getattr(principal, "subject", "")

    # WRITE-AHEAD, WITH THE REASON AND THE SUBJECT. `resource="balance"` named a KIND, not a
    # thing: «somebody reconciled a balance» is not a trail anyone can follow back to a customer.
    await request.app.state.auditor.record(
        "loyalty.reconciled", actor=actor, tenant=body.tenant,
        resource=f"balance:{body.subject_ref}", ip=ip,
        metadata={"reason": body.reason})

    out = await c.ledger.reconcile(body.tenant, body.subject_ref)

    # AND WHAT IT WAS BEFORE — the second of the three promises, and the one that makes the first
    # two worth anything. A repair that does not record the number it replaced cannot be argued
    # with: neither the shop nor the customer can say it was wrong, because nothing remembers.
    # Recorded after, deliberately: this is the OUTCOME, and an outcome cannot be written ahead.
    await request.app.state.auditor.record(
        "loyalty.reconcile_result", actor=actor, tenant=body.tenant,
        resource=f"balance:{body.subject_ref}", ip=ip,
        metadata={"was": out.get("was"), "now": out.get("ledger"),
                  "drift": out.get("drift"), "repaired": out.get("repaired")})
    return out
