# =============================================================================
# affiliate-service — what an affiliate does about HIS OWN team, not the platform's
# -----------------------------------------------------------------------------
# NO CAPABILITY GATE HERE, deliberately — and that is not an oversight, it is the same shape as
# operations.hire() (a shop owner needs no platform capability to hire his own staff; the gate is
# "is this his shop", a DATA check, not an RBAC check). Here it is "is this an ACTIVE manager
# affiliate", checked inside onboarding.invite() against the caller's own person_id — a
# capability would answer "may marketers in general invite", which is the wrong question; the
# real one is "is the caller himself a manager", and only a data lookup on his own identity
# answers that honestly.
# =============================================================================
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.api.auth import Principal, require_user
from app.api.ratelimit import rate_limit
from app.core.onboarding import OnboardingRefused
from app.core.payouts import PayoutError

router = APIRouter(prefix="/api/v1/affiliates/me", tags=["affiliates-self"])


class InviteIn(BaseModel):
    phone: str = Field(min_length=6, max_length=32)
    name: str = Field(min_length=1, max_length=200)


class PayoutMethodIn(BaseModel):
    channel: str = Field(min_length=1, max_length=32)
    channel_name: str = Field(default="", max_length=100)
    account_ref: str = Field(min_length=1, max_length=200)


def _svc(request: Request):
    return request.app.state.container.onboarding


def _refused(exc: OnboardingRefused) -> JSONResponse:
    body: dict[str, Any] = {"ok": False, "message": str(exc)}
    if getattr(exc, "reason", ""):
        body["reason"] = exc.reason
    status_code = 403 if exc.reason in ("not_an_active_affiliate", "managers_only") else 400
    return JSONResponse(status_code=status_code, content=body)


def _payout_refused(exc: PayoutError) -> JSONResponse:
    body: dict[str, Any] = {"ok": False, "message": str(exc)}
    if getattr(exc, "reason", ""):
        body["reason"] = exc.reason
    return JSONResponse(status_code=400, content=body)


async def _my_affiliate_id(request: Request, principal: Principal) -> str:
    """404s the route the same way `me`/`commissions` already do — never a silent empty string
    that would let a caller with no affiliate row somehow query payout data for `affiliate_id:
    ""`, which every store lookup below would then simply find nothing for and answer as if it
    were a legitimate empty account rather than "you are not one at all"."""
    affiliate = await _svc(request).me(principal.subject)
    if affiliate is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_AN_AFFILIATE")
    return affiliate["id"]


@router.get("", dependencies=[Depends(rate_limit)])
async def me(request: Request, principal: Principal = Depends(require_user)) -> dict:
    """Who I am, and — since his own `id` IS his referral code (spec §1) — everything the console
    needs to show him his own link: `?aff=<id>` for a shop, `?ref=<id>` for another marketer
    applying under him."""
    out = await _svc(request).me(principal.subject)
    if out is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_AN_AFFILIATE")
    return out


@router.post("/invite", dependencies=[Depends(rate_limit)])
async def invite(request: Request, body: InviteIn,
                 principal: Principal = Depends(require_user)) -> Any:
    """A manager names somebody he wants on his team — still goes through the admin gate (spec
    §2); see onboarding.invite() for the whole reasoning. `principal.subject` is the token's
    `sub`, which — for this service's tenant — IS the identity person_id the affiliate row was
    minted under; there is no separate lookup table to keep in step."""
    try:
        out = await _svc(request).invite(
            inviter_person_id=principal.subject, phone=body.phone, name=body.name)
    except OnboardingRefused as exc:
        return _refused(exc)
    return {"ok": True, **out}


@router.get("/commissions", dependencies=[Depends(rate_limit)])
async def commissions(request: Request, principal: Principal = Depends(require_user)) -> dict:
    """His own commissions — conversion and renewal alike (core/commission.py). The read ITSELF
    advances any commission whose hold has lapsed from pending to confirmed
    (CommissionEngine.confirm_if_due, same lazy-check shape as everywhere else in this service) —
    so a marketer looking at his own dashboard is exactly the moment that matters, never a sweep
    running on nobody's clock."""
    onboarding = _svc(request)
    affiliate = await onboarding.me(principal.subject)
    if affiliate is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_AN_AFFILIATE")
    engine = request.app.state.container.commissions
    rows = await engine.of_affiliate(affiliate["id"])
    confirmed = [await engine.confirm_if_due(r.id) for r in rows]
    return {"commissions": [c.to_dict() for c in confirmed if c is not None]}


@router.put("/payout-method", dependencies=[Depends(rate_limit)])
async def set_payout_method(request: Request, body: PayoutMethodIn,
                            principal: Principal = Depends(require_user)) -> Any:
    """spec §5, extended (Tamam, 2026-08-20): a bank IBAN or an intermediary payment platform
    (بحر or any other — `channel_name` is free text so a new one never needs a code change).
    Setting this does NOT touch any withdrawal already requested — see WithdrawalRequest's own
    note on why the method is copied, not re-read, at request time."""
    affiliate_id = await _my_affiliate_id(request, principal)
    try:
        out = await request.app.state.container.payouts.set_payout_method(
            affiliate_id, channel=body.channel, channel_name=body.channel_name,
            account_ref=body.account_ref)
    except PayoutError as exc:
        return _payout_refused(exc)
    return {"ok": True, **out}


@router.get("/balance", dependencies=[Depends(rate_limit)])
async def balance(request: Request, principal: Principal = Depends(require_user)) -> dict:
    affiliate_id = await _my_affiliate_id(request, principal)
    return await request.app.state.container.payouts.balance(affiliate_id)


@router.post("/withdrawals", dependencies=[Depends(rate_limit)])
async def request_withdrawal(request: Request,
                             principal: Principal = Depends(require_user)) -> Any:
    affiliate_id = await _my_affiliate_id(request, principal)
    try:
        out = await request.app.state.container.payouts.request_withdrawal(affiliate_id)
    except PayoutError as exc:
        return _payout_refused(exc)
    return {"ok": True, **out}


@router.get("/withdrawals", dependencies=[Depends(rate_limit)])
async def my_withdrawals(request: Request,
                         principal: Principal = Depends(require_user)) -> dict:
    affiliate_id = await _my_affiliate_id(request, principal)
    rows = await request.app.state.container.payouts.of_affiliate(affiliate_id)
    return {"withdrawals": [r.to_dict() for r in rows]}
