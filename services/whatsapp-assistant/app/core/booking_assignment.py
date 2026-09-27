"""RealBookingProvider — the BookingProvider port backed by REAL peers (Phase 4), replacing
`ConfigDrivenAvailabilityProvider`'s zero-infra placeholder once bookings-service is actually
deployed. Opt-in only: `BOOKING_PROVIDER_DRIVER=real` (see app/config.py's own note).

THE ONE POLICY QUESTION THIS MODULE ANSWERS: which operator does an AI-led WhatsApp booking get
assigned to. There is no chat UI for a customer to browse staff photos and pick one — the owner's own
framing of this feature ("تحديد الموظفه مهم") asked that a real operator be assigned, not that a
customer be made to choose. A customer naming a PREFERRED stylist is a real, later feature (a
free-text name would need to be resolved against this same list, matched, and confirmed) — not
built here; this is recorded as a documented limitation, not solved by guessing from an
unstructured message.

ASSIGNMENT-MODE REDESIGN, PHASE 4 — `_pick_operator` used to be a naive "sorted by id, first
eligible" placeholder, entirely local to this module and blind to whatever algorithm a shop had
actually chosen on the console (services/bookings/app/core/assignment.py,
AssignmentSettingsStore). It now calls the SAME merge-and-rank engine the console's own «أي متاح»
picker uses, over the internal tier (`/internal/bookings/nearest-any-real`, bookings-service's own
`BookingOperations.nearest_slots_any`) — one engine, every channel, never a second policy that can
silently disagree with what the shop configured. bookings-service's own `create()`/`nearest_slot()`
still re-asks and re-refuses independently at write time regardless — this module never trusts its
own pick as final, exactly as before.

NOTHING HERE INVENTS A BRANCH. `availability()`/`hold_and_confirm()` both REQUIRE a real
`branch_id` and return "not available"/refuse outright without one — exactly the same "ask,
never guess" discipline Phase 3's branch-selection gate exists to satisfy before a booking
conversation ever reaches this module.
"""
from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from typing import Any

from app.ports.booking_provider import Slot

# THE ATTRIBUTION CONSTANT — stamped as `created_by` on every booking this module makes, so a
# report can later tell an AI-made booking apart from a staff-made one (see internal.py's own
# `InternalCreateBookingIn.created_by`). Same naming family as this service's own audit `actor`
# values elsewhere (conversation.py/tools.py's "whatsapp-assistant" on `auditor.record` calls) —
# one honest constant, never a customer name or phone.
ACTOR = "whatsapp-assistant"


class BookingAssignmentError(Exception):
    """No eligible operator could be found for this branch/service — surfaced to
    core/tools.py::validate_and_render as "no slots", never as a crash; a customer asking about a
    service nobody at this branch can do gets a plain "no slots available" the same as a
    genuinely fully-booked one, not a stack trace."""


