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

router = APIRouter(prefix="/api/v1/affiliates/me", tags=["affiliates-self"])


class InviteIn(BaseModel):
    phone: str = Field(min_length=6, max_length=32)
    name: str = Field(min_length=1, max_length=200)


def _svc(request: Request):
    return request.app.state.container.onboarding


def _refused(exc: OnboardingRefused) -> JSONResponse:
    body: dict[str, Any] = {"ok": False, "message": str(exc)}
    if getattr(exc, "reason", ""):
        body["reason"] = exc.reason
    status_code = 403 if exc.reason in ("not_an_active_affiliate", "managers_only") else 400
    return JSONResponse(status_code=status_code, content=body)


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
