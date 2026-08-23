# =============================================================================
# affiliate-service — the unauthenticated routes («بوابة القبول», spec §2)
# -----------------------------------------------------------------------------
# Mirrors operations' own api/v1/signup.py exactly on purpose: same shape, same reasons.
#
#   /apply is the ONLY door with no token — it creates the request the token would later come
#   from, so it cannot itself require one. Rate-limited, and refusals answer with a body an
#   applicant can act on rather than a stripped 400 (see errors.py's own reasoning on that strip).
#   A referral_code applicant proves he owns the number he is applying with via /request-otp +
#   /apply's own `code` — see onboarding.py's own note on the two dormant-by-default flags.
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
    #: Optional, never required — a pasted résumé/portfolio link.
    cv_url: str = Field(default="", max_length=500)
    #: The phone-ownership code — empty unless onboarding's own AFFILIATE_REQUIRE_OTP is on, in
    #: which case apply() itself refuses without a real one. See /request-otp below.
    code: str = Field(default="", max_length=16)


class SignInIn(BaseModel):
    phone: str = Field(min_length=6, max_length=32)
    password: str = Field(min_length=1, max_length=256)
    code: str = Field(default="", max_length=16)


class RequestOtpIn(BaseModel):
    phone: str = Field(min_length=6, max_length=32)


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
            referral_code=body.referral_code, agreed=body.agreed,
            cv_url=body.cv_url, code=body.code)
    except OnboardingRefused as exc:
        return _refused(exc)
    return {"ok": True, **out}


@router.post("/apply/request-otp", dependencies=[Depends(rate_limit)])
async def request_otp(request: Request, body: RequestOtpIn) -> Any:
    try:
        out = await _svc(request).request_otp(body.phone)
    except OnboardingRefused as exc:
        return _refused(exc)
    return {"ok": True, **out}


@router.post("/signin", dependencies=[Depends(rate_limit)])
async def sign_in(request: Request, body: SignInIn) -> Any:
    try:
        return await _svc(request).sign_in(body.phone, body.password, body.code)
    except OnboardingRefused as exc:
        return _refused(exc)
