"""bookings — the one entity, and the second row that exists only to make it fast to draw.

`Booking` is the source of truth. `booking_slots` (stores.py) is a derived index written in the
same `save()` call — it exists for exactly one reason: the daily/weekly grid query (branch +
operator + a time range) is a range query crossing two equality filters, which the generic
`_find(tenant, where)` scan cannot serve on every screen-open without reading everything.

Docs/خطة-تنفيذ-الحجوزات.md §2 is the design; this module is its literal transcription.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

BOOKINGS = "bookings"
BOOKING_SLOTS = "booking_slots"

# One-way, and the four terminal states never reopen — a cancelled booking is never un-cancelled,
# it is re-created. Enforced in operations.py, not here: a dataclass cannot refuse a transition.
STATUS_BOOKED = "booked"
STATUS_ATTENDED = "attended"
STATUS_NO_SHOW = "no_show"
STATUS_CANCELLED = "cancelled"
TERMINAL = frozenset({STATUS_ATTENDED, STATUS_NO_SHOW, STATUS_CANCELLED})


@dataclass
class Booking:
    id: str
    tenant: str                          # from the verified token only — stamped at write, never
                                          # from the request body
    branch_id: str                       # fixed after creation (§2 — a branch change is a cancel
                                          # + a new booking, never a field edit)
    operator_id: str                     # mutable — reassignment
    customer_id: str                     # fixed after creation
    subject_ref: str = ""                # the customer's pseudonym, stamped once at creation
                                          # from operations (§6.5, DSAR fan-out target; also what
                                          # bookings.booking.changed events key on for reminders)
    service_ids: tuple[str, ...] = ()    # mutable; drives duration_minutes and the picker
    starts_at: int = 0                   # unix seconds, mutable — this IS the reschedule act
    duration_minutes: int = 0            # a SNAPSHOT of the sum of Service.duration_minutes at
                                          # booking time, recomputed only on an explicit
                                          # service_ids edit — never re-derived on a background read
    status: str = STATUS_BOOKED
    series_id: str | None = None
    series_seq: int | None = None
    visit_id: str | None = None          # set once, on attendance — the one link booking->visit
    deposit_taken: bool = False
    # THE ONE PRICE THAT NEVER TOUCHES THE CATALOGUE (Tamam, 2026-08-19). Some bookings are
    # negotiated at the counter — a returning customer, a bundle, a courtesy — and that number
    # belongs to THIS booking alone. `None` means "whatever the catalogue says"; a real value here
    # overrides it for this one appointment only. Writing it back to Service.price_minor is a
    # SEPARATE, explicit act (operations' own update_service), never implied by setting this.
    price_override_minor: int | None = None
    note: str = ""
    reason_no_show: str | None = None
    idempotency_key: str = ""
    created: int = 0
    created_by: str = ""
    updated: int = 0
    cancelled_reason: str | None = None
    thumb_up: bool | None = None         # Stage 2 (satisfaction ping); None = no answer yet
    rev: int = 0                         # incremented by BookingStore.save() on every write —
                                          # optimistic-concurrency's counter. NOT `updated`: two
                                          # edits landing in the same wall-clock second are
                                          # ordinary (a double-click, two fast taps) and a
                                          # second-granularity timestamp cannot tell them apart,
                                          # which would silently defeat the very guard it backs.

    def public(self) -> dict[str, Any]:
        d = self.__dict__.copy()
        d.pop("tenant", None)
        return d
