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
        self._url = url.rstrip("/") + path
        self._token = token
        self._timeout = timeout

    def call(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        body = json.dumps(payload).encode()
        req = urllib.request.Request(
            self._url, data=body, method="POST",
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
                customer_id_by_phone: _Peer, nearest_real_slot: _Peer, create_booking: _Peer
                ) -> None:
        self._branch_operators = branch_operators
        self._service_eligibility = service_eligibility
        self._customer_id_by_phone = customer_id_by_phone
        self._nearest_real_slot = nearest_real_slot
        self._create_booking = create_booking

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
                           horizon_days: int, branch_id: str = "") -> list[Slot]:
        # NO BRANCH, NO ANSWER — see module docstring. `horizon_days` is accepted for Protocol
        # compatibility but unused: `nearest_real_slot` always returns the single NEXT open
        # candidate, not a set across a window (the "أقرب موعد" shape, not the grid's).
        if not branch_id:
            return []
        try:
            operator_id = await self._pick_operator(tenant, branch_id, service_id)
        except BookingAssignmentError:
            return []
        result = self._nearest_real_slot.call(
            {"tenant": tenant, "branch_id": branch_id, "operator_id": operator_id,
             "service_ids": [service_id], "after": earliest})
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
                "idempotency_key": idempotency_key}
        if intended_reward_id:
            body["intended_reward_id"] = intended_reward_id
        result = self._create_booking.call(body)
        if result is None or not result.get("id"):
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
                             path=settings.BOOKINGS_CREATE_PATH, token=token, timeout=timeout))
