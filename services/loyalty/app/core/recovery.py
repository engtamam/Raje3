"""The path from a visit to points that does not depend on an event arriving.

WHY THIS EXISTS. `operations` publishes `operations.visit.recorded` and this service subscribes —
the fast path, and the only one there was. But the bus is AT-MOST-ONCE by contract: a pod that is
restarting, rolling out, or briefly disconnected does not receive the event, and nothing anywhere
records that it missed one. For a reminder that is a delay; for a POINT it is a customer whose
visit never earned him anything, permanently, while his balance sits there looking perfectly
correct — and the first person to notice is the customer, at the counter, holding fewer points than
he counted on.

`Earner.catch_up` was written for exactly this and HAD NO CALLER. The config key naming the route
existed too, and nothing read it. So the service's own comment («the bus is the fast path, not the
reliable one») described a mechanism that was never built.

THE CURSOR MOVES ONLY HERE, and never on the event. The reminder engine learned this the hard way:
advancing on a delivered event moves the cursor past the visit the bus DROPPED, which blinds the
recovery to the very thing it exists to recover. An event is a hint; this read is the record.

AND AN UNREADABLE PEER DOES NOT ADVANCE ANYTHING. `{}` from the reader means «we could not ask»,
which is not «no visits» — treating them alike would skip a window nobody can ever go back to.
"""
from __future__ import annotations

from typing import Any

WATERMARKS = "loyalty_watermarks"


class Recovery:
    """`run(tenant)` — award points for visits the event never brought."""

    def __init__(self, *, store: Any, earner: Any, feed: Any, telemetry: Any = None,
                 max_batches: int = 5) -> None:
        self._store = store
        self._earner = earner
        self._feed = feed
        self._t = telemetry
        # BOUNDED. A recovery pass is a repair that runs again in minutes, and progress beats
        # completeness on a repair path — an unbounded loop on a shop with a decade of history
        # would turn a cron into an outage.
        self._max_batches = max(1, int(max_batches))

    async def _mark(self, tenant: str) -> int:
        row = await self._store.get(WATERMARKS, f"{tenant}|visits")
        return int((row or {}).get("mark") or 0)

    async def _advance(self, tenant: str, mark: int) -> None:
        await self._store.put(WATERMARKS, f"{tenant}|visits",
                              {"id": f"{tenant}|visits", "tenant": tenant, "mark": int(mark)})

    async def run(self, tenant: str) -> dict[str, int | bool]:
        if self._feed is None or not getattr(self._feed, "configured", False):
            # NOT CONFIGURED IS SAID OUT LOUD. Returning zeros with no reason would read as «every
            # visit is accounted for», which is the silent-success shape this whole file answers.
            return {"read": 0, "awarded": 0, "batches": 0, "configured": False}

        mark = await self._mark(tenant)
        read = awarded = batches = 0
        while batches < self._max_batches:
            page = await self._feed.since(tenant, mark)
            if not page:
                # UNREADABLE. The cursor stays exactly where it was, so the window is re-read on
                # the next pass rather than skipped for ever.
                return {"read": read, "awarded": awarded, "batches": batches,
                        "configured": True, "unreadable": True}
            visits = list(page.get("visits") or [])
            if not visits:
                break
            out = await self._earner.catch_up(tenant, visits)
            read += len(visits)
            awarded += int(out.get("awarded") or 0)
            # ADVANCED AFTER THE AWARD, NEVER BEFORE. A crash mid-batch must re-read those visits;
            # `Ledger` refuses a second entry from the same visit id, so a re-read costs nothing
            # and a skipped one costs a customer his points.
            mark = int(page.get("watermark") or mark)
            await self._advance(tenant, mark)
            batches += 1
            if not page.get("more"):
                break

        if self._t is not None:
            self._t.event("loyalty_recovery", tenant=tenant, read=read, awarded=awarded)
        return {"read": read, "awarded": awarded, "batches": batches, "configured": True}
