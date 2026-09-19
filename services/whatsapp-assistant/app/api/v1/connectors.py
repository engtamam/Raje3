"""Meta Business Agent Connectors — the SAME 16 tools core/tools.py already validates and renders
for the LLM-driven path, exposed as their own OpenAPI-described HTTP operations for an external
caller (Meta's own agent infrastructure, calling per Connector, per shop) instead of a tool-call
name/args pair the LLM adapter forwards internally.

WHY A SEPARATE ROUTER, NOT A NEW LLM ADAPTER. core/tools.py's own module docstring already states
the plug-and-play contract: a tool's logic (`_tool_<name>`, its `ToolContext`) never knows or cares
who is calling it — the LLM's tool-call JSON today, Meta's own Connector call tomorrow. This file
is exactly that "tomorrow": a thin translation layer from Meta's per-operation HTTP shape to the
SAME `T.validate_and_render`/`T.execute_confirmed_proposal` every existing path already calls.
NOTHING in core/tools.py, core/conversation.py, or the LLM adapter changes for this to exist.

SECURITY POSTURE — DELIBERATELY THE SAME AS THE LLM-DRIVEN PATH, NEVER WEAKER:
  - A SEPARATE secret (CONNECTOR_API_TOKEN, never INTERNAL_SERVICE_TOKEN) — this caller is
    external (the public internet), not a peer inside our own fleet; see config.py's own note.
  - THE SAME licence check (`container.licence.allowed(tenant)`) every LLM turn already makes
    before touching a tool — a lapsed/never-bought subscription refuses here exactly as it would
    mid-conversation, never bypassed because the caller changed.
  - THE SAME held_apps narrowing (`T.tools_for_held_apps`) — a shop with no bookings app gets
    refused on a booking-tagged Connector call exactly as the model would never even be offered
    that tool. A single-tool allowlist per call (not the full 16) is the tightest expression of
    "may THIS tenant use THIS Connector operation" available from existing machinery.
  - THE SAME re-validation-against-real-state `validate_and_render`/`execute_confirmed_proposal`
    already perform — nothing here trusts anything the caller (Meta's agent, in this case) claims
    about availability, balances, or ownership any more than the LLM path ever did.
  - A REAL, SERVER-SIDE CONSENT BACKSTOP (`_invoke()`'s own check, added after this session's own
    end-to-end simulator found it missing) — "no tool after refusal" (the Skill's own step 6) is
    never enforced ONLY by trusting Meta's hosted agent to follow the pasted instructions; a
    DENIED/UNKNOWN-and-not-fail-open subject refuses every tool here too, same posture as
    `core/inbound_ingest.py::_gate_consent` already holds for the reply path.

THE ONE GENUINELY OPEN QUESTION (documented honestly, not guessed at): Meta's real per-call payload
shape for identifying WHICH shop/customer/conversation a Connector invocation is for is not yet
confirmed against a live sandbox (see this session's own research — the exact schema is gated
behind developer-console access). `_ConnectorContext` below is written as the plausible, explicit
shape (tenant/from_number/conversation_id/branch_id as request fields) — a thin translation layer
BY DESIGN, so if the real shape turns out to travel differently (a header, a path parameter Meta
templates per-connector-registration), only `_ConnectorContext`'s own resolution changes, never any
tool's logic, never the auth/entitlement gating above it.
"""
from __future__ import annotations

import time
from typing import Any

import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.core import tools as T
from app.core.inbound_ingest import resolve_subject_ref
from app.ports.consent_gate import ALLOWED, DENIED, UNKNOWN

router = APIRouter(prefix="/api/v1/connectors", tags=["connectors"])

_HEADER = "Authorization"
_BEARER_PREFIX = "Bearer "


async def require_connector_token(
    authorization: str | None = Header(default=None, alias=_HEADER),
    settings: Settings = Depends(get_settings),
) -> None:
    """Constant-time compare, same discipline as app/api/internal.py's own `require_internal_token`
    — a SEPARATE secret (see config.py's own note), never INTERNAL_SERVICE_TOKEN."""
    expected = settings.CONNECTOR_API_TOKEN
    provided = authorization or ""
    if provided.startswith(_BEARER_PREFIX):
        provided = provided[len(_BEARER_PREFIX):]
    if not expected or not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="UNAUTHORIZED")


