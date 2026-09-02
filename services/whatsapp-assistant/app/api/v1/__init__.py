# =============================================================================
# whatsapp-assistant — User tier (/api/v1/*, token-authenticated)
# -----------------------------------------------------------------------------
# This service is internal/operator-facing (a WhatsApp bot has no end-user UI of
# its own) — kept minimal: just the platform whoami probe every service exposes.
#
# operator.py NOW EXISTS (app/api/v1/operator.py, mounted separately in main.py, its own
# /api/v1/operator prefix) — SECRETS ONLY, no /operator/config: GEMINI_API_KEY turned out to be
# exactly the runtime-tunable credential this file's old note said would justify adding one. Every
# OTHER knob is still deploy-time env; do not add /operator/config until a real one exists.
#
# NOT ROUTED THROUGH api-gateway EITHER, for the same reason: deploy/services/api-gateway.
# values.yaml's prefix list has no `/api/v1/whatsapp-assistant` entry, so /whoami and /admin/ping
# above are reachable service-to-service only, never from a browser. Correct today — this
# service's only live input is notification-service's bus event (see main.py's lifespan
# subscription), not a customer-facing screen. Add the gateway prefix the day a real screen calls
# this service directly.
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
