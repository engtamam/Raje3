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

from fastapi import APIRouter, Depends

from app.api.auth import Principal, require_user
from app.api.deps import get_guard
from app.api.ratelimit import rate_limit
from app.api.v1.field import router as field_router
from app.api.v1.partner import router as partner_router
from app.api.v1.subscription import router as subscription_router
from app.api.v1.platform import router as platform_router
from app.api.v1.staff import router as staff_router

router = APIRouter(prefix="/api/v1", tags=["v1"])


@router.get("/whoami", dependencies=[Depends(rate_limit)])
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


# Mounted on their own prefixes rather than under this one: /api/v1/field/* and /api/v1/staff/*
# read as what they are — the shop floor and the back office — and a gateway can route or rate-limit
# them differently without parsing paths.
router.include_router(field_router)
router.include_router(staff_router)
# Ours, not an establishment's: platform.operations gates every route on it.
router.include_router(platform_router)
router.include_router(partner_router)
router.include_router(subscription_router)
