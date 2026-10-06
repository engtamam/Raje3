"""`ResourceBooking` — the one real record this whole app produces (spec §2/§3).

Everything else (resources, join requests, the pause flag) exists only to decide whether THIS can
be created. The freelancer's own end-customer never appears anywhere in this module, or anywhere
in this service — spec §2 is explicit that this app must not know who they served.

THE REFUSAL ORDER MATTERS, and every reason returned here is honest rather than generic (a shop
operator or a freelancer reading "PENDING_APPROVAL" must never be told the same thing as
"BLOCKED" — they are different situations needing different next actions):

    1. tenant paused (spec §5)              -> refused, existing bookings untouched
    2. resource missing / disabled           -> refused
    3. phone has no join record yet          -> NOT a refusal: a join request is created instead
    4. phone is blocked                      -> refused
    5. phone is still pending                -> refused, distinct reason from blocked
    6. the requested window is not free      -> refused (outside hours, exception day, overlap)

STEP 6 IS CHECKED TWICE — once cheaply before the lock (so an obviously-bad request never
contends for a lane at all), and once more INSIDE the lock (the only check that is actually
authoritative — see `core/lock.py`'s own module doc for why a read-then-write outside a lock can
never be trusted alone).
"""
from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

from app.core import availability as av
from app.core.joins import JOIN_APPROVED, JOIN_BLOCKED, JOIN_PENDING, JoinRegistry
from app.core.lock import SlotClaimBusy, claiming
from app.core.models import BOOKING_CANCELLED, BOOKING_CONFIRMED, BOOKINGS, RESOURCES
from app.core.pause import PauseSettings
from app.core.resources import ResourceService


class BookingRefused(Exception):
    """Carries a stable machine-readable `reason` alongside the human message — the public and
    admin routes both need the reason to decide what the caller should be told to do next."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


class JoinRequired(Exception):
    """Not a refusal — the FIRST attempt from an unknown phone becomes a join request instead of
    a booking (spec §6). Raised, never returned as a booking, so a caller cannot mistake "your
    request is now pending" for "you have a confirmed booking"."""


def _capacity_available(schedule: av.Schedule, busy: list[av.Busy], *, quantity: int,
                        starts_at: int, ends_at: int) -> bool:
    """The capacity-aware twin of `availability.is_free` — "is ANY one of `quantity` identical
    units free", not "is THE unit free". Same working-hours check `is_free` already does (a
    window the schedule never opens is refused regardless of capacity); the exclusivity half is
    replaced with a count: up to `quantity - 1` OTHER overlapping confirmed bookings may already
    exist and this one still fits. `quantity == 1` makes this IDENTICAL to the old `is_free` —
    the behaviour every resource created before this feature existed keeps exactly.
    """
    if ends_at <= starts_at:
        raise av.DurationNotConfigured(
            "ends_at is at or before starts_at — this service's booking length was never "
            "configured, not merely fully booked")
    import datetime as _dt

    from app.core.riyadh import RIYADH
    day = _dt.datetime.fromtimestamp(starts_at, tz=RIYADH).date()
    windows = schedule.windows_on(day)
    day_epoch = int(_dt.datetime.combine(day, _dt.time(0, 0), tzinfo=RIYADH).timestamp())
    within_a_window = any(
        day_epoch + w.start_minute * 60 <= starts_at and ends_at <= day_epoch + w.end_minute * 60
        for w in windows)
    if not within_a_window:
        return False
    overlapping = sum(1 for b in busy if b.starts_at < ends_at and starts_at < b.ends_at)
    return overlapping < quantity


def _schedule_from_resource(resource) -> av.Schedule:
    weekly = {int(day): tuple(av.Window(int(w[0]), int(w[1])) for w in windows)
             for day, windows in (resource.weekly or {}).items()}
    exceptions = {}
    for date, exc in (resource.exceptions or {}).items():
        windows = tuple(av.Window(int(w[0]), int(w[1])) for w in exc.get("windows") or [])
        exceptions[date] = av.DayException(closed=bool(exc.get("closed", True)), windows=windows)
    return av.Schedule(weekly=weekly, exceptions=exceptions)


