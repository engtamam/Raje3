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

import time

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.auth import Principal, require_user
from app.api.authz import require_capability
from app.api.deps import get_guard
from app.api.ratelimit import rate_limit
from app.core.booking_assignment import ACTOR as ACTOR_CREATED_BY
from app.core.pricing_schedule import pending as pending_pricing_changes
from app.core.shop_impact_report import report as shop_impact_report

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


@router.get("/assistant/features", dependencies=[Depends(rate_limit)])
async def assistant_features(principal: Principal = Depends(require_user)) -> dict:
    """«ايش فيه هذا التطبيق فعلاً» — the app-store card's own content (core/features.py).

    `require_user` ALONE, NOT `_PRICING_READ` — this shipped reusing that capability on the
    (wrong) theory that it was the same posture as `/assistant/pricing/current` below. It is not:
    that route reads THIS shop's own billing fact, so it needs to know who the caller's shop even
    is; this one is the SAME static catalog for every caller, tenant or not — identical to how
    bookings/loyalty/campaigns/insights's own `.../features` routes are gated (`require_user`
    only, see bookings' `app/api/v1/features.py` docstring). Found live: an admin/platform token
    (which holds no TENANT-role capability at all — `whatsapp_assistant.pricing_read` is granted
    to a shop's owner/manager role, never to the platform) got 403'd trying to read this from the
    admin panel, rendering the card's own feature list permanently empty there while every other
    app's admin card worked (owner's own screenshot). A shop deciding whether to buy — or an
    operator reviewing what is sold — both just need to be signed in, same as every other catalog
    read on this fleet.
    """
    from app.core.features import public_features

    return {"features": public_features()}


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
    from app.core.ai_unit_pricing import AiUnitPricingConfig

    container = request.app.state.container
    settings = get_settings()
    ai_unit = await AiUnitPricingConfig.from_runtime(container.runtime_config, settings)
    # ONLY THE FIELD A SHOP MAY EVER SEE, same boundary as ai_unit_units_per_halala below — a
    # pending margin/model-cost change is OUR cost basis, never a fact a shop-level `pricing_read`
    # session should read. pending_pricing_changes() itself has no such filter (it is the
    # operator-only route's own data source too), so this route must filter before returning it.
    _SHOP_VISIBLE_PENDING_KEYS = frozenset({"PRICING_AI_UNIT_UNITS_PER_HALALA"})
    upcoming = [{"key": c.key, "value": c.value, "effective_at": c.effective_at}
               for c in await pending_pricing_changes(container.datastore)
               if c.key in _SHOP_VISIBLE_PENDING_KEYS]

    return {
        # THE PLATFORM-WIDE SWITCH (2026-09-19, config.py::AI_ASSISTANT_ENABLED) — every console
        # surface that shows AI-unit balance/pricing already calls this SAME action
        # (AiUnitsGauge.tsx, Wallet.tsx, WhatsAppAssistant.tsx, useAppBilling.ts all read
        # `whatsapp_assistant.pricing_current`), so this is the one place to add the field rather
        # than a second action nobody else calls. The backend already enforces the switch
        # fleet-wide via ToggleGatedLicence with no per-shop repair needed to flip it back; this
        # lets the console hide every AI-units surface while it is off, instead of showing
        # controls for a feature answering nothing right now.
        "ai_enabled": settings.AI_ASSISTANT_ENABLED,
        # THE ONLY AI-UNIT FIELD A SHOP EVER NEEDS TO READ — the fixed halala->unit display scale
        # (core/ai_unit_pricing.py's own note: this NEVER varies by model). Margins/per-model costs
        # are our own cost basis, not a shop-facing fact — never returned here, same "a shop reads
        # a fact about their own subscription, not our internals" boundary this route already draws.
        "ai_unit_units_per_halala": ai_unit.units_per_halala,
        "pending_changes": upcoming,
    }


@router.get("/assistant/growth/my-impact", dependencies=[Depends(rate_limit)])
async def my_impact(request: Request, days: int = 30,
                    principal: Principal = Depends(_PRICING_READ)) -> dict:
    """محلّي's own "أثر الذكاء الاصطناعي" card — THIS SHOP'S OWN numbers only, never a platform
    aggregate (see core/shop_impact_report.py's own module docstring for why that isolation is
    structural here, not a per-route promise). `tenant` is ALWAYS `principal.tenant` — a real shop
    session, unlike the platform-operator routes this reuses under the hood, genuinely carries one.

    Reuses `whatsapp_assistant.pricing_read` rather than minting a narrower capability: both are
    the same family ("an owner/manager reading a fact about their own AI feature"), already granted
    to exactly the two roles (owner, manager) this card is for — see that capability's own note in
    app/manifest.py."""
    days = max(1, min(days, 365))
    if not principal.tenant:
        # A platform-operator token has no tenant claim at all (see whatsapp-assistant's own
        # operator.py note on this exact class of bug) — this route only ever answers for a real
        # shop session, so refuse cleanly rather than compute a meaningless empty report.
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            detail="no tenant on this session — this route is shop-facing only")
    from app.config import get_settings

    container = request.app.state.container
    rep = await shop_impact_report(
        datastore=container.datastore, actor_report=container.booking_actor_report,
        service_catalog=container.service_catalog, package_catalog=container.package_catalog,
        tenant=principal.tenant, created_by=ACTOR_CREATED_BY, days=days, now=int(time.time()),
        ai_enabled=get_settings().AI_ASSISTANT_ENABLED)
    return rep.as_dict()
