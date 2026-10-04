"""The double-booking lock — the lane, and the door it is enforced at.

Mirrors `bookings/app/core/lock.py`'s own `claiming()` almost exactly (copied and adapted, never
imported — this fleet's services deploy independently, see `riyadh.py`'s own note on the same
discipline): the read-then-write that decides "is this resource-hour free" was never one act, and
two freelancers opening the same resource's calendar at the same moment both read "free", both
confirm, and both win — unless the confirm is serialised.

THE LANE is `{tenant}:{resource_id}:{bucket}`, bucketed to a 15-minute grain — the same grain
`app/core/availability.py` grids candidates on, so what this lock protects and what the public
route offers as a free slot are never two different geometries. Per-RESOURCE, not per-tenant: two
different chairs booked in the same minute do not contend.

EVERY BUCKET THE BOOKING'S OWN SPAN TOUCHES, NOT JUST ITS START — see bookings' own lock.py for the
race this closes (a 60-minute booking starting 10:00 and one starting 10:20 for the SAME resource
must land on at least one shared lane, or the lock is decoration for the exact overlap it exists to
catch). `claiming()` claims one lane per 15-minute bucket the booking's `[starts_at, ends_at)` span
touches, in ascending order, and only proceeds once every one of them is held.
"""
from __future__ import annotations

import contextlib as _contextlib
from typing import Any

# ~15 minutes — the same grain availability.py's own DEFAULT_GRANULARITY_MINUTES grids on.
BUCKET_SECONDS = 15 * 60

CLAIM_TTL_SECONDS = 15.0
CLAIMS = "coworking_claims"


class SlotClaimBusy(Exception):
    """Fails closed: somebody else is confirming this resource's slot right now."""


def starts_at_bucket(starts_at: int) -> int:
    """Round down to the lock's own grain — never the exact requested second (see module doc)."""
    return int(starts_at) - (int(starts_at) % BUCKET_SECONDS)


def _span_buckets(starts_at: int, ends_at: int) -> list[int]:
    """Every 15-minute bucket `[starts_at, ends_at)` touches, ascending. Two overlapping real-time
    spans ALWAYS share at least one bucket once both are quantised to the same grain — the whole
    reason a real conflict can no longer land in two lanes that never meet.

    `ends_at <= starts_at` still claims exactly one bucket (its own start) — never zero lanes for
    a degenerate span; a lock with nothing to claim would be no lock at all.
    """
    starts_at = int(starts_at)
    end = max(int(ends_at), starts_at + 1)
    first, last = starts_at_bucket(starts_at), starts_at_bucket(end - 1)
    return list(range(first, last + 1, BUCKET_SECONDS))


@_contextlib.asynccontextmanager
async def claiming(datastore: Any, *, tenant: str, resource_id: str,
                   starts_at: int, ends_at: int, now: float) -> Any:
    """Hold every 15-minute lane this booking spans, for one confirm — see the module doc for why
    this exists, why it is per-resource, and why one lane (the start bucket alone) was not enough."""
    lanes = [f"{tenant}:{resource_id}:{b}" for b in _span_buckets(starts_at, ends_at)]
    claimed: list[str] = []
    try:
        # ASCENDING ORDER, ALWAYS — so two overlapping bookings acquire their shared buckets in
        # the same sequence and the second one blocks (or fails) on the first shared lane rather
        # than each holding a different bucket and deadlocking on the other's second.
        for lane in lanes:
            if not await datastore.claim(CLAIMS, lane, {"tenant": tenant, "resource_id": resource_id},
                                         ttl_seconds=CLAIM_TTL_SECONDS, now=now):
                raise SlotClaimBusy("تعذّر الحجز — هذا الموعد أصبح محجوزاً، اختر وقتاً آخر")
            claimed.append(lane)
        yield
    finally:
        # RELEASED, AND THE TTL IS THE BACKSTOP — a delete that fails (or a pod killed mid-claim)
        # leaves each lane held for CLAIM_TTL_SECONDS and no longer. Only the lanes this call
        # actually claimed are released.
        for lane in claimed:
            await datastore.delete(CLAIMS, lane)
