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

from typing import Any

from starlette.concurrency import run_in_threadpool

from app.api.auth import Principal
from app.api.authz import require_any_capability, require_capability
from app.api.ratelimit import rate_limit
from app.api.scope import branch_scope
from app.api import scope as SCOPE
from app.core.models import Branch, Operator, Package, Service
from app.core import branches as B
from app.core import operator_ticket as OT
from app.core import scheduling as SCHED
from app.core import seats as S
from app.core import shop_mode as SM
from app.core import vehicles as V
from app.core.signup import SignupRefused
from app.core.stores import BranchStore, OperatorStore, PackageStore, ServiceStore, new_id
from app.api.subscribed import no_subscription_needed, subscribed_write

# The parent router in __init__ already carries /api/v1 — this prefix is appended to it.
router = APIRouter(prefix="/staff", tags=["staff"])

_MANAGE = require_capability("operations.manage")
_READ = require_capability("operations.read")
# A NARROWER DOOR, ONLY FOR THE CATALOGUE ("سوي للخدمات وحدة تهتم بالخدمات من
# تعديل وانشاء وغيرها") — `operations.manage` also creates staff and branches and renames the
# shop, which is why it stayed owner/manager-only. A role that should touch the SERVICE catalogue
# and nothing else now can, without inheriting the rest of what `operations.manage` grants. A
# SINGLE capability, not an OR of two — `ci/check_capability_truth.py` reads exactly one name per
# route, so owner/manager hold `operations.manage_services` explicitly too (roles.json), same
# shape as `bookings.manage` sitting beside `bookings.write`.
_MANAGE_SERVICES = require_capability("operations.manage_services")
# A plain field operator ("الموظف الميداني") holds `bookings.read`/
# `bookings.write` but not `operations.read` — so /staff/branches (this route's OWN body already
# narrows by branch_scope, exactly like every other scoped read) answered him 403, and the
# console's Bookings screen — which genuinely needs a branch_id, the server refuses `list_bookings`
# without one — could not learn even his own single branch. It read to him as «لا فروع بعد» (no
# branches EXIST), which was false: he simply could not list them.
#
# `require_any_capability`, not a role change: this narrowly reopens ONE already-self-narrowing
# read to whoever needs a branch to work with bookings, without touching `_READ`'s other routes
# (mode, vehicles — neither of which a field operator needs). Declared TWICE in user_actions.py
# under two ids/capabilities so BOTH audiences see it in their own catalogue; the route accepts
# either, which is why this binds `require_any_capability` and is deliberately outside
# ci/check_capability_truth.py's single-capability check (see that gate's own docstring — it only
# tracks bare `require_capability`).
_READ_BRANCHES = require_any_capability("operations.read", "bookings.read", "bookings.write")
# THE SAME BUG, ONE ROUTE OVER: the Bookings screen's day view needs the
# BRANCH'S TEAM to attribute a booking and to draw the week-view staff picker — it calls
# `/staff/operators` unconditionally on mount, same as it does `/staff/branches`. This comment
# above claimed "none of which a field operator needs" the day it was written; it was wrong about
# this one route, and a field operator saw «تعذّرت قراءة فريق العمل» for the same 403 reason his
# branch list used to fail for. `list_operators` already narrows by `branch_scope`/`SCOPE.visible`
# on its own — the gate was the only thing standing between a field operator and his own team.
_READ_OPERATORS_FOR_BOOKINGS = require_any_capability("operations.read", "bookings.read", "bookings.write")
# STALE AS OF THE SAME DAY, same conversation, later: the seeded "operator"
# role above no longer HOLDS `bookings.read`/`bookings.write` at all — two operators sharing one
# schedule could edit or cancel each other's booking, and the fix was to take booking away from
# the role entirely (roles.seed.json / deploy/seed/roles.json), not to keep narrowing who can read
# around it. `_READ_BRANCHES` and `_READ_OPERATORS_FOR_BOOKINGS` stay — they are still the correct
# door for any principal who legitimately holds `bookings.*` without `operations.read` (a
# supervisor already carries both; a future or shop-defined role might not) — but neither one
# grants a plain field operator anything any more, because he does not reach this gate at all.


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
    # REQUIRED, NOT DESCRIPTIVE — every operator now names a real branch at
    # the moment he is added, the same way `till.py`'s own door already requires one on a sale.
    # No silent «كل الفروع» default: an owner with one branch still picks «الفرع الرئيسي»
    # explicitly, so the choice is a fact he made rather than one we guessed for him.
    branch_id: str = Field(min_length=1, max_length=64)


@router.post("/operators", status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(subscribed_write), Depends(rate_limit)])
async def create_operator(request: Request, body: OperatorIn,
                          principal: Principal = Depends(_MANAGE)) -> dict:
    tenant = _tenant(principal)
    store = OperatorStore(request.app.state.container.datastore)
    gauges = request.app.state.container.gauges

    # THE SHARED-TABLET EMPLOYEE IS SWITCHED OFF ON THIS DEPLOYMENT (config `PIN_OPERATORS_ENABLED`).
    #
    # The whole path is built and kept — the form, this route, `verify-pin`, the five-minute proof —
    # and it is simply not what the product is sold on today: every employee gets an account on his
    # own phone. Hiding the control in the console alone would leave the capability live to anybody
    # who kept a tab open or replayed a request, and a switch that only changes a screen is the
    # exact defect this codebase keeps finding. So the door answers too.
    if not getattr(request.app.state.container_settings, "PIN_OPERATORS_ENABLED", False):
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={
            "error": "PIN_OPERATORS_OFF",
            "message": "إضافة موظف برمز على الجهاز غير مفعّلة. أضِفه بحسابٍ يدخل به من جوّاله."})

    # AT THE DOOR, NOT IN A SWEEP. The sixteenth employee on a plan of fifteen is refused here, in
    # the screen where he is being added, with the limit named. A nightly job that finds sixteen
    # and does nothing is a limit that does not exist; one that deactivates somebody fires days
    # later at a person who did not make the mistake (core/seats.py).
    # LIVE ONES ONLY, and the same rule the update route reports by. Counting people who were
    # stopped months ago would make a shop buy seats for employees who no longer work there — and
    # the two counts disagreeing is worse still: whichever the owner is looking at is the wrong one.
    # THE COUNT AND THE INSERT ARE ONE ACT OR THE CAP IS DECORATION. Everything from the count to
    # the write happens inside the establishment's lane; two managers hiring in the same
    # millisecond are serialised rather than both told there is room (core/seats.py).
    # CHECKED BEFORE THE SEAT CLAIM AND THE AUDIT RECORD, not inside them — both are write-ahead
    # acts (a seat consumed, «operator.created» logged) that must never fire for an operator who
    # is then refused for lacking a real branch.
    try:
        branch_id = await B.resolve_required(
            BranchStore(request.app.state.container.datastore), tenant, body.branch_id)
    except B.BranchRequired:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={
            "error": "BRANCH_REQUIRED", "message": "اختر فرعاً حقيقياً لهذا الموظف."})

    try:
        async with S.claiming(request.app.state.container.datastore,
                              tenant=tenant, key=S.SEATS, now=time.time()):
            current = len([o for o in await store.list(tenant) if o.active])
            await S.guard_and_report(gauges, tenant=tenant, key=S.SEATS, current=current)

            await request.app.state.auditor.record(
                "operator.created", actor=principal.subject, tenant=tenant, resource="operator",
                ip=request.client.host if request.client else "")

            settings = request.app.state.container_settings
            op = Operator(id=new_id("opr"), tenant=tenant, name=body.name.strip(), role=body.role,
                          branch_id=branch_id, created=int(time.time()))
            op.pin_hash = _pin_hash(settings.PII_SALT, tenant, op.id, body.pin)
            await store.save(op)
            # REPORTED AFTER THE WRITE, and as the whole count rather than a delta. Before the
            # write it would be a lie for as long as the write takes, and a failed write would
            # leave billing believing in an employee who does not exist. Reporting the total means
            # a failed report heals itself on the next change.
            await gauges.report(tenant, S.SEATS, current + 1)
    except S.SeatClaimBusy as exc:
        return JSONResponse(status_code=status.HTTP_409_CONFLICT,
                            content={"error": "SEAT_BUSY", "message": str(exc)})
    except S.SeatLimitReached as exc:
        # RETURNED, NOT RAISED. The platform's error handler strips an HTTPException's detail, so
        # a raised refusal reaches the owner as a bare 403 and the sentence naming his limit —
        # the only part that tells him what to do — is thrown away.
        return JSONResponse(status_code=status.HTTP_402_PAYMENT_REQUIRED,
                            content={"error": "SEAT_LIMIT", "message": str(exc)})
    # public() omits pin_hash — a hash that is never returned cannot be attacked offline by
    # somebody who reached a read endpoint.
    return op.public()


