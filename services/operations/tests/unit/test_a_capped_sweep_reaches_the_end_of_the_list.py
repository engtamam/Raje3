"""A capped hourly sweep must reach the shops at the END of the list, not only the head.

WHAT THIS IS WRITTEN AFTER. `live_tenants` answered with `sort=("at", "desc")` and a cap — newest
connections first, the same order every hour. Two hourly jobs read it: `template-approvals` and
`template-publish`. Neither is given unlimited time; the CronJob's window closes and whatever the
pass had not reached is simply not done. Next hour it started again from the same head.

`publish` costs 67 peer calls per shop — 66 templates plus a drain — so a handful of shops fill a
window on their own. What that costs the shop at the tail is not lateness: no template of its
library is ever registered, so none is ever approved, so the send path (which correctly refuses an
unapproved template) refuses everything it will ever be asked to send. «مربوط» in green, and not one
message, for ever, with nothing logged as broken.

THE ASSERTION IS THE ROTATION, NOT THE ORDER. Testing «the oldest is first» would pass on any
sorted list; what must be true is that two consecutive passes do DIFFERENT work, and that after
enough passes every shop has been reached. Both are checked below.
"""
from __future__ import annotations

import asyncio

from app.core import connect

CONNECTIONS = connect.CONNECTIONS
SWEEP_MARKS = connect.SWEEP_MARKS


def run(c):
    return asyncio.run(c)


class Store:
    """Keyed by collection — which the sweep now genuinely needs.

    The marks live in their own collection precisely so a connection row is never rewritten to
    carry a sweep's bookkeeping, and a fake that flattened both into one dict would hide exactly
    the mistake that separation prevents.
    """

    def __init__(self, rows=None):
        self.rows: dict[str, dict[str, dict]] = {}
        for (coll, key), row in (rows or {}).items():
            self.rows.setdefault(coll, {})[key] = row

    async def put(self, coll, key, row):
        self.rows.setdefault(coll, {})[key] = row
        return row

    async def get(self, coll, key):
        return self.rows.get(coll, {}).get(key)

    async def find(self, coll, where, **kw):
        rows = [r for r in self.rows.get(coll, {}).values()
                if all(r.get(k) == v for k, v in where.items())]
        field, direction = kw.get("sort", ("at", "desc"))
        rows.sort(key=lambda r: r.get(field) or 0, reverse=(direction == "desc"))
        return rows[:kw.get("limit", 100)], None


def a_fleet(n: int) -> Store:
    """`n` connected shops, each connecting one second after the last."""
    return Store({(CONNECTIONS, f"t{i}"): {"id": f"t{i}", "tenant": f"t{i}",
                                           "state": connect.STATE_CONNECTED, "at": 1000 + i}
                  for i in range(n)})


def test_two_consecutive_passes_do_not_repeat_the_same_shops():
    store = a_fleet(10)
    s = connect.ConnectionStore(store)

    first = run(s.live_tenants(limit=3, sweep="template-publish"))
    for i, tenant in enumerate(first):
        run(s.mark_swept("template-publish", tenant, 5000 + i))

    second = run(s.live_tenants(limit=3, sweep="template-publish"))
    assert len(first) == 3 and len(second) == 3
    # THE WHOLE POINT. Before the rotation these were byte for byte identical, hour after hour.
    assert not (set(first) & set(second)), (first, second)


def test_every_shop_is_reached_within_a_bounded_number_of_passes():
    store = a_fleet(10)
    s = connect.ConnectionStore(store)
    seen: set[str] = set()
    at = 5000
    # TEN SHOPS, THREE PER PASS: four passes must cover the fleet. Not «eventually» — bounded.
    for _ in range(4):
        for tenant in run(s.live_tenants(limit=3, sweep="template-publish")):
            seen.add(tenant)
            at += 1
            run(s.mark_swept("template-publish", tenant, at))
    assert seen == {f"t{i}" for i in range(10)}, sorted(seen)


def test_a_shop_that_fails_every_time_does_not_hold_the_front_of_the_queue():
    """The starvation one layer down, and the reason the mark is written even on failure.

    A shop whose publish fails would otherwise keep its place at the head for ever — it is always
    the least-recently-SUCCEEDED — and every shop behind it would starve on its behalf. Marking on
    the attempt costs a failing shop nothing it can feel: it is retried on the next full rotation,
    and its failure is reported.
    """
    store = a_fleet(4)
    s = connect.ConnectionStore(store)
    first = run(s.live_tenants(limit=1, sweep="template-approvals"))
    run(s.mark_swept("template-approvals", first[0], 6000))     # it failed; it is still marked
    second = run(s.live_tenants(limit=1, sweep="template-approvals"))
    assert second != first


def test_the_two_passes_keep_their_own_place_in_the_queue():
    """One cursor each. The cheap pass must not drag the expensive one past shops it never did."""
    store = a_fleet(4)
    s = connect.ConnectionStore(store)
    done_by_approvals = run(s.live_tenants(limit=2, sweep="template-approvals"))
    for t in done_by_approvals:
        run(s.mark_swept("template-approvals", t, 7000))
    # publish has done nothing, so its queue is untouched by the other pass's progress.
    assert run(s.live_tenants(limit=2, sweep="template-publish")) == done_by_approvals


def test_without_a_sweep_name_the_order_is_the_old_one():
    """Callers that are not sweeps — and there are some — keep newest-first, unchanged."""
    store = a_fleet(3)
    s = connect.ConnectionStore(store)
    assert run(s.live_tenants(limit=3)) == ["t2", "t1", "t0"]
