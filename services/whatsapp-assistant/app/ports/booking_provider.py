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
                           horizon_days: int, branch_id: str = "") -> list[Slot]: ...

    async def hold_and_confirm(self, *, tenant: str, subject_ref: str, service_id: str,
                               starts_at: int, idempotency_key: str, branch_id: str = "",
                               from_number: str = "", intended_reward_id: str = "") -> dict: ...