class MemberIn(BaseModel):
    """An employee who gets his own login — not a PIN on a shared tablet."""

    name: str = Field(min_length=1, max_length=128)
    phone: str = Field(min_length=6, max_length=32)
    # LONG ENOUGH TO BE REAL. This account can read a shop's customer list; identity refuses a
    # short one anyway, and refusing here means he is told before the round trip.
    password: str = Field(min_length=8, max_length=256)
    role: str = Field(min_length=1, max_length=32)
    # REQUIRED — see OperatorIn's own note.
    branch_id: str = Field(min_length=1, max_length=64)


@router.post("/members", status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(subscribed_write), Depends(rate_limit)])
async def hire_member(request: Request, body: MemberIn,
                      principal: Principal = Depends(_MANAGE)) -> dict:
    """Hire somebody: an account he signs in with, a role, and the branch he works at.

    TWO THINGS ARE CREATED AND THEY ARE ONE ACT. The membership lives at identity — that is what a
    token is minted from — and the operator row lives here, which is what the seat gauge counts,
    what a visit is attributed to, and where his branch is written. Creating either alone gives a
    shop half an employee: a login nobody can attribute work to, or a name on a list who cannot
    open anything.

    THE ORDER IS THE MEMBERSHIP FIRST, and it is the recoverable order. If the account is created
    and our row is not, he can sign in and sees a shop that does not know him — visible, and
    repairable by hiring him again (the membership add is idempotent). The reverse leaves a seat
    consumed by somebody who cannot log in at all, and nothing on any screen says why.

    THE SEAT IS CHECKED BEFORE EITHER, because an establishment at its limit must be refused
    before an account exists at identity that we would then have to unwind.
    """
    tenant = _tenant(principal)
    store = OperatorStore(request.app.state.container.datastore)
    gauges = request.app.state.container.gauges

    # CHECKED BEFORE ANY OF IT — see create_operator's own note on why this cannot live inside the
    # seat/audit lane.
    try:
        branch_id = await B.resolve_required(
            BranchStore(request.app.state.container.datastore), tenant, body.branch_id)
    except B.BranchRequired:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={
            "error": "BRANCH_REQUIRED", "message": "اختر فرعاً حقيقياً لهذا الموظف."})

    # ONE LANE, AND IT COVERS THE MEMBERSHIP TOO. The seat is spent by the pair (identity account,
    # operator row), so the lane must not be released between them: two hires racing would both
    # count four, both create an account, and the second would find the first's row only after
    # paying for it (core/seats.py).
    try:
        async with S.claiming(request.app.state.container.datastore,
                              tenant=tenant, key=S.SEATS, now=time.time()):
            current = len([o for o in await store.list(tenant) if o.active])
            await S.guard_and_report(gauges, tenant=tenant, key=S.SEATS, current=current)

            # CRITICAL AND WRITE-AHEAD: this is a person being given access to an establishment's
            # data, which is the one family of acts that must be refused rather than performed
            # unrecorded.
            await request.app.state.auditor.record(
                "member.hired", actor=principal.subject, tenant=tenant, resource="member",
                ip=request.client.host if request.client else "")

            try:
                out = await request.app.state.container.signup.hire(
                    tenant, phone=body.phone, password=body.password, role=body.role)
            except SignupRefused as exc:
                # RETURNED, NEVER RAISED — the platform strips a raised detail, and «هذا الرقم
                # مسجّل في منشأة أخرى» is the only part of this answer the owner can act on.
                return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST,
                                    content={"error": "NOT_HIRED", "message": str(exc)})

            return await _finish_hire(request, body=body, tenant=tenant, store=store,
                                      gauges=gauges, out=out, branch_id=branch_id,
                                      current=current)
    except S.SeatClaimBusy as exc:
        return JSONResponse(status_code=status.HTTP_409_CONFLICT,
                            content={"error": "SEAT_BUSY", "message": str(exc)})
    except S.SeatLimitReached as exc:
        return JSONResponse(status_code=status.HTTP_402_PAYMENT_REQUIRED,
                            content={"error": "SEAT_LIMIT", "message": str(exc)})


async def _finish_hire(request: Request, *, body: MemberIn, tenant: str, store: Any,
                       gauges: Any, out: dict, branch_id: str, current: int) -> dict:
    """The half of `hire_member` that runs after identity answered. Split out for depth only.

    IT RUNS INSIDE THE SEAT LANE and must stay there — the caller holds the claim across this
    call. Nothing here may be reused from outside it.
    """
    person_id = out.get("person_id", "")

    # ONE PERSON IS ONE ROW, AND THE PRESS IS NOT THE ACT (ز-10). The id used to be `new_id("opr")`
    # — new on every call — while the membership behind it is keyed by phone at identity and is
    # idempotent. So a double press, or a retry on a slow reply, created a SECOND operator row for
    # the same human: two seats consumed by one employee on a plan the owner is paying per seat
    # for, a name listed twice on his team screen, and `verify-pin` picking whichever row it found
    # first — so the same person's work is attributed to one row today and the other tomorrow.
    #
    # `person_id` is the key identity already deduped for us. Reusing it means the second press
    # overwrites the first row rather than adding one, and the count stays what the owner sees.
    existing = None
    if person_id:
        for row in await store.list(tenant):
            if row.person_id == person_id:
                existing = row
                break

    op = Operator(id=existing.id if existing else new_id("opr"),
                  tenant=tenant, name=body.name.strip(), role=body.role,
                  branch_id=branch_id,
                  created=existing.created if existing else int(time.time()))
    # HIS OWN LOGIN IS HIS IDENTITY, so there is no PIN on this row. `verify-pin` compares against
    # an empty hash and refuses — which is correct: a man with an account does not also need four
    # digits, and giving him one would be a second credential to leak.
    op.person_id = person_id
    await store.save(op)
    # THE COUNT DOES NOT MOVE WHEN NOBODY WAS ADDED. Reporting `current + 1` after re-saving a row
    # that already existed would tell billing the shop grew by an employee it did not hire.
    await gauges.report(tenant, S.SEATS, current if existing else current + 1)
    return op.public()


class OperatorPatch(BaseModel):
    """What an owner changes about somebody after adding them. NOT the PIN — see below."""

    name: str | None = Field(default=None, min_length=1, max_length=128)
    role: str | None = Field(default=None, max_length=32)
    branch_id: str | None = Field(default=None, max_length=64)
    # WHAT HE MAY SEE, WHICH IS NOT WHERE HE WORKS. `branch_id` above is his station and decides
    # where his visits are counted; these two decide whose numbers, messages and customers he may
    # read. Separate fields because an owner grants them separately — a supervisor keeps working
    # out of one branch while watching four.
    #
    # `None` MEANS «LEAVE IT», as everywhere else in this model: an owner renaming somebody has not
    # asked to change what he can see.
    visible_branch_ids: list[str] | None = Field(default=None, max_length=64)
    visible_all: bool | None = None
    active: bool | None = None


