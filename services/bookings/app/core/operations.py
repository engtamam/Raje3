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
from app.core.models import (PAYMENT_DEPOSIT, PAYMENT_NONE, PAYMENT_STATES, STATUS_ATTENDED,
                             STATUS_BOOKED, STATUS_CANCELLED, STATUS_NO_SHOW, TERMINAL, Booking)
from app.core.stores import BookingStore, day_bucket, new_id


WEEKDAY_NAMES = ("الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد")


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
class RewardGateway:
    """The loyalty spend `attend()` fires — and ONLY `attend()`, never `create()` or
    `set_intended_reward()` (§ intent, not spend, at booking time; see models.py's own note on
    `Booking.intended_reward_id`). Same shape as `VisitGateway`: a peer call into operations' own
    loyalty desk. `None` means "could not redeem" — unreachable peer, loyalty refused it, or the
    reward needs a manager's approval no unattended `attend()` call can give — and `attend()`
    leaves `intended_reward_id` set when that happens rather than crashing attendance over it."""
    redeem: Any   # async (**kwargs) -> dict | None

    async def spend(self, **kwargs: Any) -> dict | None:
        return await self.redeem(**kwargs)


@dataclass
class SubjectRefLookup:
    """The customer's pseudonym (§5, §6.5) — the THIRD, and last, question this module asks
    `operations`. `None` means "could not ask", never "no pseudonym" — see
    `HttpSubjectRefLookup`'s own docstring for the distinction and why it matters here."""
    lookup: Any   # async (tenant, customer_id) -> str | None

    async def resolve(self, tenant: str, customer_id: str) -> str | None:
        return await self.lookup(tenant, customer_id)


@dataclass
class StaffEligibilityLookup:
    """Which operators may perform each of a chosen set of services — the FOURTH question this
    module asks `operations`. `{}` (or a missing key) means "no restriction found" for that
    service, exactly like an unreachable peer: a shop that never restricted a service, or a peer
    outage, must never narrow who can be booked for it. Enforced in BOTH `create()` (the actual
    write — a client cannot bypass eligibility by skipping "أقرب موعد" and posting directly) and
    `nearest_slot()` (so a probe against an ineligible operator refuses the same way, never
    leaking an open slot for a service that operator cannot actually do)."""
    lookup: Any   # async (tenant, service_ids) -> dict[service_id, list[operator_id] | None]

    async def eligible_for(self, tenant: str, service_ids: tuple[str, ...]) -> dict[str, list[str] | None]:
        return await self.lookup(tenant, service_ids)


@dataclass
class PackageDurationLookup:
    """The package sibling of `DurationLookup` — what a PACKAGE costs in minutes, right now,
    summed FRESH from its live components by `operations` on every call (never cached — see
    operations' own Package docstring). A separate port, not a `package_id` branch inside
    `DurationLookup`, because the two ask different peer routes with different bodies."""
    lookup: Any   # async (tenant, package_id) -> int | None

    async def minutes(self, tenant: str, package_id: str) -> int | None:
        return await self.lookup(tenant, package_id)


@dataclass
class PackageEligibilityLookup:
    """The package sibling of `StaffEligibilityLookup` — which operators may perform EVERY
    component of a package, already intersected by `operations`. `None` means "no restriction
    found", same convention as the service lookup's per-service `None`."""
    lookup: Any   # async (tenant, package_id) -> list[str] | None

    async def eligible_for(self, tenant: str, package_id: str) -> list[str] | None:
        return await self.lookup(tenant, package_id)


@dataclass
class PackageOfferableCheck:
    """Is this package bookable for the Riyadh calendar day a given timestamp falls on — always
    asked against the APPOINTMENT's own date (see operations' core/scheduling.py), never "now".
    `False` on any failure — an unreachable peer or an unknown package both mean "do not book
    it", never a guessed yes."""
    lookup: Any   # async (tenant, package_id, at) -> bool

    async def offerable(self, tenant: str, package_id: str, at: int) -> bool:
        return await self.lookup(tenant, package_id, at)


