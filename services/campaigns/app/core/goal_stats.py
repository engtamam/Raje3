"""How much an owner has used each goal, and how many people it reached — a side record, the same
move `locks.py` already made for exactly the same reason.

WHY THIS EXISTS. The create screen's own rail wants two honest numbers beside each goal — how many
times it has been launched, and how many customers it has actually reached — and computing either
by draining "campaigns" plus every "campaign_runs" row for the tenant, on every load of the ONE
route the create screen calls on every visit, is exactly the cost `read_locks`'s own history
already paid once and fixed: a request that grows with a shop's WHOLE campaign history to answer a
question about at most a handful of goals.

ONE ROW PER TENANT, HOLDING TWO GOAL-KEYED MAPS — `uses` and `reach` — the identical shape
`CAMPAIGN_LOCKS` already holds for its own single `locks` map, so a read here costs exactly what a
lock read already costs: one key, never a scan.

UPDATED AT THE TWO MOMENTS EITHER NUMBER CHANGES: `record_use` when a campaign is created
(api/v1/campaigns.py's `create` route, once, right after the write succeeds — never on a retried
or refused press, since `press.py`'s own idempotency guard already keeps a re-press from reaching
this route as a second creation), and `record_reach` when a run actually sends something
(`dispatch.py::Dispatcher._save`, the one place every `Run` — standing, scheduled or manual — is
persisted, so this cannot go stale by missing a firing path the way two independent counters
copied into each caller would).
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

GOAL_STATS = "campaign_goal_stats"

# SEPARATE FROM THE ROW IT GUARDS, same reasoning as `locks.py`'s own `_MUTEX_COLLECTION`: the
# mutex must be claimable/expirable on its own terms, not entangled with the value it protects.
_MUTEX_COLLECTION = "campaign_goal_stats_mutex"
_MUTEX_TTL_SECONDS = 5.0
_MUTEX_RETRY_ATTEMPTS = 5
_MUTEX_RETRY_DELAY_SECONDS = 0.05


async def _bump(store: Any, tenant: str, goal: str, field: str, by: int) -> None:
    if not goal or by <= 0:
        return
    mutex_key = f"{tenant}|{field}|{goal}"
    now = time.time()
    held = False
    for _ in range(_MUTEX_RETRY_ATTEMPTS):
        held = await store.claim(_MUTEX_COLLECTION, mutex_key, {"held": True},
                                 ttl_seconds=_MUTEX_TTL_SECONDS, now=now)
        if held:
            break
        await asyncio.sleep(_MUTEX_RETRY_DELAY_SECONDS)
    if not held:
        # NEVER AN UNPROTECTED READ-MODIFY-WRITE. Falling through here used to run the same
        # increment anyway with no lock held — a classic lost-update race under concurrent bumps
        # to the same tenant+goal (two callers read the same count, one write clobbers the
        # other's), silently understating `uses`/`reach`, the exact numbers the create screen's
        # own rail shows as ground truth. Raising loses nothing a caller cannot retry: `record_use`
        # runs once per created campaign and `record_reach` once per saved run, both already
        # wrapped by their own caller's error handling.
        raise RuntimeError(f"could not claim goal-stats lock for {tenant}/{field}/{goal}")
    try:
        row = await store.get(GOAL_STATS, tenant) or {"tenant": tenant, "uses": {}, "reach": {}}
        bucket = dict(row.get(field) or {})
        bucket[goal] = int(bucket.get(goal) or 0) + int(by)
        row["tenant"] = tenant
        row[field] = bucket
        await store.put(GOAL_STATS, tenant, row)
    finally:
        await store.delete(_MUTEX_COLLECTION, mutex_key)


async def record_use(store: Any, tenant: str, goal: str) -> None:
    """One more campaign launched under this goal."""
    await _bump(store, tenant, goal, "uses", 1)


async def record_reach(store: Any, tenant: str, goal: str, sent: int) -> None:
    """`sent` more customers actually reached, from one run of a campaign under this goal."""
    await _bump(store, tenant, goal, "reach", sent)


async def read_goal_stats(store: Any, tenant: str) -> dict[str, dict[str, int]]:
    """goal -> {"uses": int, "reach": int} — a single-key read, not a scan."""
    row = await store.get(GOAL_STATS, tenant)
    if not row:
        return {}
    uses = row.get("uses") or {}
    reach = row.get("reach") or {}
    out: dict[str, dict[str, int]] = {}
    for goal in set(uses) | set(reach):
        out[goal] = {"uses": int(uses.get(goal) or 0), "reach": int(reach.get(goal) or 0)}
    return out
