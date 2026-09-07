"""RealBookingProvider — the BookingProvider port backed by REAL peers (Phase 4), replacing
`ConfigDrivenAvailabilityProvider`'s zero-infra placeholder once bookings-service is actually
deployed. Opt-in only: `BOOKING_PROVIDER_DRIVER=real` (see app/config.py's own note).

THE ONE POLICY QUESTION THIS MODULE ANSWERS: which operator does an AI-led WhatsApp booking get
assigned to. There is no chat UI for a customer to browse staff photos and pick one — Tamam's own
framing of this feature ("تحديد الموظفه مهم") asked that a real operator be assigned, not that a
customer be made to choose. So the policy here is FIRST ELIGIBLE, DETERMINISTIC: among this
branch's own active operators (Operator.branch_id — his home station, not a read-scope grant),
the first one (sorted by id, so the same booking retried twice picks the same operator) who is
BOTH allowed to perform this service (operations' service-eligibility) reduces to a single
question bookings-service's own `create()`/`nearest_slot()` still re-asks and re-refuses on
independently — this module never trusts its own pick as final. A customer naming a PREFERRED
stylist is a real, later feature (a free-text name would need to be resolved against this same
list, matched, and confirmed) — not built here; this is recorded as a documented limitation, not
solved by guessing from an unstructured message.

NOTHING HERE INVENTS A BRANCH. `availability()`/`hold_and_confirm()` both REQUIRE a real
`branch_id` and return "not available"/refuse outright without one — exactly the same "ask,
never guess" discipline Phase 3's branch-selection gate exists to satisfy before a booking
conversation ever reaches this module.
"""
from __future__ import annotations

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
                customer_id_by_phone: _Peer, nearest_real_slot: _Peer, create_booking: _Peer,
                bookings_for_customer: _Peer | None = None, cancel_booking: _Peer | None = None,
                reschedule_booking: _Peer | None = None,
                package_eligibility: _Peer | None = None) -> None:
        self._branch_operators = branch_operators
        self._service_eligibility = service_eligibility
        self._customer_id_by_phone = customer_id_by_phone
        self._nearest_real_slot = nearest_real_slot
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

    async def _pick_operator(self, tenant: str, branch_id: str, service_id: str) -> str:
        """FIRST ELIGIBLE, DETERMINISTIC — see this module's own docstring for the policy. Raises
        BookingAssignmentError rather than returning "" so every caller is forced to handle "no
        eligible operator" explicitly instead of silently proceeding with an empty id."""
        ops = self._branch_operators.call({"tenant": tenant, "branch_id": branch_id})
        candidates = [str(o.get("id")) for o in (ops or {}).get("operators") or []]
        if not candidates:
            raise BookingAssignmentError(f"no active operators at branch {branch_id!r}")

        elig = self._service_eligibility.call({"tenant": tenant, "service_ids": [service_id]})
        allowed = (elig or {}).get("eligible_staff_ids", {}).get(service_id)
        # `None` (unrestricted) MEANS EVERY ACTIVE OPERATOR — same contract
        # services/operations/app/api/internal.py::internal_service_eligibility documents; an
        # empty LIST (as opposed to a missing key) is the real, if unusual, "restricted to
        # nobody" state and must narrow the pool to nothing, not fall back to "everyone".
        eligible_pool = candidates if allowed is None else [c for c in candidates if c in allowed]
        if not eligible_pool:
            raise BookingAssignmentError(
                f"no operator at branch {branch_id!r} is eligible for service {service_id!r}")
        return sorted(eligible_pool)[0]

    async def _resolve_customer_id(self, tenant: str, from_number: str) -> str:
        result = self._customer_id_by_phone.call({"tenant": tenant, "phone": from_number})
        return str((result or {}).get("customer_id") or "")

    async def availability(self, *, tenant: str, service_id: str, earliest: int,
                           horizon_days: int, branch_id: str = "",
                           exclude_booking_id: str = "") -> list[Slot]:
        # NO BRANCH, NO ANSWER — see module docstring. `horizon_days` is accepted for Protocol
        # compatibility but unused: `nearest_real_slot` always returns the single NEXT open
        # candidate, not a set across a window (the "أقرب موعد" shape, not the grid's).
        #
        # `exclude_booking_id` (booking-management-via-WhatsApp's reschedule check) — the booking
        # being moved is not a conflict with itself; without this, asking "is my own current time,
        # or any nearby overlapping time, available?" always reads as busy against the booking's
        # OWN occupancy and the search jumps past to the next genuinely free slot instead. See
        # app/ports/booking_provider.py's own note.
        if not branch_id:
            return []
        try:
            operator_id = await self._pick_operator(tenant, branch_id, service_id)
        except BookingAssignmentError:
            return []
        payload: dict[str, Any] = {
            "tenant": tenant, "branch_id": branch_id, "operator_id": operator_id,
            "service_ids": [service_id], "after": earliest}
        if exclude_booking_id:
            payload["exclude_booking_id"] = exclude_booking_id
        result = self._nearest_real_slot.call(payload)
        starts_at = (result or {}).get("starts_at")
        if not starts_at:
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
                               from_number: str = "", intended_reward_id: str = "") -> dict:
        if not branch_id:
            raise BookingAssignmentError("no branch on this conversation — cannot create a real booking")
        if not from_number:
            raise BookingAssignmentError("no phone on this conversation — cannot resolve a customer")

        customer_id = await self._resolve_customer_id(tenant, from_number)
        if not customer_id:
            raise BookingAssignmentError("could not resolve a real customer for this phone")

        operator_id = await self._pick_operator(tenant, branch_id, service_id)

        # INTENT ONLY, NEVER A SPEND — bookings-service's own `create()` only stamps this on the
        # row (see InternalCreateBookingIn.intended_reward_id's own docstring); the actual points
        # spend happens exclusively at attend(), and cancel()/no_show() never touch it. This is
        # the whole reason a WhatsApp-initiated reward costs the shop nothing on a no-show — see
        # core/tools.py's `propose_booking` branch for how `reward_id` gets here.
        body = {"tenant": tenant, "branch_id": branch_id, "operator_id": operator_id,
                "customer_id": customer_id, "service_ids": [service_id], "starts_at": starts_at,
                "idempotency_key": idempotency_key, "created_by": ACTOR}
        if intended_reward_id:
            body["intended_reward_id"] = intended_reward_id
        result = self._create_booking.call(body)
        if result is None or not result.get("id"):
            raise BookingAssignmentError("bookings-service refused or was unreachable")
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
        ops = self._branch_operators.call({"tenant": tenant, "branch_id": branch_id})
        candidates = [str(o.get("id")) for o in (ops or {}).get("operators") or []]
        if not candidates:
            raise BookingAssignmentError(f"no active operators at branch {branch_id!r}")
        if self._package_eligibility is None:
            return sorted(candidates)[0]
        elig = self._package_eligibility.call({"tenant": tenant, "package_id": package_id})
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
        result = self._nearest_real_slot.call(payload)
        starts_at = (result or {}).get("starts_at")
        if not starts_at:
            return []
        # DURATION 0 — same reasoning as `availability()` above: bookings-service computes the
        # real duration itself, from the package's own LIVE components, at create() time.
        return [Slot(starts_at=int(starts_at), duration_minutes=0)]

    async def hold_and_confirm_package(self, *, tenant: str, subject_ref: str, package_id: str,
                                       starts_at: int, idempotency_key: str, branch_id: str = "",
                                       from_number: str = "", intended_reward_id: str = "") -> dict:
        if not branch_id:
            raise BookingAssignmentError("no branch on this conversation — cannot create a real booking")
        if not from_number:
            raise BookingAssignmentError("no phone on this conversation — cannot resolve a customer")

        customer_id = await self._resolve_customer_id(tenant, from_number)
        if not customer_id:
            raise BookingAssignmentError("could not resolve a real customer for this phone")

        operator_id = await self._pick_operator_for_package(tenant, branch_id, package_id)

        body = {"tenant": tenant, "branch_id": branch_id, "operator_id": operator_id,
                "customer_id": customer_id, "package_id": package_id, "starts_at": starts_at,
                "idempotency_key": idempotency_key, "created_by": ACTOR}
        if intended_reward_id:
            body["intended_reward_id"] = intended_reward_id
        result = self._create_booking.call(body)
        if result is None or not result.get("id"):
            raise BookingAssignmentError("bookings-service refused or was unreachable")
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
        customer_id = await self._resolve_customer_id(tenant, from_number)
        if not customer_id:
            raise BookingAssignmentError("could not resolve a real customer for this phone")
        result = self._bookings_for_customer.call(
            {"tenant": tenant, "customer_id": customer_id, "branch_id": branch_id})
        return list((result or {}).get("bookings") or [])

    async def cancel_booking(self, *, tenant: str, from_number: str, booking_id: str,
                             reason: str = "", branch_id: str = "") -> dict:
        if self._cancel_booking is None:
            raise BookingAssignmentError("booking management is not enabled on this deployment")
        customer_id = await self._resolve_customer_id(tenant, from_number)
        if not customer_id:
            raise BookingAssignmentError("could not resolve a real customer for this phone")
        result = self._cancel_booking.call(
            {"tenant": tenant, "customer_id": customer_id, "reason": reason, "branch_id": branch_id},
            path_params={"booking_id": booking_id})
        if result is None:
            raise BookingAssignmentError("bookings-service refused or was unreachable")
        return result

    async def reschedule_booking(self, *, tenant: str, from_number: str, booking_id: str,
                                 starts_at: int, branch_id: str = "") -> dict:
        if self._reschedule_booking is None:
            raise BookingAssignmentError("booking management is not enabled on this deployment")
        customer_id = await self._resolve_customer_id(tenant, from_number)
        if not customer_id:
            raise BookingAssignmentError("could not resolve a real customer for this phone")
        result = self._reschedule_booking.call(
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
        create_booking=_Peer(url=settings.BOOKINGS_SERVICE_URL,
                             path=settings.BOOKINGS_CREATE_PATH, token=token, timeout=timeout),
        package_eligibility=_Peer(url=settings.OPERATIONS_SERVICE_URL,
                                  path=settings.OPERATIONS_PACKAGE_ELIGIBILITY_PATH,
                                  token=token, timeout=timeout),
        **management_peers)