class _ConnectorBase(BaseModel):
    """Every operation's shared identity fields — see this module's own docstring on why these are
    an explicit, adjustable guess rather than a confirmed schema."""
    tenant: str = Field(min_length=1)
    from_number: str = Field(min_length=1, description="The customer's own WhatsApp number.")
    conversation_id: str = Field(min_length=1)
    branch_id: str = ""


def _refuse(reason: str) -> dict[str, Any]:
    return {"ok": False, "error": reason}


def _serialize(result: Any) -> dict[str, Any]:
    if isinstance(result, str):
        return {"ok": True, "kind": "text", "text": result}
    if isinstance(result, T.RenderedProposal):
        return {"ok": True, "kind": "proposal", "proposal_id": result.proposal_id,
                "body": result.body, "buttons": result.buttons}
    if isinstance(result, T.RenderedCarousel):
        return {"ok": True, "kind": "carousel", "cards": [
            {"id": c.id, "kind": c.kind, "name": c.name, "price_minor": c.price_minor,
             "image_url": c.image_url} for c in result.cards]}
    if isinstance(result, T.RenderedSingleCard):
        c = result.card
        return {"ok": True, "kind": "card", "card": {
            "id": c.id, "kind": c.kind, "name": c.name, "price_minor": c.price_minor,
            "image_url": c.image_url}}
    if isinstance(result, T.MobileLocationRequest):
        return {"ok": True, "kind": "location_request", "service_ids": result.service_ids,
                "requested_time": result.requested_time}
    return _refuse("unknown_result_shape")   # pragma: no cover - exhaustive over ToolResult today


async def _invoke(request: Request, *, tool: str, ctx: _ConnectorBase,
                  args: dict[str, Any]) -> dict[str, Any]:
    """THE ONE PLACE every Connector operation below actually runs — everything above this line
    per-endpoint is just "declare this operation's own typed args for the OpenAPI spec", never a
    second copy of the security posture. See this module's own docstring for what is enforced and
    why: licence, then held_apps, both identical to the LLM-driven turn's own gating."""
    container = request.app.state.container
    settings = get_settings()

    if container.licence is not None and not await container.licence.allowed(ctx.tenant):
        return _refuse("not_subscribed")

    # THE SAME DEPLOYMENT-WIDE CAPABILITY GATE THE LLM PATH ALREADY GOES THROUGH FIRST
    # (config.py::llm_tool_allowlist) — booking-management withheld when BOOKING_PROVIDER_DRIVER
    # is not "real" (the config-driven placeholder has no list_bookings/ownership concept at
    # all), the carousel tool withheld with no real catalogue peer wired, the two rhythm tools
    # withheld with no real rhythm peer, mobile-visit withheld with no OPERATIONS_SERVICE_URL.
    # WITHOUT THIS: a Connector call could reach a tool the LLM-driven turn would never even be
    # offered, and one already did in testing — surfacing a raw Python AttributeError as this
    # tool's own "error" text instead of a clean refusal. THE CONNECTOR SURFACE MUST NEVER GRANT
    # MORE THAN THE LLM PATH CAN, only ever the same or less.
    if tool not in settings.llm_tool_allowlist:
        return _refuse("tool_not_available_on_this_deployment")

    # THE SERVER-SIDE CONSENT BACKSTOP — found missing by this session's own end-to-end simulator:
    # without this, "no tool use after refusal" (the Skill's own step 6) was enforced ENTIRELY by
    # trusting Meta's hosted agent to follow the pasted instructions, with zero check on our side —
    # a customer who refused (or was never asked) could still have every tool run successfully if
    # Meta's agent hallucinated or simply ignored the Skill. Same posture as the reference
    # implementation for the reply path (core/inbound_ingest.py::_gate_consent): DENIED always
    # refuses here too (never final — the very next check_consent call re-asks, exactly like a new
    # inbound message would); UNKNOWN follows the SAME CONSENT_POLICY_ON_UNKNOWN this deployment
    # already committed to for the reply path, never a second, different default invented here.
    # `container.consent_gate is None` means the port is not wired at all — the same "None = no
    # gating" convention every other optional peer in this service already holds.
    if container.consent_gate is not None:
        try:
            verdict = await container.consent_gate.check(
                tenant=ctx.tenant, subject=ctx.from_number, purpose=settings.CONSENT_PURPOSE)
        except Exception:                                              # noqa: BLE001
            verdict = None
        status = getattr(verdict, "status", UNKNOWN) if verdict is not None else UNKNOWN
        if status == DENIED:
            return _refuse("consent_required")
        if status == UNKNOWN and settings.CONSENT_POLICY_ON_UNKNOWN != "fail_open":
            return _refuse("consent_required")

    held: frozenset[str] | None = None
    if container.held_apps is not None:
        try:
            held = await container.held_apps.held(ctx.tenant)
        except Exception:                                              # noqa: BLE001
            held = frozenset()
    base_tools = frozenset({tool})
    allowed = T.tools_for_held_apps(base_tools, held)
    if tool not in allowed:
        return _refuse("tool_not_available_for_this_tenant")

    subject_ref = await resolve_subject_ref(container, settings, ctx.tenant, ctx.from_number)
    now = int(time.time())
    try:
        result = await T.validate_and_render(
            tenant=ctx.tenant, subject_ref=subject_ref, conversation_id=ctx.conversation_id,
            tool=tool, args=args, allowed_tools=allowed, store=container.datastore,
            booking_provider=container.booking_provider, points_summary=container.points_summary,
            proposal_ttl_seconds=1800, now=now, related_services=container.related_services,
            service_catalog=container.service_catalog, package_catalog=container.package_catalog,
            service_procedure=container.service_procedure,
            branch_id=ctx.branch_id, from_number=ctx.from_number,
            booking_history_visible=settings.BOOKING_HISTORY_VISIBLE,
            catalog_provider=container.catalog_provider, rhythm_provider=container.rhythm_provider,
            mobile_requests=container.mobile_requests, active_offers=container.active_offers,
            max_carousel_cards=settings.MAX_CAROUSEL_CARDS)
    except T.ToolValidationError as exc:
        return _refuse(str(exc))
    return _serialize(result)


