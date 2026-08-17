"""The two unauthenticated routes in this service — the only two, and they earn it.

EVERY OTHER ROUTE HERE REQUIRES A TOKEN. These cannot: one creates the account the token would
come from, and the other exchanges a phone and a password for it. So they are rate-limited, they
say the same thing to every failure, and they are kept in their own module rather than mixed in
with routes a reader would assume are guarded.

AND THEY ARE NOT IN THE ACTION CATALOGUE, deliberately. The catalogue is fetched WITH a token and
lists what the holder may do; an action that exists precisely because there is no token yet cannot
appear in it. Declaring them anyway would put two paths in a list the console reads as "things a
signed-in owner can do" — and the console would then be able to call sign-up on itself.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.api.ratelimit import rate_limit
from app.core.signup import NewShop, SignupRefused

router = APIRouter(prefix="/signup", tags=["signup"])


class OpenShopIn(BaseModel):
    """The four values, and nothing else — see core/signup.py for why each one is on the list."""

    phone: str = Field(min_length=6, max_length=32)
    password: str = Field(min_length=1, max_length=256)
    shop_name: str = Field(min_length=1, max_length=200)


class CodeIn(BaseModel):
    phone: str = Field(min_length=6, max_length=32)


class ProveIn(BaseModel):
    phone: str = Field(min_length=6, max_length=32)
    code: str = Field(min_length=3, max_length=16)


class ClaimIn(BaseModel):
    """The owner opening the shop his till company invited him to.

    HE CHOOSES THE PASSWORD, and that is the whole shape of this flow — see core/claim.py. Nobody
    else ever holds it, so nobody else can connect his WhatsApp or subscribe him or message his
    customers in his name.
    """

    phone: str = Field(min_length=6, max_length=32)
    code: str = Field(min_length=3, max_length=16)
    password: str = Field(min_length=1, max_length=256)


class SignInIn(BaseModel):
    phone: str = Field(min_length=6, max_length=32)
    password: str = Field(min_length=1, max_length=256)
    code: str = Field(default="", max_length=16)


def _svc(request: Request):
    return request.app.state.container.signup


def _refused(exc: SignupRefused) -> JSONResponse:
    # RETURNED, NEVER RAISED. The platform's error handler strips an HTTPException's detail, so a
    # raised refusal reaches the owner as a bare status with the one sentence that tells him what
    # to do thrown away. 400 with a body he can read.
    #
    # `reason` rides along when there is one, so the console can act rather than only report — see
    # SignupRefused. It is omitted otherwise rather than sent empty: a field that is always there
    # invites a screen to branch on the absence of a value it never had.
    body: dict[str, Any] = {"ok": False, "message": str(exc)}
    if getattr(exc, "reason", ""):
        body["reason"] = exc.reason
    return JSONResponse(status_code=400, content=body)


@router.post("", dependencies=[Depends(rate_limit)])
async def open_shop(request: Request, body: OpenShopIn) -> Any:
    try:
        out = await _svc(request).open_shop(NewShop(
            phone=body.phone, password=body.password,
            shop_name=body.shop_name))
    except SignupRefused as exc:
        return _refused(exc)
    # NO TOKEN IN THIS RESPONSE. The account exists; the console signs in with it immediately,
    # through the same door every later sign-in uses. Minting here would be a second mint path to
    # keep correct for ever, and the first one is one call away.
    #
    # `stamp_error` IS DROPPED HERE, NEVER FORWARDED (ك-4). It is an English sentence about a
    # partner company's key — a mistake the owner did not make and cannot fix — and `open_shop`
    # already told telemetry so an operator can. An owner shown it learns nothing actionable and a
    # partner shown nothing learns even less; the fix is that somebody who CAN act, does.
    out.pop("stamp_error", None)
    return {"ok": True, **out}


@router.post("/code", dependencies=[Depends(rate_limit)])
async def send_code(request: Request, body: CodeIn) -> Any:
    try:
        return await _svc(request).send_code(body.phone)
    except SignupRefused as exc:
        return _refused(exc)


@router.post("/verify", dependencies=[Depends(rate_limit)])
async def prove(request: Request, body: ProveIn) -> Any:
    """Spend the code HERE rather than at identity, so the verdict is written down.

    The browser used to call identity's /otp/verify directly. identity consumes the code and stores
    no verdict, and our sign-in never asked — so an owner who closed the tab on the OTP screen and
    came back through the front door was let in. The step was a screen, not a rule.
    """
    try:
        return await _svc(request).prove(body.phone, body.code)
    except SignupRefused as exc:
        return _refused(exc)


@router.post("/claim", dependencies=[Depends(rate_limit)])
async def claim(request: Request, body: ClaimIn) -> Any:
    """Open the shop a till company invited. Public — he has no token yet, that is the point.

    The same saga a shop that found us on its own runs, with the integration flag and
    the partner stamp taken from the INVITATION rather than from this request: a body that could
    name its own partner key would be a body that could redirect somebody else's commission.
    """
    try:
        out = await _svc(request).claim(body.phone, body.code, body.password)
    except SignupRefused as exc:
        return _refused(exc)
    # SAME DROP AS `open_shop` (ك-4), and the more important of the two: THIS is the route a
    # mistyped partner key actually reaches, since a till-company invitation is the one path that
    # carries one at all. See `open_shop` above for why the owner never sees it.
    out.pop("stamp_error", None)
    return out


@router.post("/signin", dependencies=[Depends(rate_limit)])
async def sign_in(request: Request, body: SignInIn) -> Any:
    try:
        return await _svc(request).sign_in(body.phone, body.password, body.code)
    except SignupRefused as exc:
        return _refused(exc)
