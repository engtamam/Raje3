"""The back office — operators, branches and the service catalogue.

A DIFFERENT PRIVILEGE FROM THE FIELD SCREEN, and separated on purpose. Recording a visit is what
everyone does all day; adding an operator, changing a price or deactivating a service is the
owner's. A shop that hires seasonal help must be able to grant the first without the second.

THE PIN IS ATTRIBUTION, NOT AUTHENTICATION — and the distinction decides the whole design.

A four-digit PIN is guessable by construction: ten thousand possibilities, and a colleague standing
beside you can watch it being typed. It is not, and cannot be, what protects an establishment's
data. That is the establishment's session, which is a real token behind a real login.

What the PIN answers is a narrower and genuinely useful question: WHICH of the three people sharing
this tablet recorded that visit. It is asked at SAVE, not at the start of a shift, because the
screen stays open all day and a login per visit would destroy the five-second rule — and the
predictable result of that is one device signed in as one person recording everybody's work, which
is worse than no attribution because it is attribution that lies.

So it is hashed (never stored readable), it is rate-limited (guessing four digits is otherwise
trivial), a wrong one is audited (a pattern of failures is the signal worth having), and it is
never returned by any read.
"""
from __future__ import annotations

import hashlib
import hmac
import time

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.api.auth import Principal
from app.api.authz import require_capability
from app.api.ratelimit import rate_limit
from app.core.models import Branch, Operator, Service
from app.core import branches as B
from app.core import seats as S
from app.core.stores import BranchStore, OperatorStore, ServiceStore, new_id

# The parent router in __init__ already carries /api/v1 — this prefix is appended to it.
router = APIRouter(prefix="/staff", tags=["staff"])

_MANAGE = require_capability("operations.manage")
_READ = require_capability("operations.read")


def _tenant(p: Principal) -> str:
    if not p.tenant:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "NO_TENANT")
    return p.tenant


def _pin_hash(salt: str, tenant: str, operator_id: str, pin: str) -> str:
    """Salted and bound to the operator.

    Bound to (tenant, operator_id) so the same four digits produce different hashes for different
    people — otherwise a leaked table would show at a glance which operators share a PIN, and
    "1234" would be identifiable across every establishment we host.
    """
    return hmac.new(salt.encode("utf-8"),
                    f"{tenant}|{operator_id}|{pin}".encode("utf-8"),
                    hashlib.sha256).hexdigest()


# ── operators ─────────────────────────────────────────────────────────────────────────────────
class OperatorIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    # Four digits, and no longer. A longer PIN is not meaningfully safer for what this protects,
    # and it IS meaningfully slower to type a hundred times a day — which is the cost that decides
    # whether the product gets used.
    pin: str = Field(min_length=4, max_length=4, pattern=r"^\d{4}$")
    role: str = Field(default="operator", max_length=32)
    branch_id: str = Field(default="", max_length=64)