@router.patch("/operators/{operator_id}", dependencies=[Depends(subscribed_write), Depends(rate_limit)])
async def update_operator(request: Request, operator_id: str, body: OperatorPatch,
                          principal: Principal = Depends(_MANAGE)) -> dict:
    """Move somebody to a branch, rename him, or stop him.

    THE BRANCH IS THE POINT OF THIS ROUTE. `branch_id` was settable at creation and changeable
    nowhere, so an owner who hired somebody before opening his second branch could never say where
    that person now works — and the visit path reads exactly this field to decide where the work
    happened (core/operations.py). A field that decides something and cannot be corrected is worse
    than one that decides nothing.

    DEACTIVATE, NEVER DELETE: `verify-pin` refuses an inactive operator, and old visits still name
    him. An employee who left is history, not a gap.

    AND THE PIN IS NOT HERE. Changing somebody's four digits from the same form that renames him
    invites it to be done casually and read aloud; it is a separate act, and this route not having
    it is the design rather than an omission.
    """
    tenant = _tenant(principal)
    store = OperatorStore(request.app.state.container.datastore)
    op = await store.get(tenant, operator_id)
    if op is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND")

    branch_id = op.branch_id
    if body.branch_id is not None:
        # `None` STILL MEANS «LEAVE IT» — an owner renaming somebody has not asked to move him.
        # An EXPLICIT VALUE MUST NOW BE A REAL BRANCH (2026-08-22): «كل الفروع» is no longer a
        # state this route can put somebody back into, matching create's own rule. An id we do
        # not recognise is refused rather than silently resolved to «unassigned».
        try:
            branch_id = await B.resolve_required(
                BranchStore(request.app.state.container.datastore), tenant, body.branch_id)
        except B.BranchRequired:
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={
                "error": "BRANCH_REQUIRED", "message": "اختر فرعاً حقيقياً لهذا الموظف."})

    # EVERY BRANCH HE IS GRANTED IS CHECKED, one at a time, against his own shop's list. An id we
    # do not recognise is DROPPED rather than stored: a scope carrying a branch that does not exist
    # is a filter that matches nothing, and a screen that goes empty for a reason nobody can see.
    if body.visible_branch_ids is not None:
        branches = BranchStore(request.app.state.container.datastore)
        granted = []
        for wanted in body.visible_branch_ids:
            resolved = await B.resolve(branches, tenant, str(wanted))
            if resolved and resolved not in granted:
                granted.append(resolved)
        op.visible_branch_ids = granted
    if body.visible_all is not None:
        op.visible_all = bool(body.visible_all)

    await request.app.state.auditor.record(
        "operator.updated", actor=principal.subject, tenant=tenant,
        resource=f"operator:{operator_id}", ip=request.client.host if request.client else "")

    # ── STOPPING HIM MUST STOP HIM ────────────────────────────────────────────────────────────
    #
    # This row is not his access. `hire` created two things — the membership at identity, which is
    # what a token is minted from, and this row — and until now `active=False` wrote only the row.
    # He signed in the same evening with the same password. Worse, an inactive row narrows nobody,
    # and a person nothing narrows reads the WHOLE establishment: being dismissed promoted him
    # from his own branch to every branch.
    #
    # THE MEMBERSHIP GOES FIRST AND A FAILURE REFUSES. Writing "stopped" on a screen while the
    # login still works is precisely the lie being fixed; a row still marked active after a failed
    # revoke is at least true.
    stopping = body.active is False and op.active
    if stopping and op.person_id:
        try:
            await request.app.state.container.signup.revoke(tenant, op.person_id)
        except SignupRefused as exc:
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST,
                                content={"error": "NOT_STOPPED", "message": str(exc)})

    # AND HE IS NOT BROUGHT BACK BY A TOGGLE. His membership is gone, and only a password nobody
    # here has can mint another; flipping this flag would return a name to «فريقي» that consumes a
    # seat and cannot open the app — the half-employee `hire` refuses to create.
    if body.active is True and not op.active and not op.person_id:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "REHIRE_REQUIRED",
                     "message": "تم إلغاء دخوله عند إيقافه. أضِفه من جديد ليعمل حسابه."})

    op.name = body.name.strip() if body.name is not None else op.name
    op.role = body.role if body.role is not None else op.role
    op.branch_id = branch_id
    op.active = body.active if body.active is not None else op.active
    # HIS ROW STAYS, HIS LOGIN DOES NOT. Old visits still name him — an employee who left is
    # history, not a gap — but the link to a membership that no longer exists is cleared, so
    # nothing later mistakes it for a live account.
    if stopping:
        op.person_id = ""
    await store.save(op)
    # SEATS ARE REPORTED AGAIN, because stopping somebody frees his seat — a gauge is the CURRENT
    # value, and an owner who deactivated two people must not be refused his next hire.
    await request.app.state.container.gauges.report(
        tenant, S.SEATS, len([o for o in await store.list(tenant) if o.active]))
    return op.public()


_WEEKDAY_NAMES_AR = ("الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد")


class OperatorHoursIn(BaseModel):
    # "0"-"6" as strings, Monday=0..Sunday=6 — `date.weekday()`'s own numbering, the SAME one
    # bookings-service's tenant-wide working-hours store already uses (models.py:17-18's own
    # comment on WORKING_HOURS), so the two never need translating into each other.
    weekly: dict[str, dict[str, Any]] = Field(default_factory=dict)


@router.put("/operators/{operator_id}/working-hours",
           dependencies=[Depends(subscribed_write), Depends(rate_limit)])
async def set_operator_working_hours(request: Request, operator_id: str, body: OperatorHoursIn,
                                     principal: Principal = Depends(_MANAGE)) -> dict:
    """An EXPLICIT override for one operator — a DEDICATED route rather than a nullable field on
    `OperatorPatch`, because `working_hours`'s own valid domain genuinely needs `None` to mean
    "inherits the shop's hours" (models.py's own docstring), which collides with `None` already
    meaning "leave this field alone" on every other patchable field. Two unambiguous routes (this
    one to SET, `DELETE` below to CLEAR) instead of one route with an ambiguous meaning for `null`.

    THE WHOLE WEEK, ALWAYS — same reasoning as bookings' own `set_working_hours`: a partial save
    is ambiguous (day 3 sent, day 5 not — keep it, or default it?), so the whole document is
    validated and written as one, never merged with what was there.

    NEVER WIDER THAN THE SHOP'S OWN HOURS — refused at write time when `bookings` can be asked
    (fail-OPEN when it cannot: an unreachable peer must not block every staff-hours edit on a
    check that simply cannot run right now — `bookings` still intersects defensively at read
    time regardless, so this is one of two independent guards, never the only one).
    """
    tenant = _tenant(principal)
    store = OperatorStore(request.app.state.container.datastore)
    op = await store.get(tenant, operator_id)
    if op is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND")

    out: dict[str, dict[str, Any]] = {}
    for d in range(7):
        entry = body.weekly.get(str(d)) or {}
        closed = bool(entry.get("closed", False))
        start = int(entry.get("start_minute", 0) or 0)
        end = int(entry.get("end_minute", 0) or 0)
        # RETURNED, NOT RAISED — the platform's own error handler strips an HTTPException's
        # `detail` before it reaches the caller (see `create_operator`'s `SEAT_LIMIT` note above),
        # so a message meant to tell an owner exactly which day is wrong must not be raised.
        if not closed and not (0 <= start < end <= 24 * 60):
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={
                "error": "BAD_HOURS",
                "message": f"وقت دوام يوم {_WEEKDAY_NAMES_AR[d]} غير صحيح"})
        out[str(d)] = {"closed": closed, "start_minute": start, "end_minute": end}

    shop_hours = await request.app.state.container.bookings_desk.working_hours(tenant)
    if shop_hours is not None:
        for d in range(7):
            shop_entry = shop_hours.get(str(d)) or {}
            mine = out[str(d)]
            if mine["closed"] or shop_entry.get("closed"):
                continue
            if (mine["start_minute"] < int(shop_entry.get("start_minute", 0))
                    or mine["end_minute"] > int(shop_entry.get("end_minute", 24 * 60))):
                return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={
                    "error": "EXCEEDS_SHOP_HOURS",
                    "message": f"دوام {_WEEKDAY_NAMES_AR[d]} يتجاوز دوام المحل نفسه — عدّله ليقع ضمنه"})

    op.working_hours = out
    await store.save(op)
    await request.app.state.auditor.record(
        "staff_hours.changed", actor=principal.subject, tenant=tenant,
        resource=f"operator:{operator_id}", ip=request.client.host if request.client else "")
    return op.public()


@router.delete("/operators/{operator_id}/working-hours",
              dependencies=[Depends(subscribed_write), Depends(rate_limit)])
async def clear_operator_working_hours(request: Request, operator_id: str,
                                       principal: Principal = Depends(_MANAGE)) -> dict:
    """Back to inheriting the shop's own hours, in full — idempotent (clearing an
    already-inherited operator is a harmless no-op success, matching this codebase's usual
    idempotent-delete shape), never an error over a double click or a stale button."""
    tenant = _tenant(principal)
    store = OperatorStore(request.app.state.container.datastore)
    op = await store.get(tenant, operator_id)
    if op is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND")
    had = op.working_hours is not None
    op.working_hours = None
    await store.save(op)
    if had:
        await request.app.state.auditor.record(
            "staff_hours.changed", actor=principal.subject, tenant=tenant,
            resource=f"operator:{operator_id}", ip=request.client.host if request.client else "")
    return op.public()


