# =============================================================================
# coworking — User tier (/api/v1/*, token-authenticated)
# -----------------------------------------------------------------------------
# Every route is protected: Depends(require_user) verifies the Bearer token
# (deny-by-default), require_capability adds fine-grained RBAC, rate_limit
# throttles. The real domain routes live in api/v1/admin.py.
# =============================================================================
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.auth import Principal, require_user
from app.api.authz import require_capability
from app.api.ratelimit import rate_limit

router = APIRouter(prefix="/api/v1", tags=["v1"])


@router.get("/coworking/whoami", dependencies=[Depends(rate_limit)])
async def whoami(principal: Principal = Depends(require_user)) -> dict:
    return {"subject": principal.subject, "caps": sorted(principal.caps),
           "tenant": principal.tenant}


@router.get("/coworking/admin/ping",
           dependencies=[Depends(require_capability("platform.secrets"))])
async def admin_ping() -> dict:
    return {"status": "ok"}
