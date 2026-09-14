# =============================================================================
# operations — User tier (/api/v1/*, token-authenticated)
# -----------------------------------------------------------------------------
# Every route is protected: require_user verifies the Bearer token (deny-by-default),
# require_capability adds fine-grained RBAC, rate_limit throttles.
#
# The real surface lives in field.py and staff.py. This module only aggregates them and keeps
# /whoami, which is the one route worth having when diagnosing a token: it answers "who does this
# platform think you are, and for which establishment" in one call, and that question is the first
# one asked whenever an authorisation looks wrong.
# =============================================================================
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.api.auth import Principal, require_user
from app.api.deps import get_guard
from app.api.ratelimit import rate_limit
from app.core.stores import AccountSettingsStore, OperatorStore
from app.api.v1.field import router as field_router
from app.api.v1.partner import router as partner_router
from app.api.v1.subscription import router as subscription_router
from app.api.v1.connect import router as connect_router
from app.api.v1.signup import router as signup_router
from app.api.v1.till import router as till_router
from app.api.v1.platform import router as platform_router
from app.api.v1.salla import router as salla_router
from app.api.v1.staff import router as staff_router

router = APIRouter(prefix="/api/v1", tags=["v1"])


@router.get("/operations/whoami", dependencies=[Depends(rate_limit)])
async def whoami(
    principal: Principal = Depends(require_user),
    guard=Depends(get_guard),
) -> dict:
    # The self-guard checks the response for secret leakage (CWE-200/532) before it leaves.
    async with guard.step("respond") as step:
        body = {
            "subject": principal.subject,
            "caps": sorted(principal.caps),
            "tenant": principal.tenant,
        }
        step.result = body
    return body


_VALID_LOCALES = {"ar", "en", "ur", "ha", "fil", "bn"}


class LocaleIn(BaseModel):
    locale: str = Field(min_length=2, max_length=8)


# THE ACCOUNT'S OWN LANGUAGE — PLATFORM-WIDE, ANY LOGGED-IN ACCOUNT (owner included).
#
# USED TO LIVE ONLY ON `Operator` (staff.py's `PATCH /staff/operators/me/locale`, still there for
# an existing operator's already-saved value — see that route's own note), which structurally
# excludes the owner: he holds no `Operator` row, so that endpoint 404s `NOT_AN_OPERATOR` for him
# by construction, and the console had to hide its own language switch for him because of it
# (2026-09-11 audit finding). This route needs nothing but `require_user` — no capability, no
# subscription, no Operator row — because a language preference is not a privilege to gate.
@router.get("/account/me/locale", dependencies=[Depends(rate_limit)])
async def get_my_locale(request: Request, principal: Principal = Depends(require_user)) -> dict:
    row = await AccountSettingsStore(request.app.state.container.datastore).get_by_subject(
        principal.tenant, principal.subject)
    locale = (row or {}).get("locale", "")
    if not locale:
        # ONE-TIME CARRY-FORWARD, NOT A SECOND SOURCE OF TRUTH. An operator who already picked a
        # language under the old, Operator-only mechanism (staff.py's `Operator.locale`) must not
        # see it silently reset the day this platform-wide store takes over — read it once as a
        # fallback; nothing here ever writes it back onto the Operator row, and the moment he sets
        # a locale through THIS route, this fallback stops mattering for him.
        op = await OperatorStore(request.app.state.container.datastore).get_by_person(
            principal.tenant, principal.subject)
        locale = op.locale if op else ""
    return {"locale": locale}


@router.patch("/account/me/locale", dependencies=[Depends(rate_limit)])
async def set_my_locale(request: Request, body: LocaleIn,
                        principal: Principal = Depends(require_user)) -> dict:
    if body.locale not in _VALID_LOCALES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "UNKNOWN_LOCALE")
    row = await AccountSettingsStore(request.app.state.container.datastore).set_locale(
        principal.tenant, principal.subject, body.locale)
    return {"locale": row["locale"]}


# Mounted on their own prefixes rather than under this one: /api/v1/field/* and /api/v1/staff/*
# read as what they are — the shop floor and the back office — and a gateway can route or rate-limit
# them differently without parsing paths.
router.include_router(field_router)
router.include_router(staff_router)
# Ours, not an establishment's: platform.operations gates every route on it.
router.include_router(platform_router)
router.include_router(partner_router)
router.include_router(subscription_router)
router.include_router(connect_router)
# The only unauthenticated routes here — see the module for why they are apart.
router.include_router(signup_router)
# The shop's own till, on a machine credential — see the module for the hole this closes.
router.include_router(till_router)
# Salla — two routes need a token (install/status), two cannot (Salla's own callback/webhook);
# see the module for why they share a file anyway.
router.include_router(salla_router)
