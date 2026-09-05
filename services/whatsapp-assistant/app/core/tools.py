"""Tool validation gate — the model PROPOSES, this VALIDATES, only then a button is rendered.

This is the core safety property of the whole service (design point 5 / point 9's priority list).
The sequence for every allowlisted tool is always:

    1. GeminiLlm returns a ToolCall — a NAME and ARGS the model chose. Untrusted.
    2. `validate_and_render()` here re-checks it against REAL current state (real availability,
       real points balance) — never trusts anything the model claimed about that state.
    3. Only if validation passes is an interactive WhatsApp message built and a PendingProposal
       persisted, keyed by an id that is embedded in the button/list reply ids.
    4. The state-changing action (a booking write, a points redemption) fires ONLY when a
       button_reply/list_reply comes back matching that PendingProposal id — see
       core/conversation.py::handle_button_reply. Free text can never trigger it, and the model is
       never consulted again for that decision.

`confirm_booking` DOES NOT EXIST as a tool anywhere in this file, the LLM schema (adapters/llm/
gemini.py), or the allowlist (config.py::LLM_TOOL_ALLOWLIST). Confirmation is button-only by
construction, not by convention.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any

from app.core.audit import AuditUnavailable
from app.core.models import PENDING_PROPOSALS, PendingProposal, as_row
from app.observability.logging import get_logger

_logger = get_logger("app.tools")


@dataclass(frozen=True)
class RenderedProposal:
    """What core/conversation.py hands to the WhatsAppSender — body text plus button ids that map
    back to a PendingProposal.id 1:1."""
    proposal_id: str
    body: str
    buttons: list[dict[str, str]]


class ToolValidationError(Exception):
    """The model proposed something reality does not support — a slot that is gone, a service that
    does not exist. Never rendered as a button; the caller falls back to plain text."""


async def validate_and_render(*, tenant: str, subject_ref: str, conversation_id: str,
                              tool: str, args: dict[str, Any], allowed_tools: frozenset[str],
                              store: Any, booking_provider: Any, points_summary: Any,
                              proposal_ttl_seconds: int, now: int | None = None,
                              related_services: Any = None, service_catalog: Any = None,
                              package_catalog: Any = None,
                              branch_id: str = "", from_number: str = "",
                              booking_history_visible: bool = True) -> RenderedProposal | str:
    """Returns a RenderedProposal (interactive message + pending proposal persisted) for a
    state-changing tool, or a plain str for a read-only one. Raises ToolValidationError if the
    model's proposal does not hold up against real state.
    """
    now = now if now is not None else int(time.time())

    if tool not in allowed_tools:
        # DEFENCE IN DEPTH: gemini.py already filters this before it ever reaches here, but a tool
        # name reaching this function outside the allowlist must never be trusted to mean "someone
        # forgot to filter" — it is refused again, unconditionally, at the one place execution
        # could actually happen.
        raise ToolValidationError(f"tool {tool!r} is not allowlisted")

    if tool == "check_availability":
        service_id = str(args.get("service_id") or "")
        package_id = str(args.get("package_id") or "")
        if not service_id and not package_id:
            raise ToolValidationError("check_availability requires service_id or package_id")
        if service_id and package_id:
            raise ToolValidationError("check_availability takes service_id OR package_id, not both")
        earliest = _parse_date(args.get("earliest_date")) or now
        if package_id:
            # PACKAGES ARE REAL-DRIVER ONLY — see booking_assignment.py's own module docstring:
            # the zero-infra placeholder has no concept of a package's real components/duration
            # at all. `getattr` rather than an isinstance check, matching how the booking-
            # management tools (list_my_bookings etc.) already gate the same distinction.
            avail = getattr(booking_provider, "availability_for_package", None)
            if avail is None:
                raise ToolValidationError("package booking is not available on this deployment")
            slots = await avail(tenant=tenant, package_id=package_id, earliest=earliest,
                                branch_id=branch_id)
        else:
            slots = await booking_provider.availability(
                tenant=tenant, service_id=service_id, earliest=earliest, horizon_days=0,
                branch_id=branch_id)
        if not slots:
            return "لا توجد مواعيد متاحة قريبًا."
        listed = ", ".join(_fmt_slot(s.starts_at) for s in slots[:5])
        return f"المواعيد المتاحة: {listed}"

    if tool == "propose_booking":
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
            avail = getattr(booking_provider, "availability_for_package", None)
            if avail is None:
                raise ToolValidationError("package booking is not available on this deployment")
            slots = await avail(tenant=tenant, package_id=package_id, earliest=starts_at,
                                branch_id=branch_id)
            anchor = package_id
        else:
            slots = await booking_provider.availability(
                tenant=tenant, service_id=service_id, earliest=starts_at, horizon_days=0,
                branch_id=branch_id)
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
            real_offers = await points_summary.offers(tenant=tenant, subject_ref=subject_ref)
            if not any(str(o.get("reward_id")) == reward_id for o in real_offers):
                reward_id = ""
                reward_dropped = True

        proposal_id = f"prp_{uuid.uuid4().hex[:24]}"
        proposal_args: dict[str, Any] = {"starts_at": starts_at}
        if package_id:
            proposal_args["package_id"] = package_id
        else:
            proposal_args["service_id"] = service_id
        if reward_id:
            proposal_args["reward_id"] = reward_id
        proposal = PendingProposal(
            id=proposal_id, tenant=tenant, subject_ref=subject_ref,
            conversation_id=conversation_id, tool="propose_booking",
            args=proposal_args,
            validated_snapshot={"validated_at": now},
            created_at=now, expires_at=now + proposal_ttl_seconds)
        await store.put(PENDING_PROPOSALS, proposal_id, as_row(proposal))
        body = f"هل تؤكد الموعد الساعة {_fmt_slot(starts_at)}؟"
        if reward_id:
            body += " سيتم استخدام مكافأتك عند حضورك للموعد."
        elif reward_dropped:
            body += " (تعذّر إرفاق المكافأة المطلوبة — يمكنك سؤالي عنها مرة أخرى.)"
        return RenderedProposal(
            proposal_id=proposal_id, body=body,
            buttons=[{"id": f"{proposal_id}:confirm", "title": "تأكيد"},
                    {"id": f"{proposal_id}:cancel", "title": "إلغاء"}])

    if tool == "get_customer_points_summary":
        summary = await points_summary.summary(tenant=tenant, subject_ref=subject_ref)
        return summary.get("text", "")

    if tool == "suggest_redeemable_offer":
        # READ-ONLY, same posture as suggest_related_service below — no proposal, no button, no
        # PendingProposal row. A reward is no longer spent standalone, unconditionally, the moment
        # a customer taps confirm: it rides on a real booking (`propose_booking`'s own `reward_id`
        # argument) so nothing is ever spent until the shop actually delivers the service. See
        # app/core/booking_assignment.py's `intended_reward_id` note for the full reasoning — this
        # is the structural fix, not a policy note, for a no-show costing the shop a reward with
        # nothing to show for it.
        offer = await points_summary.redeemable_offer(tenant=tenant, subject_ref=subject_ref)
        if not offer:
            return "لا توجد مكافأة متاحة برصيدك الحالي بعد."
        return (f"يمكنك استخدام «{offer['reward_name']}» بنقاطك الحالية — فقط اذكرها عند حجز "
               f"موعدك وسأرفقها به.")

    if tool == "suggest_related_service":
        service_id = str(args.get("service_id") or "")
        if not service_id:
            raise ToolValidationError("suggest_related_service requires service_id")
        # READ-ONLY, like check_availability/get_customer_points_summary — this NEVER adds the
        # related service to a booking itself; a customer who wants it still goes through
        # propose_booking/button-confirm like any other service. No proposal, no button, no
        # PendingProposal row.
        related_ids = (await related_services.related_to(tenant, service_id)
                      if related_services is not None else [])
        if not related_ids:
            return "لا توجد خدمة أخرى تُطلب عادةً مع هذه الخدمة."
        names_by_id: dict[str, str] = {}
        if service_catalog is not None:
            for s in await service_catalog.list_active(tenant):
                names_by_id[str(s.get("id"))] = str(s.get("name") or s.get("id"))
        # A "pkg:<id>" ANSWER (packages feature) — this service and that PACKAGE are bought
        # together often. Resolved against the package catalogue, never the service one (a
        # package id would never be found there and would print the raw "pkg:..." string).
        # UNLIKE AN ORDINARY SERVICE SUGGESTION, A PACKAGE'S PRICE IS SAFE TO STATE — see
        # package_catalog.py's own docstring: it is the owner's own published price, not a number
        # the engine or this reply invents.
        packages_by_id: dict[str, dict[str, Any]] = {}
        if package_catalog is not None and any(rid.startswith("pkg:") for rid in related_ids):
            for p in await package_catalog.list_active(tenant):
                packages_by_id[str(p.get("id"))] = p

        plain_names: list[str] = []
        package_lines: list[str] = []
        for rid in related_ids:
            if rid.startswith("pkg:"):
                pkg = packages_by_id.get(rid[len("pkg:"):])
                if pkg is None:
                    continue    # a peer read that failed, or a package retired since — skipped
                riyals = int(pkg.get("price_minor") or 0) / 100
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

    if tool == "list_my_bookings":
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
            bookings = await booking_provider.list_bookings(tenant=tenant, from_number=from_number)
        except Exception as exc:
            raise ToolValidationError(f"could not list bookings: {exc}") from exc
        wants_history = bool(args.get("include_history"))
        upcoming = [b for b in bookings if int(b.get("starts_at") or 0) >= _riyadh_today_start(now)]
        if wants_history and not booking_history_visible:
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
        rows = bookings if (wants_history and booking_history_visible) else upcoming
        if not rows:
            return ("لا توجد حجوزات قادمة لك حاليًا." if not wants_history
                   else "لا توجد حجوزات لك.")
        lines = [_fmt_booking_row(b) for b in sorted(rows, key=lambda b: b.get("starts_at") or 0)]
        return "حجوزاتك:\n" + "\n".join(lines)

    if tool == "propose_cancel_booking":
        booking_id = str(args.get("booking_id") or "")
        if not booking_id:
            raise ToolValidationError("propose_cancel_booking requires booking_id")
        booking = await _find_own_booking(booking_provider, tenant, from_number, booking_id)
        if booking is None:
            raise ToolValidationError("هذا الحجز غير موجود أو لا يخصّك")
        if booking.get("status") == "cancelled":
            return "هذا الموعد ملغى بالفعل."
        if booking.get("status") in ("attended", "no_show"):
            return "هذا الموعد انتهى، تواصل مع المحل مباشرة."

        reason = str(args.get("reason") or "")[:300]
        proposal_id = f"prp_{uuid.uuid4().hex[:24]}"
        proposal = PendingProposal(
            id=proposal_id, tenant=tenant, subject_ref=subject_ref,
            conversation_id=conversation_id, tool="propose_cancel_booking",
            args={"booking_id": booking_id, "reason": reason},
            validated_snapshot={"validated_at": now},
            created_at=now, expires_at=now + proposal_ttl_seconds)
        await store.put(PENDING_PROPOSALS, proposal_id, as_row(proposal))
        body = f"هل تؤكد إلغاء موعدك يوم {_fmt_slot(int(booking['starts_at']))}؟"
        return RenderedProposal(
            proposal_id=proposal_id, body=body,
            buttons=[{"id": f"{proposal_id}:confirm", "title": "تأكيد الإلغاء"},
                    {"id": f"{proposal_id}:cancel", "title": "تراجع"}])

    if tool == "propose_reschedule_booking":
        booking_id = str(args.get("booking_id") or "")
        new_starts_at = _parse_iso(args.get("new_starts_at_iso"))
        if not booking_id or new_starts_at is None:
            raise ToolValidationError(
                "propose_reschedule_booking requires booking_id and new_starts_at_iso")
        booking = await _find_own_booking(booking_provider, tenant, from_number, booking_id)
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
        slots = await booking_provider.availability(
            tenant=tenant, service_id=service_id, earliest=new_starts_at, horizon_days=0,
            branch_id=str(booking.get("branch_id") or ""), exclude_booking_id=booking_id)
        if not any(s.starts_at == new_starts_at for s in slots):
            raise ToolValidationError(
                f"proposed slot {new_starts_at} is not actually available")

        proposal_id = f"prp_{uuid.uuid4().hex[:24]}"
        proposal = PendingProposal(
            id=proposal_id, tenant=tenant, subject_ref=subject_ref,
            conversation_id=conversation_id, tool="propose_reschedule_booking",
            args={"booking_id": booking_id, "starts_at": new_starts_at},
            validated_snapshot={"validated_at": now},
            created_at=now, expires_at=now + proposal_ttl_seconds)
        await store.put(PENDING_PROPOSALS, proposal_id, as_row(proposal))
        body = f"هل تؤكد نقل موعدك إلى {_fmt_slot(new_starts_at)}؟"
        return RenderedProposal(
            proposal_id=proposal_id, body=body,
            buttons=[{"id": f"{proposal_id}:confirm", "title": "تأكيد"},
                    {"id": f"{proposal_id}:cancel", "title": "تراجع"}])

    raise ToolValidationError(f"tool {tool!r} has no handler")


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
    """The ONLY path that turns a proposal into a real write — reached exclusively from a matching
    button_reply id (core/conversation.py::handle_button_reply). Re-validates AGAIN: a proposal
    confirmed minutes after it was rendered must still hold against current state, not the state
    at proposal time.

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
    the two branches below for where this is actually enforced.
    """
    now = now if now is not None else int(time.time())
    row = await store.get(PENDING_PROPOSALS, proposal_id)
    if row is None or row.get("tenant") != tenant:
        raise ToolValidationError("no such pending proposal for this tenant")
    if row.get("consumed"):
        raise ToolValidationError("proposal already consumed")
    if int(row.get("expires_at") or 0) < now:
        raise ToolValidationError("proposal expired")

    tool = row.get("tool")
    args = row.get("args") or {}
    subject_ref = row.get("subject_ref", "")

    if tool == "propose_booking":
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
                hold = getattr(booking_provider, "hold_and_confirm_package", None)
                if hold is None:
                    raise ToolValidationError("package booking is not available on this deployment")
                booking = await hold(
                    tenant=tenant, subject_ref=subject_ref, package_id=package_id,
                    starts_at=int(args["starts_at"]), idempotency_key=idempotency_key,
                    branch_id=branch_id, from_number=from_number,
                    intended_reward_id=str(args.get("reward_id") or ""))
            else:
                booking = await booking_provider.hold_and_confirm(
                    tenant=tenant, subject_ref=subject_ref, service_id=args["service_id"],
                    starts_at=int(args["starts_at"]), idempotency_key=idempotency_key,
                    branch_id=branch_id, from_number=from_number,
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
        store_ok = await _mark_consumed(store=store, proposal_id=proposal_id, row=row,
                                        tenant=tenant, booking_id="", action="booking_confirmed")

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
            await auditor.record("whatsapp_assistant.booking_confirmed", actor="whatsapp-assistant",
                                 resource=f"booking:{booking.get('id', '')}", tenant=tenant,
                                 metadata={"subject_ref": subject_ref,
                                          "service_id": args.get("service_id") or "",
                                          "package_id": args.get("package_id") or "",
                                          "intended_reward_id": args.get("reward_id") or ""})
        except AuditUnavailable:
            _logger.error("booking_confirmed_audit_gap", extra={
                "tenant": tenant, "booking_id": booking.get("id", ""), "proposal_id": proposal_id})
            result = {"kind": "booking", "booking": booking, "audit_gap": True}
            if not store_ok:
                result["store_gap"] = True
            return result
        result = {"kind": "booking", "booking": booking}
        if not store_ok:
            result["store_gap"] = True
        return result

    if tool == "propose_cancel_booking":
        # THE KILL-SWITCH, RE-CHECKED AT CONFIRM TIME — see this function's own docstring on why
        # (a proposal built before the flag flipped off must not still execute after). NOT
        # consumed: refusing here leaves the proposal exactly as it was, so if the flag is a false
        # alarm and gets flipped back on within the TTL, the customer's original confirm tap is
        # simply lost, not silently half-applied — they would need to ask again, which is the
        # correct, honest outcome for "the feature was off when you tapped that".
        if not booking_management_enabled:
            raise ToolValidationError("booking management is currently disabled")
        # RE-VALIDATED AGAIN at confirm time, not just at proposal time (module docstring, point
        # 4) — booking_provider.cancel_booking re-resolves customer_id from `from_number` itself
        # and bookings-service's own internal route re-checks ownership on the STORED row before
        # doing anything, so even a long gap between propose and confirm cannot let this act on a
        # booking that changed hands or was already closed out from under the proposal.
        try:
            booking = await booking_provider.cancel_booking(
                tenant=tenant, from_number=from_number, booking_id=args["booking_id"],
                reason=str(args.get("reason") or ""))
        except Exception as exc:
            raise ToolValidationError(f"booking cancel failed: {exc}") from exc
        store_ok = await _mark_consumed(store=store, proposal_id=proposal_id, row=row,
                                        tenant=tenant, booking_id=booking.get("id", ""),
                                        action="booking_cancelled")
        try:
            await auditor.record("whatsapp_assistant.booking_cancelled", actor="whatsapp-assistant",
                                 resource=f"booking:{booking.get('id', '')}", tenant=tenant,
                                 metadata={"subject_ref": subject_ref})
        except AuditUnavailable:
            _logger.error("booking_cancelled_audit_gap", extra={
                "tenant": tenant, "booking_id": booking.get("id", ""), "proposal_id": proposal_id})
            result = {"kind": "cancel", "booking": booking, "audit_gap": True}
            if not store_ok:
                result["store_gap"] = True
            return result
        result = {"kind": "cancel", "booking": booking}
        if not store_ok:
            result["store_gap"] = True
        return result

    if tool == "propose_reschedule_booking":
        if not booking_management_enabled:
            raise ToolValidationError("booking management is currently disabled")
        try:
            booking = await booking_provider.reschedule_booking(
                tenant=tenant, from_number=from_number, booking_id=args["booking_id"],
                starts_at=int(args["starts_at"]))
        except Exception as exc:
            raise ToolValidationError(f"booking reschedule failed: {exc}") from exc
        store_ok = await _mark_consumed(store=store, proposal_id=proposal_id, row=row,
                                        tenant=tenant, booking_id=booking.get("id", ""),
                                        action="booking_rescheduled")
        try:
            await auditor.record("whatsapp_assistant.booking_rescheduled", actor="whatsapp-assistant",
                                 resource=f"booking:{booking.get('id', '')}", tenant=tenant,
                                 metadata={"subject_ref": subject_ref, "starts_at": args["starts_at"]})
        except AuditUnavailable:
            _logger.error("booking_rescheduled_audit_gap", extra={
                "tenant": tenant, "booking_id": booking.get("id", ""), "proposal_id": proposal_id})
            result = {"kind": "reschedule", "booking": booking, "audit_gap": True}
            if not store_ok:
                result["store_gap"] = True
            return result
        result = {"kind": "reschedule", "booking": booking}
        if not store_ok:
            result["store_gap"] = True
        return result

    raise ToolValidationError(f"proposal tool {tool!r} has no confirm handler")


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
    d = _dt.datetime.fromtimestamp(epoch, _dt.timezone(_dt.timedelta(hours=3)))
    return d.strftime("%Y-%m-%d %H:%M")


def _riyadh_today_start(now: int) -> int:
    """Start of "today", Riyadh business day (+3, same fixed offset _fmt_slot already uses) — the
    BOOKING_HISTORY_VISIBLE cutoff: a booking starting at or after this is "current/upcoming" and
    always shown regardless of the flag; before it is "history", gated by the flag."""
    import datetime as _dt
    tz = _dt.timezone(_dt.timedelta(hours=3))
    d = _dt.datetime.fromtimestamp(now, tz).replace(hour=0, minute=0, second=0, microsecond=0)
    return int(d.timestamp())


def _fmt_booking_row(b: dict[str, Any]) -> str:
    when = _fmt_slot(int(b.get("starts_at") or 0))
    status = {"booked": "قائم", "attended": "تم الحضور", "no_show": "لم يحضر",
             "cancelled": "ملغى"}.get(b.get("status"), b.get("status") or "")
    return f"- {when} ({status}) — رقم الحجز: {b.get('id', '')}"


async def _find_own_booking(booking_provider: Any, tenant: str, from_number: str,
                            booking_id: str) -> dict[str, Any] | None:
    """The double-check every write tool above performs before ever building a proposal: does this
    booking id genuinely exist, and does it genuinely belong to the customer on THIS conversation's
    own phone number — never trusted from the model's claim alone. Goes through
    booking_provider.list_bookings, the SAME customer-scoped read `list_my_bookings` itself uses,
    so there is no second, looser path for "does this booking belong to me" to diverge through."""
    try:
        bookings = await booking_provider.list_bookings(tenant=tenant, from_number=from_number)
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
