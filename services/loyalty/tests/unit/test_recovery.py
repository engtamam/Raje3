"""Points for the visits the event never brought.

WHY IT MATTERS MORE HERE THAN ANYWHERE. A missed reminder is late; a missed POINT is a customer
standing at a counter holding fewer points than he counted on, told by a screen that his balance is
correct. Nothing anywhere says a visit was skipped — the bus is at-most-once and forgets in silence.

`Earner.catch_up` was written for this and HAD NO CALLER, and the config key naming the read existed
and nothing read it. The service's own comment said the bus was «the fast path, not the reliable
one». There was no other path.
"""
from __future__ import annotations

import asyncio

from app.core.recovery import WATERMARKS, Recovery


def run(c):
    return asyncio.run(c)


class Store:
    def __init__(self):
        self.rows = {}

    async def get(self, coll, key):
        return self.rows.get(key)

    async def put(self, coll, key, row):
        self.rows[key] = row
        return row


class Earner:
    def __init__(self):
        self.seen = []

    async def catch_up(self, tenant, visits, tree=None):
        self.seen.extend(v.get("visit_id") for v in visits)
        return {"awarded": len(visits), "skipped": 0}


class Feed:
    """Pages of visits, or `{}` for «we could not ask»."""

    configured = True

    def __init__(self, pages):
        self._pages = list(pages)
        self.asked = []

    async def since(self, tenant, mark):
        self.asked.append((tenant, mark))
        return self._pages.pop(0) if self._pages else {"visits": [], "watermark": mark}


def test_it_awards_points_for_a_visit_the_bus_dropped():
    """THE DEFECT ITSELF: this path did not exist, so a dropped event was a point never given."""
    store, earner = Store(), Earner()
    feed = Feed([{"visits": [{"visit_id": "A"}], "watermark": 100, "more": False}])

    out = run(Recovery(store=store, earner=earner, feed=feed).run("t1"))

    assert earner.seen == ["A"]
    assert out["awarded"] == 1


def test_the_cursor_advances_only_after_the_award():
    """A crash between the read and the award must re-read those visits. The ledger refuses a
    second entry from the same visit, so a re-read costs nothing and a skip costs a customer."""
    store, earner = Store(), Earner()
    feed = Feed([{"visits": [{"visit_id": "A"}], "watermark": 250, "more": False}])

    run(Recovery(store=store, earner=earner, feed=feed).run("t1"))

    assert int(store.rows[f"t1|visits"]["mark"]) == 250


def test_an_unreadable_peer_does_not_move_the_cursor():
    """«We could not ask» is not «there was nothing». Advancing on it would skip a window nobody
    can ever go back to — the same failure the reminder engine had, in a different service."""
    store, earner = Store(), Earner()
    run(Recovery(store=store, earner=earner, feed=Feed([{}])).run("t1"))

    assert store.rows.get("t1|visits") is None
    assert earner.seen == []


def test_it_reports_that_it_could_not_ask(caplog=None):
    store, earner = Store(), Earner()
    out = run(Recovery(store=store, earner=earner, feed=Feed([{}])).run("t1"))

    assert out["unreadable"] is True, "a pass that read nothing must not look like a clean fleet"


def test_an_unconfigured_deployment_says_so_rather_than_reporting_zero():
    store, earner = Store(), Earner()

    class Off:
        configured = False

        async def since(self, tenant, mark):
            return {}

    out = run(Recovery(store=store, earner=earner, feed=Off()).run("t1"))

    assert out["configured"] is False
    assert out["awarded"] == 0


def test_it_resumes_from_where_it_stopped():
    store, earner = Store(), Earner()
    feed = Feed([{"visits": [{"visit_id": "A"}], "watermark": 10, "more": True},
                 {"visits": [{"visit_id": "B"}], "watermark": 20, "more": False}])

    run(Recovery(store=store, earner=earner, feed=feed).run("t1"))

    assert earner.seen == ["A", "B"]
    assert feed.asked == [("t1", 0), ("t1", 10)], "the second page must ask from the first's mark"


def test_a_pass_is_bounded():
    """A repair runs again in minutes; an unbounded loop on a decade of history turns a cron into
    an outage."""
    store, earner = Store(), Earner()
    endless = [{"visits": [{"visit_id": str(i)}], "watermark": i, "more": True}
               for i in range(1, 50)]

    out = run(Recovery(store=store, earner=earner, feed=Feed(endless), max_batches=3).run("t1"))

    assert out["batches"] == 3
