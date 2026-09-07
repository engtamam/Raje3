# =============================================================================
# whatsapp-assistant — User tier (/api/v1/*, token-authenticated)
# -----------------------------------------------------------------------------
# This service is internal/operator-facing (a WhatsApp bot has no end-user UI of
# its own) — kept minimal: just the platform whoami probe every service exposes.
#
# operator.py NOW EXISTS (app/api/v1/operator.py, mounted separately in main.py, its own
# /api/v1/assistant/operator prefix) — secrets (ASSISTANT_MODEL_PROJECT/ASSISTANT_MODEL_CREDENTIAL)
# AND, since 2026-09-07, /operator/config for app/runtime_policy.py's declared knobs
# (ASSISTANT_MODEL_NAME, SOFT_DECLINE_THRESHOLD, MAX_CAROUSEL_CARDS). Every OTHER setting is still
# deploy-time env — add a runtime_policy.py entry only in the same change that wires its own read.
#
# /assistant/pricing/current JOINED 2026-09-07 — THE FIRST REAL CUSTOMER-FACING ROUTE, and the
# gateway prefix (deploy/services/api-gateway.values.yaml) was added in the same change: a shop's
# own app card (المتجر) needs to show the AI feature's real price, and — the whole point of
# core/pricing_schedule.py — any change already scheduled but not yet in effect, with the date it
# lands, so an owner can never say "ما كنت أعرف" about a price that changed under him. Gated on
# `whatsapp_assistant.pricing_read` (deploy/seed/roles.json + services/operations/data/
# roles.seed.json — owner and manager, the same two roles that hold `billing.self`), never
# `platform.config`: this is a shop reading a fact about their own subscription, not an operator
# changing platform policy.
# =============================================================================
from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.auth import Principal, require_user
from app.api.authz import require_capability
from app.api.deps import get_guard
from app.api.ratelimit import rate_limit
from app.core.pricing import PricingConfig
from app.core.pricing_schedule import pending as pending_pricing_changes

router = APIRouter(prefix="/api/v1", tags=["v1"])

_PRICING_READ = require_capability("whatsapp_assistant.pricing_read")


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


@router.get("/assistant/pricing/current", dependencies=[Depends(rate_limit)])
async def pricing_current(request: Request,
                          principal: Principal = Depends(_PRICING_READ)) -> dict:
    """What the AI feature costs right now, and what it is ABOUT to cost if a change is already
    scheduled — the app card's own read. `principal.tenant` is accepted but not otherwise used to
    scope the answer: pricing is platform-wide (see core/pricing_schedule.py's own docstring), the
    same fact every shop sees. The capability dependency is what makes this a real shop session
    rather than an open read, not a per-tenant value.
    """
    from app.config import get_settings

    container = request.app.state.container
    settings = get_settings()
    current = await PricingConfig.from_runtime(container.runtime_config, settings)
    # EVERY PENDING CHANGE, NOT JUST A STRATEGY SWAP — a rate-only change (the far more common
    # case: the strategy stays "usage_based", only PRICING_USAGE_HALALAS_PER_1K_TOKENS moves) is
    # exactly as much "the price is about to change" as a strategy change is. The card decides
    # which of these keys it actually displays and matches against this list itself — this route's
    # job is to hide nothing that is genuinely coming, not to guess which one the UI cares about.
    upcoming = [{"key": c.key, "value": c.value, "effective_at": c.effective_at}
               for c in await pending_pricing_changes(container.datastore)]

    return {
        "strategy": current.strategy,
        "usage_halalas_per_1k_tokens": current.usage_halalas_per_1k_tokens,
        "usage_halalas_per_conversation": current.usage_halalas_per_conversation,
        "tier_base_halalas": current.tier_base_halalas,
        "tier_included_conversations": current.tier_included_conversations,
        "tier_overage_halalas_per_conversation": current.tier_overage_halalas_per_conversation,
        "addon_flat_halalas": current.addon_flat_halalas,
        "pending_changes": upcoming,
    }