# ── read-only / suggestion operations (no args beyond identity) ────────────────────────────────
class GetCustomerPointsSummaryIn(_ConnectorBase):
    pass


@router.post("/get_customer_points_summary", dependencies=[Depends(require_connector_token)])
async def get_customer_points_summary(body: GetCustomerPointsSummaryIn, request: Request) -> dict:
    return await _invoke(request, tool="get_customer_points_summary", ctx=body, args={})


class SuggestRedeemableOfferIn(_ConnectorBase):
    pass


@router.post("/suggest_redeemable_offer", dependencies=[Depends(require_connector_token)])
async def suggest_redeemable_offer(body: SuggestRedeemableOfferIn, request: Request) -> dict:
    return await _invoke(request, tool="suggest_redeemable_offer", ctx=body, args={})


class ListPackagesIn(_ConnectorBase):
    pass


@router.post("/list_packages", dependencies=[Depends(require_connector_token)])
async def list_packages(body: ListPackagesIn, request: Request) -> dict:
    return await _invoke(request, tool="list_packages", ctx=body, args={})


class ListDueServicesIn(_ConnectorBase):
    pass


@router.post("/list_due_services", dependencies=[Depends(require_connector_token)])
async def list_due_services(body: ListDueServicesIn, request: Request) -> dict:
    return await _invoke(request, tool="list_due_services", ctx=body, args={})


class ListLapsedServicesIn(_ConnectorBase):
    pass


@router.post("/list_lapsed_services", dependencies=[Depends(require_connector_token)])
async def list_lapsed_services(body: ListLapsedServicesIn, request: Request) -> dict:
    return await _invoke(request, tool="list_lapsed_services", ctx=body, args={})


class CheckActiveOffersIn(_ConnectorBase):
    pass


@router.post("/check_active_offers", dependencies=[Depends(require_connector_token)])
async def check_active_offers(body: CheckActiveOffersIn, request: Request) -> dict:
    return await _invoke(request, tool="check_active_offers", ctx=body, args={})


class SuggestServicesCarouselIn(_ConnectorBase):
    pass


@router.post("/suggest_services_carousel", dependencies=[Depends(require_connector_token)])
async def suggest_services_carousel(body: SuggestServicesCarouselIn, request: Request) -> dict:
    return await _invoke(request, tool="suggest_services_carousel", ctx=body, args={})


class CheckMobileVisitHoursIn(_ConnectorBase):
    pass


@router.post("/check_mobile_visit_hours", dependencies=[Depends(require_connector_token)])
async def check_mobile_visit_hours(body: CheckMobileVisitHoursIn, request: Request) -> dict:
    return await _invoke(request, tool="check_mobile_visit_hours", ctx=body, args={})


class ListMyBookingsIn(_ConnectorBase):
    include_history: bool = False


