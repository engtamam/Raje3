"""Is the till link alive? — one row per establishment, written as the sales arrive.

THE OUTAGE THIS MAKES VISIBLE IS SILENT ON BOTH SIDES. A shop whose point-of-sale stopped posting
believes its visits are being recorded; we believe the partner is healthy, because every screen we
own describes what we HAVE rather than what stopped coming. Nothing errors. The first evidence is
an owner asking months later why his customers were never reminded — by which time the visits are
gone, since a till that failed to post does not keep them.

SO THE ROW IS WRITTEN ON THE HOT PATH and read from a panel, never computed by scanning visits.
Counting a tenant's visits to answer "did anything arrive today" is a whole-collection read per
shop per screen refresh; a counter costs one write per batch, which is one write per sale-burst.

WHAT IT DELIBERATELY IS NOT: an uptime metric. It answers three questions a human acts on — has
this shop ever sent anything, when did it last send, and what is it being refused for — and each
one has a different response: chase the vendor's integration, chase the shop's connection, fix a
mapping bug. A single "healthy/unhealthy" light would collapse all three into a shrug.
"""
from __future__ import annotations

import time
from typing import Any

TILL_HEALTH = "till_health"


class TillHealth:
    def __init__(self, store) -> None:
        self._s = store

    async def record(self, tenant: str, *, accepted: int, rejected: int, duplicate: int = 0,
                     reason: str = "", now: int | None = None) -> None:
        """Note one batch's outcome. Cheap, and never allowed to fail the sale it describes."""
        if not tenant:
            return
        ts = int(now if now is not None else time.time())
        row = await self._s.get(TILL_HEALTH, tenant) or {
            "tenant": tenant, "first_at": ts, "accepted": 0, "rejected": 0, "duplicate": 0}
        row["accepted"] = int(row.get("accepted", 0)) + max(0, accepted)
        row["rejected"] = int(row.get("rejected", 0)) + max(0, rejected)
        row["duplicate"] = int(row.get("duplicate", 0)) + max(0, duplicate)
        # LAST HEARD FROM, whatever the verdict. A till posting nothing but rejections is still
        # connected — the fault is a mapping, not a link, and telling them apart is the point.
        row["last_at"] = ts
        if accepted:
            row["last_accepted_at"] = ts
        if reason:
            # ONE REASON, THE MOST RECENT. A list would grow without bound on a broken integration
            # and the newest is the one somebody debugs against.
            row["last_reason"] = reason[:200]
            row["last_reason_at"] = ts
        await self._s.put(TILL_HEALTH, tenant, row)

    async def get(self, tenant: str) -> dict[str, Any] | None:
        return await self._s.get(TILL_HEALTH, tenant)

    async def for_tenants(self, tenants: list[str], *, now: int | None = None,
                          quiet_days: int = 7) -> list[dict[str, Any]]:
        """One line per shop, INCLUDING the shops that never sent anything.

        THE ABSENT ROWS ARE THE FINDING. A list built from what exists shows only shops that are
        working; the shop enrolled three weeks ago whose vendor never finished the integration has
        no row at all, and it is exactly the one somebody needs to call.
        """
        ts = int(now if now is not None else time.time())
        quiet_before = ts - quiet_days * 86_400
        out: list[dict[str, Any]] = []
        for tenant in tenants:
            row = await self._s.get(TILL_HEALTH, tenant)
            if row is None:
                out.append({"tenant": tenant, "state": "never", "last_at": 0,
                            "accepted": 0, "rejected": 0})
                continue
            last = int(row.get("last_at", 0))
            out.append({
                "tenant": tenant,
                # THREE STATES, THREE DIFFERENT PHONE CALLS: nobody ever integrated, it stopped, or
                # it is running. Collapsing them would make the list unactionable.
                "state": "quiet" if last < quiet_before else "sending",
                "last_at": last,
                "last_accepted_at": int(row.get("last_accepted_at", 0)),
                "accepted": int(row.get("accepted", 0)),
                "rejected": int(row.get("rejected", 0)),
                "duplicate": int(row.get("duplicate", 0)),
                "last_reason": row.get("last_reason", ""),
            })
        return out
