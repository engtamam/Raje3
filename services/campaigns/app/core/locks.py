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

from typing import Any

CAMPAIGN_LOCKS = "campaign_locks"


async def record_lock(store: Any, tenant: str, goal: str, until: int) -> None:
    """Remember that `goal` is locked until `until`, merging with whatever was there.

    A no-op for an empty goal or a zero/negative `until` — nothing here should ever WRITE a lock's
    absence, only its presence, since a missing row already reads as "not locked".
    """
    if not goal or not until:
        return
    row = await store.get(CAMPAIGN_LOCKS, tenant) or {"tenant": tenant, "locks": {}}
    locks = dict(row.get("locks") or {})
    locks[goal] = max(int(locks.get(goal) or 0), int(until))
    row["tenant"] = tenant
    row["locks"] = locks
    await store.put(CAMPAIGN_LOCKS, tenant, row)


async def read_locks(store: Any, tenant: str) -> dict[str, int]:
    """goal -> locked_until, from the side record — a single-key read, not a scan."""
    row = await store.get(CAMPAIGN_LOCKS, tenant)
    if not row:
        return {}
    return {g: int(u) for g, u in (row.get("locks") or {}).items() if u}
