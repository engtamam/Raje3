# =============================================================================
# error-collector — User tier (/api/v1/*, token-authenticated)
# -----------------------------------------------------------------------------
# Every route is protected: Depends(require_user) verifies the Bearer token
# (deny-by-default), require_capability adds fine-grained RBAC, rate_limit
# throttles, and guard.step wraps risky work with CWE pre/post checks.
# The signal routes live in signals.py and are mounted onto this router at the bottom of the
# file, so they inherit the /api/v1 prefix from one place.
# =============================================================================
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.auth import Principal, require_user
from app.api.authz import require_capability
from app.api.deps import get_guard
from app.api.ratelimit import rate_limit
from app.api.v1.signals import router as signals_router

router = APIRouter(prefix="/api/v1", tags=["v1"])


@router.get("/signals/whoami", dependencies=[Depends(rate_limit)])
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


@router.get("/signals/admin/ping", dependencies=[Depends(require_capability("platform.observability"))])
async def admin_ping() -> dict:
    """What a client calls to confirm its token is accepted at all.

    KEPT FROM THE SCAFFOLD, AND RE-GATED. The generated route required a bare `admin` capability
    that this platform does not issue — nobody holds it, so the route was permanently unreachable
    while looking perfectly wired. It now requires the same capability the stream does, which is
    the honest answer to «is my token good for this service?».

    "/api/v1/admin/ping" (bare, unprefixed) is identical across every service's own scaffold copy
    of this file and unreachable through GATEWAY_ROUTES, which routes by service-specific prefix
    — "/signals/admin/ping" is this service's own answer, the same fix every other service already
    made (see loyalty's own api/v1/__init__.py for the same note).
    """
    return {"status": "ok"}


router.include_router(signals_router)
