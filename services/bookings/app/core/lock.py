"""The double-booking lock — the lane, and the door it is enforced at.

Mirrors `operations/app/core/seats.py`'s `claiming()` exactly: the read-then-write that decides
"is this slot free" was never one act, and two staff opening the same booking window at the same
moment both read "free", both confirm, and both win — unless the confirm is serialised.

────────────────────────────────────────────────────────────────────────────────────────────────
THE LANE, docs/خطة-تنفيذ-الحجوزات.md §2

`{tenant}:{branch_id}:{operator_id}:{starts_at_bucket}` — bucketed to a 15-minute grain (Tamam's
decision, 2026-08-19), not the exact second. Two attempts at 10:00:00 and 10:00:03 for the same
operator must contend for the SAME lane, or the lock is decoration for the race it exists to
guard. Per-OPERATOR, not per-branch, deliberately: two different staff at the same branch in the
same minute do not contend.

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


@_contextlib.asynccontextmanager
async def claiming(datastore: Any, *, tenant: str, branch_id: str, operator_id: str,
                   starts_at: int, now: float) -> Any:
    """Hold this operator's booking lane for one confirm. See the module doc for why this exists
    and why it is per-operator, not per-branch."""
    lane = f"{tenant}:{branch_id}:{operator_id}:{starts_at_bucket(starts_at)}"
    if not await datastore.claim(CLAIMS, lane, {"tenant": tenant, "branch_id": branch_id,
                                                "operator_id": operator_id},
                                 ttl_seconds=CLAIM_TTL_SECONDS, now=now):
        raise SlotClaimBusy("تعذّر الحجز — هذا الموعد أصبح محجوزاً، اختر وقتاً آخر")
    try:
        yield
    finally:
        # RELEASED, AND THE TTL IS THE BACKSTOP — a delete that fails (or a pod killed mid-claim)
        # leaves the lane held for CLAIM_TTL_SECONDS and no longer.
        await datastore.delete(CLAIMS, lane)
