"""The ±1-day scan window in `_refuse_if_conflicting` only covers a booking that spills past
midnight by a few hours. A multi-day-duration booking (bounded at 7 days by
`HttpDurationLookup`'s own ceiling) can start more than a day before another booking it still
genuinely overlaps -- the old fixed-±1-day window misses that conflict entirely.
"""
from __future__ import annotations

import asyncio

from app.adapters.datastore.memory import MemoryDataStore
from app.core.licence import NullLicence
from app.core.lock import SlotClaimBusy
from app.core.operations import BookingEvents, BookingOperations, DurationLookup, SubjectRefLookup, VisitGateway
from app.core.stores import BookingStore


async def _lookup_3_days(tenant: str, service_ids, quantities=None) -> int:
    return 3 * 24 * 60


async def _no_visits(**kwargs):
    return None


async def _subject_ref(tenant: str, customer_id: str) -> str:
    return "sub_" + customer_id


def _ops() -> BookingOperations:
    store = MemoryDataStore()
    return BookingOperations(datastore=store, bookings=BookingStore(store),
                             durations=DurationLookup(lookup=_lookup_3_days), licence=NullLicence(),
                             visits=VisitGateway(create=_no_visits),
                             subject_refs=SubjectRefLookup(lookup=_subject_ref),
                             events=BookingEvents(publish=None))


def test_a_3_day_booking_still_blocks_a_conflict_2_days_later():
    async def run():
        ops = _ops()
        first_start = 1_800_000_000
        first = await ops.create(tenant="t1", branch_id="b1", operator_id="op1", customer_id="c1",
                                 service_ids=["svc1"], starts_at=first_start)
        second_start = first_start + 2 * 24 * 60 * 60
        try:
            second = await ops.create(tenant="t1", branch_id="b1", operator_id="op1",
                                      customer_id="c2", service_ids=["svc1"],
                                      starts_at=second_start)
        except SlotClaimBusy:
            return first, None
        return first, second

    first, second = asyncio.run(run())
    assert second is None, (
        "a 3-day booking starting 2 days before an overlapping slot must still be caught — "
        "got a second booking created instead of a refusal")
