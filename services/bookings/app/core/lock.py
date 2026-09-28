"""The double-booking lock — the lane, and the door it is enforced at.

Mirrors `operations/app/core/seats.py`'s `claiming()` exactly: the read-then-write that decides
"is this slot free" was never one act, and two staff opening the same booking window at the same
moment both read "free", both confirm, and both win — unless the confirm is serialised.

────────────────────────────────────────────────────────────────────────────────────────────────
THE LANE, docs/خطة-تنفيذ-الحجوزات.md §2

`{tenant}:{branch_id}:{operator_id}:{starts_at_bucket}` — bucketed to a 15-minute grain, deliberately,
not the exact second. Two attempts at 10:00:00 and 10:00:03 for the same
operator must contend for the SAME lane, or the lock is decoration for the race it exists to
guard. Per-OPERATOR, not per-branch, deliberately: two different staff at the same branch in the
same minute do not contend.

EVERY BUCKET THE BOOKING'S OWN DURATION SPANS, NOT JUST ITS START — fixed 2026-09-12, a real race
found by a QA audit. A booking used to claim ONLY its start-time bucket, so a 60-minute service
starting 10:00 (bucket 10:00) and a second one for the SAME operator starting 10:20 (bucket
10:15) acquired two DIFFERENT lanes and never contended, even though 10:00-11:00 and 10:20-11:20
genuinely overlap — `_refuse_if_conflicting`, the only re-check, then ran unserialised in each
lane and could let both succeed. `claiming()` now claims one lane per 15-minute bucket the
booking's `[starts_at, starts_at + duration)` span touches, in ascending order (so two callers
that overlap always contend on their FIRST shared bucket rather than deadlocking on their
second), and only proceeds once every one of them is held.

THE TWO-STEP SEQUENCE (§2): a fast advisory read from `booking_slots` BEFORE the lock is what
lets the grid paint live colour while dragging, with no network wait. The lock itself is taken
only at drop/confirm, and re-checks for REAL conflict inside — the first read was advisory only.
A conflict discovered here fails CLOSED with `SlotClaimBusy`, never silently overwrites.
"""
from __future__ import annotations

import contextlib as _contextlib
from typing import Any

# ~15 minutes — coarse enough that ordinary drift between two clients' clocks and clock skew
# between pods never splits one real contest into two different lanes; fine enough that two
# genuinely different appointment times for the same operator rarely collide by accident.
BUCKET_SECONDS = 15 * 60

CLAIM_TTL_SECONDS = 15.0
CLAIMS = "booking_claims"


class SlotClaimBusy(Exception):
    """Fails closed: somebody else is confirming this operator's slot right now."""


def starts_at_bucket(starts_at: int) -> int:
    """Round down to the lock's own grain — never the exact requested second (see module doc)."""
    return int(starts_at) - (int(starts_at) % BUCKET_SECONDS)


def _span_buckets(starts_at: int, duration_minutes: int) -> list[int]:
    """Every 15-minute bucket `[starts_at, starts_at + duration_minutes*60)` touches, ascending.
    Two overlapping real-time spans ALWAYS share at least one bucket once both are quantised to
    the same grain — this is the whole reason the fix in the module doc works: a real conflict can
    no longer land in two lanes that never meet.

    `duration_minutes <= 0` still claims exactly one bucket (its own start) — never zero lanes for
    a degenerate booking; `_refuse_if_conflicting` already treats duration as at least a point in
    time, and a lock with nothing to claim would be no lock at all.
    """
    starts_at = int(starts_at)
    # Capped at 7 days — no real booking is ever longer; without this a bad quantities/duration
    # answer could claim an unbounded number of lanes (resource exhaustion).
    minutes = min(max(1, int(duration_minutes)), 10_080)
    end = starts_at + minutes * 60
    first, last = starts_at_bucket(starts_at), starts_at_bucket(end - 1)
    return list(range(first, last + 1, BUCKET_SECONDS))


@_contextlib.asynccontextmanager
async def claiming(datastore: Any, *, tenant: str, branch_id: str, operator_id: str,
                   starts_at: int, duration_minutes: int, now: float) -> Any:
    """Hold every 15-minute lane this operator's booking spans, for one confirm — see the module
    doc for why this exists, why it is per-operator not per-branch, and why one lane (the start
    bucket alone) was not enough."""
    lanes = [f"{tenant}:{branch_id}:{operator_id}:{b}" for b in _span_buckets(starts_at, duration_minutes)]
    claimed: list[str] = []
    try:
        # ASCENDING ORDER, ALWAYS — the same order `_span_buckets` always returns for any two
        # spans, so two overlapping bookings acquire their shared buckets in the same sequence and
        # the second one blocks (or fails) on the first shared lane rather than each holding a
        # different bucket and deadlocking on the other's second.
        for lane in lanes:
            if not await datastore.claim(CLAIMS, lane, {"tenant": tenant, "branch_id": branch_id,
                                                        "operator_id": operator_id},
                                         ttl_seconds=CLAIM_TTL_SECONDS, now=now):
                raise SlotClaimBusy("تعذّر الحجز — هذا الموعد أصبح محجوزاً، اختر وقتاً آخر")
            claimed.append(lane)
        yield
    finally:
        # RELEASED, AND THE TTL IS THE BACKSTOP — a delete that fails (or a pod killed mid-claim)
        # leaves each lane held for CLAIM_TTL_SECONDS and no longer. Only the lanes this call
        # actually claimed are released — a failed claim partway through must not delete a lane
        # some OTHER caller is holding.
        for lane in claimed:
            await datastore.delete(CLAIMS, lane)