@dataclass
class PackageServicesLookup:
    """A package's own component service ids, resolved ONCE at booking creation and stamped onto
    `Booking.service_ids` — so the picker/calendar card can still name what was booked without this
    service holding a copy of the catalogue. `None` means the package is unknown or retired."""
    lookup: Any   # async (tenant, package_id) -> list[str] | None

    async def resolve(self, tenant: str, package_id: str) -> list[str] | None:
        return await self.lookup(tenant, package_id)


@dataclass
class StaffHoursLookup:
    """Each candidate operator's own working-hours OVERRIDE — the FIFTH question this module asks
    `operations`. `None` for an operator (or an unreachable peer) means "inherits the shop's own
    hours in full", which is also this class's behaviour when no port is wired at all."""
    lookup: Any   # async (tenant, operator_ids) -> dict[operator_id, dict | None]

    async def hours_for(self, tenant: str, operator_ids: tuple[str, ...]) -> dict[str, dict | None]:
        return await self.lookup(tenant, operator_ids)


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
                events: BookingEvents, rewards: RewardGateway | None = None,
                risk_window: int = 5, risk_threshold_percent: int = 60,
                working_hours: Any = None,
                staff_eligibility: StaffEligibilityLookup | None = None,
                staff_hours: StaffHoursLookup | None = None,
                package_durations: PackageDurationLookup | None = None,
                package_eligibility: PackageEligibilityLookup | None = None,
                package_services: PackageServicesLookup | None = None,
                package_offerable: PackageOfferableCheck | None = None) -> None:
        self._store = datastore
        self._bookings = bookings
        self._durations = durations
        self._licence = licence
        self._visits = visits
        self._subject_refs = subject_refs
        self._events = events
        # OPTIONAL, LIKE `events.publish` ABOVE — a test or a local run with no loyalty desk wired
        # simply never redeems; `attend()` below treats a missing gateway the same as a failed one.
        self._rewards = rewards
        # CONFIG, NOT A CONSTANT — of the last `risk_window` CLOSED
        # appointments, `risk_threshold_percent` or more missed marks her "risky". See
        # `no_show_risk`'s own docstring below.
        self._risk_window = risk_window
        self._risk_threshold_percent = risk_threshold_percent
        # OPTIONAL, LIKE `rewards` ABOVE — `working_hours()` below falls back to the honest
        # 08:00-22:00 default when this is `None`, never crashes a read over it.
        self._working_hours = working_hours
        # OPTIONAL, LIKE `rewards` ABOVE — a shop with no restriction on any service (or a test/
        # local run with no peer wired) sees NO refusal, ever, from either of these: an absent
        # port means "everyone is eligible" and "everyone inherits the shop's hours", the same
        # safe defaults the peer itself answers with when it IS wired but has nothing to say.
        self._staff_eligibility = staff_eligibility
        self._staff_hours = staff_hours
        # OPTIONAL, SAME SHAPE — a test/local run with none of these wired simply cannot book a
        # PACKAGE at all (`create()` refuses with a clear reason rather than silently falling back
        # to treating it as an ordinary service list, which would price/duration/eligibility-check
        # it wrong in a way nobody would notice until a customer complained).
        self._package_durations = package_durations
        self._package_eligibility = package_eligibility
        self._package_services = package_services
        # OPTIONAL, SAME SHAPE — a deployment with none of these wired cannot book a PACKAGE at
        # all regardless (see `create()`'s own explicit refusal), so a missing schedule check
        # here never becomes a missing check in practice.
        self._package_offerable = package_offerable

    async def _refuse_if_ineligible(self, tenant: str, operator_id: str, service_ids: list[str]) -> None:
        """Refuses when `operator_id` cannot perform one of `service_ids` — enforced here, at the
        one place every booking is actually written (`create()`), not only suggested by "أقرب
        موعد": a client that skips the suggestion and posts a booking directly must be refused
        exactly the same way, or eligibility is a UI hint rather than a real rule."""
        if self._staff_eligibility is None:
            return
        by_service = await self._staff_eligibility.eligible_for(tenant, tuple(service_ids))
        for sid in service_ids:
            allowed = by_service.get(sid)
            if allowed and operator_id not in allowed:
                raise OperationError("هذا الموظف لا يقدر يسوّي إحدى الخدمات المختارة")

    async def _refuse_if_ineligible_for_booking(self, tenant: str, operator_id: str,
                                                service_ids: tuple, package_id: str) -> None:
        """Same eligibility rule `create()` enforces above, factored out for reuse — fixed
        2026-09-07: `reschedule()` and `edit_services()` used to skip this entirely, so
        reassigning a booking to a new operator (or swapping in a different service) never
        re-checked whether that operator can actually perform what the booking now holds. A QA
        audit found this real gap; this is the one place both call sites now route through."""
        if package_id:
            if self._package_eligibility is not None:
                allowed = await self._package_eligibility.eligible_for(tenant, package_id)
                if allowed and operator_id not in allowed:
                    raise OperationError("هذا الموظف لا يقدر يسوّي هذه الباقة")
        else:
            await self._refuse_if_ineligible(tenant, operator_id, list(service_ids))

    async def _effective_schedule(self, tenant: str, operator_id: str) -> "Any":
        """The shop's own weekly hours, narrowed to THIS operator's own override when he has
        one — never wider than the shop's, by construction: `operations` refuses to save an
        override that reaches outside the shop's hours (write-time check), and this intersects
        defensively AGAIN at read time regardless (belt and suspender, neither alone)."""
        from app.core.availability import Schedule, Window

        hours = await self.working_hours(tenant)
        override = None
        if self._staff_hours is not None:
            per_operator = await self._staff_hours.hours_for(tenant, (operator_id,))
            override = per_operator.get(operator_id)
        weekly: dict[int, tuple] = {}
        for d in range(7):
            shop_entry = hours[str(d)]
            entry = (override or {}).get(str(d)) if override else shop_entry
            if entry is None:
                entry = shop_entry
            if shop_entry["closed"] or entry.get("closed"):
                weekly[d] = ()
                continue
            # INTERSECTED, NOT TRUSTED AS-IS — an operator override that somehow reaches earlier/
            # later than the shop's own hours (a write-time check bypassed, or edited directly in
            # a store) still cannot open a slot the shop itself is closed for.
            start = max(int(entry.get("start_minute", shop_entry["start_minute"])), shop_entry["start_minute"])
            end = min(int(entry.get("end_minute", shop_entry["end_minute"])), shop_entry["end_minute"])
            weekly[d] = (Window(start, end),) if start < end else ()
        return Schedule(weekly=weekly, exceptions={})

    async def create(self, *, tenant: str, branch_id: str, operator_id: str, customer_id: str,
                     service_ids: list[str], starts_at: int, note: str = "",
                     idempotency_key: str = "", created_by: str = "",
                     series_id: str | None = None, series_seq: int | None = None,
                     payment_status: str = PAYMENT_NONE, deposit_amount_minor: int | None = None,
                     price_override_minor: int | None = None,
                     intended_reward_id: str | None = None,
                     # MUTUALLY EXCLUSIVE WITH `service_ids` — a booking is one or the other,
                     # never both (§ packages feature). "" is the ordinary, unchanged path below;
                     # everything in this `if package_id:` block is the ONLY new code path this
                     # feature adds — an ordinary service booking is untouched byte for byte.
                     package_id: str = "") -> Booking:
        if not tenant:
            raise OperationError("لا توجد منشأة على الطلب — سجّل الدخول من جديد")
        if not branch_id or not operator_id or not customer_id:
            raise OperationError("الفرع والموظفة والعميلة مطلوبون لإنشاء حجز")
        package_id = (package_id or "").strip()
        if package_id:
            if service_ids:
                raise OperationError("اختر إما خدمات منفردة أو باقة — لا الاثنين معاً")
            if self._package_services is None or self._package_durations is None:
                raise OperationError("حجز الباقات غير متاح في هذه البيئة الآن")
            resolved = await self._package_services.resolve(tenant, package_id)
            if not resolved:
                raise OperationError("هذه الباقة غير موجودة أو أُوقفت")
            service_ids = resolved
        elif not service_ids or any(not str(s).strip() for s in service_ids):
            raise OperationError("اختر خدمة واحدة على الأقل")
        if not starts_at or int(starts_at) <= 0:
            raise OperationError("وقت الحجز مطلوب")
        if package_id:
            # THE APPOINTMENT'S OWN DATE, NEVER "NOW" — a customer messaging today about a
            # Saturday-only package, for a booking on the coming Saturday, must succeed. Asked
            # AFTER `starts_at` is confirmed real and positive, for exactly that date.
            if self._package_offerable is None or not await self._package_offerable.offerable(
                    tenant, package_id, int(starts_at)):
                raise OperationError("هذه الباقة غير متاحة في هذا التاريخ")
        if payment_status not in PAYMENT_STATES:
            raise OperationError("حالة دفع غير معروفة")
        # "عربون اجباري ولكن مدفوع السعر غير اجباري" — a deposit with no
        # amount is not a fact anyone can act on later; «مدفوع» has the booking's own price to
        # stand for it and needs nothing extra. Never carried over from a different state either:
        # a booking that was never a deposit has no deposit amount to remember.
        if payment_status == PAYMENT_DEPOSIT and (
                deposit_amount_minor is None or int(deposit_amount_minor) <= 0):
            raise OperationError("مبلغ العربون مطلوب")
        deposit_amount_minor = int(deposit_amount_minor) if payment_status == PAYMENT_DEPOSIT else None

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

        if package_id:
            duration = await self._package_durations.minutes(tenant, package_id)
        else:
            duration = await self._durations.minutes(tenant, tuple(service_ids))
        if not duration:
            # THE "SILENT DEFAULT DECIDES POLICY" FAMILY, NAMED EXPLICITLY: no thirty-minute
            # guess. §4 of the plan requires this refusal by name.
            raise OperationError("مدة هذه الخدمة غير مضبوطة — اطلب من صاحب المحل ضبطها من «خدماتي»"
                                if not package_id else
                                "مدة هذه الباقة غير مضبوطة — تحقق من مدة كل خدمة داخلها")

        # THE WRITE ITSELF REFUSES, NOT ONLY THE SUGGESTION — see `_refuse_if_ineligible`'s own
        # docstring.
        if package_id:
            if self._package_eligibility is not None:
                allowed = await self._package_eligibility.eligible_for(tenant, package_id)
                if allowed and operator_id not in allowed:
                    raise OperationError("هذا الموظف لا يقدر يسوّي هذه الباقة")
        else:
            await self._refuse_if_ineligible(tenant, operator_id, service_ids)

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
            package_id=package_id,
            starts_at=int(starts_at), duration_minutes=duration, status=STATUS_BOOKED,
            series_id=series_id, series_seq=series_seq, payment_status=payment_status,
            deposit_amount_minor=deposit_amount_minor,
            intended_reward_id=(intended_reward_id or "").strip()[:128] or None,
            price_override_minor=price_override_minor,
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
        # THE WRITE ITSELF REFUSES, NOT ONLY create()'S OWN SUGGESTION FLOW — same reasoning as
        # `_refuse_if_ineligible`'s own docstring, fixed 2026-09-07: reassigning the operator here
        # used to skip this entirely.
        await self._refuse_if_ineligible_for_booking(
            tenant, booking.operator_id, booking.service_ids, booking.package_id)
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
        # Fixed 2026-09-07 — same gap as reschedule()'s own fix: swapping in a service the
        # CURRENT operator can't do used to go through unrefused.
        await self._refuse_if_ineligible_for_booking(
            tenant, booking.operator_id, tuple(service_ids), booking.package_id)
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

    async def set_payment_status(self, tenant: str, booking_id: str, payment_status: str,
                                 deposit_amount_minor: int | None = None) -> Booking:
        """Editable any time, on ANY status — including a terminal one. A booking closed as
        attended three days ago can still be marked paid today; `_require` would refuse that
        (it exists to stop the appointment itself changing after the fact), so this reads
        directly, same shape as `cancel`'s own idempotent-terminal handling above."""
        if payment_status not in PAYMENT_STATES:
            raise OperationError("حالة دفع غير معروفة")
        booking = await self._bookings.get(tenant, booking_id)
        if booking is None:
            raise OperationError("الحجز غير موجود")
        # A deposit amount omitted here still counts if the booking is ALREADY a deposit and
        # already carries one — re-sending "deposit" with no new number must not force the
        # amount to be retyped. Only a genuine switch INTO deposit, with none on file yet, needs it.
        amount = deposit_amount_minor if deposit_amount_minor is not None else (
            booking.deposit_amount_minor if booking.payment_status == PAYMENT_DEPOSIT else None)
        if payment_status == PAYMENT_DEPOSIT and (amount is None or int(amount) <= 0):
            raise OperationError("مبلغ العربون مطلوب")
        expected = booking.rev
        booking.payment_status = payment_status
        booking.deposit_amount_minor = int(amount) if payment_status == PAYMENT_DEPOSIT else None
        booking.updated = int(time.time())
        return await self._bookings.save_if_unchanged(booking, expected_rev=expected)

    async def set_intended_reward(
        self, tenant: str, booking_id: str, reward_id: str | None,
    ) -> Booking:
        """INTENT only — the actual spend happens in `attend()` below, never here. Refuses on a
        terminal booking (via `_require`, unlike `set_payment_status` above): once attended, the
        redemption has already been attempted one way or the other, and changing which reward was
        "intended" after the fact would not do anything — it would just misdescribe what already
        happened."""
        booking = await self._require(tenant, booking_id)
        expected = booking.rev
        booking.intended_reward_id = (reward_id or "").strip()[:128] or None
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
            idempotency_key=f"bkg:{booking.id}", occurred_at=occurred_at,
            package_id=booking.package_id)
        if result is None or not result.get("visit_id"):
            raise OperationError("تعذّر تسجيل الزيارة الآن — حاول مجدداً بعد قليل")

        expected = booking.rev
        booking.status = STATUS_ATTENDED
        booking.visit_id = str(result["visit_id"])
        # THE SPEND, NOW — THE ONE MOMENT THE VISIT IS REAL ("نية استبدال, لا
        # استبدال فوري"). `intended_reward_id` only ever meant "he asked for this at booking
        # time" — a customer's points were never touched until this exact line. Best-effort, like
        # every other secondary write hung off an attend: a failed redemption must not undo an
        # attendance that already succeeded, so it is never raised, only left un-cleared as its
        # own "still owed" signal (see the field's own note in models.py).
        if booking.intended_reward_id and self._rewards is not None:
            spent = await self._rewards.spend(
                tenant=tenant, subject_ref=booking.subject_ref,
                reward_id=booking.intended_reward_id, idempotency_key=f"bkg-reward:{booking.id}",
                branch_id=booking.branch_id, actor=f"booking:{booking.id}")
            # DEFAULT FALSE, NOT TRUE. The real peer (operations' internal_booking_redeem) always
            # includes "ok" explicitly — {"ok": bool, ...} on every path, by its own contract — so
            # this default should never actually fire; but reading a MISSING key as success is
            # exactly the shape that silently clears intended_reward_id for a spend that never
            # happened, so it fails closed like every other peer-response check in this codebase.
            if spent is not None and spent.get("ok", False):
                booking.intended_reward_id = None
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

    async def no_show_risk(self, tenant: str, customer_id: str) -> dict[str, int | bool]:
        """A number, never a judgement (§2.6): how many of her last N CLOSED appointments she did
        not attend, N and the risky-percentage both configured ("خليه config
        ما ابغ هاردكود") rather than fixed in code — a shop that finds 60% too strict or too loose
        changes ONE number, not a release. `booked` (still pending) and `cancelled` (never
        happened) are excluded — neither is an attendance outcome. The staff member decides what
        to do with the number; this never refuses or requires anything on its own.
        """
        rows = await self._bookings.for_customer(tenant, customer_id, limit=200)
        closed = sorted(
            (b for b in rows if b.status in (STATUS_ATTENDED, STATUS_NO_SHOW)),
            key=lambda b: b.starts_at, reverse=True,
        )[: self._risk_window]
        no_shows = sum(1 for b in closed if b.status == STATUS_NO_SHOW)
        considered = len(closed)
        # A MINIMUM SAMPLE, DERIVED FROM THE SAME CONFIG — not a second hardcoded number. One
        # no-show out of one closed appointment is 100%, and is not a pattern; the absolute count
        # needed to REACH the threshold across a full window is exactly the honest floor (window=5,
        # threshold=60% -> 3, the same absolute count this used to be fixed at).
        min_sample = -(-(self._risk_threshold_percent * self._risk_window) // 100)   # ceil div
        risky = (considered >= min_sample
                and (no_shows * 100) >= self._risk_threshold_percent * considered)
        return {"considered": considered, "no_shows": no_shows, "risky": risky,
               "threshold_percent": self._risk_threshold_percent}

    # ── working hours (docs/وصف-تطبيق-الحجوزات.md §4: "working hours… a real, still-missing
    # input") — ONE policy per tenant, every branch shares it. ────────────────

    async def working_hours(self, tenant: str) -> dict[str, dict[str, int | bool]]:
        """The shop's own weekly policy, always all 7 days (0=Monday..6=Sunday, `date.weekday()`'s
        own numbering — the same one `availability.Schedule` already uses, so this needs no
        translation at the one call site that turns it into a real `Schedule`).

        A TENANT THAT NEVER CONFIGURED THIS reads 08:00-22:00 every day — the exact honest
        stand-in `nearest_slot` used before this store existed, so nothing that worked before this
        shipped breaks the day it does. Never raises: a read that cannot reach the store answers
        the same default rather than an error a grid has no way to draw.
        """
        raw = await self._working_hours.get(tenant) if self._working_hours else None
        weekly = (raw or {}).get("weekly") or {}
        out: dict[str, dict[str, int | bool]] = {}
        for d in range(7):
            entry = weekly.get(str(d)) or {}
            out[str(d)] = {
                "closed": bool(entry.get("closed", False)),
                "start_minute": int(entry.get("start_minute", 8 * 60)),
                "end_minute": int(entry.get("end_minute", 22 * 60)),
            }
        return out

    async def set_working_hours(
        self, tenant: str, weekly: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, int | bool]]:
        """Every one of the 7 days, always — a PARTIAL save is ambiguous (day 3 sent, day 5 not:
        keep its old value, or default it?), so the whole week is validated and written as one
        document, never merged with what was there."""
        if self._working_hours is None:
            raise OperationError("تخزين أوقات الدوام غير متاح الآن")
        out: dict[str, dict[str, int | bool]] = {}
        for d in range(7):
            entry = weekly.get(str(d)) or {}
            closed = bool(entry.get("closed", False))
            start = int(entry.get("start_minute", 0) or 0)
            end = int(entry.get("end_minute", 0) or 0)
            if not closed and not (0 <= start < end <= 24 * 60):
                raise OperationError(f"وقت دوام يوم {WEEKDAY_NAMES[d]} غير صحيح")
            out[str(d)] = {"closed": closed, "start_minute": start, "end_minute": end}
        await self._working_hours.save(tenant, {"weekly": out})
        return out

    async def bookings_for_customer(self, tenant: str, customer_id: str, limit: int = 50) -> list[Booking]:
        """His own history, newest first — the customer page's own section (docs/وصف-تطبيق-
        الحجوزات.md §3: "مواعيده القادمة والسابقة"), the same store read `no_show_risk` above
        already makes, just unfiltered by status and ordered for a person to read rather than a
        percentage to compute."""
        rows = await self._bookings.for_customer(tenant, customer_id, limit=limit)
        return sorted(rows, key=lambda b: b.starts_at, reverse=True)

    async def bookings_for_subject(self, tenant: str, subject_ref: str, limit: int = 50
                                   ) -> list[Booking]:
        """SAME READ as `bookings_for_customer` above, keyed by pseudonym — for a caller (an
        investigation tool, e.g.) that only ever resolves a phone number to `subject_ref` and must
        never be handed a real `customer_id` just to look one history up."""
        rows = await self._bookings.for_subject(tenant, subject_ref, limit=limit)
        return sorted(rows, key=lambda b: b.starts_at, reverse=True)

    async def bookings_by_actor(self, tenant: str, created_by: str, *, branch_id: str = "",
                                since: int | None = None, until: int | None = None,
                                limit: int = 2000) -> tuple[list[Booking], bool]:
        """Every booking a given ACTOR made — whatsapp-assistant's own attribution stamp
        (`created_by`, see api/internal.py's `InternalCreateBookingIn`) — not a customer's history.
        The read `upsell_report.py` names as its own documented follow-up: a cross-service report
        needs bookings filtered by who made them, not by whose they are. Returns (rows, truncated);
        see `BookingStore.by_actor`'s own note on why the scan is bounded rather than exhaustive."""
        return await self._bookings.by_actor(tenant, created_by, branch_id=branch_id, since=since,
                                             until=until, limit=limit)

    async def nearest_slot(self, *, tenant: str, branch_id: str, operator_id: str,
                           service_ids: list[str], after: int,
                           search_days: int = 14,
                           exclude_booking_id: str = "",
                           # MUTUALLY EXCLUSIVE WITH `service_ids` — same packages-feature rule as
                           # `create()`. "" is the ordinary, unchanged path below.
                           package_id: str = "") -> int | None:
        """The "أقرب موعد" button (§6.2) - the same pure derivation (app/core/availability.py),
        fed busy intervals from the operator's OWN real bookings, the shop's own working hours,
        and now (this feature) THIS OPERATOR'S OWN hours when he has a custom schedule - see
        `_effective_schedule`. Refuses up front, same as `create()`, if this operator cannot
        actually perform one of `service_ids` - a probe against an ineligible operator must not
        leak an open slot he could never actually be booked into.
        """
        package_id = (package_id or "").strip()
        if package_id:
            if self._package_durations is None or self._package_eligibility is None:
                raise OperationError("حجز الباقات غير متاح في هذه البيئة الآن")
            duration = await self._package_durations.minutes(tenant, package_id)
            if not duration:
                raise OperationError("مدة هذه الباقة غير مضبوطة — تحقق من مدة كل خدمة داخلها")
            allowed = await self._package_eligibility.eligible_for(tenant, package_id)
            if allowed and operator_id not in allowed:
                raise OperationError("هذا الموظف لا يقدر يسوّي هذه الباقة")
        else:
            duration = await self._durations.minutes(tenant, tuple(service_ids))
            if not duration:
                raise OperationError(
                    "مدة هذه الخدمة غير مضبوطة — اطلب من صاحب المحل ضبطها من «خدماتي»")

            await self._refuse_if_ineligible(tenant, operator_id, service_ids)

        from app.core.availability import Busy, free_slots, nearest_slot as _nearest

        schedule = await self._effective_schedule(tenant, operator_id)

        bucket = day_bucket(after)
        end_bucket = day_bucket(after + search_days * 86400)
        candidates = await self._bookings.slots_between(
            tenant, branch_id, start_bucket=bucket, end_bucket=end_bucket, limit=500)
        # THE BOOKING BEING RESCHEDULED IS NOT BUSY AGAINST ITSELF — see the route's own note on
        # `exclude_booking_id`. Same exclusion `_refuse_if_conflicting` already makes for the write.
        busy = [Busy(b.starts_at, b.starts_at + b.duration_minutes * 60)
               for b in candidates if b.operator_id == operator_id and b.status != STATUS_CANCELLED
               and b.id != exclude_booking_id]

        if package_id:
            # DAY-STEPPED, NOT A SINGLE CALL — a package may only recur on SOME days in this
            # window (weekly/monthly/yearly, core/scheduling.py on the operations side), so the
            # ordinary "first free slot" answer would happily return a slot on a day the package
            # does not run. `free_slots` (pure, no I/O) gives every candidate across the whole
            # window at once; each is checked against the package's own schedule for its OWN day,
            # memoised so a day with several candidate slots is only asked about once.
            all_slots = free_slots(schedule, busy, duration_minutes=duration,
                                   window_start=after, window_end=after + search_days * 86400)
            offerable_by_day: dict[int, bool] = {}
            for slot in all_slots:
                day = day_bucket(slot.starts_at)
                if day not in offerable_by_day:
                    offerable_by_day[day] = (self._package_offerable is not None and
                                             await self._package_offerable.offerable(
                                                 tenant, package_id, slot.starts_at))
                if offerable_by_day[day]:
                    return slot.starts_at
            return None

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
        grid's own colouring while dragging) happened outside the lock and is not re-trusted.

        `save_if_unchanged(expected_rev=booking.rev)`, NOT a bare `save()` — found by review: the
        claim lane above only serialises TWO DIFFERENT bookings colliding on the same
        (branch, operator, time-bucket); it says nothing about two writers editing the SAME
        booking (§4's second race scenario, the exact one `edit_note`/`set_payment_status`/`cancel`
        already guard against via this same call). Without this, a caller holding a stale
        in-memory `Booking` (its own copy, `rev` unchanged since it was fetched) could silently
        overwrite a genuinely newer edit — e.g. a booking-management-via-WhatsApp reschedule retry
        landing after a staff member already moved the SAME booking elsewhere on the console.
        `booking.rev` here is always the value the caller's fetch produced (never touched by local
        mutation — `rev` only advances inside `save()` itself), so this is exactly the same
        "expected == what I actually read" contract every other write in this file already keeps.
        Harmless for a brand-new `create()`: a fresh `new_id("bkg")` has no stored row yet, so
        `save_if_unchanged` finds `current is None` and skips the comparison entirely, same as
        `save()` always did.
        """
        async with claiming(self._store, tenant=booking.tenant, branch_id=booking.branch_id,
                            operator_id=booking.operator_id, starts_at=booking.starts_at, now=now):
            await self._refuse_if_conflicting(booking)
            return await self._bookings.save_if_unchanged(booking, expected_rev=booking.rev)

    async def _refuse_if_conflicting(self, booking: Booking) -> None:
        """The AUTHORITATIVE re-check, inside the lock — the advisory grid read before the lock
        is never trusted for the actual write (§2).

        SCANS THE ADJACENT DAY-BUCKETS TOO — fixed 2026-09-07, a real bug found by a QA audit: a
        booking is stored under the bucket of its OWN start time, but a service long enough to push
        a late booking past midnight (e.g. 23:50 + 60min) OCCUPIES the next day's early slots too.
        Querying only `booking`'s own bucket missed a same-operator conflict stored under the
        PREVIOUS day's bucket (a late booking already there) as well as one that would be missed
        under the NEXT day's bucket if `booking` itself is the one spilling over — this scans one
        day either side, a cheap, safe over-read (`slots_between` is one indexed query, not a full
        scan) rather than trusting the "no shop is open at midnight" assumption to hold everywhere
        a booking can be created (nothing in `create()`/`reschedule()` actually enforces it)."""
        end = booking.starts_at + booking.duration_minutes * 60
        start_bucket = day_bucket(booking.starts_at - 86_400)
        end_bucket = day_bucket(max(end - 1, booking.starts_at) + 86_400)
        candidates = await self._bookings.slots_between(
            booking.tenant, booking.branch_id, start_bucket=start_bucket, end_bucket=end_bucket)
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
