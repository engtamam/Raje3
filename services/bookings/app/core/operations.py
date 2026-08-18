"""Booking creation, editing and cancellation — the acts that grow or change a commitment.

Stage 3 (docs/خطة-تنفيذ-الحجوزات.md §3): create/edit/cancel, the double-booking lock, the slot
index. Attendance and the booking->visit gateway are Stage 4 and do not live here — this module
never writes a Visit or touches `status` beyond the create/cancel transitions it itself owns.

THE DOUBLE-TAP GUARD, first, before anything else — same shape as `record_visit()`: one indexed
read on `idempotency_key`, before the licence check, before the lock, before anything is created.
A retried create must return the same booking, not a second one and not a licence refusal for a
shop that already has the commitment it is paying for.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from app.core.lock import SlotClaimBusy, claiming
from app.core.models import STATUS_BOOKED, STATUS_CANCELLED, TERMINAL, Booking
from app.core.stores import BookingStore, day_bucket, new_id


class OperationError(Exception):
    """A refusal an operator can act on, carrying its own Arabic sentence."""


@dataclass
class DurationLookup:
    """The one question this module asks a peer: what is `service_ids` worth in minutes, right
    now. Kept as a tiny injected port rather than a direct import — `bookings` and `operations`
    are independent services and do not import each other's code."""
    lookup: Any   # async (tenant, service_ids) -> int | None; None == not configured

    async def minutes(self, tenant: str, service_ids: tuple[str, ...]) -> int | None:
        return await self.lookup(tenant, service_ids)


