# =============================================================================
# affiliate-service — User tier (/api/v1/*, token-authenticated)
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


@router.get("/affiliates/whoami", dependencies=[Depends(rate_limit)])
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
# "/affiliates/admin/ping" matches the gateway prefix this service already answers under
# (/api/v1/affiliates). Capability changed from the scaffold's "admin" (nobody was ever granted
# it, a second ungoverned name) to "platform.secrets", already declared and granted here.
@router.get("/affiliates/admin/ping", dependencies=[Depends(require_capability("platform.secrets"))])
async def admin_ping() -> dict:
    return {"status": "ok"}

# TODO (per service): add real business routes here.
