"""THE REAL BUG: `_refuse_if_conflicting` only queries the NEW booking's own day-bucket
(`operations.py`'s own `day_bucket(booking.starts_at)`). A booking that crosses midnight is stored
under ITS OWN start day's bucket, so a second booking for the same operator placed just after
midnight — in the NEXT day's bucket — never sees it: the conflict check looks in the wrong bucket
entirely. No concurrency/timing needed: this is a plain sequential double-booking, not a race.

Found by a QA fan-out audit (2026-09-07) tracing the actual conflict-check logic, not the module's
own comment claiming "no shop is open then" — nothing in `create()` enforces that assumption; a
service whose duration pushes a legitimately-started booking past midnight is never refused.
"""
from __future__ import annotations

from app.adapters.datastore.memory import MemoryDataStore
from app.core.licence import NullLicence
from app.core.lock import SlotClaimBusy
from app.core.operations import BookingEvents, BookingOperations, DurationLookup, SubjectRefLookup, VisitGateway
from app.core.stores import BookingStore


async def _lookup(tenant: str, service_ids) -> int:
    return 60   # a full hour — long enough to push a 23:50 start past midnight


async def _no_visits(**kwargs):
    return None


async def _subject_ref(tenant: str, customer_id: str) -> str:
    return "sub_" + customer_id


def _ops() -> BookingOperations:
    store = MemoryDataStore()
    return BookingOperations(datastore=store, bookings=BookingStore(store),
                             durations=DurationLookup(lookup=_lookup), licence=NullLicence(),
                             visits=VisitGateway(create=_no_visits),
                             subject_refs=SubjectRefLookup(lookup=_subject_ref),
                             events=BookingEvents(publish=None))


def test_a_booking_spilling_past_midnight_still_blocks_the_same_operators_next_slot():
    """23:50 local + 60min occupies until 00:50 the NEXT calendar day. A second booking for the
    SAME operator at 00:10 that next day genuinely overlaps (00:10-01:10 vs 23:50-00:50) and must
    be refused — not silently accepted because the conflict check looked in the wrong bucket."""
    import asyncio

    from app.core.stores import local

    async def run():
        ops = _ops()
        # Riyadh local 23:50 on some date — the code's own `local()` helper defines "local".
        first_start = 1_800_000_000
        while local(first_start).hour != 23 or local(first_start).minute != 50:
            first_start += 60
        first = await ops.create(tenant="t1", branch_id="b1", operator_id="op1", customer_id="c1",
                                 service_ids=["svc1"], starts_at=first_start)
        # 20 minutes later in wall-clock time — inside the first booking's own 23:50-00:50 span,
        # and on the NEXT calendar day (a different day-bucket).
        second_start = first_start + 20 * 60
        try:
            second = await ops.create(tenant="t1", branch_id="b1", operator_id="op1",
                                      customer_id="c2", service_ids=["svc1"],
                                      starts_at=second_start)
        except SlotClaimBusy:
            return first, None
        return first, second

    first, second = asyncio.run(run())
    assert second is None, (
        "a booking that crosses midnight must still block the same operator's overlapping slot "
        "the next calendar day — got a second booking created instead of a refusal")