class BookingOperations:
    def __init__(self, *, datastore: Any, bookings: BookingStore, durations: DurationLookup,
                licence: Any) -> None:
        self._store = datastore
        self._bookings = bookings
        self._durations = durations
        self._licence = licence

    async def create(self, *, tenant: str, branch_id: str, operator_id: str, customer_id: str,
                     service_ids: list[str], starts_at: int, note: str = "",
                     idempotency_key: str = "", created_by: str = "",
                     series_id: str | None = None, series_seq: int | None = None,
                     deposit_taken: bool = False) -> Booking:
        if not tenant:
            raise OperationError("لا توجد منشأة على الطلب — سجّل الدخول من جديد")
        if not branch_id or not operator_id or not customer_id:
            raise OperationError("الفرع والموظفة والعميلة مطلوبون لإنشاء حجز")
        if not service_ids or any(not str(s).strip() for s in service_ids):
            raise OperationError("اختر خدمة واحدة على الأقل")
        if not starts_at or int(starts_at) <= 0:
            raise OperationError("وقت الحجز مطلوب")

        # The double-tap guard, before the licence check and before the lock — a retry of an
        # already-created booking must never be told "ليس في اشتراكك" or contend for a lane it
        # already won.
        if idempotency_key:
            existing = await self._bookings.by_idempotency_key(tenant, idempotency_key)
            if existing is not None:
                return existing

        # REFUSED ON THE GROWING HALF (app/core/licence.py's own line). A lapsed subscription
        # never strands an existing booking, but it stops a new one being made.
        await self._licence.require(tenant)

        duration = await self._durations.minutes(tenant, tuple(service_ids))
        if not duration:
            # THE "SILENT DEFAULT DECIDES POLICY" FAMILY, NAMED EXPLICITLY: no thirty-minute
            # guess. §4 of the plan requires this refusal by name.
            raise OperationError("مدة هذه الخدمة غير مضبوطة — اطلب من صاحب المحل ضبطها من «خدماتي»")

        now = time.time()
        booking = Booking(
            id=new_id("bkg"), tenant=tenant, branch_id=branch_id, operator_id=operator_id,
            customer_id=customer_id, service_ids=tuple(service_ids), starts_at=int(starts_at),
            duration_minutes=duration, status=STATUS_BOOKED, series_id=series_id,
            series_seq=series_seq, deposit_taken=deposit_taken, note=note.strip()[:500],
            idempotency_key=idempotency_key, created=int(now), created_by=created_by,
            updated=int(now))
        return await self._claim_and_save(booking, now=now)

    async def reschedule(self, *, tenant: str, booking_id: str, starts_at: int,
                         operator_id: str = "") -> Booking:
        """Moving the time, and/or reassigning the operator — the same act (§6.1.1 of the design
        doc: the drag-and-drop IS this call)."""
        booking = await self._require(tenant, booking_id)
        await self._licence.require(tenant)
        now = time.time()
        booking.starts_at = int(starts_at)
        if operator_id:
            booking.operator_id = operator_id
        booking.updated = int(now)
        return await self._claim_and_save(booking, now=now)

    async def edit_services(self, tenant: str, booking_id: str, service_ids: list[str]) -> Booking:
        """`duration_minutes` is a SNAPSHOT (§2) — it is recomputed HERE, on an explicit edit, and
        nowhere else. A background read must never silently reshuffle a booking's length."""
        booking = await self._require(tenant, booking_id)
        await self._licence.require(tenant)
        if not service_ids or any(not str(s).strip() for s in service_ids):
            raise OperationError("اختر خدمة واحدة على الأقل")
        duration = await self._durations.minutes(tenant, tuple(service_ids))
        if not duration:
            raise OperationError("مدة هذه الخدمة غير مضبوطة — اطلب من صاحب المحل ضبطها من «خدماتي»")
        now = time.time()
        booking.service_ids = tuple(service_ids)
        booking.duration_minutes = duration
        booking.updated = int(now)
        # A duration-only edit does not move the slot's time, so it cannot create a NEW conflict —
        # re-claiming the same lane it already holds is still correct and cheap.
        return await self._claim_and_save(booking, now=now)

    async def edit_note(self, tenant: str, booking_id: str, note: str) -> Booking:
        """The one edit that touches nothing time- or resource-related — no claim lane (that
        lane serialises DIFFERENT bookings for one operator, not two writers of this one row), so
        this goes through `save_if_unchanged` instead (§4's second race scenario)."""
        booking = await self._require(tenant, booking_id)
        expected = booking.rev
        booking.note = note.strip()[:500]
        booking.updated = int(time.time())
        return await self._bookings.save_if_unchanged(booking, expected_rev=expected)

    async def cancel(self, tenant: str, booking_id: str, reason: str = "") -> Booking:
        # NOT `_require`: that refuses every TERMINAL status uniformly, and CANCELLED is one of
        # them — a cancel of an already-cancelled booking would be told "أُغلِق ولا يمكن تعديله",
        # which breaks the idempotency this method exists to promise. Fetched directly instead,
        # so the already-cancelled case can return early rather than being refused.
        booking = await self._bookings.get(tenant, booking_id)
        if booking is None:
            raise OperationError("الحجز غير موجود")
        if booking.status == STATUS_CANCELLED:
            # Idempotent — a retried cancel of an already-cancelled booking is a no-op success,
            # not an error (same shape as `record_visit`'s and `erase()`'s own idempotency).
            return booking
        if booking.status in TERMINAL:
            # attended / no_show ARE terminal and are NOT cancellable — only "already cancelled"
            # gets the idempotent early return above.
            raise OperationError("هذا الحجز أُغلِق ولا يمكن إلغاؤه")
        expected = booking.rev
        booking.status = STATUS_CANCELLED
        booking.cancelled_reason = (reason or "").strip()[:300] or None
        booking.updated = int(time.time())
        return await self._bookings.save_if_unchanged(booking, expected_rev=expected)

    async def _require(self, tenant: str, booking_id: str) -> Booking:
        booking = await self._bookings.get(tenant, booking_id)
        if booking is None:
            raise OperationError("الحجز غير موجود")
        if booking.status in TERMINAL:
            # ONE-WAY TRANSITIONS (§2): a terminal booking is never edited back to life.
            raise OperationError("هذا الحجز أُغلِق ولا يمكن تعديله")
        return booking

    async def _claim_and_save(self, booking: Booking, *, now: float) -> Booking:
        """The lock, taken only here — at the one moment a time/operator commitment is actually
        confirmed. §2's two-step sequence: any advisory read the caller did before this (the
        grid's own colouring while dragging) happened outside the lock and is not re-trusted."""
        async with claiming(self._store, tenant=booking.tenant, branch_id=booking.branch_id,
                            operator_id=booking.operator_id, starts_at=booking.starts_at, now=now):
            await self._refuse_if_conflicting(booking)
            return await self._bookings.save(booking)

    async def _refuse_if_conflicting(self, booking: Booking) -> None:
        """The AUTHORITATIVE re-check, inside the lock — the advisory grid read before the lock
        is never trusted for the actual write (§2)."""
        end = booking.starts_at + booking.duration_minutes * 60
        bucket = day_bucket(booking.starts_at)
        candidates = await self._bookings.slots_between(
            booking.tenant, booking.branch_id, start_bucket=bucket, end_bucket=bucket)
        for other in candidates:
            if other.id == booking.id or other.operator_id != booking.operator_id:
                continue
            if other.status == STATUS_CANCELLED:
                # A cancelled booking gives its slot back — the only status that does. attended
                # and no_show still OCCUPIED the operator's time and remain real conflicts.
                continue
            other_end = other.starts_at + other.duration_minutes * 60
            if booking.starts_at < other_end and other.starts_at < end:
                raise SlotClaimBusy("تعذّر الحجز — هذا الموعد أصبح محجوزاً، اختر وقتاً آخر")