@router.post("/list_my_bookings", dependencies=[Depends(require_connector_token)])
async def list_my_bookings(body: ListMyBookingsIn, request: Request) -> dict:
    return await _invoke(request, tool="list_my_bookings", ctx=body,
                         args={"include_history": body.include_history})


# ── operations that take a real argument ────────────────────────────────────────────────────────
class CheckAvailabilityIn(_ConnectorBase):
    service_id: str = ""
    package_id: str = ""
    earliest_date: str = Field(default="", description="YYYY-MM-DD")


@router.post("/check_availability", dependencies=[Depends(require_connector_token)])
async def check_availability(body: CheckAvailabilityIn, request: Request) -> dict:
    return await _invoke(request, tool="check_availability", ctx=body, args={
        "service_id": body.service_id, "package_id": body.package_id,
        "earliest_date": body.earliest_date})


class ProposeBookingIn(_ConnectorBase):
    service_id: str = ""
    package_id: str = ""
    starts_at_iso: str
    reward_id: str = ""


@router.post("/propose_booking", dependencies=[Depends(require_connector_token)])
async def propose_booking(body: ProposeBookingIn, request: Request) -> dict:
    return await _invoke(request, tool="propose_booking", ctx=body, args={
        "service_id": body.service_id, "package_id": body.package_id,
        "starts_at_iso": body.starts_at_iso, "reward_id": body.reward_id})


class GetServiceProcedureIn(_ConnectorBase):
    service_id: str = Field(min_length=1)


@router.post("/get_service_procedure", dependencies=[Depends(require_connector_token)])
async def get_service_procedure(body: GetServiceProcedureIn, request: Request) -> dict:
    return await _invoke(request, tool="get_service_procedure", ctx=body,
                         args={"service_id": body.service_id})


class SuggestRelatedServiceIn(_ConnectorBase):
    service_id: str = Field(min_length=1)


@router.post("/suggest_related_service", dependencies=[Depends(require_connector_token)])
async def suggest_related_service(body: SuggestRelatedServiceIn, request: Request) -> dict:
    return await _invoke(request, tool="suggest_related_service", ctx=body,
                         args={"service_id": body.service_id})


class ProposeCancelBookingIn(_ConnectorBase):
    booking_id: str = Field(min_length=1)
    reason: str = ""


@router.post("/propose_cancel_booking", dependencies=[Depends(require_connector_token)])
async def propose_cancel_booking(body: ProposeCancelBookingIn, request: Request) -> dict:
    return await _invoke(request, tool="propose_cancel_booking", ctx=body,
                         args={"booking_id": body.booking_id, "reason": body.reason})


class ProposeRescheduleBookingIn(_ConnectorBase):
    booking_id: str = Field(min_length=1)
    new_starts_at_iso: str


@router.post("/propose_reschedule_booking", dependencies=[Depends(require_connector_token)])
async def propose_reschedule_booking(body: ProposeRescheduleBookingIn, request: Request) -> dict:
    return await _invoke(request, tool="propose_reschedule_booking", ctx=body, args={
        "booking_id": body.booking_id, "new_starts_at_iso": body.new_starts_at_iso})


class RequestMobileVisitIn(_ConnectorBase):
    service_ids: list[str] = Field(min_length=1)
    starts_at_iso: str


@router.post("/request_mobile_visit", dependencies=[Depends(require_connector_token)])
async def request_mobile_visit(body: RequestMobileVisitIn, request: Request) -> dict:
    return await _invoke(request, tool="request_mobile_visit", ctx=body, args={
        "service_ids": body.service_ids, "starts_at_iso": body.starts_at_iso})


class CheckGrowthOpportunitiesIn(_ConnectorBase):
    service_ids: list[str] = Field(default_factory=list)


@router.post("/check_growth_opportunities", dependencies=[Depends(require_connector_token)])
async def check_growth_opportunities(body: CheckGrowthOpportunitiesIn, request: Request) -> dict:
    return await _invoke(request, tool="check_growth_opportunities", ctx=body,
                         args={"service_ids": body.service_ids})


# ── confirm — the ONLY path a proposal turns into a real write, exactly as the button-reply path
# already is. Never a new tool, never a new allowlist: this is T.execute_confirmed_proposal
# itself, translated. ───────────────────────────────────────────────────────────────────────────
class ConfirmProposalIn(_ConnectorBase):
    proposal_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)


