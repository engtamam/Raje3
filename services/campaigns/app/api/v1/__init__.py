# =============================================================================
# campaigns — User tier (/api/v1/*, token-authenticated)
# -----------------------------------------------------------------------------
# Every route is protected: Depends(require_user) verifies the Bearer token
# (deny-by-default), require_capability adds fine-grained RBAC, rate_limit
# throttles, and guard.step wraps risky work with CWE pre/post checks.
# The routes below are EXAMPLES — replace with real business routes per service.
# =============================================================================
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.auth import Principal, require_user
from app.api.authz import require_capability
from app.api.deps import get_guard
from app.api.ratelimit import rate_limit

router = APIRouter(prefix="/api/v1", tags=["v1"])

# The child carries its own prefix and this one carries /api/v1. Both carrying it produced
# /api/v1/api/v1/... once already — a 404 on every route, found only by calling one.
from app.api.v1 import campaigns as _campaigns   # noqa: E402
from app.api.v1 import features as _features   # noqa: E402

router.include_router(_campaigns.router)
router.include_router(_features.router)


@router.get("/campaigns/whoami", dependencies=[Depends(rate_limit)])
async def whoami(
    principal: Principal = Depends(require_user),
    guard=Depends(get_guard),
) -> dict:
    # Demonstrate the self-guard: the response is checked for secret leakage
    # (CWE-200/532) before it leaves the service.
    async with guard.step("respond") as step:
        body = {
            "subject": principal.subject,
            "caps": sorted(principal.caps),
            "tenant": principal.tenant,
        }
        step.result = body
    return body


# "/api/v1/admin/ping" (bare, unprefixed) is identical across every service's own scaffold copy of
# this file — one gateway prefix can only point at one upstream, so it was never reachable through
# api-gateway for ANY of them (ci/check_deploy_wiring.py's own guard, run for real, found this).
# "/campaigns/admin/ping" is this service's own answer. Capability changed from the scaffold's
# "admin" (nobody was ever granted it, a second ungoverned name) to "platform.secrets" — the one
# admin_actions.py already declared for this exact action, so enforcement now matches the
# declaration instead of silently diverging from it.
@router.get("/campaigns/admin/ping", dependencies=[Depends(require_capability("platform.secrets"))])
async def admin_ping() -> dict:
    return {"status": "ok"}

# TODO (per service): add real business routes here.
