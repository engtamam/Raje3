"""The admin panel's cross-tenant rollup — aggregates already-computed snapshots, never raw
visits (see core/rollup.py's own module note)."""
from __future__ import annotations

import asyncio

from app.adapters.datastore.memory import MemoryDataStore
from app.core.models import PLATFORM_SUMMARY, SNAPSHOTS
from app.core.rollup import PlatformRollup

NOW = 1_800_000_000


def run(c):
    return asyncio.run(c)


async def _seed_snapshot(store, tenant, values):
    await store.put(SNAPSHOTS, f"{tenant}|_all", {"id": f"{tenant}|_all", "tenant": tenant,
                                                   "values": values, "computed_at": NOW})


def build_rollup():
    store = MemoryDataStore()
    return store, PlatformRollup(store, peers=None, batch=500)


def test_a_tenant_with_no_snapshot_is_skipped_not_failed():
    store, rollup = build_rollup()
    res = run(rollup.run(now=NOW, tenants=["ghost"]))
    assert res == {"tenants_seen": 1, "tenants_with_snapshot": 0, "more": False}
    row = run(store.get(PLATFORM_SUMMARY, "platform"))
    assert row["tenants_with_snapshot"] == 0


def test_return_rate_is_averaged_across_tenants_with_a_snapshot():
    store, rollup = build_rollup()

    async def go():
        await _seed_snapshot(store, "a", {"return_rate": 0.4})
        await _seed_snapshot(store, "b", {"return_rate": 0.6})
        return await rollup.run(now=NOW, tenants=["a", "b", "ghost"])

    res = run(go())
    assert res["tenants_seen"] == 3
    assert res["tenants_with_snapshot"] == 2
    row = run(store.get(PLATFORM_SUMMARY, "platform"))
    assert row["values"]["return_rate"] == 0.5


def test_peak_map_grids_are_summed_across_tenants():
    store, rollup = build_rollup()

    async def go():
        await _seed_snapshot(store, "a", {"peak_map": {"grid": {"0:9": 3, "1:10": 1}, "busiest": "0:9"}})
        await _seed_snapshot(store, "b", {"peak_map": {"grid": {"0:9": 2}, "busiest": "0:9"}})
        return await rollup.run(now=NOW, tenants=["a", "b"])

    run(go())
    row = run(store.get(PLATFORM_SUMMARY, "platform"))
    grid = row["values"]["peak_map"]["grid"]
    assert grid["0:9"] == 5 and grid["1:10"] == 1
    assert row["values"]["peak_map"]["busiest"] == "0:9"


def test_at_risk_tenant_count_counts_shops_not_customers():
    store, rollup = build_rollup()

    async def go():
        await _seed_snapshot(store, "a", {"at_risk": [{"subject_ref": "c1"}, {"subject_ref": "c2"}]})
        await _seed_snapshot(store, "b", {"at_risk": []})
        await _seed_snapshot(store, "c", {"at_risk": [{"subject_ref": "c3"}]})
        return await rollup.run(now=NOW, tenants=["a", "b", "c"])

    run(go())
    row = run(store.get(PLATFORM_SUMMARY, "platform"))
    # two SHOPS (a, c) have at-risk customers — not three customers.
    assert row["values"]["at_risk_tenant_count"] == 2


def test_retention_series_averages_pointwise_and_skips_learning_tenants():
    store, rollup = build_rollup()

    async def go():
        await _seed_snapshot(store, "a", {"retention_series": {
            "learning": False,
            "points": [{"at": 100, "value": 0.2}, {"at": 200, "value": 0.4}] + [{"at": 0, "value": None}] * 4,
        }})
        await _seed_snapshot(store, "b", {"retention_series": {
            "learning": False,
            "points": [{"at": 100, "value": 0.6}, {"at": 200, "value": None}] + [{"at": 0, "value": None}] * 4,
        }})
        await _seed_snapshot(store, "c", {"retention_series": {"learning": True, "points": []}})
        return await rollup.run(now=NOW, tenants=["a", "b", "c"])

    run(go())
    row = run(store.get(PLATFORM_SUMMARY, "platform"))
    series = row["values"]["retention_series"]
    assert series["learning"] is False
    # index 0: (0.2 + 0.6) / 2 = 0.4 — both tenants contributed
    assert series["points"][0]["value"] == 0.4
    # index 1: only tenant a had a real value (b's was None, c is learning) -> 0.4
    assert series["points"][1]["value"] == 0.4
    # index 2-5: nobody contributed -> None, a gap not a zero
    assert series["points"][2]["value"] is None


def test_every_tenant_still_learning_reports_the_platform_as_learning_too():
    store, rollup = build_rollup()

    async def go():
        await _seed_snapshot(store, "a", {"retention_series": {"learning": True, "points": []}})
        return await rollup.run(now=NOW, tenants=["a"])

    run(go())
    row = run(store.get(PLATFORM_SUMMARY, "platform"))
    assert row["values"]["retention_series"] == {"points": [], "learning": True}


def test_the_sweep_is_bounded_and_says_when_more_remain():
    store = MemoryDataStore()
    rollup = PlatformRollup(store, peers=None, batch=2)

    async def go():
        for t in ("a", "b", "c"):
            await _seed_snapshot(store, t, {"return_rate": 0.5})
        return await rollup.run(now=NOW, tenants=["a", "b", "c"])

    res = run(go())
    assert res["tenants_seen"] == 2
    assert res["more"] is True
