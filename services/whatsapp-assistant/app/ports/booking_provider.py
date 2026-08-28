"""BookingProvider port — availability and slot-holding, behind a port a real bookings service
can implement later without touching the conversation engine.

No bookings/availability/slots domain service exists anywhere on this platform today. Rather than
invent a dependency on one, `ConfigDrivenAvailabilityProvider` (app/core/booking.py) is the
zero-infra default: business hours, service durations and concurrency read from THIS service's own
config/DB, computing availability arithmetically against already-confirmed bookings it holds
itself. Mirrors the "null driver that still works" philosophy used elsewhere on this platform (e.g.
assistant-service's null model) — self-contained, swappable, never a hard external dependency.
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
                           horizon_days: int) -> list[Slot]: ...

    async def hold_and_confirm(self, *, tenant: str, subject_ref: str, service_id: str,
                               starts_at: int, idempotency_key: str) -> dict: ...
