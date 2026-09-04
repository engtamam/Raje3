# =============================================================================
# secrets-admin — User tier (/api/v1/*, token-authenticated)
# -----------------------------------------------------------------------------
# Every route is protected: Depends(require_user) verifies the Bearer token
# (deny-by-default), require_capability adds fine-grained RBAC, rate_limit
# throttles.
#
# NO /api/v1/admin/ping HERE, and its absence is a decision rather than a trim. The scaffold ships
# one gated on a capability called "admin" that nothing in this product grants — so it answered 403
# to everybody while being declared as a route the console could show. /whoami answers the question
# it was there for (is my token accepted) and actually works.
# =============================================================================
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.auth import Principal, require_user
from app.api.deps import get_guard
from app.api.ratelimit import rate_limit
from app.api.v1.secrets import router as secrets_router

router = APIRouter(prefix="/api/v1", tags=["v1"])


@router.get("/secrets/whoami", dependencies=[Depends(rate_limit)])
async def whoami(
    principal: Principal = Depends(require_user),
    guard=Depends(get_guard),
) -> dict:
    # The self-guard: the response is checked for secret leakage (CWE-200/532) before it leaves
    # the service — which matters more here than anywhere else on the product.
    async with guard.step("respond") as step:
        body = {
            "subject": principal.subject,
            "caps": sorted(principal.caps),
            "tenant": principal.tenant,
        }
        step.result = body
    return body


router.include_router(secrets_router)