@router.post("/operators", status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(rate_limit)])
async def create_operator(request: Request, body: OperatorIn,
                          principal: Principal = Depends(_MANAGE)) -> dict:
    tenant = _tenant(principal)
    store = OperatorStore(request.app.state.container.datastore)
    gauges = request.app.state.container.gauges

    # AT THE DOOR, NOT IN A SWEEP. The sixteenth employee on a plan of fifteen is refused here, in
    # the screen where he is being added, with the limit named. A nightly job that finds sixteen
    # and does nothing is a limit that does not exist; one that deactivates somebody fires days
    # later at a person who did not make the mistake (core/seats.py).
    current = len(await store.list(tenant))
    try:
        await S.guard_and_report(gauges, tenant=tenant, key=S.SEATS, current=current)
    except S.SeatLimitReached as exc:
        # RETURNED, NOT RAISED. The platform's error handler strips an HTTPException's detail, so
        # a raised refusal reaches the owner as a bare 403 and the sentence naming his limit —
        # the only part that tells him what to do — is thrown away.
        return JSONResponse(status_code=status.HTTP_402_PAYMENT_REQUIRED,
                            content={"error": "SEAT_LIMIT", "message": str(exc)})

    await request.app.state.auditor.record(
        "operator.created", actor=principal.subject, tenant=tenant, resource="operator",
        ip=request.client.host if request.client else "")

    settings = request.app.state.container_settings
    # HIS BRANCH, IF THE SHOP HAS ONE BY THAT ID. Unlike a visit this is a field on a form we
    # serve, so a bad value here is our bug rather than a till's — but the same rule applies: an
    # employee is not refused over a label, he is recorded without one.
    branch_id = ""
    if body.branch_id.strip():
        branch_id = await B.resolve(BranchStore(request.app.state.container.datastore),
                                    tenant, body.branch_id)
    op = Operator(id=new_id("opr"), tenant=tenant, name=body.name.strip(), role=body.role,
                  branch_id=branch_id, created=int(time.time()))
    op.pin_hash = _pin_hash(settings.PII_SALT, tenant, op.id, body.pin)
    await store.save(op)
    # REPORTED AFTER THE WRITE, and as the whole count rather than a delta. Before the write it
    # would be a lie for as long as the write takes, and a failed write would leave billing
    # believing in an employee who does not exist. Reporting the total means a failed report
    # heals itself on the next change.
    await gauges.report(tenant, S.SEATS, current + 1)
    # public() omits pin_hash — a hash that is never returned cannot be attacked offline by
    # somebody who reached a read endpoint.
    return op.public()


@router.get("/operators", dependencies=[Depends(rate_limit)])
async def list_operators(request: Request, principal: Principal = Depends(_READ)) -> dict:
    rows = await OperatorStore(request.app.state.container.datastore).list(_tenant(principal))
    return {"operators": [o.public() for o in rows]}


class PinVerifyIn(BaseModel):
    operator_id: str = Field(min_length=1, max_length=64)
    pin: str = Field(min_length=4, max_length=4, pattern=r"^\d{4}$")


@router.post("/operators/verify-pin", dependencies=[Depends(rate_limit)])
async def verify_pin(request: Request, body: PinVerifyIn,
                     principal: Principal = Depends(_READ)) -> dict:
    """Confirm which operator is saving. Called by the field screen at the moment of saving.

    Rate-limited like every route here, and that is what makes a four-digit secret defensible at
    all: ten thousand possibilities fall in minutes to an unthrottled endpoint.
    """
    tenant = _tenant(principal)
    settings = request.app.state.container_settings
    op = await OperatorStore(request.app.state.container.datastore).get(tenant, body.operator_id)

    expected = op.pin_hash if op else ""
    candidate = _pin_hash(settings.PII_SALT, tenant, body.operator_id, body.pin)
    # compare_digest on both paths, and an unknown operator takes the same path as a wrong PIN:
    # one answer for "no such operator", "wrong PIN" and "deactivated" (CWE-203/208). Anything
    # else lets a caller enumerate who works here.
    ok = bool(op) and op.active and hmac.compare_digest(expected, candidate)

    if not ok:
        # Audited. One failure is a fat finger; a pattern of them is the signal worth having, and
        # it cannot be seen if failures are not recorded.
        await request.app.state.auditor.record(
            "operator.pin_rejected", actor=principal.subject, tenant=tenant,
            resource=f"operator:{body.operator_id}",
            ip=request.client.host if request.client else "")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "PIN_REJECTED")

    return {"operator": op.public()}


# ── branches ──────────────────────────────────────────────────────────────────────────────────
class BranchIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)


class BranchPatch(BaseModel):
    """Rename, close, reopen. NO DELETE — see `update_branch`."""

    name: str | None = Field(default=None, min_length=1, max_length=128)
    active: bool | None = None


def _live(rows: list[Branch]) -> int:
    return len([b for b in rows if b.active])