@router.get("/operators", dependencies=[Depends(rate_limit)])
async def list_operators(request: Request, principal: Principal = Depends(_READ_OPERATORS_FOR_BOOKINGS)) -> dict:
    """«فريقي» — and HIS branch's team, not the chain's.

    FOUND BY THE GATE, not by the audit. `Operator.public()` carries the name, the role and the
    branch, and this route handed every branch's staff to anyone who could read — so a manager
    scoped to Jeddah read the whole chain's roster, which is the same widening as the customer
    strip (و-8) wearing different rows.

    Unbranched operators stay visible to everyone, exactly as unbranched visits do: a shop in
    the default central mode gives nobody a branch, and hiding those would empty the screen.
    """
    tenant = _tenant(principal)
    rows = await OperatorStore(request.app.state.container.datastore).list(tenant)
    scope = await branch_scope(request.app.state.container.datastore, principal)
    return {
        "operators": SCOPE.visible([o.public() for o in rows], scope),
        # WHETHER THE SHARED-TABLET EMPLOYEE EXISTS ON THIS DEPLOYMENT (config
        # `PIN_OPERATORS_ENABLED`). Carried on the read the screen already makes, so the form
        # offers one way of adding somebody rather than two, one of which the door refuses.
        #
        # ANSWERED HERE RATHER THAN ASSUMED THERE: a console that hard-coded «off» would have to be
        # rebuilt to turn it on, which is the opposite of a switch.
        "pin_operators_enabled": bool(
            getattr(request.app.state.container_settings, "PIN_OPERATORS_ENABLED", False)),
    }


# THE OPERATOR SCREENS' LANGUAGE (Visit, Bookings, Services, ...) — current phase covers field
# operators only (see Operator.locale's own note). Self-service, not `_MANAGE`: an operator sets
# HIS OWN language, never anyone else's, and needs nothing more than the read he already holds to
# see «فريقي» — the same gate `list_operators` above uses.
_VALID_OPERATOR_LOCALES = {"ar", "en", "ur", "ha", "fil"}


@router.get("/operators/me", dependencies=[Depends(rate_limit)])
async def get_my_operator_row(request: Request,
                              principal: Principal = Depends(_READ_OPERATORS_FOR_BOOKINGS)) -> dict:
    """His own operator row, or 404 — the owner himself has none (he is not an `Operator` row),
    and that is a real, expected answer, not a fault."""
    tenant = _tenant(principal)
    op = await OperatorStore(request.app.state.container.datastore).get_by_person(tenant, principal.subject)
    if op is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_AN_OPERATOR")
    return op.public()


class LocaleIn(BaseModel):
    locale: str = Field(min_length=2, max_length=8)


@router.patch("/operators/me/locale", dependencies=[Depends(subscribed_write), Depends(rate_limit)])
async def set_my_locale(request: Request, body: LocaleIn,
                        principal: Principal = Depends(_READ_OPERATORS_FOR_BOOKINGS)) -> dict:
    if body.locale not in _VALID_OPERATOR_LOCALES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "UNKNOWN_LOCALE")
    tenant = _tenant(principal)
    store = OperatorStore(request.app.state.container.datastore)
    op = await store.get_by_person(tenant, principal.subject)
    if op is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_AN_OPERATOR")
    op.locale = body.locale
    await store.save(op)
    return op.public()


class PinVerifyIn(BaseModel):
    operator_id: str = Field(min_length=1, max_length=64)
    pin: str = Field(min_length=4, max_length=4, pattern=r"^\d{4}$")


@router.post("/operators/verify-pin", dependencies=[Depends(subscribed_write), Depends(rate_limit)])
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

    # AND IT ISSUES THE PROOF, which it never used to. Confirming an operator and then handing back
    # only his name left the visit that followed to name whoever it liked in `operator_id` — and
    # that field decides which BRANCH the work is filed under. See core/operator_ticket.py.
    return {"operator": op.public(),
            "ticket": OT.issue(settings.PII_SALT, tenant, body.operator_id),
            "ticket_ttl": OT.TTL_SECONDS}


# ── how this establishment runs its branches ──────────────────────────────────────────────────
class ModeIn(BaseModel):
    mode: str = Field(min_length=1, max_length=32)


def _modes_available(request: Request) -> set[str]:
    """Which modes this deployment can actually honour.

    PER-BRANCH NEEDS A SENDING IDENTITY PER NUMBER, and until that exists every message resolves
    one credential per establishment — so a shop switched into it would keep sending from the one
    number while its screens promised otherwise. Configuration rather than a constant, so the day
    it ships is a values change and not a release.
    """
    modes = {SM.CENTRAL}
    if getattr(request.app.state.container_settings, "BRANCH_MODE_PER_BRANCH_READY", False):
        modes.add(SM.PER_BRANCH)
    return modes


@router.get("/mode", dependencies=[Depends(rate_limit)])
async def read_mode(request: Request, principal: Principal = Depends(_READ)) -> dict:
    """Central or per-branch — and whether the second is offered at all.

    `available` IS PART OF THE ANSWER, not a fact the screen may assume. A choice rendered as
    selectable while its plumbing is half-built is the defect this product keeps finding: a control
    with nothing behind it. The screen shows both, explains both, and offers what is real.
    """
    c = request.app.state.container
    row = await SM.ModeStore(c.datastore).get(_tenant(principal))
    return {**row, "available": SM.PER_BRANCH in _modes_available(request)}


@router.put("/mode", dependencies=[Depends(subscribed_write), Depends(rate_limit)])
async def set_mode(request: Request, body: ModeIn,
                   principal: Principal = Depends(_MANAGE)) -> dict:
    """Move to per-branch. One way, and never back from this screen — see core/shop_mode.py."""
    tenant = _tenant(principal)
    store = SM.ModeStore(request.app.state.container.datastore)
    try:
        row = await store.set(tenant, body.mode,
                              available=SM.PER_BRANCH in _modes_available(request))
    except SM.ModeError as exc:
        # RETURNED, NEVER RAISED. The three refusals differ for the owner — an unknown value, a
        # mode not yet live, and the one-way rule — and the platform strips a raised detail.
        return JSONResponse(status_code=status.HTTP_409_CONFLICT,
                            content={"error": "MODE_REFUSED", "message": str(exc)})
    # RECORDED AFTER IT HAPPENED, not before it was allowed. An audit line written on the way in
    # says a shop changed its mode on the day it was refused — and the one question this record
    # exists to answer, months later, is when the change was actually made.
    await request.app.state.auditor.record(
        "shop.mode_changed", actor=principal.subject, tenant=tenant, resource="shop_mode",
        ip=request.client.host if request.client else "")
    return row


class VehiclesIn(BaseModel):
    tracks_vehicle: bool


@router.get("/vehicles", dependencies=[Depends(rate_limit)])
async def read_vehicles(request: Request, principal: Principal = Depends(_READ)) -> dict:
    """Does this shop work on cars — the one question the plate page and the meter depend on."""
    tracks = await V.VehicleStore(request.app.state.container.datastore).tracks_vehicle(
        _tenant(principal))
    return {"tracks_vehicle": tracks}


@router.put("/vehicles", dependencies=[Depends(subscribed_write), Depends(rate_limit)])
async def set_vehicles(request: Request, body: VehiclesIn,
                       principal: Principal = Depends(_MANAGE)) -> dict:
    """Turn the plate page on or off for this establishment.

    BOTH DIRECTIONS, UNLIKE THE BRANCH MODE NEXT DOOR. Nothing outside our own database depends on
    the answer — no number is registered, no template is approved against it — so a shop that tried
    it and stopped doing cars simply says so, and the plate page goes away. A one-way switch here
    would be strictness with nothing behind it.

    AND IT IS EDITABLE AT ALL, which the trade it replaced was not: «نوع النشاط» was chosen once at
    sign-up and never again, so the tyre shop that added detailing, and the car wash that stopped,
    both lived with a screen that was wrong about them for ever.
    """
    tenant = _tenant(principal)
    row = await V.VehicleStore(request.app.state.container.datastore).set(
        tenant, body.tracks_vehicle)
    await request.app.state.auditor.record(
        "shop.vehicles_changed", actor=principal.subject, tenant=tenant, resource="shop_vehicles",
        ip=request.client.host if request.client else "")
    return row


class ShopNameIn(BaseModel):
    name: str = Field(min_length=1, max_length=256)


