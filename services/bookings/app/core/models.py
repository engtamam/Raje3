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
# THE DOUBLE-TAP GUARD'S OWN LOCK — added 2026-09-07. `by_idempotency_key()` (stores.py) is a
# `find()` over `bookings`, not a primary-key lookup, so it cannot itself be made atomic via
# `store.claim()` (a fixed-key primitive). This is a small, separate collection keyed on
# `f"{tenant}|{idempotency_key}"` purely to give the check a real lock to claim before the create
# path — see `BookingOperations.create()`'s own note on the race this closes.
IDEMPOTENCY_CLAIMS = "booking_idempotency_claims"
# ONE DOCUMENT PER TENANT, NOT PER BRANCH ("كل الفروع تاخذ نفس النظام") — a
# shop's working hours are one policy, not a per-branch setting; see WorkingHoursStore.
WORKING_HOURS = "working_hours"

# Three states, one field — "how much of this booking's price is actually in hand", never two
# booleans that can silently disagree ("بدون عربون بعربون او مدفوع"). Chosen at
# booking time, editable any time after — never inferred from status (a booking can be attended
# with nothing paid, or paid in full days before the appointment).
PAYMENT_NONE = "none"
PAYMENT_DEPOSIT = "deposit"
PAYMENT_PAID = "paid"
PAYMENT_STATES = frozenset({PAYMENT_NONE, PAYMENT_DEPOSIT, PAYMENT_PAID})

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
    # "" for an ordinary booking. Set at creation, MUTUALLY EXCLUSIVE with a client-chosen
    # `service_ids` (which is instead RESOLVED from the package's own components and stamped here
    # for display continuity — see BookingOperations.create's own note). Fixed after creation, same
    # as `branch_id`: changing what package a booking is for is a cancel + a new booking, never a
    # field edit — the price/duration/eligibility were all computed for THIS package at THIS time.
    package_id: str = ""
    starts_at: int = 0                   # unix seconds, mutable — this IS the reschedule act
    duration_minutes: int = 0            # a SNAPSHOT of the sum of Service.duration_minutes at
                                          # booking time, recomputed only on an explicit
                                          # service_ids edit — never re-derived on a background read
    status: str = STATUS_BOOKED
    series_id: str | None = None
    series_seq: int | None = None
    visit_id: str | None = None          # set once, on attendance — the one link booking->visit
    payment_status: str = PAYMENT_NONE   # one of PAYMENT_STATES — see the constants above
    # THE PROOF OF "عربون", NOT A GUESS — required whenever payment_status is PAYMENT_DEPOSIT
    # (enforced in operations.py), cleared whenever it is anything else. `paid` needs no amount
    # of its own: the booking's own price (price_override_minor, or the catalogue sum) already
    # says what was owed, and "مدفوع" means all of it came in.
    deposit_amount_minor: int | None = None
    # THE ONE PRICE THAT NEVER TOUCHES THE CATALOGUE. Some bookings are
    # negotiated at the counter — a returning customer, a bundle, a courtesy — and that number
    # belongs to THIS booking alone. `None` means "whatever the catalogue says"; a real value here
    # overrides it for this one appointment only. Writing it back to Service.price_minor is a
    # SEPARATE, explicit act (operations' own update_service), never implied by setting this.
    price_override_minor: int | None = None
    # A NIGHT SPENT AT THE TAP, NOT ON THE ROAD ("نية استبدال, لا استبدال
    # فوري"). Redeeming the moment a reward is CHOSEN — days before the appointment — would spend
    # a customer's points for a visit that has not happened yet; a cancelled or no-show booking
    # would then owe him points back, silently, forever. So this is only INTENT: the actual spend
    # (loyalty's own redeem()) fires in operations.py's `attend()`, the one moment the visit is
    # real. STAYS SET if that spend failed (unreachable peer, or a reward needing an approval no
    # automated attend() can give) — its continued presence on an ATTENDED booking is itself the
    # signal "still owed, redeem him by hand from the visit screen"; cleared only on success.
    intended_reward_id: str | None = None
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