@router.post("/branches", status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(rate_limit)])
async def create_branch(request: Request, body: BranchIn,
                        principal: Principal = Depends(_MANAGE)) -> dict:
    tenant = _tenant(principal)
    store = BranchStore(request.app.state.container.datastore)
    gauges = request.app.state.container.gauges

    # HIS MAIN BRANCH IS ONE OF THEM, and this is where the base plan's single branch is spent.
    # An establishment that has never opened «فريقي» has no row yet, so it is created before the
    # count — otherwise his first added branch would be counted as one while he owns two.
    await B.ensure_main(store, tenant=tenant)
    # LIVE ONES ONLY. A branch he closed is history on old visits, not capacity he keeps paying
    # for — counting it would make «فرع إضافي» a purchase that buys back a place he shut down.
    current = _live(await store.list(tenant))
    try:
        await S.guard_and_report(gauges, tenant=tenant, key=S.BRANCHES, current=current)
    except S.SeatLimitReached as exc:
        return JSONResponse(status_code=status.HTTP_402_PAYMENT_REQUIRED,
                            content={"error": "BRANCH_LIMIT", "message": str(exc)})

    await request.app.state.auditor.record(
        "branch.created", actor=principal.subject, tenant=tenant, resource="branch",
        ip=request.client.host if request.client else "")
    b = Branch(id=new_id("brn"), tenant=tenant, name=body.name.strip(), created=int(time.time()))
    await store.save(b)
    await gauges.report(tenant, S.BRANCHES, current + 1)
    return b.public()


@router.patch("/branches/{branch_id}", dependencies=[Depends(rate_limit)])
async def update_branch(request: Request, branch_id: str, body: BranchPatch,
                        principal: Principal = Depends(_MANAGE)) -> dict:
    """Rename a branch, or close one — and NEVER delete one.

    DEACTIVATE RATHER THAN DELETE, the same rule the service catalogue follows above and for a
    harder reason: visits, points movements and schedules all carry a `branch_id` as a plain
    string, so deleting the row would leave a year of records pointing at a place with no name —
    and the branch table would report those visits under an id nobody recognises.

    THE MAIN BRANCH CANNOT BE CLOSED. It is what an unrecognised branch falls back to and the one
    place a shop with no others has; closing it would leave the establishment with nowhere to
    record a visit. Renaming it is his — «الفرع الرئيسي» is our word, not his shop's.

    REOPENING IS GUARDED LIKE AN ADDITION, because it is one: it puts a place back into service
    and a plan that allows one branch must not be passed by closing and reopening.
    """
    tenant = _tenant(principal)
    store = BranchStore(request.app.state.container.datastore)
    gauges = request.app.state.container.gauges

    b = await store.get(tenant, branch_id)
    if b is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND")

    if body.active is False and B.is_main(branch_id):
        # RETURNED, NEVER RAISED — the platform's handler strips a raised detail, and the sentence
        # naming the rule is the only useful part of this answer.
        return JSONResponse(status_code=status.HTTP_409_CONFLICT,
                            content={"error": "MAIN_BRANCH",
                                     "message": "الفرع الرئيسي لا يُغلق. غيّر اسمه إن أردت."})

    rows = await store.list(tenant)
    if body.active is True and not b.active:
        try:
            await S.guard_and_report(gauges, tenant=tenant, key=S.BRANCHES, current=_live(rows))
        except S.SeatLimitReached as exc:
            return JSONResponse(status_code=status.HTTP_402_PAYMENT_REQUIRED,
                                content={"error": "BRANCH_LIMIT", "message": str(exc)})

    await request.app.state.auditor.record(
        "branch.updated", actor=principal.subject, tenant=tenant,
        resource=f"branch:{branch_id}", ip=request.client.host if request.client else "")

    if body.name is not None:
        b.name = body.name.strip()
    if body.active is not None:
        b.active = body.active
    await store.save(b)
    # THE WHOLE COUNT, RECOMPUTED — a gauge is reported, never incremented (core/seats.py). The
    # saved row is the one in `rows` by identity only if the store returned the same object, so
    # the live count is taken from the list with this row's new state substituted in.
    await gauges.report(tenant, S.BRANCHES,
                        _live([b if r.id == b.id else r for r in rows]))
    return b.public()