@router.put("/shop-name", dependencies=[Depends(subscribed_write), Depends(rate_limit)])
async def set_shop_name(request: Request, body: ShopNameIn,
                        principal: Principal = Depends(_MANAGE)) -> Any:
    """The shop's name — ONE name, and the owner can change it.

    IT IS CAPTURED ONCE AT SIGNUP AND WAS PERMANENT — a browser autofilling a password into that
    box left an owner reading garbage at the top of his own account screen for good. This route
    is the one place the name is written, and `ci/check_a_shop_has_one_name.py` keeps it the only
    name there is.

    WHY WE PROXY IT. The registry's rename is INTERNAL — service-to-service, on the internal
    token — because a tenant renaming itself directly is a user-tier surface the platform does
    not offer. So the owner's edit arrives here, on his own token and his own capability, and
    this service makes the internal call with the tenant taken from the TOKEN and never from the
    body: a caller who can name the tenant can name somebody else's.
    """
    tenant = _tenant(principal)
    s = request.app.state.container_settings
    base = (getattr(s, "TENANT_SERVICE_URL", "") or "").rstrip("/")
    if not base:
        # NOT CONFIGURED IS SAID OUT LOUD, never rendered as success — the owner would retype
        # his name, read «تم», and find the old one still there on the next screen.
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            content={"error": "NOT_CONFIGURED",
                                     "message": "تعذّر حفظ الاسم — سجلّ المنشآت غير مُهيّأ لدينا."})
    from app.core.signup import Http

    http = Http(timeout=getattr(s, "SIGNUP_TIMEOUT_SECONDS", 10),
                internal_token=s.INTERNAL_SERVICE_TOKEN)
    code, out = await run_in_threadpool(
        http.call, f"{base}/internal/tenants/{tenant}",
        method="PATCH", body={"name": body.name.strip()}, internal=True)
    # ── ONLY A REFUSAL OF THE NAME MAY SAY «جرّب اسماً آخر» ────────────────────────────────────
    #
    # THIS LINE READ `if code >= 400` AND SAID THE SAME SENTENCE TO EVERY FAILURE. The registry
    # answers 400 INVALID_NAME for a name it will not take — and 404 when the tenant is unknown OR
    # when the route itself is absent, which is exactly what an older tenant-service returns
    # (#338: the cluster ran a digest predating this route). It answers 401/403 on a bad internal
    # token, and 5xx when it is simply down.
    #
    # Every one of those was rendered as «تعذّر حفظ الاسم. جرّب اسماً آخر.» — so an owner whose
    # shop name is perfectly fine retypes it, shortens it, drops the «مؤسسة», tries English, and
    # fails every time, because the thing that is broken is not his name and no name he can think
    # of will fix it. That is the worst shape a refusal can have: actionable-looking, and
    # impossible to act on.
    if code == status.HTTP_400_BAD_REQUEST:
        # THE REGISTRY'S REFUSAL IS THE REGISTRY'S. A name it rejects is one it can explain;
        # inventing a sentence of our own here would answer for a rule that is not ours.
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST,
                            content={"error": "RENAME_REFUSED",
                                     "message": "تعذّر حفظ الاسم. جرّب اسماً آخر.",
                                     "detail": out})
    if code >= 400:
        # ANYTHING ELSE IS OURS, NOT HIS. He is told to wait rather than to invent, and the code
        # travels in `detail` so whoever reads the report can tell a stale image from a bad token
        # without asking him to reproduce it.
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            content={"error": "RENAME_UNAVAILABLE",
                                     "message": "تعذّر حفظ الاسم الآن — الخلل عندنا لا في الاسم. "
                                                "حاول بعد قليل.",
                                     "detail": {"status": code, "body": out}})
    await request.app.state.auditor.record(
        "shop.renamed", actor=principal.subject, tenant=tenant, resource="tenant",
        ip=request.client.host if request.client else "")
    return {"name": str(out.get("name") or body.name.strip())}


# ── branches ──────────────────────────────────────────────────────────────────────────────────
class BranchIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    #: Optional, set by the owner if he wants his branch on the admin panel's own map — never
    #: required to open a branch, same trade as every other optional field on this product.
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    city: str = Field(default="", max_length=80)


class BranchPatch(BaseModel):
    """Rename, close, reopen, or set/correct its location. NO DELETE — see `update_branch`."""

    name: str | None = Field(default=None, min_length=1, max_length=128)
    active: bool | None = None
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    city: str | None = Field(default=None, max_length=80)


def _live(rows: list[Branch]) -> int:
    return len([b for b in rows if b.active])


@router.post("/branches", status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(subscribed_write), Depends(rate_limit)])
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
    try:
        async with S.claiming(request.app.state.container.datastore,
                              tenant=tenant, key=S.BRANCHES, now=time.time()):
            current = _live(await store.list(tenant))
            # LOCATION IS OPTIONAL ON THE FIRST BRANCH, REQUIRED FROM THE SECOND ONE ON. A shop
            # with a single location has one obvious place — asking him to paste a map link to
            # open the account at all is friction with nothing to show for it (§ the docstring on
            # BranchIn.lat/lng above still holds for that case). The MOMENT a second branch
            # exists, "which one" stops being obvious to anyone reading this data later —
            # whatsapp-assistant's own branch-selection step (asking a customer for his city) has
            # nothing to match against for a branch nobody located, and the admin map silently
            # drops it (services/operations/app/api/v1/platform.py's own 0.0/0.0 filter). Refusing
            # here, once, is cheaper than a shop discovering the gap the day a customer's WhatsApp
            # conversation cannot find their second branch at all.
            if current >= 1 and (body.lat is None or body.lng is None):
                return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={
                    "error": "LOCATION_REQUIRED",
                    "message": "حدّد موقع الفرع على الخريطة — لازم من الفرع الثاني فأكثر."})
            await S.guard_and_report(gauges, tenant=tenant, key=S.BRANCHES, current=current)

            await request.app.state.auditor.record(
                "branch.created", actor=principal.subject, tenant=tenant, resource="branch",
                ip=request.client.host if request.client else "")
            b = Branch(id=new_id("brn"), tenant=tenant, name=body.name.strip(),
                       created=int(time.time()),
                       lat=body.lat or 0.0, lng=body.lng or 0.0, city=body.city.strip())
            await store.save(b)
            await gauges.report(tenant, S.BRANCHES, current + 1)
    except S.SeatClaimBusy as exc:
        return JSONResponse(status_code=status.HTTP_409_CONFLICT,
                            content={"error": "BRANCH_BUSY", "message": str(exc)})
    except S.SeatLimitReached as exc:
        return JSONResponse(status_code=status.HTTP_402_PAYMENT_REQUIRED,
                            content={"error": "BRANCH_LIMIT", "message": str(exc)})
    return b.public()


