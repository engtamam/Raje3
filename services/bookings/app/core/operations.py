"""Booking creation, editing, cancellation, and the states an attended booking passes through.

Stage 3 (docs/خطة-تنفيذ-الحجوزات.md §3): create/edit/cancel, the double-booking lock, the slot
index. Stage 4 (§3, "الحالات ونداء بوابة الحجز→الزيارة") adds `attend`/`no_show` — attendance
is the ONLY path that ever produces a Visit, and it does so by calling `operations` (a peer
service), never by writing a Visit row directly: this service does not own that shape. Stage 5
adds the `bookings.booking.changed` event `reminders` schedules the confirmation from, and stamps
`subject_ref` at create time (§6.5) — the SAME peer question, since the event needs the same
pseudonym the DSAR fan-out needs.

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
from app.core.models import (STATUS_ATTENDED, STATUS_BOOKED, STATUS_CANCELLED, STATUS_NO_SHOW,
                             TERMINAL, Booking)
from app.core.stores import BookingStore, day_bucket, new_id


class OperationError(Exception):
    """A refusal an operator can act on, carrying its own Arabic sentence."""


@dataclass
class DurationLookup:
    """The one question this module asks `operations`: what is `service_ids` worth in minutes,
    right now. Kept as a tiny injected port rather than a direct import — `bookings` and
    `operations` are independent services and do not import each other's code."""
    lookup: Any   # async (tenant, service_ids) -> int | None; None == not configured

    async def minutes(self, tenant: str, service_ids: tuple[str, ...]) -> int | None:
        return await self.lookup(tenant, service_ids)


@dataclass
class VisitGateway:
    """The booking->visit gateway (§4) — the SECOND question this module asks `operations`. Same
    shape as `DurationLookup`: a tiny injected port, not a direct import."""
    create: Any   # async (**kwargs) -> dict | None; see HttpVisitGateway.create's signature

    async def record(self, **kwargs: Any) -> dict | None:
        return await self.create(**kwargs)


@dataclass
class SubjectRefLookup:
    """The customer's pseudonym (§5, §6.5) — the THIRD, and last, question this module asks
    `operations`. `None` means "could not ask", never "no pseudonym" — see
    `HttpSubjectRefLookup`'s own docstring for the distinction and why it matters here."""
    lookup: Any   # async (tenant, customer_id) -> str | None

    async def resolve(self, tenant: str, customer_id: str) -> str | None:
        return await self.lookup(tenant, customer_id)


BOOKING_EVENTS_TOPIC = "bookings.booking.changed"


@dataclass
class BookingEvents:
    """Publishes what `reminders` schedules the confirmation from (§5) — never a direct call into
    another service, same reasoning as `operations`' own `_emit_visit`: a service that knows its
    consumers has to be changed every time one is added. `publish` is `None` in tests/local runs
    with no event bus; a missed publish there costs one confirmation, never the booking itself."""
    publish: Any   # bound EventBus.publish(topic, Event), or None

    async def emit(self, *, kind: str, booking: Booking) -> None:
        if self.publish is None:
            return
        try:
            from app.ports.event_bus import Event
            await self.publish(BOOKING_EVENTS_TOPIC, Event(
                type=BOOKING_EVENTS_TOPIC,
                payload={
                    "tenant": booking.tenant, "subject_ref": booking.subject_ref,
                    "booking_id": booking.id, "kind": kind, "starts_at": booking.starts_at,
                    "branch_id": booking.branch_id,
                }))
        except Exception:                                                   # noqa: BLE001
            # A CONFIRMATION MISSED IS NOT A BOOKING LOST. The write already happened; failing the
            # request now over a notification side effect would tell the shop their booking did
            # not go through when it did. Same asymmetry as `operations`' own event publish.
            pass


