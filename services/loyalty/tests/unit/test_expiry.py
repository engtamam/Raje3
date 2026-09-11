"""Points that die — and the customer who never loses any."""
from __future__ import annotations

import asyncio

from app.adapters.cache.memory import MemoryCache
from app.adapters.datastore.memory import MemoryDataStore
from app.core.expiry import DAY, Expiry
from app.core.ledger import Ledger
from app.core.models import BALANCES, ENTRIES
from app.core.spend_lock import SpendLock

T = "shop"
S = "ref_abcdef123456"
NOW = 1_800_000_000


def run(c):
    return asyncio.run(c)


def build(days=365, warn=14, cache=None):
    store = MemoryDataStore()
    ledger = Ledger(store)
    return store, ledger, Expiry(store, ledger, days=days, warn_days=warn, cache=cache)


def earn(ledger, at, points=100, source="v1", subject=S):
    run(ledger.post(tenant=T, subject_ref=subject, delta=points, reason="earn",
                    source=source, now=at))


def test_a_subject_whose_spend_lock_is_held_is_skipped_this_pass_not_lost():
    """loyalty-004 (QA audit, 2026-09-12): the expiry writer used to call Ledger.post unlocked,
    racing a redemption/earn for the same subject holding SpendLock. A subject whose lock is
    already held right now must be skipped for this pass — not crash the sweep, and not expire
    the balance against a lock that says someone else is mid-write."""
    cache = MemoryCache()
    store, ledger, exp = build(cache=cache)
    earn(ledger, NOW - 400 * DAY)

    async def go():
        async with SpendLock(cache, T, S):   # simulates a redemption in flight right now
            return await exp.sweep(now=NOW)

    res = run(go())
    assert res["expired"] == 0
    # THE BALANCE IS UNTOUCHED — the busy skip must not have quietly zeroed it anyway.
    assert run(ledger.balance(T, S)).points == 100


def test_a_lapsed_balance_expires_and_says_so_in_the_ledger():
    """Never a silent zero: the owner asking where 100 points went must find a row that answers."""
    store, ledger, exp = build()
    earn(ledger, NOW - 400 * DAY)
    res = run(exp.sweep(now=NOW))
    assert res["expired"] == 1
    assert run(ledger.balance(T, S)).points == 0
    rows = [r for r in run(store.scan_all(ENTRIES, 100)) if r["reason"] == "expire"]
    assert len(rows) == 1 and rows[0]["delta"] == -100


def test_the_active_customer_never_loses_anything():
    """Every visit resets his whole clock — per-point expiry would read as theft."""
    _, ledger, exp = build()
    earn(ledger, NOW - 400 * DAY, source="old")
    earn(ledger, NOW - 10 * DAY, points=5, source="recent")
    assert run(exp.sweep(now=NOW))["expired"] == 0
    assert run(ledger.balance(T, S)).points == 105


def test_a_balance_inside_the_warning_window_is_reported_not_expired():
    _, ledger, exp = build()
    earn(ledger, NOW - 358 * DAY)
    res = run(exp.sweep(now=NOW))
    assert res["expired"] == 0 and len(res["to_warn"]) == 1
    assert res["to_warn"][0]["points"] == 100


def test_the_warning_goes_once_per_cycle():
    _, ledger, exp = build()
    earn(ledger, NOW - 358 * DAY)
    run(exp.mark_warned(T, S, NOW))
    assert run(exp.sweep(now=NOW))["to_warn"] == []


def test_coming_back_and_lapsing_again_earns_a_second_warning():
    _, ledger, exp = build()
    earn(ledger, NOW - 800 * DAY, source="a")
    run(exp.mark_warned(T, S, NOW - 700 * DAY))
    earn(ledger, NOW - 358 * DAY, points=5, source="b")   # a movement clears the flag
    assert len(run(exp.sweep(now=NOW))["to_warn"]) == 1


def test_the_sweep_runs_twice_in_a_day_and_expires_once():
    _, ledger, exp = build()
    earn(ledger, NOW - 400 * DAY)
    run(exp.sweep(now=NOW))
    earn(ledger, NOW - 400 * DAY, points=50, source="v2")  # a stale visit lands late
    second = run(exp.sweep(now=NOW + 60))
    # The day key means the second pass finds the same cause already posted.
    assert second["expired"] == 0


def test_expiry_switched_off_means_never():
    _, ledger, exp = build(days=0)
    earn(ledger, NOW - 5000 * DAY)
    assert run(exp.sweep(now=NOW))["expired"] == 0
    assert exp.due_at({"last_movement_at": NOW}) == 0


def test_a_zero_balance_is_skipped_entirely():
    store, ledger, exp = build()
    run(store.put(BALANCES, f"{T}|{S}", {"tenant": T, "subject_ref": S, "points": 0,
                                         "last_movement_at": NOW - 900 * DAY}))
    assert run(exp.sweep(now=NOW))["expired"] == 0


def test_the_sweep_is_bounded_and_says_when_more_remain():
    """A tenant with a hundred thousand customers must not turn one tick into a timeout loop."""
    _, ledger, exp = build()
    for i in range(6):
        earn(ledger, NOW - 400 * DAY, source=f"v{i}", subject=f"ref_person{i:08d}")
    res = run(exp.sweep(now=NOW, limit=3))
    assert res["seen"] == 3 and res["more"] is True
    assert run(exp.sweep(now=NOW, limit=100))["more"] is False


def test_one_tenants_sweep_leaves_another_alone():
    store, ledger, exp = build()
    run(ledger.post(tenant="a", subject_ref=S, delta=100, reason="earn", source="v1",
                    now=NOW - 400 * DAY))
    run(ledger.post(tenant="b", subject_ref=S, delta=100, reason="earn", source="v1",
                    now=NOW - 400 * DAY))
    run(exp.sweep(now=NOW, tenant="a"))
    assert run(ledger.balance("a", S)).points == 0
    assert run(ledger.balance("b", S)).points == 100
