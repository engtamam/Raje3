"""The awareness lock, indexed by goal — a side record so reading it is not a campaign scan.

WHY THIS EXISTS. `campaigns` has no `locked_until > now` query: the store filters by equality
(JSONB containment) only, not by range, so finding "the campaigns that are currently locked" meant
reading every campaign row for the tenant and checking each one — a scan that grows with the
tenant's whole campaign history to answer a question about at most one lock per goal.

ONE ROW PER TENANT, KEYED BY GOAL, HOLDING THE LATEST `locked_until`. There are only a handful of
goals (see `app.core.goals.CARDS`), so this is always a small, single-key read — `_locks()` in the
API layer used to page through up to two hundred campaign rows for the same answer.

UPDATED AT EVERY PLACE A CAMPAIGN'S `locked_until` IS WRITTEN — currently `tick.py`'s `_fire` (the
standing/automatic path) and the manual-create route in `api/v1/campaigns.py`. `record_lock` is the
one function both call, so there is one place this invariant can break rather than two copies of
the same three lines silently drifting apart.

`record_lock` only ever raises `until` for a goal, never lowers it — the same behaviour as the scan
it replaces, which took the MAX across every campaign that carried a lock for that goal.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

CAMPAIGN_LOCKS = "campaign_locks"

# A SEPARATE COLLECTION FROM THE ROW IT GUARDS — the mutex must be claimable/expirable on its own
# terms, not entangled with the value being protected.
_MUTEX_COLLECTION = "campaign_locks_mutex"
_MUTEX_TTL_SECONDS = 5.0
# Bounded, not indefinite — two writers on the same tenant+goal within the same request window is
# already the rare case this closes; a caller that still cannot get the mutex after this many tries
# falls back to the old read-then-write rather than hang the tick or the create route on it.
_MUTEX_RETRY_ATTEMPTS = 5
_MUTEX_RETRY_DELAY_SECONDS = 0.05


async def record_lock(store: Any, tenant: str, goal: str, until: int) -> None:
    """Remember that `goal` is locked until `until`, merging with whatever was there.

    A no-op for an empty goal or a zero/negative `until` — nothing here should ever WRITE a lock's
    absence, only its presence, since a missing row already reads as "not locked".

    ATOMIC NOW — fixed 2026-09-12, a real gap a QA audit found: this used to be a plain
    check-then-act (`get` the row, mutate the in-memory dict, `put` it back), the identical race
    `core/press.py` was hardened against after an earlier audit found it there. Two writers racing
    on the same tenant+goal (a tick firing the same moment an owner presses manually, or two pods
    racing the same tick) could both read the old row before either wrote, and the loser's `put`
    would silently overwrite the winner's fresher `locked_until` with a stale, lower value. A short
    `store.claim()`-backed mutex around the read-modify-write closes it — `max()` is already
    idempotent under retry, so a caller that could not get the mutex in time still gets a correct,
    merely non-atomic, answer rather than none at all.
    """
    if not goal or not until:
        return
    mutex_key = f"{tenant}|{goal}"
    now = time.time()
    held = False
    for _ in range(_MUTEX_RETRY_ATTEMPTS):
        held = await store.claim(_MUTEX_COLLECTION, mutex_key, {"held": True},
                                 ttl_seconds=_MUTEX_TTL_SECONDS, now=now)
        if held:
            break
        await asyncio.sleep(_MUTEX_RETRY_DELAY_SECONDS)
    try:
        row = await store.get(CAMPAIGN_LOCKS, tenant) or {"tenant": tenant, "locks": {}}
        locks = dict(row.get("locks") or {})
        locks[goal] = max(int(locks.get(goal) or 0), int(until))
        row["tenant"] = tenant
        row["locks"] = locks
        await store.put(CAMPAIGN_LOCKS, tenant, row)
    finally:
        if held:
            await store.delete(_MUTEX_COLLECTION, mutex_key)


async def read_locks(store: Any, tenant: str) -> dict[str, int]:
    """goal -> locked_until, from the side record — a single-key read, not a scan."""
    row = await store.get(CAMPAIGN_LOCKS, tenant)
    if not row:
        return {}
    return {g: int(u) for g, u in (row.get("locks") or {}).items() if u}
