"""Mobile/on-the-go service requests — the shop's own review queue. See
`core/mobile_requests.py`'s own module docstring for the full design; this file is only the HTTP
door for the SHOP's side of it (list, accept, reject, assign, complete, no-show, the risk hint at
accept time). The WhatsApp bot's own creation door lives in `api/internal.py`
(`POST /internal/operations/mobile-requests`) — a different tier, a different caller, a
deliberately separate file (same split `till.py`/`staff.py` already keep elsewhere in this
service).

TWO CAPABILITIES, TWO SCOPES (the second added 2026-09-15, the owner's own idea — reusing the
review queue's own assignment field to scope a field operator's view rather than inventing a
second engine): `operations.mobile_requests_manage` (owner/manager/supervisor) is the FULL review
queue — accept/reject/assign/complete/no-show on anything, same placement as
`operations.grant_coupon_direct`. `operations.mobile_requests_execute` (the plain field operator
role too) is a SCOPED half: list only what a manager assigned to THEM, and mark تم/لم يتم only on
that — never accept, reject, or assign, which stay a manager-level decision same as before.

`_scope()` below is the ONE place that decides which of the two a given caller actually gets —
every route that accepts either capability calls it exactly once, right after resolving the
tenant, and every read/write downstream is built from what it returns rather than re-deriving the
distinction.

A THIRD, LATER DIMENSION — BRANCH (registry: `core/branch_domains.py`'s own `mobile_requests` row,
`derived_from="assigned_operator_branch"`). A request itself carries no `branch_id` at all — the
technician travels TO the customer, not to a shop branch — so it cannot be scoped the way every
other branch-scoped domain in this service is (a plain `branch_id` field filtered against
`branch_scope()`). It is scoped INDIRECTLY, through whoever it is currently ASSIGNED to:
`_operator_branch()` below resolves that operator's own station (`staff.py`'s own `Operator.
branch_id`, the exact fact `branch_scope()` itself is built from), and `_branch_allowed()` applies
the SAME membership rule `app/api/scope.py::visible()` already applies everywhere else in this
service — reused, not reinvented, per the owner's own instruction on this feature.

AN UNASSIGNED REQUEST (`assigned_to == ""`) IS ALWAYS VISIBLE TO EVERY BRANCH'S MANAGER — the
owner's own words, paraphrased: anyone should be able to pick it up. `_branch_allowed()` returns
`True` unconditionally for an empty `branch_id` for exactly this reason, mirroring `visible()`'s
own "a row with no branch is kept for everyone" rule for the identical reason (a till that never
recorded one).

ONCE ASSIGNED, THE SAME BRANCH BOUNDARY EVERY OTHER DOMAIN HOLDS APPLIES: a manager scoped to one
branch may not SEE a request assigned to another branch's operator (`list_mobile_requests`), may
not REASSIGN one away from its current assignee (`assign_mobile_request`'s pre-check on the
CURRENT `assigned_to`), and may not assign one TO an operator outside their own scope in the first
place (`assign_mobile_request`'s pre-check on the REQUESTED `operator_id`, and
`create_mobile_request`'s identical check when a manager assigns at creation time). The same guard
also covers accept/reject/risk/complete/no-show once a request has already been assigned to
someone the caller may not see — refused with 403, never a silent narrowing that would just show a
smaller, wrong queue.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.api.auth import Principal
from app.api.authz import require_any_capability, require_capability
from app.api.ratelimit import rate_limit
from app.api.scope import REVOKED, branch_scope
from app.core.mobile_requests import MobileRequestError
from app.core.stores import OperatorStore

router = APIRouter(prefix="/staff/mobile-requests", tags=["mobile-requests"])

_MANAGE_CAP = "operations.mobile_requests_manage"
_EXECUTE_CAP = "operations.mobile_requests_execute"
_MANAGE = require_capability(_MANAGE_CAP)
_ANY = require_any_capability(_MANAGE_CAP, _EXECUTE_CAP)


def _tenant(p: Principal) -> str:
    if not p.tenant:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "NO_TENANT")
    return p.tenant


@dataclass(frozen=True)
class _Scope:
    """`assigned_to_filter`/`expected_assignee` are the SAME value under two names, threaded to
    two different callees (`list(assigned_to=...)` vs `complete(expected_assignee=...)`) — kept
    as one field, not two, so there is exactly one place a manager's own "" (no restriction) could
    ever be typo'd into an operator's real id or vice versa."""
    is_manager: bool
    own_id: str

    @property
    def assigned_to_filter(self) -> str:
        return "" if self.is_manager else self.own_id


def _scope(principal: Principal) -> _Scope:
    return _Scope(is_manager=_MANAGE_CAP in principal.caps, own_id=principal.subject)


async def _operator_branch(datastore: Any, tenant: str, operator_id: str) -> str:
    """The branch this operator works at (his station) — resolved fresh on every call, never
    cached, since a manager can move an operator's station at any time and a stale answer here
    would either hide or leak a request depending on which way it was stale. `""` for an
    unassigned request (the caller's own job never to call this with one) or an operator id this
    tenant no longer holds a row for — both read as "no branch", which `_branch_allowed` below
    already treats as visible to everyone, the same as an unbranched visit reads everywhere else
    in this service."""
    if not operator_id:
        return ""
    op = await OperatorStore(datastore).get(tenant, operator_id)
    return op.branch_id if op else ""


def _branch_allowed(bscope: "str | frozenset[str] | None", branch_id: str) -> bool:
    """Whether `branch_id` — an assigned operator's own station, or `""` for unassigned — is
    visible under `bscope` (the caller's own `branch_scope()` answer). Same membership rule as
    `app/api/scope.py::visible()`, reused rather than reinvented (this module's own docstring):
    an unassigned request is ALWAYS allowed regardless of scope — see that docstring for why —
    and REVOKED (a stopped employee) never is, checked before the empty-scope case for the same
    reason `visible()`'s own comment gives: `None` is falsy and a naive truthiness test would hand
    a dismissed employee everything."""
    if not branch_id:
        return True
    if bscope is REVOKED:
        return False
    if not bscope:
        return True
    allowed = bscope if isinstance(bscope, (set, frozenset)) else {bscope}
    return branch_id in allowed


@router.get("", dependencies=[Depends(rate_limit)])
async def list_mobile_requests(request: Request, status_filter: str = "",
                               principal: Principal = Depends(_ANY)) -> Any:
    """`?status_filter=pending` for the review queue, `accepted` for what is due a تم/لم يتم
    decision, or empty for everything — the console's own tabs, not three separate routes.

    A manager sees the whole tenant MINUS what branch scoping narrows (see module docstring); an
    execute-tier caller is FORCED to their own assigned_to here, server-side — never trusted from
    a query param, so there is no way for that caller to ask for anyone else's queue by simply
    omitting a filter. Branch narrowing is skipped for an execute-tier caller on purpose: their own
    assigned requests are, by construction, assigned to their own operator id, whose own station is
    always inside their own scope — the check would cost a lookup per row and could never refuse
    anything."""
    tenant = _tenant(principal)
    scope = _scope(principal)
    ds = request.app.state.container.datastore
    svc = request.app.state.container.mobile_requests
    rows = await svc.list(tenant, status=status_filter, assigned_to=scope.assigned_to_filter)
    if scope.is_manager:
        bscope = await branch_scope(ds, principal)
        branches: dict[str, str] = {}
        kept = []
        for r in rows:
            if r.assigned_to:
                if r.assigned_to not in branches:
                    branches[r.assigned_to] = await _operator_branch(ds, tenant, r.assigned_to)
                if not _branch_allowed(bscope, branches[r.assigned_to]):
                    continue
            kept.append(r)
        rows = kept
    return {"requests": [r.public() for r in rows]}


class ManualCreateIn(BaseModel):
    """The shop's OWN door to create a request by hand — a customer called in, or the shop wants
    this standalone (owner's own decision, 2026-09-15: never requiring the WhatsApp bot app
    first). Same fields the bot's own `/internal/operations/mobile-requests` door takes, plus the
    one thing only a manager creating it by hand can usefully do at the same moment: assign it."""
    phone: str = Field(min_length=3, max_length=32)
    customer_name: str = Field(default="", max_length=128)
    service_ids: list[str] = Field(min_length=1, max_length=20)
    requested_time: int = Field(gt=0)
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    operator_id: str = Field(default="", max_length=200)
    referral_code: str = Field(default="", max_length=16)


@router.post("", dependencies=[Depends(rate_limit)])
async def create_mobile_request(request: Request, body: ManualCreateIn,
                                principal: Principal = Depends(_MANAGE)) -> Any:
    """Manager-only, same tier as accept/reject — a request the SHOP itself typed in still goes
    through the identical review queue afterward (still PENDING, still needs its own accept), so
    a manually-added request is never quietly treated as pre-approved just because a human at the
    shop, not a customer over WhatsApp, is the one who typed it."""
    tenant = _tenant(principal)
    ds = request.app.state.container.datastore
    svc = request.app.state.container.mobile_requests
    if body.operator_id:
        # A MANAGER MAY NOT HAND A FRESH REQUEST TO AN OPERATOR OUTSIDE THEIR OWN SCOPE — same
        # branch boundary `assign_mobile_request` enforces on an EXISTING request, applied here
        # too since creating-and-assigning in one step is the same act split across two calls.
        bscope = await branch_scope(ds, principal)
        target_branch = await _operator_branch(ds, tenant, body.operator_id)
        if not _branch_allowed(bscope, target_branch):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "OUTSIDE_YOUR_BRANCH")
    try:
        row = await svc.create(
            tenant=tenant, phone=body.phone, customer_name=body.customer_name,
            service_ids=body.service_ids, requested_time=body.requested_time,
            lat=body.lat, lng=body.lng, referral_code=body.referral_code)
        if body.operator_id:
            row = await svc.assign(tenant, row.id, operator_id=body.operator_id)
    except MobileRequestError as exc:
        _refuse(exc)
    await request.app.state.auditor.record(
        "mobile_request.created_manually", actor=principal.subject, tenant=tenant,
        resource=f"mobile_request:{row.id}", ip=request.client.host if request.client else "")
    return row.public()


async def _require_branch_access(ds: Any, tenant: str, principal: Principal, row: Any) -> None:
    """Refuses, 403, when `row` is currently assigned to an operator whose own branch this caller
    may not see — the enforcement half of this module's own docstring on branch scoping. A no-op
    for an unassigned row (always allowed) and for an execute-tier caller (their own assigned
    request is, by construction, always their own branch — see `list_mobile_requests`'s own note),
    so this is called unconditionally by every route below that acts on ONE existing request."""
    bscope = await branch_scope(ds, principal)
    branch_id = await _operator_branch(ds, tenant, row.assigned_to)
    if not _branch_allowed(bscope, branch_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "OUTSIDE_YOUR_BRANCH")


@router.get("/{request_id}/risk", dependencies=[Depends(rate_limit)])
async def mobile_request_risk(request: Request, request_id: str,
                              principal: Principal = Depends(_MANAGE)) -> Any:
    """A number beside the request at the moment the shop is about to accept it — see
    `MobileRequestService.no_show_risk`'s own docstring: a heads-up, never an enforcement, this
    product having no deposit/payment concept at all."""
    tenant = _tenant(principal)
    ds = request.app.state.container.datastore
    svc = request.app.state.container.mobile_requests
    row = await svc.get(tenant, request_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND")
    await _require_branch_access(ds, tenant, principal, row)
    risk = await svc.no_show_risk(tenant, row.phone)
    return risk.public()


def _refuse(exc: MobileRequestError) -> None:
    """Every action below shares the same shape: the engine's own refusal, verbatim, never a bare
    500 — same posture `CouponError` gets from the coupons routes."""
    raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


class RejectIn(BaseModel):
    reason: str = Field(default="", max_length=300)


class AssignIn(BaseModel):
    # "" CLEARS THE ASSIGNMENT — a manager taking a request back off someone's plate, or
    # correcting a mis-assignment, is exactly as real a case as assigning it in the first place.
    operator_id: str = Field(default="", max_length=200)


@router.post("/{request_id}/assign", dependencies=[Depends(rate_limit)])
async def assign_mobile_request(request: Request, request_id: str, body: AssignIn,
                                principal: Principal = Depends(_MANAGE)) -> Any:
    """Manager-only, same as accept/reject/risk — see `core/mobile_requests.py::assign`'s own
    docstring for why this is never gated on status and never auto-routed.

    TWO BRANCH CHECKS, NOT ONE — a manager may not pull a request away from a branch they cannot
    see (the CURRENT `assigned_to`, checked below via `_require_branch_access`), and may not hand
    it to an operator OUTSIDE their own scope either (the REQUESTED `body.operator_id`, checked
    right after) — both are the same "never widen what a scoped manager can touch" rule this
    module's own docstring describes."""
    tenant = _tenant(principal)
    ds = request.app.state.container.datastore
    svc = request.app.state.container.mobile_requests
    row = await svc.get(tenant, request_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND")
    await _require_branch_access(ds, tenant, principal, row)
    if body.operator_id:
        bscope = await branch_scope(ds, principal)
        target_branch = await _operator_branch(ds, tenant, body.operator_id)
        if not _branch_allowed(bscope, target_branch):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "OUTSIDE_YOUR_BRANCH")
    try:
        row = await svc.assign(tenant, request_id, operator_id=body.operator_id)
    except MobileRequestError as exc:
        _refuse(exc)
    await request.app.state.auditor.record(
        "mobile_request.assigned", actor=principal.subject, tenant=tenant,
        resource=f"mobile_request:{request_id}",
        ip=request.client.host if request.client else "",
        metadata={"operator_id": body.operator_id})
    return row.public()


@router.post("/{request_id}/accept", dependencies=[Depends(rate_limit)])
async def accept_mobile_request(request: Request, request_id: str,
                                principal: Principal = Depends(_MANAGE)) -> Any:
    tenant = _tenant(principal)
    ds = request.app.state.container.datastore
    svc = request.app.state.container.mobile_requests
    existing = await svc.get(tenant, request_id)
    if existing is not None:
        await _require_branch_access(ds, tenant, principal, existing)
    try:
        row = await svc.accept(tenant, request_id, actor=principal.subject)
    except MobileRequestError as exc:
        _refuse(exc)
    await request.app.state.auditor.record(
        "mobile_request.accepted", actor=principal.subject, tenant=tenant,
        resource=f"mobile_request:{request_id}",
        ip=request.client.host if request.client else "")
    return row.public()


@router.post("/{request_id}/reject", dependencies=[Depends(rate_limit)])
async def reject_mobile_request(request: Request, request_id: str, body: RejectIn,
                                principal: Principal = Depends(_MANAGE)) -> Any:
    tenant = _tenant(principal)
    ds = request.app.state.container.datastore
    svc = request.app.state.container.mobile_requests
    existing = await svc.get(tenant, request_id)
    if existing is not None:
        await _require_branch_access(ds, tenant, principal, existing)
    try:
        row = await svc.reject(tenant, request_id, actor=principal.subject, reason=body.reason)
    except MobileRequestError as exc:
        _refuse(exc)
    await request.app.state.auditor.record(
        "mobile_request.rejected", actor=principal.subject, tenant=tenant,
        resource=f"mobile_request:{request_id}",
        ip=request.client.host if request.client else "")
    return row.public()


@router.post("/{request_id}/complete", dependencies=[Depends(rate_limit)])
async def complete_mobile_request(request: Request, request_id: str,
                                  principal: Principal = Depends(_ANY)) -> Any:
    """الموعد تم — records a real Visit (`MobileRequestService.complete`'s own docstring): the
    loyalty points, insights and reminders that follow are automatic, the same as any other
    visit, from here on.

    A manager may complete ANY request their own branch scope allows; an execute-tier operator
    only their OWN assigned one — `_scope()`'s `assigned_to_filter` doubles as the ownership
    check `complete()` itself enforces (empty string for a manager means "no restriction", the
    exact same value that scopes their own `list()` above to "everyone"). The BRANCH check below
    is a no-op for that execute-tier caller (see `_require_branch_access`'s own docstring) and a
    real refusal for a manager scoped away from wherever this request is currently assigned."""
    tenant = _tenant(principal)
    scope = _scope(principal)
    ds = request.app.state.container.datastore
    svc = request.app.state.container.mobile_requests
    existing = await svc.get(tenant, request_id)
    if existing is not None:
        await _require_branch_access(ds, tenant, principal, existing)
    try:
        row = await svc.complete(tenant, request_id, expected_assignee=scope.assigned_to_filter)
    except MobileRequestError as exc:
        _refuse(exc)
    await request.app.state.auditor.record(
        "mobile_request.completed", actor=principal.subject, tenant=tenant,
        resource=f"mobile_request:{request_id}",
        ip=request.client.host if request.client else "")
    return row.public()


@router.post("/{request_id}/no-show", dependencies=[Depends(rate_limit)])
async def mobile_request_no_show(request: Request, request_id: str,
                                 principal: Principal = Depends(_ANY)) -> Any:
    """الموعد لم يتم — never creates a visit; feeds the next customer's own no-show risk read.
    Same manager-vs-own-assignment scoping, and the same branch check, as `complete` above."""
    tenant = _tenant(principal)
    scope = _scope(principal)
    ds = request.app.state.container.datastore
    svc = request.app.state.container.mobile_requests
    existing = await svc.get(tenant, request_id)
    if existing is not None:
        await _require_branch_access(ds, tenant, principal, existing)
    try:
        row = await svc.no_show(tenant, request_id, expected_assignee=scope.assigned_to_filter)
    except MobileRequestError as exc:
        _refuse(exc)
    await request.app.state.auditor.record(
        "mobile_request.no_show", actor=principal.subject, tenant=tenant,
        resource=f"mobile_request:{request_id}",
        ip=request.client.host if request.client else "")
    return row.public()