@router.patch("/branches/{branch_id}", dependencies=[Depends(subscribed_write), Depends(rate_limit)])
async def update_branch(request: Request, branch_id: str, body: BranchPatch,
                        principal: Principal = Depends(_MANAGE)) -> dict:
    """Rename a branch, close one, or set/correct its location — and NEVER delete one.

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

    # THE LANE IS TAKEN FOR EVERY EDIT, not only a reopen. Whether this request needs the guard
    # depends on `b.active`, which is read inside — deciding that outside the lane would mean
    # reading the state that decides, before holding the thing that keeps it still. A rename pays
    # a few microseconds of queueing for a rule with no exception in it (core/seats.py).
    try:
        async with S.claiming(request.app.state.container.datastore,
                              tenant=tenant, key=S.BRANCHES, now=time.time()):
            b = await store.get(tenant, branch_id)
            if b is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND")
            rows = await store.list(tenant)
            if body.active is True and not b.active:
                await S.guard_and_report(gauges, tenant=tenant, key=S.BRANCHES,
                                         current=_live(rows))

            # THE REAL DIFF, NOT JUST "SOMETHING CHANGED" — found by review: this event used to
            # carry no metadata at all, so a close, a reopen, a rename and a relocation were all
            # indistinguishable in the trail, one line reading "branch.updated" with nothing to
            # tell them apart. For a dispute over "was this branch open on date X" that is not a
            # log, it is a rumour. Computed BEFORE the mutation below, against the row this
            # request actually read, so it reflects what THIS call changes — never a stale diff
            # against a row a concurrent writer already moved past (the claim lane above already
            # protects the write itself; this only has to describe it honestly).
            changes: dict[str, Any] = {}
            if body.active is not None and body.active != b.active:
                changes["active"] = {"from": b.active, "to": body.active}
            if body.name is not None and body.name.strip() != b.name:
                changes["name"] = {"from": b.name, "to": body.name.strip()}
            if body.lat is not None and body.lat != b.lat:
                changes["lat"] = {"from": b.lat, "to": body.lat}
            if body.lng is not None and body.lng != b.lng:
                changes["lng"] = {"from": b.lng, "to": body.lng}
            if body.city is not None and body.city.strip() != b.city:
                changes["city"] = {"from": b.city, "to": body.city.strip()}

            await request.app.state.auditor.record(
                "branch.updated", actor=principal.subject, tenant=tenant,
                resource=f"branch:{branch_id}", ip=request.client.host if request.client else "",
                metadata=changes)

            if body.name is not None:
                b.name = body.name.strip()
            if body.active is not None:
                # THE CACHE `Branch.closed_at` SPLIT — see that field's own docstring. Set on
                # close, cleared on reopen; the real open/close TIMELINE is the audit event above.
                b.closed_at = int(time.time()) if body.active is False else 0
                b.active = body.active
            if body.lat is not None:
                b.lat = body.lat
            if body.lng is not None:
                b.lng = body.lng
            if body.city is not None:
                b.city = body.city.strip()
            await store.save(b)
            # THE WHOLE COUNT, RECOMPUTED — a gauge is reported, never incremented
            # (core/seats.py). The saved row is the one in `rows` by identity only if the store
            # returned the same object, so the live count is taken from the list with this row's
            # new state substituted in.
            await gauges.report(tenant, S.BRANCHES,
                                _live([b if r.id == b.id else r for r in rows]))
    except S.SeatClaimBusy as exc:
        return JSONResponse(status_code=status.HTTP_409_CONFLICT,
                            content={"error": "BRANCH_BUSY", "message": str(exc)})
    except S.SeatLimitReached as exc:
        return JSONResponse(status_code=status.HTTP_402_PAYMENT_REQUIRED,
                            content={"error": "BRANCH_LIMIT", "message": str(exc)})
    return b.public()


@router.get("/branches", dependencies=[Depends(rate_limit)])
async def list_branches(request: Request, principal: Principal = Depends(_READ_BRANCHES)) -> dict:
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

    # ── AND ONLY THE ONES HE MAY SEE (§12.4) ──────────────────────────────────────────────────
    # This read returned the whole chain to anybody holding `operations.list_branches`, while every
    # other read in this service — visits, customers, the dashboards — was already narrowed by
    # `branch_scope`. So a manager granted one branch could not read Jeddah's numbers and could
    # read Jeddah's NAME, its id, and how many places the chain has. «لا يرى موظف فرع أ بيانات
    # فرع ب» covers the names too: they are that shop's data.
    #
    # AND THE SWITCHER IS BUILT FROM THIS LIST. It moves to the sidebar, where the choice scopes
    # every screen, and its one non-negotiable rule is «يُضيِّق ولا يوسّع أبداً» — which can only
    # hold if the list it offers was narrowed first. Otherwise it offers him a branch the server
    # then refuses, and the product looks broken to a person who did nothing wrong.
    # `field="id"` AND NOT THE DEFAULT, which is the whole difference between a filter and a
    # no-op. `visible` keeps a row whose branch field is empty — right for a visit, because a
    # till records plenty with no branch and «غير محدَّد» belongs to everybody. A BRANCH row has
    # no `branch_id` at all: it IS the branch, and its key is `id`. Called with the default this
    # line would find the field missing on every row, keep every row, and read in review as
    # protection that was never applied.
    scope = await branch_scope(request.app.state.container.datastore, principal)
    kept = SCOPE.visible([b.public() for b in rows], scope, field="id")

    # ── HOW MANY HE MAY HAVE, BECAUSE THE SCREEN CANNOT GUESS IT (هـ-3) ────────────────────────
    # «فريقي» locked its branches tab on whether the caller holds `operations.list_branches` —
    # a ROLE fact — and wrote a PLAN sentence on the lock. Both halves were wrong at once: an
    # owner whose plan allows one branch holds the capability, saw no lock at all, and met the
    # refusal only after typing a name; and a supervisor without the capability was told
    # «الفروع متاحة في باقة أعلى» about a plan his shop may well already be paying for.
    #
    # So the entitlement travels with the read, exactly as `shop_mode.available` does.
    #
    # -1 IS «NO KNOWN CEILING» AND IT COVERS TWO CASES: an unlimited plan, and a billing we could
    # not reach — `allows_one_more` fails open by design (core/seats.py). Neither may draw a lock:
    # telling a paying shop it has not paid is the worst sentence in the product, and an outage
    # must never be the thing that says it.
    #
    # AND THE FIRST HALF OF THE SAME ANSWER TRAVELS TOO — «may he open ONE MORE, right now». The
    # limit alone only closes the tab for a shop whose plan allows exactly one branch. A shop
    # allowed three and holding three sees an open tab and a live «إضافة فرع», types a name, and
    # meets the refusal at the end — the same journey this finding is about, reached at a
    # different number. The gauge already computes both; taking only `[1]` threw away the half
    # that answers the button.
    may_add, limit = await request.app.state.container.gauges.allows_one_more(
        tenant, S.BRANCHES, _live(rows))
    # THE GAUGE COUNTS THE SHOP'S REAL BRANCHES, not the ones this caller may see. The limit and
    # «may he open one more» are facts about the establishment's PLAN — computing them from a
    # narrowed list would tell a one-branch manager his chain of five has room for four more.
    return {"branches": kept, "branch_limit": int(limit), "may_add_branch": bool(may_add)}


# ── the service catalogue ─────────────────────────────────────────────────────────────────────
class ServiceIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    # 0 means "no natural cycle" — a one-off repair generates no reminder. Explicitly a valid
    # value rather than a missing one, because a default of 30 would schedule a reminder for a
    # puncture repair and teach a customer that our messages are noise.
    cycle_days: int = Field(default=0, ge=0, le=3650)
    # Minor units. No float ever touches an amount.
    price_minor: int = Field(default=0, ge=0)
    # 0 means NOT CONFIGURED, read by bookings to derive availability (docs/خطة-تنفيذ-الحجوزات.md
    # §2). Not defaulted to a guessed length here for the same reason `cycle_days` is not defaulted
    # to 30 above — an invented duration would let bookings compute a slot nobody actually set.
    # 720 = 12 hours, generous above any real salon/workshop service, still a real ceiling.
    duration_minutes: int = Field(default=0, ge=0, le=720)
    sort: int = Field(default=0, ge=0, le=9999)


@router.get("/services", dependencies=[Depends(rate_limit)])
async def list_services(request: Request, include_retired: bool = False,
                        principal: Principal = Depends(_MANAGE_SERVICES)) -> dict:
    """The OWNER's catalogue, which is not the field grid.

    /field/catalogue answers what an operator may record a visit against, and it is right that a
    retired service is absent from it. But the same list was the only one there was, so a service
    stopped from the management screen vanished from the management screen — and «تفعيل» had
    nothing left to act on. The same shape of bug as the rewards table, found the same way: by
    stopping something and looking for it.

    Gated on `operations.manage` OR `operations.manage_services` — not read:
    this is the list you edit, and an operator has no business seeing what the shop has retired.
    """
    rows = await ServiceStore(request.app.state.container.datastore).list(
        _tenant(principal), active_only=not include_retired)
    return {"services": [s.public() for s in rows]}


@router.post("/services", status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(subscribed_write), Depends(rate_limit)])
async def create_service(request: Request, body: ServiceIn,
                         principal: Principal = Depends(_MANAGE_SERVICES)) -> dict:
    tenant = _tenant(principal)
    await request.app.state.auditor.record(
        "service.created", actor=principal.subject, tenant=tenant, resource="service",
        ip=request.client.host if request.client else "")
    s = Service(id=new_id("srv"), tenant=tenant, name=body.name.strip(),
                cycle_days=body.cycle_days, price_minor=body.price_minor,
                duration_minutes=body.duration_minutes, sort=body.sort,
                created=int(time.time()))
    await ServiceStore(request.app.state.container.datastore).save(s)
    return s.public()


class ServiceImportRow(BaseModel):
    """One line of an uploaded catalogue file — the console parses the spreadsheet client-side and
    sends structured rows, never a raw file; this service has no business knowing what a .csv or
    .xlsx looks like. Same field shape and same limits as `ServiceIn` on purpose: importing must
    not be a second, looser way to create a service than typing one in by hand."""
    name: str = Field(min_length=1, max_length=128)
    cycle_days: int = Field(default=0, ge=0, le=3650)
    price_minor: int = Field(default=0, ge=0)
    duration_minutes: int = Field(default=0, ge=0, le=720)
    # THE TILL'S OWN ID, OPTIONAL — Service.external_id's own docstring is the reason this exists:
    # matching by name alone forks a renamed product into two rows on the next re-upload. A row
    # carrying one matches an EXISTING service by it first (survives a rename in the file);
    # falls back to matching by name only when empty, same as a shop that never had a POS.
    external_id: str = Field(default="", max_length=128)


class ServiceImportIn(BaseModel):
    rows: list[ServiceImportRow] = Field(min_length=1, max_length=200)
    # DEFAULT FALSE, AND NAMED WHAT IT DOES — an owner uploading a partial file by mistake must
    # never silently retire the rest of the catalogue. Explicit opt-in, asked again on every
    # import (the console never remembers a previous choice), because "everything not in this
    # file" is a different set on every upload.
    deactivate_missing: bool = False


@router.post("/services/bulk_import", dependencies=[Depends(subscribed_write), Depends(rate_limit)])
async def bulk_import_services(request: Request, body: ServiceImportIn,
                               principal: Principal = Depends(_MANAGE_SERVICES)) -> dict:
    """Create/update many services from an uploaded file, in one call.

    VALIDATION HAPPENS BEFORE ANY WRITE, ALWAYS — twice over. Pydantic's own field limits on
    `ServiceImportRow` (`name` non-empty, a price/duration/cycle in range) already refuse the
    WHOLE request with a 422 if even one row is malformed, before this function body ever runs —
    the same all-or-nothing guarantee `ServiceIn` already gives a single manual add, extended to a
    batch. The second check, below, is duplicate NAMES within the file itself: two rows meaning
    "the same service" is a file the owner needs to fix, not a coin flip about which row wins.

    MATCHED BY external_id FIRST, THEN NAME — see `ServiceImportRow.external_id`'s own note.
    A match UPDATES the existing row (and reactivates it if it was stopped); no match CREATES one.
    A previously-stopped service reappearing in a new upload is read as "bring it back", which is
    the only sane reading of an owner naming it in a file they are actively importing.

    `deactivate_missing` is the ONE destructive thing this route can do, and it is opt-in, per
    call, every time — see `ServiceImportIn.deactivate_missing`'s own note.
    """
    tenant = _tenant(principal)
    seen: dict[str, int] = {}
    dupes: set[str] = set()
    for row in body.rows:
        key = row.name.strip().lower()
        if key in seen:
            dupes.add(row.name.strip())
        seen[key] = 1
    if dupes:
        return JSONResponse(
            {"error": "DUPLICATE_NAMES", "names": sorted(dupes),
             "reason": "الملف فيه أكثر من صف بنفس الاسم — صحّح الملف وأعد الرفع."},
            status_code=status.HTTP_400_BAD_REQUEST)

    store = ServiceStore(request.app.state.container.datastore)
    existing = await store.list(tenant, active_only=False)
    by_external_id = {s.external_id: s for s in existing if s.external_id}
    by_name = {s.name.strip().lower(): s for s in existing}

    created = updated = reactivated = 0
    touched_ids: set[str] = set()
    for row in body.rows:
        name = row.name.strip()
        target = by_external_id.get(row.external_id) if row.external_id else None
        if target is None:
            target = by_name.get(name.lower())

        if target is not None:
            was_stopped = target.active is False
            target.name = name
            target.cycle_days = row.cycle_days
            target.price_minor = row.price_minor
            target.duration_minutes = row.duration_minutes
            target.active = True
            if row.external_id:
                target.external_id = row.external_id
            await store.save(target)
            touched_ids.add(target.id)
            if was_stopped:
                reactivated += 1
            else:
                updated += 1
        else:
            s = Service(id=new_id("srv"), tenant=tenant, name=name, cycle_days=row.cycle_days,
                       price_minor=row.price_minor, duration_minutes=row.duration_minutes,
                       external_id=row.external_id, created=int(time.time()))
            await store.save(s)
            touched_ids.add(s.id)
            created += 1

    deactivated = 0
    if body.deactivate_missing:
        for s in existing:
            if s.id not in touched_ids and s.active is not False:
                s.active = False
                await store.save(s)
                deactivated += 1

    await request.app.state.auditor.record(
        "service.bulk_imported", actor=principal.subject, tenant=tenant, resource="service",
        ip=request.client.host if request.client else "",
        metadata={"created": created, "updated": updated, "reactivated": reactivated,
                  "deactivated": deactivated, "rows": len(body.rows)})
    return {"created": created, "updated": updated, "reactivated": reactivated,
            "deactivated": deactivated}


class ServicePatch(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    cycle_days: int | None = Field(default=None, ge=0, le=3650)
    price_minor: int | None = Field(default=None, ge=0)
    duration_minutes: int | None = Field(default=None, ge=0, le=720)
    active: bool | None = None
    sort: int | None = Field(default=None, ge=0, le=9999)
    # WHO CAN ACTUALLY DO THIS — `None` MEANS «LEAVE IT», same convention every other field on
    # this model already uses. An EXPLICIT empty list is a real value (models.py's own
    # `Service.eligible_staff_ids` docstring: "[] means every active operator"), not "leave it" —
    # so an owner can deliberately clear a restriction back to unrestricted from this same route.
    eligible_staff_ids: list[str] | None = Field(default=None, max_length=64)


@router.patch("/services/{service_id}", dependencies=[Depends(subscribed_write), Depends(rate_limit)])
async def update_service(request: Request, service_id: str, body: ServicePatch,
                         principal: Principal = Depends(_MANAGE_SERVICES)) -> dict:
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

    for fld in ("name", "cycle_days", "price_minor", "duration_minutes", "active", "sort"):
        val = getattr(body, fld)
        if val is not None:
            setattr(s, fld, val.strip() if isinstance(val, str) else val)

    # EVERY OPERATOR GRANTED IS CHECKED against this tenant's own roster, same discipline
    # `update_operator`'s `visible_branch_ids` already uses — an id we do not recognise is
    # DROPPED, not stored, so a stale/foreign id cannot silently narrow a service to nobody.
    if body.eligible_staff_ids is not None:
        operators = OperatorStore(request.app.state.container.datastore)
        real = {o.id for o in await operators.list(tenant)}
        s.eligible_staff_ids = [oid for oid in body.eligible_staff_ids if oid in real]

    await store.save(s)
    return s.public()


# ── the package catalogue ─────────────────────────────────────────────────────────────────────
# A package is a named, priced GROUP of the owner's own services (see core/models.py::Package's
# own docstring for why price and points are never derived from the components). Same house style
# as the service routes just above — same capability gate (packages are "خدماتي ومنتجاتي" too),
# same subscribed_write, same rate limit, same audit-on-write, same deactivate-never-delete.
class PackageIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    # AT LEAST TWO, NO UPPER BOUND — a "package" of one service is just that service; how many
    # belong together past that is entirely the owner's call (packages feature decision).
    service_ids: list[str] = Field(min_length=2, max_length=64)
    # Minor units, OWNER-ENTERED, > 0 — a package at price 0 is an accidental free booking, never
    # a real state (see Package's own docstring: never derived from the components either way).
    price_minor: int = Field(gt=0)
    sort: int = Field(default=0, ge=0, le=9999)
    # Set by the console when a package is accepted straight from محلّي's "اجعلها باقة" suggestion
    # — see services/insights/app/core/bundles.py. Left at the default for anything typed by hand.
    source: str = Field(default="manual", pattern="^(manual|suggested)$")
    source_service_ids: list[str] = Field(default_factory=list, max_length=64)
    # ── scheduling (packages feature, phase 2) — see core/scheduling.py::is_offerable ──────────
    starts_at: int = Field(default=0, ge=0)
    ends_at: int = Field(default=0, ge=0)
    recurrence: str = Field(default="none", pattern="^(none|weekly|monthly|yearly)$")
    recurrence_weekdays: list[int] = Field(default_factory=list, max_length=7)
    recurrence_days_of_month: list[int] = Field(default_factory=list, max_length=31)
    recurrence_yearly_from: str = Field(default="", max_length=5)
    recurrence_yearly_to: str = Field(default="", max_length=5)
    # PURELY DESCRIPTIVE — see Package.person_count's own docstring. 1 = say nothing about it.
    person_count: int = Field(default=1, ge=1, le=50)


def _validate_package_services(tenant: str, service_ids: list[str],
                               live: dict[str, Service]) -> list[str] | None:
    """Every id must exist, belong to THIS tenant, and still be active — a package is a promise
    that everything inside it can actually be delivered today. Returns the cleaned, de-duplicated
    list, or None if any id fails (the caller turns that into a 400 naming the reason)."""
    seen: list[str] = []
    for sid in service_ids:
        if sid in seen:
            continue
        svc = live.get(sid)
        if svc is None or svc.tenant != tenant or not svc.active:
            return None
        seen.append(sid)
    return seen if len(seen) >= 2 else None


def _schedule_error(*, starts_at: int, ends_at: int, recurrence: str,
                    weekdays: list[int], days_of_month: list[int],
                    yearly_from: str, yearly_to: str) -> str:
    """One sentence naming what is wrong with a proposed schedule, or "" — checked at WRITE time
    so a malformed schedule is refused here, never discovered the first time a booking silently
    fails to validate against it (core/scheduling.py's own module docstring)."""
    if ends_at and starts_at and ends_at < starts_at:
        return "تاريخ النهاية قبل تاريخ البداية"
    return SCHED.validate_recurrence(
        recurrence=recurrence, weekdays=weekdays, days_of_month=days_of_month,
        yearly_from=yearly_from, yearly_to=yearly_to)


@router.get("/packages", dependencies=[Depends(rate_limit)])
async def list_packages(request: Request, include_retired: bool = False,
                        principal: Principal = Depends(_MANAGE_SERVICES)) -> dict:
    rows = await PackageStore(request.app.state.container.datastore).list(
        _tenant(principal), active_only=not include_retired)
    now = int(time.time())
    # `offerable_now` IS A CONVENIENCE, COMPUTED HERE FROM THE SAME FUNCTION EVERYTHING ELSE USES
    # — never a second rule. The console reads it to show "غير مفعّلة اليوم" beside a package
    # that is `active` but simply outside its own schedule right now (e.g. a Saturday-only
    # package viewed on a Tuesday) — a real, useful distinction from "the owner turned it off".
    return {"packages": [{**p.public(), "offerable_now": SCHED.is_offerable(p, now)} for p in rows]}


@router.post("/packages", status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(subscribed_write), Depends(rate_limit)])
async def create_package(request: Request, body: PackageIn,
                         principal: Principal = Depends(_MANAGE_SERVICES)) -> dict:
    tenant = _tenant(principal)
    svc_store = ServiceStore(request.app.state.container.datastore)
    live = {s.id: s for s in await svc_store.list(tenant, active_only=False)}
    cleaned = _validate_package_services(tenant, body.service_ids, live)
    if cleaned is None:
        return JSONResponse(
            {"error": "INVALID_SERVICES",
             "reason": "لازم خدمتين على الأقل، موجودتين وفعّالتين في قائمتك."},
            status_code=status.HTTP_400_BAD_REQUEST)

    sched_error = _schedule_error(
        starts_at=body.starts_at, ends_at=body.ends_at, recurrence=body.recurrence,
        weekdays=body.recurrence_weekdays, days_of_month=body.recurrence_days_of_month,
        yearly_from=body.recurrence_yearly_from, yearly_to=body.recurrence_yearly_to)
    if sched_error:
        return JSONResponse({"error": "INVALID_SCHEDULE", "reason": sched_error},
                            status_code=status.HTTP_400_BAD_REQUEST)

    await request.app.state.auditor.record(
        "package.created", actor=principal.subject, tenant=tenant, resource="package",
        ip=request.client.host if request.client else "")
    p = Package(id=new_id("pkg"), tenant=tenant, name=body.name.strip(),
               service_ids=cleaned, price_minor=body.price_minor, sort=body.sort,
               source=body.source, source_service_ids=list(body.source_service_ids),
               starts_at=body.starts_at, ends_at=body.ends_at, recurrence=body.recurrence,
               recurrence_weekdays=list(body.recurrence_weekdays),
               recurrence_days_of_month=list(body.recurrence_days_of_month),
               recurrence_yearly_from=body.recurrence_yearly_from,
               recurrence_yearly_to=body.recurrence_yearly_to,
               person_count=body.person_count,
               created=int(time.time()))
    await PackageStore(request.app.state.container.datastore).save(p)
    return {**p.public(), "offerable_now": SCHED.is_offerable(p, int(time.time()))}