class BookingOperations:
    def __init__(self, *, datastore: Any, bookings: BookingStore, durations: DurationLookup,
                licence: Any, visits: VisitGateway, subject_refs: SubjectRefLookup,
                events: BookingEvents) -> None:
        self._store = datastore
        self._bookings = bookings
        self._durations = durations
        self._licence = licence
        self._visits = visits
        self._subject_refs = subject_refs
        self._events = events

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

        # STAMPED ONCE, HERE, FAIL-CLOSED — same family as the duration refusal above. Without a
        # pseudonym this booking can never be found by a DSAR (§6.5) and can never key a
        # confirmation event `reminders` can act on (§5): a booking created without one is a
        # booking this product cannot honour either promise for, silently, for its whole life.
        subject_ref = await self._subject_refs.resolve(tenant, customer_id)
        if not subject_ref:
            raise OperationError(
                "تعذّر التحقق من العميلة الآن — حاول مجدداً بعد قليل" if subject_ref is None
                else "العميلة غير موجودة — أعد اختيارها")

        now = time.time()
        booking = Booking(
            id=new_id("bkg"), tenant=tenant, branch_id=branch_id, operator_id=operator_id,
            customer_id=customer_id, subject_ref=subject_ref, service_ids=tuple(service_ids),
            starts_at=int(starts_at), duration_minutes=duration, status=STATUS_BOOKED,
            series_id=series_id, series_seq=series_seq, deposit_taken=deposit_taken,
            note=note.strip()[:500], idempotency_key=idempotency_key, created=int(now),
            created_by=created_by, updated=int(now))
        saved = await self._claim_and_save(booking, now=now)
        await self._events.emit(kind="created", booking=saved)
        return saved

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
        saved = await self._claim_and_save(booking, now=now)
        await self._events.emit(kind="rescheduled", booking=saved)
        return saved

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
        saved = await self._bookings.save_if_unchanged(booking, expected_rev=expected)
        await self._events.emit(kind="cancelled", booking=saved)
        return saved

    async def attend(self, tenant: str, booking_id: str, occurred_at: int = 0) -> Booking:
        """The ONE way an attended booking becomes a real Visit (§4). `occurred_at` empty means
        "now"; a value lets a late entry (recorded after the fact) carry the real time.

        NOT `_require`: cancelled and no_show ARE terminal and correctly refuse re-entry, but
        ATTENDED must return early — idempotent, same shape as `cancel()` — rather than be told
        the booking is closed, since a retried confirm-attendance tap must not risk a second call
        into the visit gateway.
        """
        booking = await self._bookings.get(tenant, booking_id)
        if booking is None:
            raise OperationError("الحجز غير موجود")
        if booking.status == STATUS_ATTENDED:
            return booking   # idempotent — the visit already exists, nothing to redo
        if booking.status in TERMINAL:
            raise OperationError("هذا الحجز أُغلِق ولا يمكن تسجيل حضوره")

        # THE PEER CALL, BEFORE THE STATUS FLIPS. A Visit that failed to get created must never be
        # implied by a booking that already reads "attended" — the booking's own idempotency_key
        # namespace is reused as the visit's (prefixed, so a booking id can never collide with a
        # till's own key), so a retried attend() that DID create the visit last time reaches the
        # SAME visit through `operations`' own idempotency, never a second one.
        result = await self._visits.record(
            tenant=tenant, customer_id=booking.customer_id, service_ids=booking.service_ids,
            operator_id=booking.operator_id, branch_id=booking.branch_id, note=booking.note,
            idempotency_key=f"bkg:{booking.id}", occurred_at=occurred_at)
        if result is None or not result.get("visit_id"):
            raise OperationError("تعذّر تسجيل الزيارة الآن — حاول مجدداً بعد قليل")

        expected = booking.rev
        booking.status = STATUS_ATTENDED
        booking.visit_id = str(result["visit_id"])
        booking.updated = int(time.time())
        saved = await self._bookings.save_if_unchanged(booking, expected_rev=expected)
        await self._events.emit(kind="attended", booking=saved)
        return saved

    async def no_show(self, tenant: str, booking_id: str, reason: str = "") -> Booking:
        """The other terminal outcome — no peer call, no Visit: the customer never arrived."""
        booking = await self._bookings.get(tenant, booking_id)
        if booking is None:
            raise OperationError("الحجز غير موجود")
        if booking.status == STATUS_NO_SHOW:
            return booking   # idempotent, same shape as cancel()/attend()
        if booking.status in TERMINAL:
            raise OperationError("هذا الحجز أُغلِق ولا يمكن تعديله")
        expected = booking.rev
        booking.status = STATUS_NO_SHOW
        booking.reason_no_show = (reason or "").strip()[:300] or None
        booking.updated = int(time.time())
        saved = await self._bookings.save_if_unchanged(booking, expected_rev=expected)
        await self._events.emit(kind="no_show", booking=saved)
        return saved

    # ── Stage 8 (docs/وصف-تطبيق-الحجوزات.md §2.6/§6.2): read at the moment it is useful ────────

    RISK_WINDOW = 5     # of the last five COMPLETED appointments…
    RISK_THRESHOLD = 3  # …three or more no-shows is worth a number beside her name, not a verdict

    async def no_show_risk(self, tenant: str, customer_id: str) -> dict[str, int | bool]:
        """A number, never a judgement (§2.6): how many of her last five CLOSED appointments she
        did not attend. `booked` (still pending) and `cancelled` (never happened) are excluded —
        neither is an attendance outcome. The staff member decides what to do with the number;
        this never refuses or requires anything on its own.
        """
        rows = await self._bookings.for_customer(tenant, customer_id, limit=200)
        closed = sorted(
            (b for b in rows if b.status in (STATUS_ATTENDED, STATUS_NO_SHOW)),
            key=lambda b: b.starts_at, reverse=True,
        )[: self.RISK_WINDOW]
        no_shows = sum(1 for b in closed if b.status == STATUS_NO_SHOW)
        return {"considered": len(closed), "no_shows": no_shows,
               "risky": len(closed) > 0 and no_shows >= self.RISK_THRESHOLD}

    async def nearest_slot(self, *, tenant: str, branch_id: str, operator_id: str,
                           service_ids: list[str], after: int,
                           search_days: int = 14) -> int | None:
        """The "أقرب فتحة" button (§6.2) — the same pure derivation
        (app/core/availability.py), fed busy intervals from the operator's OWN real bookings.

        NO WORKING-HOURS STORE YET (§4 names working hours as a real, still-missing input) — the
        schedule used here is the grid's own fixed display window (08:00–22:00 Riyadh, every day),
        the same simplification Bookings.tsx's grid already renders against. This is an honest
        stand-in, not a silent guess: the day a real working-hours store exists, only THIS
        function's `schedule` changes, not its callers.
        """
        duration = await self._durations.minutes(tenant, tuple(service_ids))
        if not duration:
            raise OperationError("مدة هذه الخدمة غير مضبوطة — اطلب من صاحب المحل ضبطها من «خدماتي»")

        from app.core.availability import Schedule, Window, Busy, nearest_slot as _nearest

        FULL_WINDOW = (Window(8 * 60, 22 * 60),)
        schedule = Schedule(weekly={d: FULL_WINDOW for d in range(7)}, exceptions={})

        bucket = day_bucket(after)
        end_bucket = day_bucket(after + search_days * 86400)
        candidates = await self._bookings.slots_between(
            tenant, branch_id, start_bucket=bucket, end_bucket=end_bucket, limit=500)
        busy = [Busy(b.starts_at, b.starts_at + b.duration_minutes * 60)
               for b in candidates if b.operator_id == operator_id and b.status != STATUS_CANCELLED]

        found = _nearest(schedule, busy, duration_minutes=duration, after=after,
                         search_days=search_days)
        return found.starts_at if found else None

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