@router.post("/confirm_proposal", dependencies=[Depends(require_connector_token)])
async def confirm_proposal(body: ConfirmProposalIn, request: Request) -> dict:
    container = request.app.state.container
    settings = get_settings()
    if container.licence is not None and not await container.licence.allowed(body.tenant):
        return _refuse("not_subscribed")
    try:
        result = await T.execute_confirmed_proposal(
            tenant=body.tenant, proposal_id=body.proposal_id, store=container.datastore,
            booking_provider=container.booking_provider, auditor=request.app.state.auditor,
            idempotency_key=body.idempotency_key, branch_id=body.branch_id,
            from_number=body.from_number,
            booking_management_enabled=settings.BOOKING_MANAGEMENT_ENABLED)
    except T.ToolValidationError as exc:
        return _refuse(str(exc))
    return {"ok": True, "result": result}


# ── consent — the two operations Meta's own hosted agent (not our code) must call on every FIRST
# contact now that ordinary conversation runs entirely inside Meta Business Agent (owner decision,
# 2026-09-19; see this file's own module docstring on the plug-and-play contract, and
# core/inbound_ingest.py::_gate_consent — the reference implementation of this EXACT logic for the
# path where OUR code still replies). These are NOT one of the 16 `core/tools.py` tools — consent
# is its own port (app/ports/consent_gate.py), never `_TOOL_HANDLERS`-registered, so they do not go
# through `_invoke()`'s tool-dispatch/held_apps narrowing above. They DO get the same licence check
# every other route here makes first — an unsubscribed shop's Connector calls are refused across
# the board, consent included — see `confirm_proposal` just above for the same shape.
class CheckConsentIn(_ConnectorBase):
    pass


@router.post("/check_consent", dependencies=[Depends(require_connector_token)])
async def check_consent(body: CheckConsentIn, request: Request) -> dict:
    container = request.app.state.container
    settings = get_settings()
    if container.licence is not None and not await container.licence.allowed(body.tenant):
        return _refuse("not_subscribed")

    try:
        verdict = await container.consent_gate.check(
            tenant=body.tenant, subject=body.from_number, purpose=settings.CONSENT_PURPOSE)
    except Exception as exc:                                          # noqa: BLE001
        # NEVER RAISES — same defensive posture as every other operation in this file. Meta's
        # agent gets an honest "unknown" rather than a 500 it has no instruction for.
        return {"ok": True, "status": UNKNOWN, "reason": f"consent_gate_error: {exc}"[:200]}

    status_map = {ALLOWED: "allowed", DENIED: "denied", UNKNOWN: "unknown"}
    return {"ok": True, "status": status_map.get(verdict.status, "unknown"),
            "reason": verdict.reason}


class RecordConsentIn(_ConnectorBase):
    granted: bool


@router.post("/record_consent", dependencies=[Depends(require_connector_token)])
async def record_consent(body: RecordConsentIn, request: Request) -> dict:
    container = request.app.state.container
    settings = get_settings()
    if container.licence is not None and not await container.licence.allowed(body.tenant):
        return _refuse("not_subscribed")

    try:
        recorded = await container.consent_gate.record(
            tenant=body.tenant, subject=body.from_number, purpose=settings.CONSENT_PURPOSE,
            granted=body.granted)
    except Exception:                                                 # noqa: BLE001
        # A failed record() call, per the port's own contract, returns False rather than throwing —
        # this is the belt-and-braces case of an adapter that broke that contract; surfaced the
        # same honest way, never pretended success.
        recorded = False

    # "نسجل رقم كل عميل يوافق ضروري" — owner's own requirement, 2026-09-19: a GRANTED consent must
    # also register this number as a real جهات الاتصال row, the SAME mechanism
    # core/conversation.py's own turn-building already uses on a stranger's first message
    # (`self._customer_lookup.register(tenant, from_number)`, core/conversation.py ~L872) — reused
    # here verbatim, never reinvented. `register()` itself reads this tenant's own opt-in flag
    # fresh every call and is a no-op for a tenant that never turned auto-registration on — this
    # call never overrides that, the consent recording above happens regardless either way.
    # Best-effort, exactly like every other side-effect in this file: a customer-lookup peer being
    # briefly unreachable must never turn a successfully recorded consent answer into an error.
    if body.granted and container.customer_lookup is not None:
        try:
            await container.customer_lookup.register(body.tenant, body.from_number)
        except Exception:                                              # noqa: BLE001
            pass

    return {"ok": True, "recorded": recorded}
