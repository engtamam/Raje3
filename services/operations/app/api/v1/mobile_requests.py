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
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.api.auth import Principal
from app.api.authz import require_any_capability, require_capability
from app.api.ratelimit import rate_limit
from app.core.mobile_requests import MobileRequestError

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


@router.get("", dependencies=[Depends(rate_limit)])
async def list_mobile_requests(request: Request, status_filter: str = "",
                               principal: Principal = Depends(_ANY)) -> Any:
    """`?status_filter=pending` for the review queue, `accepted` for what is due a تم/لم يتم
    decision, or empty for everything — the console's own tabs, not three separate routes.

    A manager sees the whole tenant; an execute-tier caller is FORCED to their own assigned_to
    here, server-side — never trusted from a query param, so there is no way for that caller to
    ask for anyone else's queue by simply omitting a filter."""
    tenant = _tenant(principal)
    scope = _scope(principal)
    svc = request.app.state.container.mobile_requests
    rows = await svc.list(tenant, status=status_filter, assigned_to=scope.assigned_to_filter)
    return {"requests": [r.public() for r in rows]}


@router.get("/{request_id}/risk", dependencies=[Depends(rate_limit)])
async def mobile_request_risk(request: Request, request_id: str,
                              principal: Principal = Depends(_MANAGE)) -> Any:
    """A number beside the request at the moment the shop is about to accept it — see
    `MobileRequestService.no_show_risk`'s own docstring: a heads-up, never an enforcement, this
    product having no deposit/payment concept at all."""
    tenant = _tenant(principal)
    svc = request.app.state.container.mobile_requests
    row = await svc.get(tenant, request_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND")
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
    docstring for why this is never gated on status and never auto-routed."""
    tenant = _tenant(principal)
    svc = request.app.state.container.mobile_requests
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
    svc = request.app.state.container.mobile_requests
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
    svc = request.app.state.container.mobile_requests
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

    A manager may complete ANY request; an execute-tier operator only their OWN assigned one —
    `_scope()`'s `assigned_to_filter` doubles as the ownership check `complete()` itself enforces
    (empty string for a manager means "no restriction", the exact same value that scopes their
    own `list()` above to "everyone")."""
    tenant = _tenant(principal)
    scope = _scope(principal)
    svc = request.app.state.container.mobile_requests
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
    Same manager-vs-own-assignment scoping as `complete` above."""
    tenant = _tenant(principal)
    scope = _scope(principal)
    svc = request.app.state.container.mobile_requests
    try:
        row = await svc.no_show(tenant, request_id, expected_assignee=scope.assigned_to_filter)
    except MobileRequestError as exc:
        _refuse(exc)
    await request.app.state.auditor.record(
        "mobile_request.no_show", actor=principal.subject, tenant=tenant,
        resource=f"mobile_request:{request_id}",
        ip=request.client.host if request.client else "")
    return row.public()
