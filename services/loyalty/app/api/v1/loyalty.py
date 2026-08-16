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
from app.core.models import LoyaltyError, Overdraft
from app.core.notify import to_next_reward

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
    affordable = await c.rewards.affordable(tenant, bal.points)
    all_costs = [r.cost for r in await c.rewards.list(tenant)]
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
    # Set by a manager approving a reward above the threshold (spec §9.5). Empty otherwise, and
    # the core decides whether that is allowed — not this model.
    approved_by: str = Field(default="", max_length=128)
    # WHERE — AND IT IS NO LONGER SENT. This field said the screen knew which branch it stood in.
    # It did not: `redeem()` in the console never passed one, so every redemption in a branched
    # shop was filed under «غير محدَّد» while the till's were filed correctly, and «أيّ فرع يصرف
    # أكثر؟» answered from half the data. Meanwhile loyalty holds no staff list, so whatever a
    # caller DID send was written unchecked.
    #
    # The branch is now resolved from the person's own operator row, exactly as the visit path
    # resolves it (spec 12.2). The field is kept so an old client is not rejected, and ignored.
    branch_id: str = Field(default="", max_length=64)


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
        branch_id = await resolver.scope(tenant, actor)
        if branch_id in DENIED:
            return _refuse("تعذّر التحقق من فرعك الآن. أعد المحاولة بعد قليل.",
                           status.HTTP_503_SERVICE_UNAVAILABLE)

    await request.app.state.auditor.record(
        "loyalty.redeemed", actor=actor, tenant=tenant, resource="redemption",
        ip=request.client.host if request.client else "")

    try:
        rec, is_new = await c.redeemer.redeem(
            tenant, body.subject_ref, body.reward_id, actor=actor,
            idem_key=body.idempotency_key, channel="field",
            approved_by=body.approved_by, branch_id=branch_id,
            manager_threshold=await _threshold(c, tenant))
    except Overdraft as exc:
        return _refuse(str(exc), status.HTTP_409_CONFLICT)
    except LoyaltyError as exc:
        return _refuse(str(exc))

    bal = await c.ledger.balance(tenant, body.subject_ref)
    if is_new:
        # After the commit. And only when new — a retry must not produce a second receipt for one
        # reward, which is exactly what a customer would read as being charged twice.
        await _after_redeem(c, tenant, rec, bal.points, actor)
    return {"redemption": rec.to_dict(), "balance": bal.points, "duplicate": not is_new}


async def _threshold(c, tenant: str) -> int:
    tree = await c.earn_settings.load(tenant)
    return int((tree.general or {}).get("manager_threshold") or 0)


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
        try:
            reward = await c.rewards.get(tenant, rec.reward_id)
            await c.visits.record(tenant=tenant, subject_ref=rec.subject_ref,
                                  service_id=reward.service_id, actor=actor, source=rec.id)
        except Exception as exc:                                        # noqa: BLE001
            c.telemetry.event("loyalty_free_visit_failed", tenant=tenant, error=str(exc)[:200])


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

    # NEVER BELOW ZERO. A negative balance is a number no screen in this product can explain, and
    # a customer who reads «-30 نقطة» concludes the shop is charging him for loyalty.
    bal = await c.ledger.balance(tenant, body.subject_ref)
    if body.delta < 0 and bal.points + body.delta < 0:
        return {"ok": False,
                "reason": f"رصيده {bal.points} نقطة — لا يمكن خصم أكثر من ذلك"}

    await request.app.state.auditor.record(
        "loyalty.adjusted", actor=actor, tenant=tenant, resource=f"subject:{body.subject_ref}",
        ip=request.client.host if request.client else "",
        metadata={"delta": body.delta, "note": body.note[:120]})

    entry = await c.ledger.post(
        tenant=tenant, subject_ref=body.subject_ref, delta=body.delta, reason="adjust",
        source=body.idempotency_key, actor=actor, note=body.note)
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
    # The manager-approval threshold (spec §9.5), kept at the general level because it is one
    # number for the whole establishment rather than a per-service one.
    #
    # `None` MEANS «LEAVE IT», AND 0 MEANS «REMOVE THE REQUIREMENT» — two different intentions that
    # `default=0` collapsed into one value. The write was guarded by `if body.manager_threshold:`,
    # so an owner who set 500 and then decided his operators should redeem freely sent 0, got a
    # 200, and saw the response echo 500 back at him: the screen reported the change as accepted
    # while every reward over 500 kept demanding an approval. Writing it unconditionally instead
    # would have been the opposite bug — every request that only changes `points` would silently
    # clear the threshold. So the field carries the three states it actually has.
    manager_threshold: int | None = Field(default=None, ge=0, le=1_000_000)


class GroupIn(BaseModel):
    group: str = Field(min_length=1, max_length=64)
    points: int = Field(ge=0, le=100_000)
    service_ids: list[str] = Field(default_factory=list, max_length=200)


class ServiceIn(BaseModel):
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
    if body.manager_threshold is not None:
        # Stored on the same row but outside the inheriting FIELDS — it is not a per-service
        # value, and putting it in the tree would make it inheritable, which it is not.
        #
        # `is not None`, never truthiness: 0 is a decision — «no reward needs approval» — and the
        # truthiness test silently discarded exactly that one.
        tree.general["manager_threshold"] = int(body.manager_threshold)
        await c.earn_settings._save(tree)        # noqa: SLF001 — same module's storage shape
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


@router.put("/settings/mode", dependencies=[Depends(rate_limit)])
async def set_mode(request: Request, body: ConfigIn,
                   principal: Principal = Depends(_MANAGE)) -> dict:
    """The earning switch (spec §9.3). Two states, never both.

    Refused with the reason when `invoice` is asked for by an establishment with no till: the
    manual screen records no amounts, so the mode would silently earn nothing.
    """
    # SWITCHES THE PROGRAMME'S MODE — visits or invoices (§9.3).
    refusal = await _may_grow(request, principal)
    if refusal is not None:
        return refusal
    c = request.app.state.container
    try:
        tree = await c.earn_settings.set_config(_tenant(principal), mode=body.mode,
                                                points_per_riyal=body.points_per_riyal)
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
    await request.app.state.auditor.record(
        "loyalty.reconciled", actor=getattr(principal, "subject", ""), tenant=body.tenant,
        resource="balance", ip=request.client.host if request.client else "")
    return await c.ledger.reconcile(body.tenant, body.subject_ref)
