# =============================================================================
# whatsapp-assistant — User tier (/api/v1/*, token-authenticated)
# -----------------------------------------------------------------------------
# This service is internal/operator-facing (a WhatsApp bot has no end-user UI of
# its own) — kept minimal: just the platform whoami probe every service exposes.
# =============================================================================
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.auth import Principal, require_user
from app.api.authz import require_capability
from app.api.deps import get_guard
from app.api.ratelimit import rate_limit

router = APIRouter(prefix="/api/v1", tags=["v1"])


@router.get("/whoami", dependencies=[Depends(rate_limit)])
async def whoami(principal: Principal = Depends(require_user), guard=Depends(get_guard)) -> dict:
    async with guard.step("respond") as step:
        body = {"subject": principal.subject, "caps": sorted(principal.caps),
                "tenant": principal.tenant}
        step.result = body
    return body


@router.get("/admin/ping", dependencies=[Depends(require_capability("admin"))])
async def admin_ping() -> dict:
    return {"status": "ok"}
