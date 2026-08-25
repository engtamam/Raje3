"""The platform-wide rollup — a cross-tenant summary FOR THE ADMIN PANEL, computed by a scheduled
pass and read as a plain stored row, never on a request path (spec: the admin plan's own phase
11.1-11.4).

WHY THIS IS A SEPARATE JOB FROM `Tick`, NOT A NEW INDICATOR INSIDE IT. `Tick.compute` reads one
tenant's own visits and writes one tenant's own snapshot — this reads MANY tenants' ALREADY-WRITTEN
snapshots and writes one platform-wide row. Folding it into `Tick.compute` would mean every single
tenant's own nightly pass also re-reads every OTHER tenant's snapshot, which is O(tenants²) for no
reason: the rollup only needs to run once per pass, after tick has updated what it can.

BOUNDED AND RESUMABLE, same shape as `Tick.run` — a tenant list capped at `batch`, one tenant's
missing/corrupt snapshot skipped rather than failing the pass (a stale rollup for everyone is worse
than a slightly incomplete one).

WHAT "AVERAGE" MEANS HERE. A platform of 3 tiny shops and 1 huge one is not summarized honestly by
weighting every tenant equally — but weighting by visit count would let one huge, unusual tenant's
own numbers pass as "the platform's own trend", which is worse for a company-wide decision. Every
average below is an unweighted mean across TENANTS, and `tenants_with_snapshot` travels with the
result so nobody reads a rollup off eleven shops as if it covered the platform's real size.
"""
from __future__ import annotations

from typing import Any

from app.core.models import PLATFORM_SUMMARY, SNAPSHOTS, PlatformSummary


class PlatformRollup:
    def __init__(self, store: Any, peers: Any, *, batch: int = 500) -> None:
        self.store = store
        self.peers = peers
        self.batch = batch

    async def run(self, *, now: int, tenants: list[str]) -> dict:
        seen = tenants[: self.batch]
        rows: list[dict[str, Any]] = []
        for tenant in seen:
            snap = await self.store.get(SNAPSHOTS, f"{tenant}|_all")
            if snap:
                rows.append(snap)
        summary = self._aggregate(rows, now=now, tenants_seen=len(seen))
        await self.store.put(PLATFORM_SUMMARY, "platform", summary.to_dict())
        return {"tenants_seen": summary.tenants_seen,
               "tenants_with_snapshot": summary.tenants_with_snapshot,
               "more": len(tenants) > self.batch}

    def _aggregate(self, rows: list[dict[str, Any]], *, now: int, tenants_seen: int) -> PlatformSummary:
        values: dict[str, Any] = {
            "return_rate": self._avg_return_rate(rows),
            "peak_map": self._merge_peak_map(rows),
            "at_risk_tenant_count": self._at_risk_tenant_count(rows),
            "retention_series": self._avg_retention_series(rows),
        }
        return PlatformSummary(values=values, computed_at=now, tenants_seen=tenants_seen,
                               tenants_with_snapshot=len(rows))

    @staticmethod
    def _avg_return_rate(rows: list[dict[str, Any]]) -> float | None:
        rates = [r.get("values", {}).get("return_rate") for r in rows]
        rates = [float(x) for x in rates if isinstance(x, (int, float))]
        if not rates:
            return None
        return round(sum(rates) / len(rates), 4)

    @staticmethod
    def _merge_peak_map(rows: list[dict[str, Any]]) -> dict[str, Any]:
        """The same «day:hour» → count grid `indicators.peak_map` returns, summed across every
        tenant that had one — a platform-wide busiest slot answers "when does the whole product
        get used", the operational question behind staffing support/on-call coverage."""
        grid: dict[str, int] = {}
        for r in rows:
            pm = r.get("values", {}).get("peak_map") or {}
            for slot, count in (pm.get("grid") or {}).items():
                grid[slot] = grid.get(slot, 0) + int(count)
        busiest = max(grid, key=grid.get) if grid else ""
        return {"grid": grid, "busiest": busiest}

    @staticmethod
    def _at_risk_tenant_count(rows: list[dict[str, Any]]) -> int:
        """How many SHOPS currently have at least one of THEIR OWN customers overdue for return
        (`indicators.at_risk` — a list of that shop's own lapsing customers, never about the shop's
        own subscription to us). A count of shops with churn signal in their own book, not a count
        of people."""
        return sum(1 for r in rows if r.get("values", {}).get("at_risk"))

    @staticmethod
    def _avg_retention_series(rows: list[dict[str, Any]]) -> dict[str, Any]:
        """A 6-point platform trend, averaged POSITION BY POSITION (same trailing-window index
        every tenant's own `retention_series` already aligns on — each point i is "i steps before
        now", computed independently per tenant but on the same step/window/points defaults, so
        index alignment is index alignment in real time too). A tenant still `learning` (too few
        of its own customers) contributes nothing at any index — it is not silently treated as a
        zero, which would read as "nobody came back" for a shop that simply has no answer yet."""
        per_index: list[list[float]] = [[] for _ in range(6)]
        ats: list[int | None] = [None] * 6
        for r in rows:
            series = r.get("values", {}).get("retention_series") or {}
            if series.get("learning"):
                continue
            points = series.get("points") or []
            for i, p in enumerate(points[:6]):
                if p.get("value") is not None:
                    per_index[i].append(float(p["value"]))
                if ats[i] is None and p.get("at") is not None:
                    ats[i] = int(p["at"])

        drawn = [round(sum(vals) / len(vals), 4) if vals else None for vals in per_index]
        if all(v is None for v in drawn):
            return {"points": [], "learning": True}
        points = [{"at": ats[i], "value": drawn[i]} for i in range(6)]
        first = next((v for v in drawn if v is not None), None)
        last = next((v for v in reversed(drawn) if v is not None), None)
        delta = round(last - first, 4) if first is not None and last is not None else None
        return {"points": points, "learning": False, "first": first, "last": last, "delta": delta}
