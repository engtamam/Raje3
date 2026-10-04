"""BookingProvider port — availability and slot-holding, behind a port a real bookings service
can implement later without touching the conversation engine.

TWO IMPLEMENTATIONS NOW EXIST. `ConfigDrivenAvailabilityProvider` (app/core/booking.py) is the
original zero-infra default: business hours, service durations and concurrency read from THIS
service's own config/DB, computing availability arithmetically against already-confirmed bookings
it holds itself — the right choice for a deployment with no bookings-service reachable at all.
`RealBookingProvider` (app/core/booking_assignment.py, Phase 4) is the real one, once
bookings-service and its own operator-assignment peers ARE reachable — see
`BOOKING_PROVIDER_DRIVER` in app/config.py for how a deployment opts into it. Neither is assumed;
core/conversation.py and core/tools.py depend on this port alone, never on which one is wired.

`branch_id`/`from_number` ARE OPTIONAL, NOT REQUIRED BY THE PROTOCOL — `ConfigDrivenAvailabilityProvider`
ignores both (it never needed a branch or a phone; a `subject_ref` pseudonym was always enough for
its own local store). `RealBookingProvider` requires them in practice and refuses without them —
see its own docstring — but the PORT stays permissive so a placeholder implementation with no use
for either need not accept or thread through arguments it would only ever discard.

`referral_code` (owner instruction, 2026-09-27) — a new customer's own referral code, offered
during the conversation and passed through to whoever resolves `from_number` into a real
`customer_id`; this is the ONLY moment a WhatsApp customer ever has to give one (by the time a
booking is attended, the customer already exists — same reasoning the console's own booking
dialog and the mobile app's new-booking sheet already follow). `ConfigDrivenAvailabilityProvider`
accepts and ignores it (no customer-resolution concept of its own); `RealBookingProvider` threads
it to `/internal/operations/customer-id-by-phone`, which already accepts it.

`exclude_booking_id` (booking-management-via-WhatsApp) — the booking being RESCHEDULED is not a
conflict with itself; without excluding it, a candidate slot inside its own current window reads
as busy against its own occupancy. `ConfigDrivenAvailabilityProvider` accepts and ignores it (no
concept of an existing booking id to exclude in its own arithmetic); `RealBookingProvider` threads
it to bookings-service's own `nearest_slot(exclude_booking_id=...)`, the SAME parameter the
console's own reschedule screen already relies on (app/api/v1/bookings.py's `nearest_slot` route).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class Slot:
    starts_at: int
    duration_minutes: int


@runtime_checkable
class BookingProvider(Protocol):
    driver: str

    async def availability(self, *, tenant: str, service_id: str, earliest: int,
                           horizon_days: int, branch_id: str = "",
                           exclude_booking_id: str = "") -> list[Slot]: ...

    async def hold_and_confirm(self, *, tenant: str, subject_ref: str, service_id: str,
                               starts_at: int, idempotency_key: str, branch_id: str = "",
                               from_number: str = "", intended_reward_id: str = "",
                               referral_code: str = "") -> dict: ...
