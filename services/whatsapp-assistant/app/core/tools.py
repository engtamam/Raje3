"""Tool validation gate — the model PROPOSES, this VALIDATES, only then a button is rendered.

This is the core safety property of the whole service (design point 5 / point 9's priority list).
The sequence for every allowlisted tool is always:

    1. The LLM adapter (app/adapters/llm/assistant_service.py) returns a ToolCall — a NAME and
       ARGS the model chose. Untrusted.
    2. `validate_and_render()` here re-checks it against REAL current state (real availability,
       real points balance) — never trusts anything the model claimed about that state.
    3. Only if validation passes is an interactive WhatsApp message built and a PendingProposal
       persisted, keyed by an id that is embedded in the button/list reply ids.
    4. The state-changing action (a booking write, a points redemption) fires ONLY when a
       button_reply/list_reply comes back matching that PendingProposal id — see
       core/conversation.py::handle_button_reply. Free text can never trigger it, and the model is
       never consulted again for that decision.

`confirm_booking` DOES NOT EXIST as a tool anywhere in this file, the LLM schema (adapters/llm/
assistant_service.py), or the allowlist (config.py::LLM_TOOL_ALLOWLIST). Confirmation is
button-only by construction, not by convention.

PLUG-AND-PLAY BY DESIGN. Every tool's logic lives in its own `_tool_<name>` function taking a
`ToolContext` (the shop/conversation state, never a wire format) and the model's raw `args` — never
a Meta/Vertex/any-provider shape. `_TOOL_HANDLERS` is the one place a tool is registered; adding,
removing or replacing a tool touches only its own handler and this one registry entry, never the
dispatcher below and never anything upstream of it (the LLM adapter that calls this module, or a
future provider adapter that calls it instead). The confirm-time counterpart
(`_execute_confirmed_proposal`) is the same pattern, one level down, via `_CONFIRM_HANDLERS`.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from app.core.audit import AuditUnavailable
from app.core.models import PENDING_PROPOSALS, PendingProposal, as_row
from app.core.upsell_ledger import record_offer as record_upsell_offer
from app.core.upsell_ledger import record_outcome as record_upsell_outcome
from app.observability.logging import get_logger
from app.ports.catalog_provider import CatalogCard

_logger = get_logger("app.tools")

# Serialises `execute_confirmed_proposal` per proposal_id — added 2026-09-07, a QA audit found the
# "consumed" guard below is itself a read-then-write TOCTOU: two concurrent calls for the SAME
# proposal_id (a redelivered wamid before its own dedup settled, or WhatsApp itself replaying a
# button tap) both read `consumed=False` before either writes it, and both proceed into a REAL
# booking-provider write. This lock is deliberately SEPARATE from the proposal row's own
# `consumed` field (never merged into it) — the row is only marked consumed AFTER the real write
# genuinely succeeds (see `_mark_consumed` below), so a real failure (a network hiccup calling
# bookings-service) still lets a customer's retry through once this short lock naturally expires,
# exactly as before this fix. Short TTL, same value SpendLock uses in services/loyalty for the
# identical reasoning: long enough to cover one real peer round trip, short enough that a genuine
# retry after a real failure is not made to wait.
_EXECUTE_LOCKS = "wa_proposal_execute_locks"
_EXECUTE_LOCK_TTL_SECONDS = 15

# list_due_services / list_lapsed_services' own bands over (days since last visit) / interval_days.
# Below 0.8 the customer is not due yet by his own learned rhythm; at/above 2.5x his usual interval
# "hasn't come back this week" has become a real, meaningfully stopped pattern rather than normal
# variation — the same "wide on purpose" reasoning reminders/core/adaptive.py's own anomaly_factor
# (2.5) uses, reused here rather than a second, unrelated number invented for this file.
_DUE_SOON_RATIO_MIN = 0.8
_LAPSED_RATIO_MIN = 2.5

# ── soft-decline (core/soft_decline.py) — which tools are a PITCH, and how to tell a real one
# from "nothing to offer" ────────────────────────────────────────────────────────────────────────
#
# PROMO_TOOLS are every read-only SUGGESTION — never propose_booking/cancel/reschedule (those are
# the customer's own direct request, gated by their own confirm/cancel buttons already, not an
# unprompted pitch) and never check_availability/get_customer_points_summary/list_my_bookings
# (informational, answering a question the customer asked, not offering something extra).
PROMO_TOOLS = frozenset({
    "suggest_related_service", "suggest_redeemable_offer", "list_packages",
    "suggest_services_carousel", "list_due_services", "list_lapsed_services",
})

# THE EXACT "NOTHING TO OFFER" STRING EACH PROMO TOOL RETURNS — named here, once, so
# core/conversation.py never re-types (and risks drifting from) the literal a tool above already
# returns. A "nothing" answer is not a pitch a customer could decline; only a REAL suggestion
# counts toward the soft-decline signal.
_EMPTY_PROMO_RESULTS = frozenset({
    "لا توجد مكافأة متاحة برصيدك الحالي بعد.",
    "لا تتوفر باقات لهذا المحل حاليًا.", "لا توجد باقات متاحة للحجز حاليًا.",
    "لا تتوفر بيانات كافية الآن.", "لا يوجد شيء هنا الآن.",
    "لا توجد خدمة أخرى تُطلب عادةً مع هذه الخدمة.",
    "لا تتوفر صور للخدمات حالياً.",
    "ما عندي صور كافية حالياً أعرضها لك — بس أقدر أخبرك عن خدماتنا بالتفصيل.",
})


def is_declinable_promo_result(tool: str, result: Any) -> bool:
    """True only when `tool` is a PROMO_TOOLS member AND its result is a REAL suggestion the
    customer could plausibly decline — a RenderedCarousel, or any text result other than that
    tool's own "nothing to offer" line. Used by core/conversation.py right after a tool call to
    decide whether the CUSTOMER'S NEXT message should even be checked for a soft decline."""
    if tool not in PROMO_TOOLS:
        return False
    if isinstance(result, (RenderedCarousel, RenderedSingleCard)):
        return True
    return isinstance(result, str) and result not in _EMPTY_PROMO_RESULTS


@dataclass(frozen=True)
class RenderedProposal:
    """What core/conversation.py hands to the WhatsAppSender — body text plus button ids that map
    back to a PendingProposal.id 1:1."""
    proposal_id: str
    body: str
    buttons: list[dict[str, str]]


@dataclass(frozen=True)
class RenderedCarousel:
    """What core/conversation.py hands to WhatsAppSender.send_carousel — presentational, no
    PendingProposal (a carousel never books or changes anything by itself; see
    suggest_services_carousel's own note below). `cards` already carries only items with a real
    `image_url`, capped at MAX_CAROUSEL_CARDS."""
    cards: list[CatalogCard]


@dataclass(frozen=True)
class RenderedSingleCard:
    """One CatalogCard, photo + text + one button — the INVITE/quick-reply shape, not a carousel
    of one. Meta's carousel component needs 2+ cards; a shop with exactly one photographed
    service was getting the "not enough photos" apology for having exactly the photo needed.
    Never a PendingProposal: identical posture to RenderedCarousel — presentational, the
    state-changing action is still gated behind the button tap, never this tool call."""
    card: CatalogCard


@dataclass(frozen=True)
class MobileLocationRequest:
    """What `request_mobile_visit` hands core/conversation.py — NOT a PendingProposal (there is
    nothing here for a button to confirm yet). `service_ids` are already re-validated against the
    shop's own real catalogue. core/conversation.py turns this into a `send_location_request`
    interactive message and stamps ConversationState.awaiting_mobile_location so the customer's
    NEXT inbound location (never any other free text) is what actually creates the request — see
    core/conversation.py::handle_location. `requested_time` is already a real, validated epoch
    instant (see `check_mobile_visit_hours`'s own sibling tool and `_MOBILE_TIME_TOO_FAR` below)
    — never free text."""
    service_ids: list[str]
    requested_time: int
    referral_code: str = ""


class ToolValidationError(Exception):
    """The model proposed something reality does not support — a slot that is gone, a service that
    does not exist. Never rendered as a button; the caller falls back to plain text."""


@dataclass(frozen=True)
class ToolContext:
    """Everything a tool handler needs to validate against REAL state — shop/conversation state
    only, never a wire format. A provider adapter (the LLM's tool-call shape today, a Meta
    Connector payload tomorrow, anything else later) translates its own request into `(tool, args)`
    and lets `validate_and_render` build this; no handler below ever sees, or needs to know about,
    which provider is asking."""
    tenant: str
    subject_ref: str
    conversation_id: str
    store: Any
    booking_provider: Any
    points_summary: Any
    proposal_ttl_seconds: int
    now: int
    related_services: Any = None
    service_catalog: Any = None
    package_catalog: Any = None
    service_procedure: Any = None
    branch_id: str = ""
    from_number: str = ""
    booking_history_visible: bool = True
    catalog_provider: Any = None
    rhythm_provider: Any = None
    mobile_requests: Any = None
    active_offers: Any = None
    max_carousel_cards: int = 5


