"""Mobile/on-the-go service requests — the shop's own review queue. See
`core/mobile_requests.py`'s own module docstring for the full design; this file is only the HTTP
door for the SHOP's side of it (list, accept, reject, complete, no-show, the risk hint at accept
time). The WhatsApp bot's own creation door lives in `api/internal.py`
(`POST /internal/operations/mobile-requests`) — a different tier, a different caller, a
deliberately separate file (same split `till.py`/`staff.py` already keep elsewhere in this
service).

ONE CAPABILITY FOR EVERYTHING HERE, `operations.mobile_requests_manage` — same placement as
`operations.grant_coupon_direct` (owner/manager/supervisor, never a plain field operator):
reviewing a request is an owner-level operational decision, the same class of act as granting a
discount directly, not a visit a field operator records all day.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.api.auth import Principal
from app.api.authz import require_capability
from app.api.ratelimit import rate_limit
from app.core.mobile_requests import MobileRequestError

router = APIRouter(prefix="/staff/mobile-requests", tags=["mobile-requests"])

_MANAGE = require_capability("operations.mobile_requests_manage")


def _tenant(p: Principal) -> str:
    if not p.tenant:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "NO_TENANT")
    return p.tenant


@router.get("", dependencies=[Depends(rate_limit)])
async def list_mobile_requests(request: Request, status_filter: str = "",
                               principal: Principal = Depends(_MANAGE)) -> Any:
    """`?status_filter=pending` for the review queue, `accepted` for what is due a تم/لم يتم
    decision, or empty for everything — the console's own tabs, not three separate routes."""
    tenant = _tenant(principal)
    svc = request.app.state.container.mobile_requests
    rows = await svc.list(tenant, status=status_filter)
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
                                  principal: Principal = Depends(_MANAGE)) -> Any:
    """الموعد تم — records a real Visit (`MobileRequestService.complete`'s own docstring): the
    loyalty points, insights and reminders that follow are automatic, the same as any other
    visit, from here on."""
    tenant = _tenant(principal)
    svc = request.app.state.container.mobile_requests
    try:
        row = await svc.complete(tenant, request_id)
    except MobileRequestError as exc:
        _refuse(exc)
    await request.app.state.auditor.record(
        "mobile_request.completed", actor=principal.subject, tenant=tenant,
        resource=f"mobile_request:{request_id}",
        ip=request.client.host if request.client else "")
    return row.public()


@router.post("/{request_id}/no-show", dependencies=[Depends(rate_limit)])
async def mobile_request_no_show(request: Request, request_id: str,
                                 principal: Principal = Depends(_MANAGE)) -> Any:
    """الموعد لم يتم — never creates a visit; feeds the next customer's own no-show risk read."""
    tenant = _tenant(principal)
    svc = request.app.state.container.mobile_requests
    try:
        row = await svc.no_show(tenant, request_id)
    except MobileRequestError as exc:
        _refuse(exc)
    await request.app.state.auditor.record(
        "mobile_request.no_show", actor=principal.subject, tenant=tenant,
        resource=f"mobile_request:{request_id}",
        ip=request.client.host if request.client else "")
    return row.public()
