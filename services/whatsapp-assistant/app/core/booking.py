"""ConfigDrivenAvailabilityProvider — the zero-infra default BookingProvider.

Business hours, a default service duration, and per-slot concurrency are read from config (JSON —
see BOOKING_DEFAULT_BUSINESS_HOURS_JSON etc. in app/config.py); confirmed bookings are read from
this service's own datastore. Availability is pure arithmetic over those two things: walk the
tenant's open hours forward from `earliest`, in SLOT_GRANULARITY steps, and offer any slot whose
[start, start+duration) window holds fewer confirmed bookings than the configured concurrency.

THIS IS A PLACEHOLDER, DOCUMENTED AS ONE. The day a real bookings/scheduling service exists on this
platform, it implements the same BookingProvider port and this class is deleted — nothing in
core/conversation.py or core/tools.py needs to change, because they depend on the port, not this
class. See deploy/services/whatsapp-assistant.values.yaml for the same note in operator-facing form.

CONCURRENCY AND IDEMPOTENCY. `hold_and_confirm` re-checks capacity at write time (never trusts the
caller's earlier `availability()` read — a slot can fill between "the model asked" and "the customer
tapped confirm") and is keyed by `idempotency_key` so a retried confirm cannot double-book.
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from app.adapters.datastore.drain import drain
from app.core.models import BOOKINGS, Booking, as_row
from app.ports.booking_provider import Slot

_DAY_KEYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

# HOLD LOCK, ONE PER SLOT — fixed 2026-09-12, a real gap a QA audit found: `hold_and_confirm` was a
# non-atomic read-check-write (drain busy rows, count overlap, then `put`), so two customers
# confirming the same slot within the same instant could both pass the capacity check and both get
# confirmed, exceeding the shop's configured concurrency. Mirrors `conversation.py`'s
# `_CONV_LOCKS`/`_acquire_conv_lock` idiom: a short-TTL `store.claim()` keyed on the slot's own
# identity (tenant + service + start time — the exact thing capacity is counted over), held only
# for the duration of the re-check-and-write, so confirms for the SAME slot serialize while confirms
# for different slots never contend.
_HOLD_LOCKS = "wa_booking_hold_locks"
_HOLD_LOCK_TTL_SECONDS = 15.0
_HOLD_LOCK_RETRY_ATTEMPTS = 40
_HOLD_LOCK_RETRY_DELAY_SECONDS = 0.05


@dataclass(frozen=True)
class BookingConfig:
    business_hours: dict[str, list[str]]     # {"mon": ["09:00-17:00"], ...}
    default_duration_minutes: int
    concurrency: int
    max_lead_days: int
    slot_granularity_minutes: int
    # Overridden per-service where the tenant's own catalogue declares a duration (design point 6:
    # "swappable for a real bookings service via this same port later" — reading the catalogue
    # keeps this default honest about the shop's own services rather than a flat guess for all).
    service_durations: dict[str, int]

    @classmethod
    def from_settings(cls, settings: Any, *, service_durations: dict[str, int] | None = None
                      ) -> "BookingConfig":
        raw = json.loads(settings.BOOKING_DEFAULT_BUSINESS_HOURS_JSON or "{}")
        return cls(
            business_hours={k: list(v) for k, v in raw.items()},
            default_duration_minutes=settings.BOOKING_DEFAULT_SERVICE_DURATION_MINUTES,
            concurrency=max(1, settings.BOOKING_DEFAULT_CONCURRENCY),
            max_lead_days=max(1, settings.BOOKING_MAX_LEAD_DAYS),
            slot_granularity_minutes=max(5, settings.BOOKING_SLOT_GRANULARITY_MINUTES),
            service_durations=dict(service_durations or {}))

    def duration_for(self, service_id: str) -> int:
        return self.service_durations.get(service_id, self.default_duration_minutes)


def _windows_for_day(cfg: BookingConfig, day: datetime) -> list[tuple[datetime, datetime]]:
    key = _DAY_KEYS[day.weekday()]
    out = []
    for span in cfg.business_hours.get(key, []):
        try:
            start_s, end_s = span.split("-")
            sh, sm = (int(x) for x in start_s.split(":"))
            eh, em = (int(x) for x in end_s.split(":"))
        except (ValueError, IndexError):
            continue
        start = day.replace(hour=sh, minute=sm, second=0, microsecond=0)
        end = day.replace(hour=eh, minute=em, second=0, microsecond=0)
        if end > start:
            out.append((start, end))
    return out


class ConfigDrivenAvailabilityProvider:
    driver = "config"

    def __init__(self, *, store: Any, cfg: BookingConfig, tz_offset_hours: int = 3) -> None:
        self._store = store
        self._cfg = cfg
        self._tz = timezone(timedelta(hours=tz_offset_hours))

    async def availability(self, *, tenant: str, service_id: str, earliest: int,
                           horizon_days: int = 0, branch_id: str = "",
                           exclude_booking_id: str = "") -> list[Slot]:
        # `branch_id`/`exclude_booking_id` ARE ACCEPTED AND IGNORED — this placeholder never had a
        # branch concept (a `subject_ref` pseudonym was always enough for its own local store), and
        # has no existing-booking-id concept to exclude either; see app/ports/booking_provider.py's
        # own note on why the port keeps both optional.
        horizon = min(horizon_days or self._cfg.max_lead_days, self._cfg.max_lead_days)
        duration = self._cfg.duration_for(service_id)
        step = self._cfg.slot_granularity_minutes
        start_dt = datetime.fromtimestamp(max(earliest, int(time.time())), self._tz)

        # Confirmed bookings in the whole horizon, read once — O(rows/page) datastore calls
        # regardless of how many slots are walked, rather than one `find` per candidate slot.
        # DRAINED, not a single `find(..., limit=1000)`: a shop with more than 1,000 confirmed
        # bookings for one service would have silently had its oldest/newest rows fall out of the
        # busy set, and every slot computed from the truncated set would be confidently wrong —
        # ci/check_a_read_that_meant_everything_admits_it_stopped.py is what caught this.
        rows = await drain(
            self._store, BOOKINGS, {"tenant": tenant, "service_id": service_id, "state": "confirmed"},
            sort=("starts_at", "asc"))
        busy = [(int(r["starts_at"]), int(r["starts_at"]) + int(r["duration_minutes"]) * 60)
               for r in rows]

        out: list[Slot] = []
        for day_offset in range(horizon + 1):
            day = (start_dt + timedelta(days=day_offset)).replace(
                hour=0, minute=0, second=0, microsecond=0)
            for win_start, win_end in _windows_for_day(self._cfg, day):
                cursor = max(win_start, start_dt) if day_offset == 0 else win_start
                while cursor + timedelta(minutes=duration) <= win_end:
                    s = int(cursor.timestamp())
                    e = s + duration * 60
                    overlapping = sum(1 for bs, be in busy if bs < e and be > s)
                    if overlapping < self._cfg.concurrency:
                        out.append(Slot(starts_at=s, duration_minutes=duration))
                    cursor += timedelta(minutes=step)
        return out

    async def hold_and_confirm(self, *, tenant: str, subject_ref: str, service_id: str,
                               starts_at: int, idempotency_key: str, branch_id: str = "",
                               from_number: str = "", intended_reward_id: str = "") -> dict:
        # `branch_id`/`from_number`/`intended_reward_id` IGNORED, same reason as `availability`
        # above — this placeholder has no attend()/reward concept at all to stamp intent onto.
        # IDEMPOTENT ON THE KEY, not on the slot — a retried confirm (a timeout, a doubled button
        # tap) must return the SAME booking, never create a second one.
        existing, _ = await self._store.find(
            BOOKINGS, {"tenant": tenant, "idempotency_key": idempotency_key}, limit=1)
        if existing:
            return existing[0]

        lock_key = f"{tenant}|{service_id}|{starts_at}"
        held = await self._acquire_hold_lock(lock_key)
        if not held:
            # Another confirm for this SAME slot is mid-flight and did not release in time — treat
            # it the same as "filled between proposal and confirmation" rather than racing it
            # unlocked, which is the exact bug this lock exists to close.
            raise SlotNoLongerAvailable(
                f"slot at {starts_at} for {service_id!r} is being confirmed by another request")
        try:
            # Re-check idempotency INSIDE the lock too — a concurrent retried confirm for the same
            # key could have been the one that just won the race above.
            existing, _ = await self._store.find(
                BOOKINGS, {"tenant": tenant, "idempotency_key": idempotency_key}, limit=1)
            if existing:
                return existing[0]

            duration = self._cfg.duration_for(service_id)
            end = starts_at + duration * 60
            # DRAINED — same reasoning as availability() above: this is the write-time re-check that
            # decides whether a booking is created at all, so a truncated read here does not just
            # offer a wrong slot, it double-books one.
            rows = await drain(
                self._store, BOOKINGS,
                {"tenant": tenant, "service_id": service_id, "state": "confirmed"},
                sort=("starts_at", "asc"))
            overlapping = sum(1 for r in rows
                              if int(r["starts_at"]) < end
                              and int(r["starts_at"]) + int(r["duration_minutes"]) * 60 > starts_at)
            if overlapping >= self._cfg.concurrency:
                raise SlotNoLongerAvailable(
                    f"slot at {starts_at} for {service_id!r} filled between proposal and confirmation")

            booking = Booking(
                id=f"bkg_{uuid.uuid4().hex[:24]}", tenant=tenant, subject_ref=subject_ref,
                service_id=service_id, starts_at=starts_at, duration_minutes=duration,
                idempotency_key=idempotency_key)
            row = as_row(booking)
            await self._store.put(BOOKINGS, booking.id, row)
            return row
        finally:
            await self._store.delete(_HOLD_LOCKS, lock_key)

    async def _acquire_hold_lock(self, lock_key: str) -> bool:
        """Wait for the per-slot mutex — bounded, same reasoning as `conversation.py`'s
        `_acquire_conv_lock`: the TTL alone reclaims a crashed holder's lock, this bound is only a
        cheap extra safety net so a caller never hangs forever."""
        now = time.time()
        for _ in range(_HOLD_LOCK_RETRY_ATTEMPTS):
            took = await self._store.claim(
                _HOLD_LOCKS, lock_key, {"held": True},
                ttl_seconds=_HOLD_LOCK_TTL_SECONDS, now=now)
            if took:
                return True
            await asyncio.sleep(_HOLD_LOCK_RETRY_DELAY_SECONDS)
        return False


class SlotNoLongerAvailable(Exception):
    """The deterministic re-check (design point 5: "re-validated server-side against real state
    before any button is offered") found the slot gone. The caller must not confirm."""


def build(settings: Any, *, store: Any, service_durations: dict[str, int] | None = None
         ) -> ConfigDrivenAvailabilityProvider:
    cfg = BookingConfig.from_settings(settings, service_durations=service_durations)
    return ConfigDrivenAvailabilityProvider(store=store, cfg=cfg)