ToolResult = RenderedProposal | RenderedCarousel | RenderedSingleCard | MobileLocationRequest | str
ToolHandler = Callable[["ToolContext", dict[str, Any]], Awaitable[ToolResult]]


async def _tool_check_availability(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    service_id = str(args.get("service_id") or "")
    package_id = str(args.get("package_id") or "")
    if not service_id and not package_id:
        raise ToolValidationError("check_availability requires service_id or package_id")
    if service_id and package_id:
        raise ToolValidationError("check_availability takes service_id OR package_id, not both")
    earliest = _parse_date(args.get("earliest_date")) or ctx.now
    if package_id:
        # PACKAGES ARE REAL-DRIVER ONLY — see booking_assignment.py's own module docstring:
        # the zero-infra placeholder has no concept of a package's real components/duration
        # at all. `getattr` rather than an isinstance check, matching how the booking-
        # management tools (list_my_bookings etc.) already gate the same distinction.
        avail = getattr(ctx.booking_provider, "availability_for_package", None)
        if avail is None:
            raise ToolValidationError("package booking is not available on this deployment")
        slots = await avail(tenant=ctx.tenant, package_id=package_id, earliest=earliest,
                            branch_id=ctx.branch_id)
    else:
        slots = await ctx.booking_provider.availability(
            tenant=ctx.tenant, service_id=service_id, earliest=earliest, horizon_days=0,
            branch_id=ctx.branch_id)
    if not slots:
        return "لا توجد مواعيد متاحة قريبًا."
    listed = ", ".join(_fmt_slot(s.starts_at) for s in slots[:5])
    return f"المواعيد المتاحة: {listed}"


async def _tool_propose_booking(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    service_id = str(args.get("service_id") or "")
    package_id = str(args.get("package_id") or "")
    starts_at = _parse_iso(args.get("starts_at_iso"))
    if not (service_id or package_id) or starts_at is None:
        raise ToolValidationError(
            "propose_booking requires (service_id or package_id) and starts_at_iso")
    if service_id and package_id:
        raise ToolValidationError("propose_booking takes service_id OR package_id, not both")
    # RE-VALIDATED, not trusted: is this slot STILL real, right now, independent of whatever
    # the model believed when it proposed it — including, for a package, whether TODAY's
    # request still falls on a day it actually recurs on (operations' own schedule check,
    # re-asked fresh here, never assumed from an earlier turn's context block).
    if package_id:
        avail = getattr(ctx.booking_provider, "availability_for_package", None)
        if avail is None:
            raise ToolValidationError("package booking is not available on this deployment")
        slots = await avail(tenant=ctx.tenant, package_id=package_id, earliest=starts_at,
                            branch_id=ctx.branch_id)
        anchor = package_id
    else:
        slots = await ctx.booking_provider.availability(
            tenant=ctx.tenant, service_id=service_id, earliest=starts_at, horizon_days=0,
            branch_id=ctx.branch_id)
        anchor = service_id
    if not any(s.starts_at == starts_at for s in slots):
        raise ToolValidationError(
            f"proposed slot {starts_at} for {anchor!r} is not actually available")

    # OPTIONAL — «و+use my reward with this booking». RE-VALIDATED against the customer's REAL
    # affordable-without-approval offers (never trusted from the model's own args, same
    # discipline as the slot check above) — a reward the model half-remembers from three turns
    # ago, or one that expired/was spent since, is DROPPED rather than failing the whole
    # booking: the customer still gets the appointment they asked for, just told plainly that
    # the reward specifically could not be attached. This is intent, not a spend — see
    # app/core/booking_assignment.py's own note on `intended_reward_id` for why nothing here
    # risks the shop anything if the customer never shows.
    reward_id = str(args.get("reward_id") or "")
    reward_dropped = False
    if reward_id:
        real_offers = await ctx.points_summary.offers(tenant=ctx.tenant, subject_ref=ctx.subject_ref)
        if not any(str(o.get("reward_id")) == reward_id for o in real_offers):
            reward_id = ""
            reward_dropped = True

    # A NEW CUSTOMER'S OWN REFERRAL CODE — the model fills this ONLY when the customer actually
    # said one in the conversation (see the tool's own schema description); never validated here,
    # never trusted as real — it rides along as plain intent and is checked for real, against the
    # real engine, only at confirm time (`_confirm_propose_booking` below), the same "the model
    # proposes, the backend decides" posture `reward_id` right above already holds.
    referral_code = str(args.get("referral_code") or "").strip()

    proposal_id = f"prp_{uuid.uuid4().hex[:24]}"
    proposal_args: dict[str, Any] = {"starts_at": starts_at}
    if package_id:
        proposal_args["package_id"] = package_id
    else:
        proposal_args["service_id"] = service_id
    if reward_id:
        proposal_args["reward_id"] = reward_id
    if referral_code:
        proposal_args["referral_code"] = referral_code
    proposal = PendingProposal(
        id=proposal_id, tenant=ctx.tenant, subject_ref=ctx.subject_ref,
        conversation_id=ctx.conversation_id, tool="propose_booking",
        args=proposal_args,
        validated_snapshot={"validated_at": ctx.now},
        created_at=ctx.now, expires_at=ctx.now + ctx.proposal_ttl_seconds)
    await ctx.store.put(PENDING_PROPOSALS, proposal_id, as_row(proposal))
    if package_id:
        # THE UPSELL LEDGER'S OWN OFFER MOMENT — see upsell_ledger.py's module docstring for
        # why a package proposal specifically, and why written here rather than inferred later.
        # Price comes from the SAME real catalogue read `list_packages`/context_builder.py's
        # upsell section already trust — never invented, and left `None` (never 0) if the
        # package cannot be found (a race with it being retired/deactivated between the
        # earlier availability check and here).
        pkg_price: int | None = None
        if ctx.package_catalog is not None:
            for p in await ctx.package_catalog.list_active(ctx.tenant):
                if str(p.get("id")) == package_id:
                    pkg_price = int(p.get("price_minor") or 0)
                    break
        await record_upsell_offer(
            ctx.store, proposal_id=proposal_id, tenant=ctx.tenant, branch_id=ctx.branch_id,
            subject_ref=ctx.subject_ref, package_id=package_id, price_minor=pkg_price, now=ctx.now)
    body = f"هل تؤكد الموعد الساعة {_fmt_slot(starts_at)}؟"
    if reward_id:
        body += " سيتم استخدام مكافأتك عند حضورك للموعد."
    elif reward_dropped:
        body += " (تعذّر إرفاق المكافأة المطلوبة — يمكنك سؤالي عنها مرة أخرى.)"
    return RenderedProposal(
        proposal_id=proposal_id, body=body,
        buttons=[{"id": f"{proposal_id}:confirm", "title": "تأكيد"},
                {"id": f"{proposal_id}:cancel", "title": "إلغاء"}])


async def _tool_get_customer_points_summary(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    summary = await ctx.points_summary.summary(tenant=ctx.tenant, subject_ref=ctx.subject_ref)
    return summary.get("text", "")


async def _tool_suggest_redeemable_offer(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    # READ-ONLY, same posture as suggest_related_service below — no proposal, no button, no
    # PendingProposal row. A reward is no longer spent standalone, unconditionally, the moment
    # a customer taps confirm: it rides on a real booking (`propose_booking`'s own `reward_id`
    # argument) so nothing is ever spent until the shop actually delivers the service. See
    # app/core/booking_assignment.py's `intended_reward_id` note for the full reasoning — this
    # is the structural fix, not a policy note, for a no-show costing the shop a reward with
    # nothing to show for it.
    offer = await ctx.points_summary.redeemable_offer(tenant=ctx.tenant, subject_ref=ctx.subject_ref)
    if not offer:
        return "لا توجد مكافأة متاحة برصيدك الحالي بعد."
    return (f"يمكنك استخدام «{offer['reward_name']}» بنقاطك الحالية — فقط اذكرها عند حجز "
           f"موعدك وسأرفقها به.")


async def _tool_list_packages(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    # READ-ONLY, same posture as suggest_related_service/list_my_bookings below — no
    # proposal, no button. Booking one still goes through propose_booking(package_id=...)
    # like any other item.
    #
    # DELIBERATELY NOT THE SAME FILTER context_builder.py's upsell section uses — that one
    # additionally requires price_minor >= component_price_minor_sum, because it exists to
    # protect an UNPROMPTED suggestion from ever looking like a downsell. A customer who asks
    # "do you have packages/deals?" is asking a direct question a genuine discount bundle (the
    # normal shape of a package — priced BELOW its parts) is exactly the right answer to; that
    # restriction would silently hide the shop's actual deals from its own customers. Only
    # "does this package genuinely exist and can it be booked soon" gates a package here.
    if ctx.package_catalog is None:
        return "لا تتوفر باقات لهذا المحل حاليًا."
    packages = [p for p in await ctx.package_catalog.list_active(ctx.tenant)
               if p.get("active") and (p.get("next_offerable_dates") or [])]
    if not packages:
        return "لا توجد باقات متاحة للحجز حاليًا."
    names_by_id: dict[str, str] = {}
    if ctx.service_catalog is not None:
        for s in await ctx.service_catalog.list_active(ctx.tenant):
            names_by_id[str(s.get("id"))] = str(s.get("name") or s.get("id"))
    lines = ["باقاتنا المتاحة الآن:"]
    for p in packages:
        included = "، ".join(names_by_id.get(sid, sid) for sid in p.get("service_ids") or [])
        riyals = int(p.get("price_minor") or 0) / 100  # money: ok — SAR only, see context_builder.py::_fmt_price's own note
        line = f"- {p.get('name')} (id: {p.get('id')}): تشمل {included} — بسعر {riyals:g} ريال"
        person_count = int(p.get("person_count") or 1)
        if person_count > 1:
            line += f"، تكفي {person_count} أشخاص"
        out = p.get("next_offerable_dates") or []
        if out:
            line += f" — الأيام المتاحة قريبًا: {'، '.join(out)}"
        lines.append(line)
    return "\n".join(lines)


async def _tool_due_or_lapsed_services(ctx: ToolContext, args: dict[str, Any], *,
                                       tool: str) -> ToolResult:
    # READ-ONLY, same posture as list_packages/suggest_related_service — no proposal, no
    # button. Booking one still goes through propose_booking(service_id=...) like any other.
    #
    # A DECISION INPUT, NEVER A SENTENCE ABOUT THE CUSTOMER — see core/conversation.py's
    # `personalization` persona section and its `_FORBIDDEN_HISTORY_DISCLOSURE_PATTERNS`
    # backstop: this tool's result names services, never "you usually" or "it's been a
    # while" — the model must build its own suggestion without echoing why.
    #
    # ONLY is_learned ROWS COUNT — reminders' own /rhythm-for-subject already marks a
    # defaulted (below-warmup) estimate as such; presenting one here as a real pattern would
    # be exactly the "guess dressed as measurement" adaptive.py's own docstring warns against.
    if ctx.rhythm_provider is None:
        return "لا تتوفر بيانات كافية الآن."
    rhythm = await ctx.rhythm_provider.for_subject(tenant=ctx.tenant, subject_ref=ctx.subject_ref)
    names_by_id: dict[str, str] = {}
    if ctx.service_catalog is not None:
        for s in await ctx.service_catalog.list_active(ctx.tenant):
            names_by_id[str(s.get("id"))] = str(s.get("name") or s.get("id"))
    matches: list[str] = []
    for r in rhythm:
        if not r.is_learned or r.interval_days <= 0 or r.last_visit_at <= 0:
            continue
        days_since = (ctx.now - r.last_visit_at) / 86400
        ratio = days_since / r.interval_days
        name = names_by_id.get(r.service_id, r.service_id)
        # DUE SOON: approaching or just past the customer's own learned interval, not yet the
        # "hasn't been back in ages" case below — the two tools' bands never overlap.
        if tool == "list_due_services" and _DUE_SOON_RATIO_MIN <= ratio < _LAPSED_RATIO_MIN:
            matches.append(name)
        # LAPSED: well past double the customer's own learned interval — a real, meaningfully
        # stopped pattern, not merely "hasn't come back yet this week".
        elif tool == "list_lapsed_services" and ratio >= _LAPSED_RATIO_MIN:
            matches.append(name)
    if not matches:
        return "لا يوجد شيء هنا الآن."
    return "، ".join(matches)


async def _tool_list_due_services(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    return await _tool_due_or_lapsed_services(ctx, args, tool="list_due_services")


async def _tool_list_lapsed_services(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    return await _tool_due_or_lapsed_services(ctx, args, tool="list_lapsed_services")


async def _tool_check_active_offers(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    # READ-ONLY, same posture as list_due_services/check_growth_opportunities — plain facts
    # back to the model, never a sentence for the customer. Reuses reminders' own send-log
    # read (core/active_offers.py's own module docstring) — no guessing which campaign the
    # customer means: `for_subject` already answers "every offer this customer is still
    # genuinely holding", expired or already-spent ones silently absent.
    if ctx.active_offers is None:
        return "لا توجد عروض حالية لهذا العميل."
    offers = await ctx.active_offers.for_subject(tenant=ctx.tenant, subject_ref=ctx.subject_ref)
    if not offers:
        return "لا يوجد عرض حالي ساري لهذا العميل الآن."
    import datetime as _dt

    from app.core.riyadh import RIYADH
    lines = ["عروضه الحالية الحقيقية:"]
    for o in offers:
        until = _dt.datetime.fromtimestamp(o.expires_at, RIYADH).strftime("%Y-%m-%d")
        line = f"- {o.text} — ساري حتى {until}"
        if o.value:
            line += f" (القيمة: {o.value})"
        if o.scoped:
            names = "، ".join(o.services) if o.services else "خدمات محددة"
            line += f" — يشمل: {names}"
        lines.append(line)
    return "\n".join(lines)


async def _tool_check_growth_opportunities(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    # ONE ORCHESTRATING READ, NEVER FIVE THE MODEL CHAINS ITSELF — see core/growth.py's own
    # module docstring for the full reasoning (owner's own instruction, 2026-09-16). Lazily
    # imported: growth.py imports the due/lapsed ratio constants FROM this module, so importing
    # it back at this module's own top level would be circular; a function-local import here,
    # at call time, is safe because by then this module has already finished loading.
    from app.core import growth as G
    raw_ids = args.get("service_ids") or []
    selected = [str(sid) for sid in raw_ids if str(sid).strip()][:20]
    report = await G.build_report(
        tenant=ctx.tenant, subject_ref=ctx.subject_ref, selected_service_ids=selected,
        package_catalog=ctx.package_catalog, service_catalog=ctx.service_catalog,
        rhythm_provider=ctx.rhythm_provider, related_services=ctx.related_services,
        points_summary=ctx.points_summary, now=ctx.now)
    return report or "لا توجد فرصة حقيقية لرفع الفاتورة تُذكر الآن."


async def _tool_get_service_procedure(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    # READ-ONLY, same posture as list_packages/suggest_related_service — no proposal, no button.
    #
    # ONE SERVICE AT A TIME, BY DESIGN — see core/service_procedure.py's own module docstring:
    # the owner's explicit instruction was per-service, never the whole catalogue in one call, to
    # keep this tool's token cost bounded. A model that wants to compare two services calls this
    # twice; there is no batched shape offered here to accidentally reach for instead.
    #
    # RAW FACTS ONLY, NOT SALES COPY — this returns the real step order/text/severity exactly as
    # the shop wrote it; turning that into a confident, natural-sounding answer is the model's own
    # job, governed by the `procedure_selling` PromptSection (core/conversation.py), never baked
    # into this tool's own output.
    service_id = str(args.get("service_id") or "")
    if not service_id:
        raise ToolValidationError("get_service_procedure requires service_id")
    if ctx.service_procedure is None:
        return "لا تتوفر تفاصيل الإجراء لهذه الخدمة حاليًا."
    procedure = await ctx.service_procedure.get(ctx.tenant, service_id)
    if not procedure or not procedure.get("steps"):
        return "لا تتوفر خطوات مفصّلة لهذه الخدمة حاليًا."
    name = str(procedure.get("service_name") or service_id)
    lines = [f"خطوات خدمة «{name}» بالترتيب:"]
    for i, step in enumerate(procedure["steps"], start=1):
        text = str(step.get("text") or "")
        # CRITICAL IS THE ONLY SEVERITY WORTH SURFACING TO THE MODEL HERE — it is the one flag
        # that is meaningfully customer-relevant (a step the shop itself treats as non-negotiable
        # quality/safety, exactly the kind of concrete detail a confident answer should be able to
        # lean on); "normal" carries no comparable signal and would only add noise to every line.
        marker = " (أساسية)" if step.get("severity") == "critical" else ""
        lines.append(f"{i}. {text}{marker}")
    return "\n".join(lines)


async def _tool_suggest_related_service(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    service_id = str(args.get("service_id") or "")
    if not service_id:
        raise ToolValidationError("suggest_related_service requires service_id")
    # READ-ONLY, like check_availability/get_customer_points_summary — this NEVER adds the
    # related service to a booking itself; a customer who wants it still goes through
    # propose_booking/button-confirm like any other service. No proposal, no button, no
    # PendingProposal row.
    related_ids = (await ctx.related_services.related_to(ctx.tenant, service_id)
                  if ctx.related_services is not None else [])
    if not related_ids:
        return "لا توجد خدمة أخرى تُطلب عادةً مع هذه الخدمة."
    names_by_id: dict[str, str] = {}
    if ctx.service_catalog is not None:
        for s in await ctx.service_catalog.list_active(ctx.tenant):
            names_by_id[str(s.get("id"))] = str(s.get("name") or s.get("id"))
    # A "pkg:<id>" ANSWER (packages feature) — this service and that PACKAGE are bought
    # together often. Resolved against the package catalogue, never the service one (a
    # package id would never be found there and would print the raw "pkg:..." string).
    # UNLIKE AN ORDINARY SERVICE SUGGESTION, A PACKAGE'S PRICE IS SAFE TO STATE — see
    # package_catalog.py's own docstring: it is the owner's own published price, not a number
    # the engine or this reply invents.
    packages_by_id: dict[str, dict[str, Any]] = {}
    if ctx.package_catalog is not None and any(rid.startswith("pkg:") for rid in related_ids):
        for p in await ctx.package_catalog.list_active(ctx.tenant):
            packages_by_id[str(p.get("id"))] = p

    plain_names: list[str] = []
    package_lines: list[str] = []
    for rid in related_ids:
        if rid.startswith("pkg:"):
            pkg = packages_by_id.get(rid[len("pkg:"):])
            if pkg is None:
                continue    # a peer read that failed, or a package retired since — skipped
            riyals = int(pkg.get("price_minor") or 0) / 100  # money: ok — SAR only, see context_builder.py::_fmt_price's own note
            package_lines.append(f"باقة «{pkg.get('name')}» بسعر {riyals:g} ريال")
        else:
            plain_names.append(names_by_id.get(rid, rid))

    if package_lines and not plain_names:
        listed = "، ".join(package_lines[:3])
        return f"عندنا {listed} تجمع هذه الخدمة مع خدمات أخرى تُطلب معها عادةً. هل تحب معرفة المزيد؟"
    if package_lines:
        return (f"عادةً ما يُطلب مع هذه الخدمة أيضًا: {'، '.join(plain_names[:3])}. "
               f"وعندنا أيضًا {package_lines[0]} تجمعها مع خدمات أخرى. هل تحب إضافتها؟")
    # NO DISCOUNT FIELD EXISTS ANYWHERE IN THIS RESULT — the associations engine
    # (services/insights/app/core/associations.py) returns only a verdict and an id, never a
    # price or a discount. There is nothing here for the model to embellish from; any discount
    # claim in its reply is therefore always fabricated and is caught by
    # core/conversation.py's `_sanitize_reply` regardless of what this tool returns.
    listed = "، ".join(plain_names[:3])
    return f"عادةً ما يُطلب مع هذه الخدمة أيضًا: {listed}. هل تحب إضافتها؟"


async def _tool_suggest_services_carousel(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    # READ-ONLY, same posture as suggest_related_service above — a carousel is presentational;
    # a customer wanting an item still goes through propose_booking like any other service.
    if ctx.catalog_provider is None:
        return "لا تتوفر صور للخدمات حالياً."
    cards = await ctx.catalog_provider.list_cards(tenant=ctx.tenant, limit=ctx.max_carousel_cards * 2)
    # THE FLOOR IS ENFORCED HERE, NOT AT SEND TIME — Meta's own carousel minimum is two cards,
    # and checking it here (before ever building a RenderedCarousel) means a network hiccup on
    # one photo at SEND time is the only way the sender's own floor can ever fire, never a
    # model proposing something invalid.
    with_images = [c for c in cards if c.image_url][:ctx.max_carousel_cards]
    # THREE-WAY, NOT A FLOOR — zero real candidates is genuinely "nothing to show"; exactly
    # one is a real, photographed service that deserves its own card, not the apology meant
    # for zero (Meta's own carousel component needs 2+ cards, but that is a SEND-SHAPE limit,
    # not a reason to hide the one photo we actually have).
    if len(with_images) == 0:
        return "ما عندي صور كافية حالياً أعرضها لك — بس أقدر أخبرك عن خدماتنا بالتفصيل."
    if len(with_images) == 1:
        return RenderedSingleCard(card=with_images[0])
    return RenderedCarousel(cards=with_images)


async def _tool_list_my_bookings(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    # READ-ONLY — no proposal, no button, same posture as check_availability. Ownership is
    # structural, not a check we perform: booking_provider.list_bookings resolves customer_id
    # from `from_number` itself (see booking_assignment.py) — there is no argument here a
    # customer or the model could use to name a different customer.
    #
    # CAUGHT, NOT LEFT TO PROPAGATE: list_bookings can raise BookingAssignmentError (peer
    # unreachable, no phone on this conversation, or the management peers were never built
    # because the flag was off) — an exception that is NOT a ToolValidationError, so
    # core/conversation.py's own except clause would never catch it. Left uncaught, this would
    # crash the turn with no reply sent at all — the exact "silence" defect class this
    # module's docstring already flags for the audit step below; the fix is the same shape.
    try:
        bookings = await ctx.booking_provider.list_bookings(
            tenant=ctx.tenant, from_number=ctx.from_number, branch_id=ctx.branch_id)
    except Exception as exc:
        raise ToolValidationError(f"could not list bookings: {exc}") from exc
    wants_history = bool(args.get("include_history"))
    upcoming = [b for b in bookings if int(b.get("starts_at") or 0) >= _riyadh_today_start(ctx.now)]
    if wants_history and not ctx.booking_history_visible:
        # Declined, not hallucinated and not a bare error — the flag exists precisely so this
        # answer is a clean, honest refusal a human can then help with (BOOKING_HISTORY_VISIBLE's
        # own note in app/config.py). CURRENT/UPCOMING STILL SHOW, prepended to the decline —
        # "I can't show your history" must never also silently swallow "and here is nothing
        # about your appointment tomorrow either", which contradicts the flag's own documented
        # contract ("current and upcoming bookings always show regardless of this flag") and
        # would be a real, if narrow, hallucination-by-omission if a customer asked a compound
        # question ("what did I book last month, and is tomorrow's still on?").
        decline = ("لا أقدر أعرض حجوزاتك السابقة حاليًا. تواصل مع المحل مباشرة إن احتجت "
                  "سجلك القديم.")
        if not upcoming:
            return decline
        lines = [_fmt_booking_row(b) for b in sorted(upcoming, key=lambda b: b.get("starts_at") or 0)]
        return decline + "\n\nحجوزاتك القادمة:\n" + "\n".join(lines)
    rows = bookings if (wants_history and ctx.booking_history_visible) else upcoming
    if not rows:
        return ("لا توجد حجوزات قادمة لك حاليًا." if not wants_history
               else "لا توجد حجوزات لك.")
    lines = [_fmt_booking_row(b) for b in sorted(rows, key=lambda b: b.get("starts_at") or 0)]
    return "حجوزاتك:\n" + "\n".join(lines)


async def _tool_propose_cancel_booking(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    booking_id = str(args.get("booking_id") or "")
    if not booking_id:
        raise ToolValidationError("propose_cancel_booking requires booking_id")
    booking = await _find_own_booking(ctx.booking_provider, ctx.tenant, ctx.from_number,
                                      booking_id, ctx.branch_id)
    if booking is None:
        raise ToolValidationError("هذا الحجز غير موجود أو لا يخصّك")
    if booking.get("status") == "cancelled":
        return "هذا الموعد ملغى بالفعل."
    if booking.get("status") in ("attended", "no_show"):
        return "هذا الموعد انتهى، تواصل مع المحل مباشرة."

    reason = str(args.get("reason") or "")[:300]
    proposal_id = f"prp_{uuid.uuid4().hex[:24]}"
    proposal = PendingProposal(
        id=proposal_id, tenant=ctx.tenant, subject_ref=ctx.subject_ref,
        conversation_id=ctx.conversation_id, tool="propose_cancel_booking",
        args={"booking_id": booking_id, "reason": reason},
        validated_snapshot={"validated_at": ctx.now},
        created_at=ctx.now, expires_at=ctx.now + ctx.proposal_ttl_seconds)
    await ctx.store.put(PENDING_PROPOSALS, proposal_id, as_row(proposal))
    body = f"هل تؤكد إلغاء موعدك يوم {_fmt_slot(int(booking['starts_at']))}؟"
    return RenderedProposal(
        proposal_id=proposal_id, body=body,
        buttons=[{"id": f"{proposal_id}:confirm", "title": "تأكيد الإلغاء"},
                {"id": f"{proposal_id}:cancel", "title": "تراجع"}])


async def _tool_propose_reschedule_booking(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    booking_id = str(args.get("booking_id") or "")
    new_starts_at = _parse_iso(args.get("new_starts_at_iso"))
    if not booking_id or new_starts_at is None:
        raise ToolValidationError(
            "propose_reschedule_booking requires booking_id and new_starts_at_iso")
    booking = await _find_own_booking(ctx.booking_provider, ctx.tenant, ctx.from_number,
                                      booking_id, ctx.branch_id)
    if booking is None:
        raise ToolValidationError("هذا الحجز غير موجود أو لا يخصّك")
    if booking.get("status") != "booked":
        raise ToolValidationError("هذا الحجز لم يعد قابلًا للتأجيل")

    service_ids = booking.get("service_ids") or []
    service_id = str(service_ids[0]) if service_ids else ""
    # RE-VALIDATED against REAL availability, exactly like propose_booking above — never
    # trusted from the model's own args. Checked on the BOOKING'S OWN branch, not the
    # conversation's current one: branch_id is fixed after creation (models.py's own note),
    # so a reschedule can never silently move a booking to a different branch.
    #
    # `exclude_booking_id=booking_id` — WITHOUT this, this exact booking's own current
    # occupancy makes any time inside its own current window read as "busy against itself",
    # so asking to move to the SAME time (an idempotent replay) or a nearby overlapping one
    # would be wrongly refused as unavailable. See app/ports/booking_provider.py's own note.
    slots = await ctx.booking_provider.availability(
        tenant=ctx.tenant, service_id=service_id, earliest=new_starts_at, horizon_days=0,
        branch_id=str(booking.get("branch_id") or ""), exclude_booking_id=booking_id)
    if not any(s.starts_at == new_starts_at for s in slots):
        raise ToolValidationError(
            f"proposed slot {new_starts_at} is not actually available")

    proposal_id = f"prp_{uuid.uuid4().hex[:24]}"
    proposal = PendingProposal(
        id=proposal_id, tenant=ctx.tenant, subject_ref=ctx.subject_ref,
        conversation_id=ctx.conversation_id, tool="propose_reschedule_booking",
        args={"booking_id": booking_id, "starts_at": new_starts_at},
        validated_snapshot={"validated_at": ctx.now},
        created_at=ctx.now, expires_at=ctx.now + ctx.proposal_ttl_seconds)
    await ctx.store.put(PENDING_PROPOSALS, proposal_id, as_row(proposal))
    body = f"هل تؤكد نقل موعدك إلى {_fmt_slot(new_starts_at)}؟"
    return RenderedProposal(
        proposal_id=proposal_id, body=body,
        buttons=[{"id": f"{proposal_id}:confirm", "title": "تأكيد"},
                {"id": f"{proposal_id}:cancel", "title": "تراجع"}])


async def _tool_check_mobile_visit_hours(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    # READ-ONLY, same posture as check_availability — grounds the model in the shop's REAL
    # weekly hours before it ever proposes a time via request_mobile_visit, so the customer is
    # asked for something that will actually be accepted rather than finding out only after
    # they already shared a location.
    if ctx.mobile_requests is None:
        raise ToolValidationError("mobile visit requests are not available on this deployment")
    weekly = await ctx.mobile_requests.hours(ctx.tenant)
    if weekly is None:
        return "لا أقدر أتأكد من أوقات الدوام الآن — اسأل عن الوقت المناسب وسيراجعه المحل بنفسه."
    return _format_working_hours(weekly)


async def _tool_request_mobile_visit(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    raw_ids = args.get("service_ids") or []
    service_ids = [str(sid) for sid in raw_ids if str(sid).strip()][:20]
    if not service_ids:
        raise ToolValidationError("request_mobile_visit requires at least one service_id")
    # RE-VALIDATED against the shop's REAL catalogue — never trusted from the model's own
    # args, same discipline as propose_booking's slot check above. A model that half-remembers
    # a service id from three turns ago (retired since, or never real) must not reach the
    # customer's next step (sharing a real location) for nothing.
    if ctx.service_catalog is None:
        raise ToolValidationError("mobile visit requests are not available on this deployment")
    real_ids = {str(s.get("id")) for s in await ctx.service_catalog.list_active(ctx.tenant)}
    unknown = [sid for sid in service_ids if sid not in real_ids]
    if unknown:
        raise ToolValidationError(f"unknown service_id(s): {', '.join(unknown)}")

    starts_at = _parse_iso(args.get("starts_at_iso"))
    if starts_at is None:
        raise ToolValidationError("request_mobile_visit requires a real starts_at_iso")
    # RE-VALIDATED against the shop's REAL working hours — never trusted from the model's own
    # judgement of what "9 to 9" means. Mirrors operations' own `validate_requested_time()`
    # (services/operations/app/core/mobile_requests.py), the SAME check the request will be
    # held to again once the customer's location actually creates it — this is a courtesy so
    # a bad guess is caught here, at the conversation, rather than after a location was
    # already asked for and shared.
    if ctx.mobile_requests is not None:
        weekly = await ctx.mobile_requests.hours(ctx.tenant)
        if weekly is not None:
            reason = _working_hours_violation(starts_at, weekly)
            if reason:
                raise ToolValidationError(reason)

    # A NEW CUSTOMER'S OWN REFERRAL CODE — same "the model fills it only when the customer
    # actually said one" posture as propose_booking's own referral_code (this function's own
    # sibling above); never validated here, only carried along until the request is created.
    referral_code = str(args.get("referral_code") or "").strip()
    return MobileLocationRequest(service_ids=service_ids, requested_time=starts_at,
                                 referral_code=referral_code)


# ── WHICH APP(S) EACH TOOL BELONGS TO ───────────────────────────────────────────────────────────
# Real console app keys (apps/console/src/apps.ts::APP_ROWS), traced 2026-09-19 to each tool's
# ACTUAL peer/provider dependency, not guessed from its name — see
# services/whatsapp-assistant/app/core/held_apps.py's own docstring for how this set gets checked
# per tenant. A tool absent from this dict (or mapped to an empty frozenset) is GENERAL: available
# to every tenant who holds the base feature.whatsapp subscription alone, never narrowed further.
#
# PLUG-AND-PLAY ON PURPOSE — a frozenset, not a single key: a tool tied to one app today gains a
# second (or a third) the day another app genuinely starts reusing it, by editing this one line —
# never the handler, never the dispatcher, never a caller. `list_due_services`/`list_lapsed_services`
# are tagged `feature.bookings` today (their real data source is reminders' learned rhythm, but the
# capability is documented as shared with bookings) precisely so a FUTURE app that also wants "due
# soon"/"lapsed" suggestions can add its own key here without moving a single line of the tool
# itself.
_TOOL_APP_KEYS: dict[str, frozenset[str]] = {
    "check_availability": frozenset({"feature.bookings"}),
    "propose_booking": frozenset({"feature.bookings"}),
    "list_my_bookings": frozenset({"feature.bookings"}),
    "propose_cancel_booking": frozenset({"feature.bookings"}),
    "propose_reschedule_booking": frozenset({"feature.bookings"}),
    "list_packages": frozenset({"feature.bookings"}),
    "list_due_services": frozenset({"feature.bookings"}),
    "list_lapsed_services": frozenset({"feature.bookings"}),
    # get_service_procedure: reads a Service's own procedure_step_ids (services/operations'
    # console-facing services tab, "الإجراءات") — the same app that owns everything else about a
    # service's own definition (durations, eligibility, packages) above, confirmed 2026-09-19
    # against apps.ts::APP_ROWS.
    "get_service_procedure": frozenset({"feature.bookings"}),
    "get_customer_points_summary": frozenset({"feature.loyalty"}),
    "suggest_redeemable_offer": frozenset({"feature.loyalty"}),
    "check_mobile_visit_hours": frozenset({"feature.mobile_requests"}),
    "request_mobile_visit": frozenset({"feature.mobile_requests"}),
    "check_active_offers": frozenset({"feature.campaigns"}),
    "suggest_related_service": frozenset({"feature.insights.engine"}),
    # check_growth_opportunities genuinely reads bookings + loyalty + insights data in one report
    # (core/growth.py's own module docstring) — a real cross-app tool, not a guess.
    "check_growth_opportunities": frozenset(
        {"feature.bookings", "feature.loyalty", "feature.insights.engine"}),
    # suggest_services_carousel: confirmed 2026-09-19 to depend ONLY on operations' own service/
    # package catalogue (core/catalog_provider.py) — no insights dependency despite reading photo
    # data that superficially resembles "صفقات" — genuinely general.
}


def tools_for_held_apps(base_tools: frozenset[str],
                        held_apps: frozenset[str] | None) -> frozenset[str]:
    """Narrows `base_tools` (the deployment-wide allowlist config.py already computes) to the
    ones THIS TENANT may actually be offered: a tool tagged in `_TOOL_APP_KEYS` needs at least one
    of its keys held; an untagged (general) tool is never narrowed by this at all.

    `held_apps=None` MEANS "NO GATING APPLIED" — every existing caller/test that never wires a
    held-apps port (core/conversation.py's own None-safe default, same convention as
    base_entitlement.py's `has_any_app`) sees `base_tools` completely unchanged."""
    if held_apps is None:
        return base_tools

    def _visible(tool: str) -> bool:
        needed = _TOOL_APP_KEYS.get(tool)
        return not needed or bool(needed & held_apps)

    return frozenset(t for t in base_tools if _visible(t))


# ── THE ONE REGISTRATION POINT ──────────────────────────────────────────────────────────────────
# Add/remove/replace a tool by editing this dict alone — no other line in this module, and nothing
# upstream of it, needs to change. Every value has the exact same shape: `ToolContext, args -> ToolResult`.
_TOOL_HANDLERS: dict[str, ToolHandler] = {
    "check_availability": _tool_check_availability,
    "propose_booking": _tool_propose_booking,
    "get_customer_points_summary": _tool_get_customer_points_summary,
    "suggest_redeemable_offer": _tool_suggest_redeemable_offer,
    "list_packages": _tool_list_packages,
    "list_due_services": _tool_list_due_services,
    "list_lapsed_services": _tool_list_lapsed_services,
    "check_active_offers": _tool_check_active_offers,
    "check_growth_opportunities": _tool_check_growth_opportunities,
    "get_service_procedure": _tool_get_service_procedure,
    "suggest_related_service": _tool_suggest_related_service,
    "suggest_services_carousel": _tool_suggest_services_carousel,
    "list_my_bookings": _tool_list_my_bookings,
    "propose_cancel_booking": _tool_propose_cancel_booking,
    "propose_reschedule_booking": _tool_propose_reschedule_booking,
    "check_mobile_visit_hours": _tool_check_mobile_visit_hours,
    "request_mobile_visit": _tool_request_mobile_visit,
}


async def validate_and_render(*, tenant: str, subject_ref: str, conversation_id: str,
                              tool: str, args: dict[str, Any], allowed_tools: frozenset[str],
                              store: Any, booking_provider: Any, points_summary: Any,
                              proposal_ttl_seconds: int, now: int | None = None,
                              related_services: Any = None, service_catalog: Any = None,
                              package_catalog: Any = None, service_procedure: Any = None,
                              branch_id: str = "", from_number: str = "",
                              booking_history_visible: bool = True,
                              catalog_provider: Any = None,
                              rhythm_provider: Any = None,
                              mobile_requests: Any = None,
                              active_offers: Any = None,
                              max_carousel_cards: int = 5,
                              ) -> ToolResult:
    """Returns a RenderedProposal (interactive message + pending proposal persisted) for a
    state-changing tool, or a plain str for a read-only one. Raises ToolValidationError if the
    model's proposal does not hold up against real state.
    """
    now = now if now is not None else int(time.time())

    if tool not in allowed_tools:
        # DEFENCE IN DEPTH: the LLM adapter already filters this before it ever reaches here, but a tool
        # name reaching this function outside the allowlist must never be trusted to mean "someone
        # forgot to filter" — it is refused again, unconditionally, at the one place execution
        # could actually happen.
        raise ToolValidationError(f"tool {tool!r} is not allowlisted")

    handler = _TOOL_HANDLERS.get(tool)
    if handler is None:
        raise ToolValidationError(f"tool {tool!r} has no handler")

    ctx = ToolContext(
        tenant=tenant, subject_ref=subject_ref, conversation_id=conversation_id, store=store,
        booking_provider=booking_provider, points_summary=points_summary,
        proposal_ttl_seconds=proposal_ttl_seconds, now=now, related_services=related_services,
        service_catalog=service_catalog, package_catalog=package_catalog,
        service_procedure=service_procedure, branch_id=branch_id,
        from_number=from_number, booking_history_visible=booking_history_visible,
        catalog_provider=catalog_provider, rhythm_provider=rhythm_provider,
        mobile_requests=mobile_requests, active_offers=active_offers,
        max_carousel_cards=max_carousel_cards)
    return await handler(ctx, args)


async def _mark_consumed(*, store: Any, proposal_id: str, row: dict[str, Any], tenant: str,
                         booking_id: str, action: str) -> bool:
    """Persist `consumed=True` on an ALREADY-SUCCEEDED real write. Returns True on a clean write,
    False on a caught failure — never raises, and never left bare: an unguarded `store.put` here
    was a genuine, if narrow, defect (found by review) sharing the EXACT shape the audit-gap
    handling just below already exists for — the real booking/cancel/reschedule write has already
    happened in bookings-service by the time this runs, so a datastore hiccup at this exact instant
    must not surface as an unhandled exception with no reply sent to the customer.

    UNLIKE the audit gap, a failure here also means the PROPOSAL ROW ITSELF never got marked
    consumed — so a redelivered webhook or a re-entrant button tap could reach this branch again
    for the same proposal. That retry is genuinely safe for all three callers: cancel is naturally
    idempotent (BookingOperations.cancel's own already-cancelled early return), create is protected
    by its own `idempotency_key`, and a reschedule retry is now DOUBLY protected — the
    exclude_booking_id fix above means the booking's own current slot is never treated as busy
    against itself, AND `BookingOperations._claim_and_save` now uses
    `save_if_unchanged(expected_rev=...)` instead of a bare `save()` (found by this same review):
    a genuinely independent edit to the SAME booking landing in the gap (a staff member moving it
    on the console, or a second WhatsApp reschedule) is refused with `ConcurrentEditError` rather
    than silently overwritten by the retry's stale target — the exact §4 race `edit_note`/
    `set_payment_status`/`cancel` already guarded against, now closed for `reschedule`/`create`/
    `edit_services` too (see `_claim_and_save`'s own docstring in services/bookings' operations.py).

    So the safe, honest choice THIS function makes is: log the gap for reconciliation, and still
    tell the customer the truth — never silence, and a retry can now only ever be refused loudly,
    never silently wrong.
    """
    try:
        row["consumed"] = True
        await store.put(PENDING_PROPOSALS, proposal_id, row)
        return True
    except Exception as exc:
        _logger.error(f"{action}_consumed_write_failed", extra={
            "tenant": tenant, "booking_id": booking_id, "proposal_id": proposal_id,
            "error": str(exc)})
        return False


async def execute_confirmed_proposal(*, tenant: str, proposal_id: str, store: Any,
                                     booking_provider: Any, auditor: Any,
                                     idempotency_key: str, now: int | None = None,
                                     branch_id: str = "", from_number: str = "",
                                     booking_management_enabled: bool = True
                                     ) -> dict[str, Any]:
    """The ONLY path that turns a proposal into a real write — see `_execute_confirmed_proposal`'s
    own docstring for the full reasoning; this wrapper only owns the concurrency lock.

    THE LOCK IS RELEASED HERE, IN `finally`, REGARDLESS OF OUTCOME — not left to its own TTL. A
    refusal (the management flag was off, the proposal was already consumed) or a genuine failure
    (a store hiccup mid-write — see `_mark_consumed`'s own docstring) must let an immediate retry
    through, exactly as it could before this lock existed; only a SECOND call GENUINELY
    CONCURRENT with this one (still running when the second arrives) is what the lock exists to
    refuse."""
    now = now if now is not None else int(time.time())
    row = await store.get(PENDING_PROPOSALS, proposal_id)
    if row is None or row.get("tenant") != tenant:
        raise ToolValidationError("no such pending proposal for this tenant")
    if row.get("consumed"):
        raise ToolValidationError("proposal already consumed")
    if int(row.get("expires_at") or 0) < now:
        raise ToolValidationError("proposal expired")

    # THE ACTUAL RACE GUARD — added 2026-09-07 (a QA audit found this whole function had none,
    # despite `_mark_consumed`'s own read-then-write below being exactly the shape every other
    # lock in this codebase exists for). A separate short-lived lock, deliberately not folded into
    # the row's own `consumed` field — see this function's own docstring for why.
    took = await store.claim(
        _EXECUTE_LOCKS, proposal_id, {"proposal_id": proposal_id, "tenant": tenant, "at": now},
        ttl_seconds=_EXECUTE_LOCK_TTL_SECONDS, now=now)
    if not took:
        raise ToolValidationError("another confirmation for this proposal is already in progress")
    try:
        return await _execute_confirmed_proposal(
            tenant=tenant, proposal_id=proposal_id, store=store, row=row,
            booking_provider=booking_provider, auditor=auditor, idempotency_key=idempotency_key,
            now=now, branch_id=branch_id, from_number=from_number,
            booking_management_enabled=booking_management_enabled)
    finally:
        await store.delete(_EXECUTE_LOCKS, proposal_id)


@dataclass(frozen=True)
class ExecuteContext:
    """Confirm-time twin of `ToolContext` — the state a confirm handler needs to actually perform
    the write, never a wire format. Same plug-and-play contract: `_CONFIRM_HANDLERS` is the one
    registration point."""
    tenant: str
    proposal_id: str
    store: Any
    booking_provider: Any
    auditor: Any
    idempotency_key: str
    now: int
    branch_id: str = ""
    from_number: str = ""
    booking_management_enabled: bool = True


ConfirmHandler = Callable[["ExecuteContext", dict, dict[str, Any], str], Awaitable[dict[str, Any]]]


async def _confirm_propose_booking(ctx: ExecuteContext, row: dict, args: dict[str, Any],
                                   subject_ref: str) -> dict[str, Any]:
    # `reward_id`, WHEN PRESENT, IS INTENT ONLY — never a spend here. It rides on the booking
    # (bookings-service's own `intended_reward_id`, stamped by `hold_and_confirm` below) and
    # is only ever actually spent when the shop marks the customer attended. A customer who
    # never shows costs the shop nothing: nothing was ever spent to begin with. See
    # app/core/booking_assignment.py's own note, and this function's module docstring — the
    # standalone, unconditional-on-confirm redemption this branch used to also handle
    # (tool == "suggest_redeemable_offer") no longer exists; see that tool's own docstring in
    # `validate_and_render` above for why.
    package_id = str(args.get("package_id") or "")
    try:
        if package_id:
            hold = getattr(ctx.booking_provider, "hold_and_confirm_package", None)
            if hold is None:
                raise ToolValidationError("package booking is not available on this deployment")
            booking = await hold(
                tenant=ctx.tenant, subject_ref=subject_ref, package_id=package_id,
                starts_at=int(args["starts_at"]), idempotency_key=ctx.idempotency_key,
                branch_id=ctx.branch_id, from_number=ctx.from_number,
                intended_reward_id=str(args.get("reward_id") or ""),
                referral_code=str(args.get("referral_code") or ""))
        else:
            booking = await ctx.booking_provider.hold_and_confirm(
                tenant=ctx.tenant, subject_ref=subject_ref, service_id=args["service_id"],
                starts_at=int(args["starts_at"]), idempotency_key=ctx.idempotency_key,
                branch_id=ctx.branch_id, from_number=ctx.from_number,
                referral_code=str(args.get("referral_code") or ""),
                intended_reward_id=str(args.get("reward_id") or ""))
    except ToolValidationError:
        raise
    except Exception as exc:
        raise ToolValidationError(f"booking confirm failed: {exc}") from exc

    # CONSUMED THE MOMENT THE REAL WRITE SUCCEEDS — BEFORE the audit call below, not after.
    # The booking now exists in bookings-service regardless of what happens next; a proposal
    # left "not consumed" because the AUDIT step failed is exactly what let a re-entrant
    # button tap or a redelivered webhook reach `hold_and_confirm` a second time for a booking
    # that was already made — `idempotency_key` would catch that specific case, but nothing
    # should have to rely on it here. See the audit step's own note just below for why an
    # audit-sink failure at this exact moment must never look like the booking itself failed.
    # See `_mark_consumed`'s own docstring for why THIS write is guarded too, not just the
    # audit call.
    store_ok = await _mark_consumed(store=ctx.store, proposal_id=ctx.proposal_id, row=row,
                                    tenant=ctx.tenant, booking_id="", action="booking_confirmed")
    if package_id:
        # THE UPSELL LEDGER'S OWN ACCEPT MOMENT — a real booking now exists; see
        # upsell_ledger.py's module docstring for why this, not silence or a heuristic, is what
        # "accepted" means here.
        await record_upsell_outcome(ctx.store, proposal_id=ctx.proposal_id, outcome="accepted",
                                    now=ctx.now, booking_id=str(booking.get("id") or ""))

    # CRITICAL: a booking confirmed by this assistant on a customer's behalf must be
    # witnessed. Fail-closed per app/core/audit.py — see auditable_actions.py. BUT the write
    # above ALREADY SUCCEEDED — this is a REAL booking, right now, in bookings-service. An
    # audit-sink outage at this exact instant must not surface to the customer as "did my
    # booking even work?" silence (an unhandled AuditUnavailable propagating out of this
    # function with no reply sent — the exact defect a 5-agent research pass on this codebase
    # found live here). So this one call is caught, logged for manual reconciliation (the
    # audit line is genuinely missing and somebody needs to know that), and the booking is
    # still reported to the customer as what it truthfully is: confirmed.
    try:
        await ctx.auditor.record("whatsapp_assistant.booking_confirmed", actor="whatsapp-assistant",
                             resource=f"booking:{booking.get('id', '')}", tenant=ctx.tenant,
                             metadata={"subject_ref": subject_ref,
                                      "service_id": args.get("service_id") or "",
                                      "package_id": args.get("package_id") or "",
                                      "intended_reward_id": args.get("reward_id") or ""})
    except AuditUnavailable:
        _logger.error("booking_confirmed_audit_gap", extra={
            "tenant": ctx.tenant, "booking_id": booking.get("id", ""), "proposal_id": ctx.proposal_id})
        result = {"kind": "booking", "booking": booking, "audit_gap": True}
        if not store_ok:
            result["store_gap"] = True
        return result
    result = {"kind": "booking", "booking": booking}
    if not store_ok:
        result["store_gap"] = True
    return result


async def _confirm_propose_cancel_booking(ctx: ExecuteContext, row: dict, args: dict[str, Any],
                                          subject_ref: str) -> dict[str, Any]:
    # THE KILL-SWITCH, RE-CHECKED AT CONFIRM TIME — see this function's own docstring on why
    # (a proposal built before the flag flipped off must not still execute after). NOT
    # consumed: refusing here leaves the proposal exactly as it was, so if the flag is a false
    # alarm and gets flipped back on within the TTL, the customer's original confirm tap is
    # simply lost, not silently half-applied — they would need to ask again, which is the
    # correct, honest outcome for "the feature was off when you tapped that".
    if not ctx.booking_management_enabled:
        raise ToolValidationError("booking management is currently disabled")
    # RE-VALIDATED AGAIN at confirm time, not just at proposal time (module docstring, point
    # 4) — booking_provider.cancel_booking re-resolves customer_id from `from_number` itself
    # and bookings-service's own internal route re-checks ownership on the STORED row before
    # doing anything, so even a long gap between propose and confirm cannot let this act on a
    # booking that changed hands or was already closed out from under the proposal.
    try:
        booking = await ctx.booking_provider.cancel_booking(
            tenant=ctx.tenant, from_number=ctx.from_number, booking_id=args["booking_id"],
            reason=str(args.get("reason") or ""), branch_id=ctx.branch_id)
    except Exception as exc:
        raise ToolValidationError(f"booking cancel failed: {exc}") from exc
    store_ok = await _mark_consumed(store=ctx.store, proposal_id=ctx.proposal_id, row=row,
                                    tenant=ctx.tenant, booking_id=booking.get("id", ""),
                                    action="booking_cancelled")
    try:
        await ctx.auditor.record("whatsapp_assistant.booking_cancelled", actor="whatsapp-assistant",
                             resource=f"booking:{booking.get('id', '')}", tenant=ctx.tenant,
                             metadata={"subject_ref": subject_ref})
    except AuditUnavailable:
        _logger.error("booking_cancelled_audit_gap", extra={
            "tenant": ctx.tenant, "booking_id": booking.get("id", ""), "proposal_id": ctx.proposal_id})
        result = {"kind": "cancel", "booking": booking, "audit_gap": True}
        if not store_ok:
            result["store_gap"] = True
        return result
    result = {"kind": "cancel", "booking": booking}
    if not store_ok:
        result["store_gap"] = True
    return result


async def _confirm_propose_reschedule_booking(ctx: ExecuteContext, row: dict, args: dict[str, Any],
                                              subject_ref: str) -> dict[str, Any]:
    if not ctx.booking_management_enabled:
        raise ToolValidationError("booking management is currently disabled")
    try:
        booking = await ctx.booking_provider.reschedule_booking(
            tenant=ctx.tenant, from_number=ctx.from_number, booking_id=args["booking_id"],
            starts_at=int(args["starts_at"]), branch_id=ctx.branch_id)
    except Exception as exc:
        raise ToolValidationError(f"booking reschedule failed: {exc}") from exc
    store_ok = await _mark_consumed(store=ctx.store, proposal_id=ctx.proposal_id, row=row,
                                    tenant=ctx.tenant, booking_id=booking.get("id", ""),
                                    action="booking_rescheduled")
    try:
        await ctx.auditor.record("whatsapp_assistant.booking_rescheduled", actor="whatsapp-assistant",
                             resource=f"booking:{booking.get('id', '')}", tenant=ctx.tenant,
                             metadata={"subject_ref": subject_ref, "starts_at": args["starts_at"]})
    except AuditUnavailable:
        _logger.error("booking_rescheduled_audit_gap", extra={
            "tenant": ctx.tenant, "booking_id": booking.get("id", ""), "proposal_id": ctx.proposal_id})
        result = {"kind": "reschedule", "booking": booking, "audit_gap": True}
        if not store_ok:
            result["store_gap"] = True
        return result
    result = {"kind": "reschedule", "booking": booking}
    if not store_ok:
        result["store_gap"] = True
    return result


# ── THE ONE REGISTRATION POINT for confirm-time execution — mirrors _TOOL_HANDLERS above.
_CONFIRM_HANDLERS: dict[str, ConfirmHandler] = {
    "propose_booking": _confirm_propose_booking,
    "propose_cancel_booking": _confirm_propose_cancel_booking,
    "propose_reschedule_booking": _confirm_propose_reschedule_booking,
}


async def _execute_confirmed_proposal(*, tenant: str, proposal_id: str, store: Any, row: dict,
                                      booking_provider: Any, auditor: Any,
                                      idempotency_key: str, now: int,
                                      branch_id: str = "", from_number: str = "",
                                      booking_management_enabled: bool = True
                                      ) -> dict[str, Any]:
    """Re-validates AGAIN: a proposal confirmed minutes after it was rendered must still hold
    against current state, not the state at proposal time.

    `booking_management_enabled` CLOSES A REAL GAP `validate_and_render`'s own allowlist check
    does not: BOOKING_MANAGEMENT_ENABLED gates whether a NEW propose_cancel_booking/
    propose_reschedule_booking proposal can be CREATED, but a proposal created BEFORE the flag was
    flipped off is still sitting in the store, still unexpired (up to proposal_ttl_seconds, e.g.
    30 minutes), and a customer's later button tap reaches straight here — a path that never
    re-checks the tool allowlist at all (propose_booking's own confirm branch below never has, on
    the same reasoning: a slot already validated once should not be re-gated on the allowlist a
    second time). For an OPERATOR-TRIGGERED EMERGENCY SHUTOFF specifically — "if we hit a problem,
    turn it false and it's done, no code change" (the explicit requirement this flag exists for) —
    that stale window is not acceptable: flipping the flag must stop booking MANAGEMENT
    (cancel/reschedule) outright, including whatever was already proposed and not yet tapped. See
    the two confirm handlers above for where this is actually enforced.
    """
    tool = row.get("tool")
    args = row.get("args") or {}
    subject_ref = row.get("subject_ref", "")

    handler = _CONFIRM_HANDLERS.get(tool)
    if handler is None:
        raise ToolValidationError(f"proposal tool {tool!r} has no confirm handler")

    ctx = ExecuteContext(
        tenant=tenant, proposal_id=proposal_id, store=store, booking_provider=booking_provider,
        auditor=auditor, idempotency_key=idempotency_key, now=now, branch_id=branch_id,
        from_number=from_number, booking_management_enabled=booking_management_enabled)
    return await handler(ctx, row, args, subject_ref)


def _parse_date(value: Any) -> int | None:
    if not value:
        return None
    import datetime as _dt
    try:
        d = _dt.datetime.strptime(str(value), "%Y-%m-%d")
        return int(d.replace(tzinfo=_dt.timezone.utc).timestamp())
    except ValueError:
        return None


def _parse_iso(value: Any) -> int | None:
    if not value:
        return None
    import datetime as _dt
    try:
        return int(_dt.datetime.fromisoformat(str(value)).timestamp())
    except ValueError:
        return None


def _fmt_slot(epoch: int) -> str:
    import datetime as _dt

    from app.core.riyadh import RIYADH
    d = _dt.datetime.fromtimestamp(epoch, RIYADH)
    return d.strftime("%Y-%m-%d %H:%M")


def _riyadh_today_start(now: int) -> int:
    """Start of "today", Riyadh business day (+3, same fixed offset _fmt_slot already uses) — the
    BOOKING_HISTORY_VISIBLE cutoff: a booking starting at or after this is "current/upcoming" and
    always shown regardless of the flag; before it is "history", gated by the flag."""
    import datetime as _dt

    from app.core.riyadh import RIYADH
    d = _dt.datetime.fromtimestamp(now, RIYADH).replace(hour=0, minute=0, second=0, microsecond=0)
    return int(d.timestamp())


# Monday..Sunday, date.weekday()'s own numbering — the SAME one the `weekly` dict this tool reads
# is keyed on (services/operations/app/core/mobile_requests.py::validate_requested_time, and
# services/bookings/app/core/operations.py::working_hours before that).
_WEEKDAY_NAMES_AR = ("الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد")


def _fmt_hm(minute_of_day: int) -> str:
    return f"{minute_of_day // 60:02d}:{minute_of_day % 60:02d}"


def _format_working_hours(weekly: dict[str, Any]) -> str:
    """One line per day, in order — deliberately not grouped ("السبت-الخميس 9-9") for a first
    version: correct and simple beats a nicer phrasing that has to get the grouping right for
    every possible schedule (a shop closed Tuesdays only, say)."""
    lines = []
    for d in range(7):
        entry = weekly.get(str(d)) or {}
        name = _WEEKDAY_NAMES_AR[d]
        if entry.get("closed"):
            lines.append(f"{name}: إجازة")
        else:
            start = int(entry.get("start_minute", 0))
            end = int(entry.get("end_minute", 0))
            lines.append(f"{name}: {_fmt_hm(start)}–{_fmt_hm(end)}")
    return "أوقات الدوام:\n" + "\n".join(lines)


def _working_hours_violation(starts_at: int, weekly: dict[str, Any]) -> str | None:
    """None when `starts_at` is inside the shop's real hours; otherwise a real, sayable reason —
    the SAME two cases operations' own `validate_requested_time()` checks, kept in sync
    deliberately (both read the identical `weekly` shape) rather than trusted to agree by luck."""
    import datetime as _dt

    from app.core.riyadh import RIYADH
    when = _dt.datetime.fromtimestamp(starts_at, RIYADH)
    entry = weekly.get(str(when.weekday())) or {}
    if entry.get("closed"):
        return "المحل مغلق في هذا اليوم — اختر وقتاً آخر."
    minute_of_day = when.hour * 60 + when.minute
    start = int(entry.get("start_minute", 0))
    end = int(entry.get("end_minute", 0))
    if not (start <= minute_of_day < end):
        return f"هذا الوقت خارج أوقات دوام المحل ({_fmt_hm(start)}–{_fmt_hm(end)})."
    return None


def _fmt_booking_row(b: dict[str, Any]) -> str:
    when = _fmt_slot(int(b.get("starts_at") or 0))
    status = {"booked": "قائم", "attended": "تم الحضور", "no_show": "لم يحضر",
             "cancelled": "ملغى"}.get(b.get("status"), b.get("status") or "")
    return f"- {when} ({status}) — رقم الحجز: {b.get('id', '')}"


async def _find_own_booking(booking_provider: Any, tenant: str, from_number: str,
                            booking_id: str, branch_id: str = "") -> dict[str, Any] | None:
    """The double-check every write tool above performs before ever building a proposal: does this
    booking id genuinely exist, and does it genuinely belong to the customer on THIS conversation's
    own phone number — never trusted from the model's claim alone. Goes through
    booking_provider.list_bookings, the SAME customer-scoped (and now branch-scoped) read
    `list_my_bookings` itself uses, so there is no second, looser path for "does this booking
    belong to me" to diverge through. `branch_id`, when this conversation has one, means a booking
    at a DIFFERENT branch is treated exactly like one that does not exist at all — a per_branch
    shop's number is a branch, and texting branch B's number must not surface branch A's booking."""
    try:
        bookings = await booking_provider.list_bookings(
            tenant=tenant, from_number=from_number, branch_id=branch_id)
    except Exception as exc:
        # SAME "caught, not left to propagate" reasoning as list_my_bookings above — this helper
        # is called from inside propose_cancel_booking/propose_reschedule_booking, where an
        # uncaught BookingAssignmentError would otherwise skip straight past the
        # ToolValidationError handling those callers (and conversation.py) rely on.
        raise ToolValidationError(f"could not verify booking ownership: {exc}") from exc
    for b in bookings:
        if str(b.get("id")) == booking_id:
            return b
    return None