class BookingService:
    def __init__(self, store: Any, *, resources: ResourceService, joins: JoinRegistry,
                pause: PauseSettings) -> None:
        self._store = store
        self._resources = resources
        self._joins = joins
        self._pause = pause

    async def _busy(self, tenant: str, resource_id: str, *, window_start: int,
                    window_end: int) -> list[av.Busy]:
        rows, _ = await self._store.find(
            BOOKINGS, {"tenant": tenant, "resource_id": resource_id, "status": BOOKING_CONFIRMED},
            limit=5000, sort=("starts_at", "asc"))
        return [av.Busy(starts_at=int(r["starts_at"]), ends_at=int(r["ends_at"]))
               for r in rows if int(r["ends_at"]) > window_start and int(r["starts_at"]) < window_end]

    async def free_slots(self, tenant: str, resource_id: str, *, window_start: int,
                         window_end: int, duration_minutes: int) -> list[av.Slot]:
        resource = await self._resources.get(tenant, resource_id)
        if resource is None or not resource.active:
            return []
        schedule = _schedule_from_resource(resource)
        busy = await self._busy(tenant, resource_id, window_start=window_start, window_end=window_end)
        return av.free_slots(schedule, busy, duration_minutes=duration_minutes,
                             window_start=window_start, window_end=window_end)

    async def create(self, tenant: str, *, resource_id: str, phone: str, starts_at: int,
                     ends_at: int) -> dict:
        if ends_at <= starts_at:
            raise BookingRefused("BAD_WINDOW", "وقت النهاية يجب أن يكون بعد وقت البداية")
        if not phone:
            raise BookingRefused("BAD_PHONE", "رقم الجوال غير صالح")

        # ── 1. tenant pause (spec §5) ─────────────────────────────────────────────────────────
        if await self._pause.is_paused(tenant):
            raise BookingRefused("SHOP_PAUSED", "هذا المحل أوقف استقبال حجوزات جديدة مؤقتاً")

        # ── 2. resource must exist, belong to this tenant, and be active ────────────────────────
        resource = await self._resources.get(tenant, resource_id)
        if resource is None:
            raise BookingRefused("RESOURCE_NOT_FOUND", "المورد غير موجود")
        if not resource.active:
            raise BookingRefused("RESOURCE_INACTIVE", "هذا المورد متوقف حالياً عن استقبال حجوزات جديدة")

        # ── 3-5. the join gate (spec §6) ─────────────────────────────────────────────────────────
        status = await self._joins.status(tenant, phone)
        if status is None:
            await self._joins.ensure_pending(tenant, phone)
            raise JoinRequired("طلب انضمامك أُرسل لصاحب المحل بانتظار الموافقة")
        if status == JOIN_BLOCKED:
            raise BookingRefused("BLOCKED", "هذا الرقم محظور من الحجز في هذا المحل")
        if status == JOIN_PENDING:
            raise BookingRefused("PENDING_APPROVAL", "طلب انضمامك لا يزال بانتظار موافقة صاحب المحل")
        assert status == JOIN_APPROVED

        # ── 6a. cheap, advisory check BEFORE contending for a lane ──────────────────────────────
        schedule = _schedule_from_resource(resource)
        busy = await self._busy(tenant, resource_id, window_start=starts_at, window_end=ends_at)
        if not _capacity_available(schedule, busy, quantity=resource.quantity,
                                   starts_at=starts_at, ends_at=ends_at):
            raise BookingRefused("SLOT_UNAVAILABLE",
                                 "هذا الوقت غير متاح — إما خارج ساعات عمل هذا المورد أو محجوز بالكامل")

        # ── 6b. the ONLY authoritative check — inside the lock ──────────────────────────────────
        # RETRIED ON CONTENTION, NOT JUST ON QUANTITY==1. `claiming()` is a single, non-blocking
        # attempt (lock.py's own doc) — fine when a resource holds exactly one booking, because
        # losing that race DOES mean the resource is taken. It is WRONG the instant `quantity > 1`:
        # five people booking a five-seat resource at once must take turns through the one lane
        # the lock serialises, not have four of them refused on lock contention alone while the
        # resource still has open capacity. Found live by this exact test (`quantity=5`,
        # `CONTENDERS=7` under `_SlowStore`): without the retry, only the single first caller to
        # win the lock ever got in — every other contender saw `SlotClaimBusy` and was refused
        # outright, even though four more seats were still free the moment the lock let go.
        # BOUNDED, SHORT, NEVER ASLEEP LONG ENOUGH TO MATTER — `CLAIM_TTL_SECONDS` (15s) upper-bounds
        # how long any one holder can block another anyway; this only covers the sliver between two
        # back-to-back legitimate claims on the same resource.
        deadline = time.time() + 2.0
        last_busy_exc: SlotClaimBusy | None = None
        while time.time() < deadline:
            now = time.time()
            try:
                async with claiming(self._store, tenant=tenant, resource_id=resource_id,
                                    starts_at=starts_at, ends_at=ends_at, now=now):
                    # Re-read the resource — it may have been disabled or reschedule the instant
                    # before we took the lock; re-read busy — a competing booking may have
                    # committed between the advisory check above and now.
                    resource = await self._resources.get(tenant, resource_id)
                    if resource is None or not resource.active:
                        raise BookingRefused("RESOURCE_INACTIVE",
                                             "هذا المورد متوقف حالياً عن استقبال حجوزات جديدة")
                    schedule = _schedule_from_resource(resource)
                    busy = await self._busy(tenant, resource_id, window_start=starts_at,
                                            window_end=ends_at)
                    if not _capacity_available(schedule, busy, quantity=resource.quantity,
                                               starts_at=starts_at, ends_at=ends_at):
                        raise BookingRefused("SLOT_UNAVAILABLE",
                                             "هذا الوقت أصبح غير متاح — اختر وقتاً آخر")
                    booking = {
                        "id": str(uuid.uuid4()), "tenant": tenant, "resource_id": resource_id,
                        "freelancer_phone": phone, "starts_at": int(starts_at),
                        "ends_at": int(ends_at),
                        # STAMPED NOW, NOT READ LIVE LATER — spec §3's own "historical fact that
                        # must never silently change if the shop edits the price later".
                        "hourly_price_minor": resource.hourly_price_minor,
                        # SAME REASONING, ONE DOOR DOWN (owner decision, 2026-09-27) — the
                        # resource's OWN branch at booking time, copied rather than joined on
                        # every read, so a branch-scoped list never needs a second lookup per row;
                        # and a booking made before a resource was ever reassigned to a different
                        # branch still shows the branch it was actually booked at, not wherever
                        # the resource sits today.
                        "branch_id": resource.branch_id,
                        "status": BOOKING_CONFIRMED, "created_at": int(now),
                    }
                    await self._store.put(BOOKINGS, booking["id"], booking)
                    return booking
            except SlotClaimBusy as exc:
                last_busy_exc = exc
                await asyncio.sleep(0)   # yield once; let the current holder finish and release
                continue
        raise BookingRefused("SLOT_UNAVAILABLE", str(last_busy_exc) if last_busy_exc else
                             "تعذّر الحجز — هذا الموعد أصبح محجوزاً، اختر وقتاً آخر")

    async def cancel(self, tenant: str, booking_id: str) -> dict:
        row = await self._store.get(BOOKINGS, booking_id)
        if row is None or row.get("tenant") != tenant:
            raise BookingRefused("NOT_FOUND", "الحجز غير موجود")
        row = {**row, "status": BOOKING_CANCELLED}
        await self._store.put(BOOKINGS, booking_id, row)
        return row

    async def list_for_tenant(self, tenant: str, *, resource_id: str | None = None,
                              status: str | None = None) -> list[dict]:
        where: dict[str, Any] = {"tenant": tenant}
        if resource_id:
            where["resource_id"] = resource_id
        if status:
            where["status"] = status
        rows, _ = await self._store.find(BOOKINGS, where, limit=5000, sort=("starts_at", "asc"))
        return rows

    async def list_for_phone(self, tenant: str, phone: str) -> list[dict]:
        """The freelancer's OWN bookings at THIS tenant only (spec §6's own "scoped only to their
        own phone, only for this one tenant") — `where` carries both, so a row from another
        tenant, or another phone at this same tenant, can never surface here even by accident."""
        rows, _ = await self._store.find(
            BOOKINGS, {"tenant": tenant, "freelancer_phone": phone}, limit=1000,
            sort=("starts_at", "asc"))
        return rows
