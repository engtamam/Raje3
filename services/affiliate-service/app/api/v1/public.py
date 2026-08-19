# =============================================================================
# affiliate-service — the two unauthenticated routes («بوابة القبول», spec §2)
# -----------------------------------------------------------------------------
# Mirrors operations' own api/v1/signup.py exactly on purpose: same shape, same reasons.
#
#   /apply is the ONLY door with no token — it creates the request the token would later come
#   from, so it cannot itself require one. Rate-limited, and refusals answer with a body an
#   applicant can act on rather than a stripped 400 (see errors.py's own reasoning on that strip).
#
#   /signin is ordinary sign-in with nothing invented here: identity does every real check
#   (password, lockout, MFA). This file only resolves WHICH tenant, since an applicant does not
#   and should not know the tenant id.
#
# NEITHER APPEARS IN THE ACTION CATALOGUE for the same reason operations' own do not: a catalogue
# is fetched WITH a token and lists what the holder may already do, and a route that exists
# precisely because there is no token yet has no business in that list.
# =============================================================================
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.api.ratelimit import rate_limit
from app.core.onboarding import OnboardingRefused

router = APIRouter(prefix="/api/v1/affiliates", tags=["affiliates-public"])


class ApplyIn(BaseModel):
    phone: str = Field(min_length=6, max_length=32)
    name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=1, max_length=256)
    #: The referring affiliate's id — a manager applies with none, a promoter with his manager's
    #: (or another promoter's, per spec §1's tree). Never trusted as a role claim by itself; see
    #: onboarding.apply() for the lookup that actually decides the role.
    referral_code: str = Field(default="", max_length=64)
    #: spec §2 — required True or the application is refused. A checkbox the console renders,
    #: never assumed on the applicant's behalf.
    agreed: bool = False


class SignInIn(BaseModel):
    phone: str = Field(min_length=6, max_length=32)
    password: str = Field(min_length=1, max_length=256)
    code: str = Field(default="", max_length=16)


class AcceptInviteIn(BaseModel):
    token: str = Field(min_length=1, max_length=512)
    password: str = Field(min_length=1, max_length=256)
    agreed: bool = False


def _svc(request: Request):
    return request.app.state.container.onboarding


def _refused(exc: OnboardingRefused) -> JSONResponse:
    body: dict[str, Any] = {"ok": False, "message": str(exc)}
    if getattr(exc, "reason", ""):
        body["reason"] = exc.reason
    return JSONResponse(status_code=400, content=body)


@router.post("/apply", dependencies=[Depends(rate_limit)])
async def apply(request: Request, body: ApplyIn) -> Any:
    try:
        out = await _svc(request).apply(
            phone=body.phone, name=body.name, password=body.password,
            referral_code=body.referral_code, agreed=body.agreed)
    except OnboardingRefused as exc:
        return _refused(exc)
    return {"ok": True, **out}


@router.post("/signin", dependencies=[Depends(rate_limit)])
async def sign_in(request: Request, body: SignInIn) -> Any:
    try:
        return await _svc(request).sign_in(body.phone, body.password, body.code)
    except OnboardingRefused as exc:
        return _refused(exc)


@router.post("/accept-invite", dependencies=[Depends(rate_limit)])
async def accept_invite(request: Request, body: AcceptInviteIn) -> Any:
    """The other half of a manager's invite() — no token yet, same reason /apply has none: the
    invited person holds nothing identity or we would authenticate with until this call sets his
    own password."""
    try:
        out = await _svc(request).accept_invite(
            token=body.token, password=body.password, agreed=body.agreed)
    except OnboardingRefused as exc:
        return _refused(exc)
    return {"ok": True, **out}