class _Peer:
    """One JSON-over-HTTP internal call, same shape as every other peer client in this
    service (customer_lookup.py, branch_directory.py, service_catalog.py) — never a shared
    import, this service holds no shared library with any other."""

    def __init__(self, *, url: str, path: str, token: str, timeout: int) -> None:
        # `path` may carry a "{booking_id}"-style placeholder (see BOOKINGS_CANCEL_PATH/
        # BOOKINGS_RESCHEDULE_PATH) — left unformatted here, filled in per-call by `call()`'s
        # own `path_params`, since a single _Peer instance is built once at startup for every
        # booking id it will ever be asked about, not one per id.
        self._base = url.rstrip("/")
        self._path = path
        self._token = token
        self._timeout = timeout

    def call(self, payload: dict[str, Any], path_params: dict[str, str] | None = None
             ) -> dict[str, Any] | None:
        url = self._base + self._path.format(**(path_params or {}))
        body = json.dumps(payload).encode()
        req = urllib.request.Request(
            url, data=body, method="POST",
            headers={"Content-Type": "application/json", "X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                if not 200 <= resp.status < 300:
                    return None
                return json.loads(resp.read() or b"{}")
        except (urllib.error.URLError, OSError, ValueError):
            return None


class RealBookingProvider:
    driver = "real"

    def __init__(self, *, branch_operators: _Peer, service_eligibility: _Peer,
                customer_id_by_phone: _Peer, nearest_real_slot: _Peer,
                nearest_any_real_slot: _Peer, create_booking: _Peer,
                bookings_for_customer: _Peer | None = None, cancel_booking: _Peer | None = None,
                reschedule_booking: _Peer | None = None,
                package_eligibility: _Peer | None = None) -> None:
        self._branch_operators = branch_operators
        self._service_eligibility = service_eligibility
        self._customer_id_by_phone = customer_id_by_phone
        self._nearest_real_slot = nearest_real_slot
        # THE REAL ENGINE (phase 4) — see module docstring. `_pick_operator` below is the only
        # caller; kept as its own peer (not folded into `nearest_real_slot`) because the two ask
        # genuinely different questions: one operator's own diary vs. the shop's whole eligible
        # pool ranked by its own algorithm.
        self._nearest_any_real_slot = nearest_any_real_slot
        self._create_booking = create_booking
        # Optional — only set when BOOKING_MANAGEMENT_ENABLED is true at build() time (see below).
        # None-guarded at every call site so an old/half-configured deployment fails the same loud
        # way the rest of this module already does, rather than a silent AttributeError.
        self._bookings_for_customer = bookings_for_customer
        self._cancel_booking = cancel_booking
        self._reschedule_booking = reschedule_booking
        # OPTIONAL, SAME SHAPE — packages feature. `availability_for_package`/
        # `hold_and_confirm_package` below are EXTRA methods, not part of `BookingProvider`'s own
        # Protocol (app/ports/booking_provider.py stays untouched, deliberately — see that file's
        # own docstring on why every package capability lives here, checked by the caller via
        # `getattr`, the same pattern the booking-management methods below already use). A
        # deployment with this unset simply cannot offer a package through the chat at all; the
        # ordinary single-service path is completely unaffected either way.
        self._package_eligibility = package_eligibility

    async def _eligible_pool(self, tenant: str, branch_id: str,
                             service_ids: list[str]) -> list[str]:
        """This branch's own active operators, narrowed to whoever is eligible for EVERY id in
        `service_ids` — the shared first half of `_pick_operator` below, factored out so the merge
        call can be skipped entirely once the pool is already known empty.

        A SINGLE service is just the one-element-list case; nothing here is new for that caller.
        For several (the WhatsApp Flow's multi-select service step, platform v0.19.16+), the
        eligible pool is the INTERSECTION across all of them — an operator must be able to do
        EVERY chosen service, never just one of several, the same "the write refuses, not only
        the suggestion" posture the rest of this module already holds. A service with no
        restriction at all (`allowed is None`) simply contributes no narrowing of its own."""
        # OFF THE EVENT LOOP — see core/customer_lookup.py::HttpCustomerLookup.resolve.
        ops = await asyncio.to_thread(
            self._branch_operators.call, {"tenant": tenant, "branch_id": branch_id})
        candidates = [str(o.get("id")) for o in (ops or {}).get("operators") or []]
        if not candidates:
            raise BookingAssignmentError(f"no active operators at branch {branch_id!r}")

        elig = await asyncio.to_thread(
            self._service_eligibility.call, {"tenant": tenant, "service_ids": list(service_ids)})
        eligible_staff = (elig or {}).get("eligible_staff_ids", {})
        eligible_pool = candidates
        for service_id in service_ids:
            allowed = eligible_staff.get(service_id)
            # `None` (unrestricted) MEANS EVERY ACTIVE OPERATOR — same contract
            # services/operations/app/api/internal.py::internal_service_eligibility documents; an
            # empty LIST (as opposed to a missing key) is the real, if unusual, "restricted to
            # nobody" state and must narrow the pool to nothing, not fall back to "everyone".
            if allowed is not None:
                eligible_pool = [c for c in eligible_pool if c in allowed]
        if not eligible_pool:
            raise BookingAssignmentError(
                f"no operator at branch {branch_id!r} is eligible for services {service_ids!r}")
        return eligible_pool

    async def _pick_slot(self, tenant: str, branch_id: str, service_ids: list[str], after: int,
                         exclude_booking_id: str = "", operator_id: str = "") -> tuple[str, int]:
        """THE REAL ENGINE (phase 4) — see module docstring. Returns (operator_id, starts_at)
        TOGETHER, from the SAME merge call — `availability()` used to discard the slot this same
        pick already found and immediately re-ask a second peer (`nearest_real_slot`) for that
        one operator's own next opening; that redundant round trip, and the small window for the
        two answers to disagree under real concurrency, are both gone now that one call answers
        both questions at once. `after` anchors the search: `availability()` passes `earliest`
        (who is free soonest from right now); `hold_and_confirm()` passes the exact `starts_at`
        the customer already confirmed (who is ACTUALLY free at that specific instant — the shop's
        algorithm may have ranked things differently a moment earlier; each call trusts
        bookings-service's own answer at ITS OWN moment, never a stale one from the other).
        Raises BookingAssignmentError rather than returning an empty id so every caller is forced
        to handle "nothing free" explicitly instead of silently proceeding with one.

        `operator_id`, WHEN GIVEN, PINS THE POOL TO THAT ONE PERSON — never trusted blindly: it
        still goes through `_eligible_pool` and is refused (BookingAssignmentError) if that
        operator turns out not to be eligible for EVERY id in `service_ids` at this branch, the
        same "the write refuses, not only the suggestion" rule every other pick in this module
        already holds. This is what a `named`-mode service picked via the WhatsApp Flow (Phase 5)
        needs: the customer already chose WHO on an earlier screen — the merge search below
        exists to answer "who is free", never to override a choice the customer already made."""
        eligible_pool = await self._eligible_pool(tenant, branch_id, service_ids)
        if operator_id:
            if operator_id not in eligible_pool:
                raise BookingAssignmentError(
                    f"operator {operator_id!r} is not eligible for services {service_ids!r} "
                    f"at branch {branch_id!r}")
            eligible_pool = [operator_id]
        payload: dict[str, Any] = {
            "tenant": tenant, "branch_id": branch_id, "operator_ids": eligible_pool,
            "service_ids": list(service_ids), "after": after, "max_slots": 1}
        if exclude_booking_id:
            payload["exclude_booking_id"] = exclude_booking_id
        # OFF THE EVENT LOOP — see core/customer_lookup.py::HttpCustomerLookup.resolve.
        result = await asyncio.to_thread(self._nearest_any_real_slot.call, payload)
        slots = (result or {}).get("slots") or []
        if not slots:
            raise BookingAssignmentError(
                f"no operator at branch {branch_id!r} is free for services {service_ids!r} "
                f"near {after}")
        return str(slots[0]["operator_id"]), int(slots[0]["starts_at"])

    async def _pick_operator(self, tenant: str, branch_id: str, service_ids: list[str], after: int,
                             operator_id: str = "") -> str:
        """Same engine as `_pick_slot`, for a caller (`hold_and_confirm`) that already knows WHEN
        (the customer's own confirmed time) and only needs WHO."""
        picked, _starts_at = await self._pick_slot(tenant, branch_id, service_ids, after,
                                                    operator_id=operator_id)
        return picked

    async def _resolve_customer_id(self, tenant: str, from_number: str, referral_code: str = ""
                                   ) -> tuple[str, dict[str, Any] | None]:
        """`(customer_id, referral_registration)` — the second is `None` unless a code was
        actually offered; see `hold_and_confirm_multi`'s own note on why this is the real
        "new customer" moment for a WhatsApp-initiated booking, never `hold_and_confirm` alone."""
        # OFF THE EVENT LOOP — see core/customer_lookup.py::HttpCustomerLookup.resolve.
        body: dict[str, Any] = {"tenant": tenant, "phone": from_number}
        if referral_code:
            body["referral_code"] = referral_code
        result = await asyncio.to_thread(self._customer_id_by_phone.call, body)
        return (str((result or {}).get("customer_id") or ""),
               (result or {}).get("referral_registration"))

    async def availability(self, *, tenant: str, service_id: str, earliest: int,
                           horizon_days: int, branch_id: str = "",
                           exclude_booking_id: str = "") -> list[Slot]:
        # NO BRANCH, NO ANSWER — see module docstring. `horizon_days` is accepted for Protocol
        # compatibility but unused: the merge always returns the single NEXT open candidate
        # across the whole eligible pool, not a set across a window (the "أقرب موعد" shape, not
        # the grid's).
        #
        # `exclude_booking_id` (booking-management-via-WhatsApp's reschedule check) — the booking
        # being moved is not a conflict with itself; without this, asking "is my own current time,
        # or any nearby overlapping time, available?" always reads as busy against the booking's
        # OWN occupancy and the search jumps past to the next genuinely free slot instead. See
        # app/ports/booking_provider.py's own note.
        if not branch_id:
            return []
        try:
            _operator_id, starts_at = await self._pick_slot(
                tenant, branch_id, [service_id], earliest, exclude_booking_id=exclude_booking_id)
        except BookingAssignmentError:
            return []
        # DURATION IS 0 HERE, ON PURPOSE — bookings-service computes the real duration itself at
        # create() time from `operations`' own service-durations lookup (the single source of
        # truth for it); nothing this provider tells the caller about duration is ever trusted
        # back at write time, so inventing a number here would only be decoration, never a fact
        # anything downstream relies on. See core/tools.py's `_fmt_slot` — the only reader of a
        # Slot's fields outside this module — which never reads `duration_minutes` at all.
        return [Slot(starts_at=int(starts_at), duration_minutes=0)]

    async def hold_and_confirm(self, *, tenant: str, subject_ref: str, service_id: str,
                               starts_at: int, idempotency_key: str, branch_id: str = "",
                               from_number: str = "", intended_reward_id: str = "",
                               preferred_operator_id: str = "", referral_code: str = "") -> dict:
        """The single-service shape the AI text channel's own port (`app/ports/booking_provider.py`)
        still declares — kept byte-for-byte unchanged so `ConfigDrivenAvailabilityProvider`'s own
        matching signature, and every `tools.py` call site, need no edit. See
        `hold_and_confirm_multi` below for the WhatsApp Flow's own multi-select entry point — the
        same underlying write, just with a real list instead of one wrapped in a list here."""
        return await self.hold_and_confirm_multi(
            tenant=tenant, subject_ref=subject_ref, service_ids=[service_id],
            starts_at=starts_at, idempotency_key=idempotency_key, branch_id=branch_id,
            from_number=from_number, intended_reward_id=intended_reward_id,
            preferred_operator_id=preferred_operator_id, referral_code=referral_code)

    async def hold_and_confirm_multi(self, *, tenant: str, subject_ref: str,
                                     service_ids: list[str], starts_at: int, idempotency_key: str,
                                     branch_id: str = "", from_number: str = "",
                                     intended_reward_id: str = "",
                                     preferred_operator_id: str = "",
                                     referral_code: str = "") -> dict:
        """The real write, for one service or several — see module docstring on why this is a
        SIBLING to `hold_and_confirm`, not a signature change to it (same shape as
        `hold_and_confirm_package` right below being a sibling of this one, not a merge into it).
        `bookings-service`'s own `/internal/bookings` route already accepts `service_ids` as a
        list and computes duration from the REAL set server-side (confirmed directly against
        `InternalCreateBookingIn`) — nothing about the write itself is new; only the operator
        pick now has to find someone eligible for EVERY chosen service (see `_eligible_pool`'s
        own docstring), not just one.

        `referral_code` IS RESOLVED HERE, NOT AT THE BOOKING WRITE — `_resolve_customer_id` is
        the real "new customer" moment (owner instruction, 2026-09-27): by the time
        bookings-service's own `create()` runs, the customer already exists either way, same
        reasoning `services/operations/app/core/operations.py::ensure_customer`'s own docstring
        holds for the console/mobile booking dialogs. A real grant or a rejection rides back on
        the returned dict's own `referral_registration` key — never allowed to affect whether the
        booking itself is made."""
        if not service_ids:
            raise BookingAssignmentError("no service chosen — cannot create a real booking")
        if not branch_id:
            raise BookingAssignmentError("no branch on this conversation — cannot create a real booking")
        if not from_number:
            raise BookingAssignmentError("no phone on this conversation — cannot resolve a customer")

        customer_id, referral_registration = await self._resolve_customer_id(
            tenant, from_number, referral_code)
        if not customer_id:
            raise BookingAssignmentError("could not resolve a real customer for this phone")

        # `preferred_operator_id` (Phase 5): the WhatsApp Flow's own `named`-service staff step
        # already resolved WHO — see `_pick_operator`'s own docstring on why this still goes
        # through the eligible-pool check rather than being trusted as-is.
        operator_id = await self._pick_operator(tenant, branch_id, service_ids, starts_at,
                                                operator_id=preferred_operator_id)

        # INTENT ONLY, NEVER A SPEND — bookings-service's own `create()` only stamps this on the
        # row (see InternalCreateBookingIn.intended_reward_id's own docstring); the actual points
        # spend happens exclusively at attend(), and cancel()/no_show() never touch it. This is
        # the whole reason a WhatsApp-initiated reward costs the shop nothing on a no-show — see
        # core/tools.py's `propose_booking` branch for how `reward_id` gets here.
        body = {"tenant": tenant, "branch_id": branch_id, "operator_id": operator_id,
                "customer_id": customer_id, "service_ids": list(service_ids),
                "starts_at": starts_at, "idempotency_key": idempotency_key, "created_by": ACTOR}
        if intended_reward_id:
            body["intended_reward_id"] = intended_reward_id
        # OFF THE EVENT LOOP — see core/customer_lookup.py::HttpCustomerLookup.resolve.
        result = await asyncio.to_thread(self._create_booking.call, body)
        if result is None or not result.get("id"):
            raise BookingAssignmentError("bookings-service refused or was unreachable")
        if referral_registration is not None:
            result["referral_registration"] = referral_registration
        return result

    # ── packages (book a PACKAGE instead of a single service) ─────────────────────────────────
    # Same shape as availability()/hold_and_confirm() above, but the peer questions are answered
    # by bookings-service's own package-aware routes (nearest-real-slot/create with `package_id`
    # set instead of `service_ids` — see services/bookings' own operations.py, phase 2 of this
    # feature) — which already enforce the package's schedule against the REAL requested date and
    # the eligibility-intersection rule for multi-specialist packages. Nothing about the schedule
    # or eligibility logic is duplicated here; this module only resolves which operator to try and
    # forwards the call.

    async def _pick_operator_for_package(self, tenant: str, branch_id: str, package_id: str) -> str:
        """Same "first eligible, deterministic" policy as `_pick_operator` — but "eligible" here
        already accounts for the multi-specialist degradation (operations' own package-eligibility
        route: a genuinely disjoint-specialty package reads as unrestricted, never impossible)."""
        # OFF THE EVENT LOOP — see core/customer_lookup.py::HttpCustomerLookup.resolve.
        ops = await asyncio.to_thread(
            self._branch_operators.call, {"tenant": tenant, "branch_id": branch_id})
        candidates = [str(o.get("id")) for o in (ops or {}).get("operators") or []]
        if not candidates:
            raise BookingAssignmentError(f"no active operators at branch {branch_id!r}")
        if self._package_eligibility is None:
            return sorted(candidates)[0]
        elig = await asyncio.to_thread(
            self._package_eligibility.call, {"tenant": tenant, "package_id": package_id})
        allowed = (elig or {}).get("eligible_staff_ids")
        eligible_pool = candidates if allowed is None else [c for c in candidates if c in allowed]
        if not eligible_pool:
            raise BookingAssignmentError(
                f"no operator at branch {branch_id!r} is eligible for package {package_id!r}")
        return sorted(eligible_pool)[0]

    async def availability_for_package(self, *, tenant: str, package_id: str, earliest: int,
                                       branch_id: str = "", exclude_booking_id: str = ""
                                       ) -> list[Slot]:
        if not branch_id:
            return []
        try:
            operator_id = await self._pick_operator_for_package(tenant, branch_id, package_id)
        except BookingAssignmentError:
            return []
        payload: dict[str, Any] = {
            "tenant": tenant, "branch_id": branch_id, "operator_id": operator_id,
            "package_id": package_id, "after": earliest}
        if exclude_booking_id:
            payload["exclude_booking_id"] = exclude_booking_id
        # OFF THE EVENT LOOP — see core/customer_lookup.py::HttpCustomerLookup.resolve.
        result = await asyncio.to_thread(self._nearest_real_slot.call, payload)
        starts_at = (result or {}).get("starts_at")
        if not starts_at:
            return []
        # DURATION 0 — same reasoning as `availability()` above: bookings-service computes the
        # real duration itself, from the package's own LIVE components, at create() time.
        return [Slot(starts_at=int(starts_at), duration_minutes=0)]

    async def hold_and_confirm_package(self, *, tenant: str, subject_ref: str, package_id: str,
                                       starts_at: int, idempotency_key: str, branch_id: str = "",
                                       from_number: str = "", intended_reward_id: str = "",
                                       referral_code: str = "") -> dict:
        if not branch_id:
            raise BookingAssignmentError("no branch on this conversation — cannot create a real booking")
        if not from_number:
            raise BookingAssignmentError("no phone on this conversation — cannot resolve a customer")

        customer_id, referral_registration = await self._resolve_customer_id(
            tenant, from_number, referral_code)
        if not customer_id:
            raise BookingAssignmentError("could not resolve a real customer for this phone")

        operator_id = await self._pick_operator_for_package(tenant, branch_id, package_id)

        body = {"tenant": tenant, "branch_id": branch_id, "operator_id": operator_id,
                "customer_id": customer_id, "package_id": package_id, "starts_at": starts_at,
                "idempotency_key": idempotency_key, "created_by": ACTOR}
        if intended_reward_id:
            body["intended_reward_id"] = intended_reward_id
        # OFF THE EVENT LOOP — see core/customer_lookup.py::HttpCustomerLookup.resolve.
        result = await asyncio.to_thread(self._create_booking.call, body)
        if result is None or not result.get("id"):
            raise BookingAssignmentError("bookings-service refused or was unreachable")
        if referral_registration is not None:
            result["referral_registration"] = referral_registration
        return result

    # ── booking management (view/cancel/reschedule an EXISTING booking) ──────────────────────
    # Each method resolves customer_id from the phone the same way hold_and_confirm does above —
    # the caller NEVER supplies a customer_id itself, so there is no parameter anywhere in this
    # class that could be pointed at someone else's bookings. Ownership of the specific booking
    # id is re-checked again, server-side, by bookings-service's own internal route (see that
    # file's `_own_booking`) — this module does not trust its own resolve as the final word either.

    async def list_bookings(self, *, tenant: str, from_number: str, branch_id: str = "") -> list[dict]:
        """`branch_id`, WHEN THE CONVERSATION HAS ONE, NARROWS TO THAT BRANCH — a per_branch shop's
        WhatsApp number IS a branch, so a customer texting branch B's number must not see her own
        booking at branch A. Empty (a central shop with no branch fixed on this conversation yet)
        means every branch, unchanged from before this existed. bookings-service's own internal
        route re-applies this as ownership, not a filter it trusts from here (see that route's
        `_own_booking`)."""
        if self._bookings_for_customer is None:
            raise BookingAssignmentError("booking management is not enabled on this deployment")
        customer_id, _rr = await self._resolve_customer_id(tenant, from_number)
        if not customer_id:
            raise BookingAssignmentError("could not resolve a real customer for this phone")
        # OFF THE EVENT LOOP — see core/customer_lookup.py::HttpCustomerLookup.resolve.
        result = await asyncio.to_thread(
            self._bookings_for_customer.call,
            {"tenant": tenant, "customer_id": customer_id, "branch_id": branch_id})
        return list((result or {}).get("bookings") or [])

    async def cancel_booking(self, *, tenant: str, from_number: str, booking_id: str,
                             reason: str = "", branch_id: str = "") -> dict:
        if self._cancel_booking is None:
            raise BookingAssignmentError("booking management is not enabled on this deployment")
        customer_id, _rr = await self._resolve_customer_id(tenant, from_number)
        if not customer_id:
            raise BookingAssignmentError("could not resolve a real customer for this phone")
        # OFF THE EVENT LOOP — see core/customer_lookup.py::HttpCustomerLookup.resolve.
        result = await asyncio.to_thread(
            self._cancel_booking.call,
            {"tenant": tenant, "customer_id": customer_id, "reason": reason, "branch_id": branch_id},
            path_params={"booking_id": booking_id})
        if result is None:
            raise BookingAssignmentError("bookings-service refused or was unreachable")
        return result

    async def reschedule_booking(self, *, tenant: str, from_number: str, booking_id: str,
                                 starts_at: int, branch_id: str = "") -> dict:
        if self._reschedule_booking is None:
            raise BookingAssignmentError("booking management is not enabled on this deployment")
        customer_id, _rr = await self._resolve_customer_id(tenant, from_number)
        if not customer_id:
            raise BookingAssignmentError("could not resolve a real customer for this phone")
        # OFF THE EVENT LOOP — see core/customer_lookup.py::HttpCustomerLookup.resolve.
        result = await asyncio.to_thread(
            self._reschedule_booking.call,
            {"tenant": tenant, "customer_id": customer_id, "starts_at": starts_at,
             "branch_id": branch_id},
            path_params={"booking_id": booking_id})
        if result is None:
            raise BookingAssignmentError("bookings-service refused or was unreachable")
        return result


def build(settings: Any) -> Any:
    """"config" (default) keeps the zero-infra placeholder built in core/booking.py — this
    function is never even called in that case (see container.py). "real" requires BOTH peers
    configured; a half-configured deployment fails loudly at boot (fail-fast, same posture as
    every other required-config assertion in app/config.py) rather than starting and silently
    never creating a real booking.
    """
    if not settings.OPERATIONS_SERVICE_URL or not settings.BOOKINGS_SERVICE_URL:
        raise ValueError(
            "BOOKING_PROVIDER_DRIVER=real requires OPERATIONS_SERVICE_URL and "
            "BOOKINGS_SERVICE_URL both set")
    timeout = settings.PEER_TIMEOUT_SECONDS
    token = settings.INTERNAL_SERVICE_TOKEN
    # BOOKING_MANAGEMENT_ENABLED is THE master kill-switch (app/config.py's own note): false means
    # these three peers are simply never built, so list/cancel/reschedule_booking above always
    # raise "not enabled" — the SAME "flip a value, no redeploy" shutoff LLM_TOOL_ALLOWLIST's own
    # property enforces on the tool side. Two independent layers refusing the same thing on purpose.
    management_peers: dict[str, _Peer] = {}
    if settings.BOOKING_MANAGEMENT_ENABLED:
        management_peers = dict(
            bookings_for_customer=_Peer(url=settings.BOOKINGS_SERVICE_URL,
                                        path=settings.BOOKINGS_FOR_CUSTOMER_PATH,
                                        token=token, timeout=timeout),
            cancel_booking=_Peer(url=settings.BOOKINGS_SERVICE_URL,
                                 path=settings.BOOKINGS_CANCEL_PATH, token=token, timeout=timeout),
            reschedule_booking=_Peer(url=settings.BOOKINGS_SERVICE_URL,
                                     path=settings.BOOKINGS_RESCHEDULE_PATH,
                                     token=token, timeout=timeout))
    return RealBookingProvider(
        branch_operators=_Peer(url=settings.OPERATIONS_SERVICE_URL,
                               path=settings.OPERATIONS_BRANCH_OPERATORS_PATH,
                               token=token, timeout=timeout),
        service_eligibility=_Peer(url=settings.OPERATIONS_SERVICE_URL,
                                  path=settings.OPERATIONS_SERVICE_ELIGIBILITY_PATH,
                                  token=token, timeout=timeout),
        customer_id_by_phone=_Peer(url=settings.OPERATIONS_SERVICE_URL,
                                   path=settings.OPERATIONS_CUSTOMER_ID_BY_PHONE_PATH,
                                   token=token, timeout=timeout),
        nearest_real_slot=_Peer(url=settings.BOOKINGS_SERVICE_URL,
                                path=settings.BOOKINGS_NEAREST_REAL_SLOT_PATH,
                                token=token, timeout=timeout),
        # THE REAL ENGINE (phase 4) — `_pick_slot`/`_pick_operator`'s own peer, the single-service
        # path only. `_pick_operator_for_package` below still uses `nearest_real_slot` above with
        # its own simpler policy — packages are a separate, later pass, deliberately untouched here.
        nearest_any_real_slot=_Peer(url=settings.BOOKINGS_SERVICE_URL,
                                    path=settings.BOOKINGS_NEAREST_ANY_REAL_SLOT_PATH,
                                    token=token, timeout=timeout),
        create_booking=_Peer(url=settings.BOOKINGS_SERVICE_URL,
                             path=settings.BOOKINGS_CREATE_PATH, token=token, timeout=timeout),
        package_eligibility=_Peer(url=settings.OPERATIONS_SERVICE_URL,
                                  path=settings.OPERATIONS_PACKAGE_ELIGIBILITY_PATH,
                                  token=token, timeout=timeout),
        **management_peers)
