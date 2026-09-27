"""Phase 4 of docs/خطة-تطبيق-الإحالة-والمسوقين-2026-09-27.md — the shop's own admin surface for
its marketer/influencer tier: add an affiliate directly by phone, pause/resume one, and record a
manual settlement. See core/affiliates.py's own module docstring for the full design (no request/
approval step, never both roles at once, settlement is bookkeeping only — never money movement).

`operations.manage` GATES EVERY WRITE HERE, same door `staff.py`'s own mutual-benefit propose/
accept routes use — adding an affiliate and recording a settlement are both an owner/manager-level
act, never a routine per-visit one the way granting a coupon at the counter is. Reads use
`operations.read`, same split `staff.py`'s referral-partnership routes already draw.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.api.auth import Principal
from app.api.authz import require_capability
from app.api.ratelimit import rate_limit
from app.api.subscribed import subscribed_write
from app.core.affiliates import AffiliateError

router = APIRouter(prefix="/affiliates", tags=["affiliates"])

_MANAGE = require_capability("operations.manage")
_READ = require_capability("operations.read")


def _tenant(principal: Principal) -> str:
    return principal.tenant or ""


def _refuse(reason: str, *, status_code: int = status.HTTP_400_BAD_REQUEST) -> JSONResponse:
    return JSONResponse({"error": "BAD_REQUEST", "reason": reason}, status_code=status_code)


def _public(affiliate: Any) -> dict:
    return {
        "id": affiliate.id, "phone": affiliate.phone, "code": affiliate.code,
        "discount_percent": affiliate.discount_percent, "reward_type": affiliate.reward_type,
        "reward_params": affiliate.reward_params, "active": affiliate.active,
        "created_at": affiliate.created_at, "unsettled_points": affiliate.unsettled_points,
        "total_earned_points": affiliate.total_earned_points,
    }


class AffiliateIn(BaseModel):
    phone: str = Field(min_length=3, max_length=32)
    code: str = Field(min_length=1, max_length=16)
    discount_percent: int = Field(ge=1, le=99)
    reward_type: str = Field(min_length=1, max_length=32)
    reward_params: dict = Field(default_factory=dict)


@router.post("", dependencies=[Depends(subscribed_write), Depends(rate_limit)])
async def add_affiliate(request: Request, body: AffiliateIn,
                        principal: Principal = Depends(_MANAGE)) -> Any:
    if not principal.tenant:
        return _refuse("هذا الاعتماد غير مرتبط بمنشأة.", status_code=status.HTTP_403_FORBIDDEN)
    tenant = _tenant(principal)
    affiliates = request.app.state.container.affiliates
    try:
        affiliate = await affiliates.add(
            tenant, phone=body.phone, code=body.code, discount_percent=body.discount_percent,
            reward_type=body.reward_type, reward_params=body.reward_params)
    except AffiliateError as exc:
        return _refuse(str(exc))
    await request.app.state.auditor.record(
        "affiliate.added", actor=principal.subject, tenant=tenant,
        resource=f"affiliate:{affiliate.id}", ip=request.client.host if request.client else "")
    return _public(affiliate)


@router.get("", dependencies=[Depends(rate_limit)])
async def list_affiliates(request: Request, principal: Principal = Depends(_READ)) -> dict:
    tenant = _tenant(principal)
    rows = await request.app.state.container.affiliates.list(tenant)
    return {"affiliates": [_public(r) for r in rows]}


@router.get("/{affiliate_id}", dependencies=[Depends(rate_limit)])
async def get_affiliate(request: Request, affiliate_id: str,
                        principal: Principal = Depends(_READ)) -> Any:
    tenant = _tenant(principal)
    affiliate = await request.app.state.container.affiliates.get(tenant, affiliate_id)
    if affiliate is None:
        return _refuse("المسوّق غير موجود", status_code=status.HTTP_404_NOT_FOUND)
    return _public(affiliate)


class ActiveIn(BaseModel):
    active: bool


@router.put("/{affiliate_id}/active",
           dependencies=[Depends(subscribed_write), Depends(rate_limit)])
async def set_affiliate_active(request: Request, affiliate_id: str, body: ActiveIn,
                               principal: Principal = Depends(_MANAGE)) -> Any:
    tenant = _tenant(principal)
    affiliates = request.app.state.container.affiliates
    try:
        affiliate = await affiliates.set_active(tenant, affiliate_id, active=body.active)
    except AffiliateError as exc:
        return _refuse(str(exc), status_code=status.HTTP_404_NOT_FOUND)
    await request.app.state.auditor.record(
        "affiliate.status_changed", actor=principal.subject, tenant=tenant,
        resource=f"affiliate:{affiliate.id}", ip=request.client.host if request.client else "")
    return _public(affiliate)


class SettleIn(BaseModel):
    # None (omitted) means "settle the entire current balance" — see core/affiliates.py::settle's
    # own docstring for why a full settlement is the default shape, not a special case of it.
    points: int | None = Field(default=None, ge=1)
    note: str = Field(default="", max_length=500)


@router.post("/{affiliate_id}/settle",
            dependencies=[Depends(subscribed_write), Depends(rate_limit)])
async def settle_affiliate(request: Request, affiliate_id: str, body: SettleIn,
                          principal: Principal = Depends(_MANAGE)) -> Any:
    """Record a settlement the owner already carried out OUTSIDE this system (cash, a bank
    transfer — plan doc §5's own "بلا أي تدخل مالي"). This route moves no money and calls no
    payment rail; it only decrements the running balance and appends an immutable audit row."""
    tenant = _tenant(principal)
    affiliates = request.app.state.container.affiliates
    try:
        affiliate, record = await affiliates.settle(
            tenant, affiliate_id, points=body.points, note=body.note, actor=principal.subject)
    except AffiliateError as exc:
        # A settlement can be refused for TWO different reasons an owner reads very differently:
        # the affiliate itself does not exist (404), or the requested amount does not fit the
        # current balance (400, a real correction to make, not a missing resource).
        status_code = (status.HTTP_404_NOT_FOUND if "غير موجود" in str(exc)
                       else status.HTTP_400_BAD_REQUEST)
        return _refuse(str(exc), status_code=status_code)
    await request.app.state.auditor.record(
        "affiliate.settlement_recorded", actor=principal.subject, tenant=tenant,
        resource=f"affiliate_settlement:{record.id}",
        ip=request.client.host if request.client else "")
    return {"affiliate": _public(affiliate),
           "settlement": {"id": record.id, "points_settled": record.points_settled,
                          "full": record.full, "note": record.note, "actor": record.actor,
                          "created_at": record.created_at}}


@router.get("/{affiliate_id}/settlements", dependencies=[Depends(rate_limit)])
async def list_affiliate_settlements(request: Request, affiliate_id: str,
                                    principal: Principal = Depends(_READ)) -> dict:
    tenant = _tenant(principal)
    affiliates = request.app.state.container.affiliates
    affiliate = await affiliates.get(tenant, affiliate_id)
    if affiliate is None:
        return _refuse("المسوّق غير موجود", status_code=status.HTTP_404_NOT_FOUND)
    rows = await affiliates.list_settlements(tenant, affiliate_id)
    return {"settlements": [{"id": r.id, "points_settled": r.points_settled, "full": r.full,
                             "note": r.note, "actor": r.actor, "created_at": r.created_at}
                            for r in rows]}