class PackagePatch(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    service_ids: list[str] | None = Field(default=None, min_length=2, max_length=64)
    price_minor: int | None = Field(default=None, gt=0)
    active: bool | None = None
    sort: int | None = Field(default=None, ge=0, le=9999)
    # ── scheduling — `None` MEANS "LEAVE IT", same convention as every other field here. Editing
    # the schedule always sends the WHOLE shape (all recurrence-relevant fields together) rather
    # than one piece — a partial edit could otherwise leave e.g. `recurrence="weekly"` with the
    # PREVIOUS package's `recurrence_weekdays` silently still attached.
    starts_at: int | None = Field(default=None, ge=0)
    ends_at: int | None = Field(default=None, ge=0)
    recurrence: str | None = Field(default=None, pattern="^(none|weekly|monthly|yearly)$")
    recurrence_weekdays: list[int] | None = Field(default=None, max_length=7)
    recurrence_days_of_month: list[int] | None = Field(default=None, max_length=31)
    recurrence_yearly_from: str | None = Field(default=None, max_length=5)
    recurrence_yearly_to: str | None = Field(default=None, max_length=5)
    person_count: int | None = Field(default=None, ge=1, le=50)


@router.patch("/packages/{package_id}",
              dependencies=[Depends(subscribed_write), Depends(rate_limit)])
async def update_package(request: Request, package_id: str, body: PackagePatch,
                         principal: Principal = Depends(_MANAGE_SERVICES)) -> dict:
    """Edit a package. DEACTIVATE rather than delete — same reasoning as `update_service`: a past
    visit that fulfilled this package must still make sense a year from now."""
    tenant = _tenant(principal)
    store = PackageStore(request.app.state.container.datastore)
    p = await store.get(tenant, package_id)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND")

    if body.service_ids is not None:
        svc_store = ServiceStore(request.app.state.container.datastore)
        live = {s.id: s for s in await svc_store.list(tenant, active_only=False)}
        cleaned = _validate_package_services(tenant, body.service_ids, live)
        if cleaned is None:
            return JSONResponse(
                {"error": "INVALID_SERVICES",
                 "reason": "لازم خدمتين على الأقل، موجودتين وفعّالتين في قائمتك."},
                status_code=status.HTTP_400_BAD_REQUEST)
        p.service_ids = cleaned

    # SCHEDULE FIELDS VALIDATED TOGETHER, AS THE SHAPE THEY WILL END UP AS — merging each patched
    # field over the package's CURRENT value first (the same "None = leave it" convention every
    # other field on this route uses), so an edit that only touches `recurrence` still gets
    # checked against whatever weekdays/dates the package already had, not against an empty patch.
    schedule_touched = any(
        getattr(body, f) is not None for f in
        ("starts_at", "ends_at", "recurrence", "recurrence_weekdays", "recurrence_days_of_month",
         "recurrence_yearly_from", "recurrence_yearly_to"))
    if schedule_touched:
        starts_at = body.starts_at if body.starts_at is not None else p.starts_at
        ends_at = body.ends_at if body.ends_at is not None else p.ends_at
        recurrence = body.recurrence if body.recurrence is not None else p.recurrence
        weekdays = (body.recurrence_weekdays if body.recurrence_weekdays is not None
                   else p.recurrence_weekdays)
        days_of_month = (body.recurrence_days_of_month if body.recurrence_days_of_month is not None
                         else p.recurrence_days_of_month)
        yearly_from = (body.recurrence_yearly_from if body.recurrence_yearly_from is not None
                      else p.recurrence_yearly_from)
        yearly_to = (body.recurrence_yearly_to if body.recurrence_yearly_to is not None
                    else p.recurrence_yearly_to)
        sched_error = _schedule_error(
            starts_at=starts_at, ends_at=ends_at, recurrence=recurrence, weekdays=weekdays,
            days_of_month=days_of_month, yearly_from=yearly_from, yearly_to=yearly_to)
        if sched_error:
            return JSONResponse({"error": "INVALID_SCHEDULE", "reason": sched_error},
                                status_code=status.HTTP_400_BAD_REQUEST)
        p.starts_at, p.ends_at, p.recurrence = starts_at, ends_at, recurrence
        p.recurrence_weekdays = list(weekdays)
        p.recurrence_days_of_month = list(days_of_month)
        p.recurrence_yearly_from, p.recurrence_yearly_to = yearly_from, yearly_to

    await request.app.state.auditor.record(
        "package.updated", actor=principal.subject, tenant=tenant,
        resource=f"package:{package_id}", ip=request.client.host if request.client else "")

    for fld in ("name", "price_minor", "active", "sort", "person_count"):
        val = getattr(body, fld)
        if val is not None:
            setattr(p, fld, val.strip() if isinstance(val, str) else val)

    await store.save(p)
    return {**p.public(), "offerable_now": SCHED.is_offerable(p, int(time.time()))}