@router.get("/branches", dependencies=[Depends(rate_limit)])
async def list_branches(request: Request, principal: Principal = Depends(_READ)) -> dict:
    """His places — and the main one is created here if it is somehow missing.

    A WRITE ON A READ, AND IT EARNS ITS PLACE. Signup creates the main branch (core/signup.py),
    but every establishment that existed before that step did not get one, and there is no
    migration to run — the rule is that a repair belongs in the code that needs the row, not in a
    script somebody has to remember. `ensure_main` is keyed on a fixed id, so this is one write the
    first time a shop opens the screen and none ever after.
    """
    store = BranchStore(request.app.state.container.datastore)
    tenant = _tenant(principal)
    await B.ensure_main(store, tenant=tenant)
    rows = await store.list(tenant)
    return {"branches": [b.public() for b in rows]}


# ── the service catalogue ─────────────────────────────────────────────────────────────────────
class ServiceIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    # 0 means "no natural cycle" — a one-off repair generates no reminder. Explicitly a valid
    # value rather than a missing one, because a default of 30 would schedule a reminder for a
    # puncture repair and teach a customer that our messages are noise.
    cycle_days: int = Field(default=0, ge=0, le=3650)
    # Minor units. No float ever touches an amount.
    price_minor: int = Field(default=0, ge=0)
    sort: int = Field(default=0, ge=0, le=9999)


@router.get("/services", dependencies=[Depends(rate_limit)])
async def list_services(request: Request, include_retired: bool = False,
                        principal: Principal = Depends(_MANAGE)) -> dict:
    """The OWNER's catalogue, which is not the field grid.

    /field/catalogue answers what an operator may record a visit against, and it is right that a
    retired service is absent from it. But the same list was the only one there was, so a service
    stopped from the management screen vanished from the management screen — and «تفعيل» had
    nothing left to act on. The same shape of bug as the rewards table, found the same way: by
    stopping something and looking for it.

    Gated on `operations.manage`, not read: this is the list you edit, and an operator has no
    business seeing what the shop has retired.
    """
    rows = await ServiceStore(request.app.state.container.datastore).list(
        _tenant(principal), active_only=not include_retired)
    return {"services": [s.public() for s in rows]}


@router.post("/services", status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(rate_limit)])
async def create_service(request: Request, body: ServiceIn,
                         principal: Principal = Depends(_MANAGE)) -> dict:
    tenant = _tenant(principal)
    await request.app.state.auditor.record(
        "service.created", actor=principal.subject, tenant=tenant, resource="service",
        ip=request.client.host if request.client else "")
    s = Service(id=new_id("srv"), tenant=tenant, name=body.name.strip(),
                cycle_days=body.cycle_days, price_minor=body.price_minor, sort=body.sort,
                created=int(time.time()))
    await ServiceStore(request.app.state.container.datastore).save(s)
    return s.public()


class ServicePatch(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    cycle_days: int | None = Field(default=None, ge=0, le=3650)
    price_minor: int | None = Field(default=None, ge=0)
    active: bool | None = None
    sort: int | None = Field(default=None, ge=0, le=9999)


@router.patch("/services/{service_id}", dependencies=[Depends(rate_limit)])
async def update_service(request: Request, service_id: str, body: ServicePatch,
                         principal: Principal = Depends(_MANAGE)) -> dict:
    """Edit a catalogue entry.

    DEACTIVATE rather than delete — `active: false`. Deleting a service would orphan every visit
    that references it, and a shop that stops offering something still needs last year's records
    to make sense.
    """
    tenant = _tenant(principal)
    store = ServiceStore(request.app.state.container.datastore)
    s = await store.get(tenant, service_id)
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND")

    await request.app.state.auditor.record(
        "service.updated", actor=principal.subject, tenant=tenant,
        resource=f"service:{service_id}", ip=request.client.host if request.client else "")

    for fld in ("name", "cycle_days", "price_minor", "active", "sort"):
        val = getattr(body, fld)
        if val is not None:
            setattr(s, fld, val.strip() if isinstance(val, str) else val)
    await store.save(s)
    return s.public()
