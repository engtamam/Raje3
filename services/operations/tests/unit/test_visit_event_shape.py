"""أ-8 · the event and the catch-up feed promise to be the same shape, and were not.

`/internal/operations/visits/since` carries `quantities` and says why in the file: «SAME NAME AS
THE EVENT, because loyalty's catch-up reads this row when the bus drops one — two spellings would
make a repaired visit earn differently from a live one». The event payload had no `quantities` at
all.

Nothing is broken by it TODAY, because insights reads the feed. That is exactly what makes it worth
closing now: the next consumer to subscribe to the event reads a basket with no quantities and
cannot tell one oil change from four, and the promise in the comment is what it will have trusted.
"""
from __future__ import annotations

import asyncio


class _Bus:
    def __init__(self):
        self.published = []

    async def publish(self, topic, event):
        self.published.append((topic, event))


def _emit(visit, customer):
    from app.core.seams import Seams

    bus = _Bus()

    class _Result:
        pass

    res = _Result()
    res.visit = visit
    res.customer = customer
    asyncio.run(Seams(events=bus)._emit_visit(res))
    return bus


def _rows():
    from app.core.models import Customer, Visit

    visit = Visit(id="vis_1", tenant="t1", customer_id="cus_1",
                  service_ids=["svc_oil", "svc_filter"],
                  quantities={"svc_oil": 4, "svc_filter": 1}, total_minor=48_000)
    customer = Customer(id="cus_1", tenant="t1", phone="0501234567", subject_ref="sub_a")
    return visit, customer


def test_the_event_carries_the_quantities_the_feed_carries():
    visit, customer = _rows()

    bus = _emit(visit, customer)

    assert bus.published, "the visit event is the seam every peer waits on"
    payload = bus.published[0][1].payload
    assert payload["quantities"] == {"svc_oil": 4, "svc_filter": 1}, (
        "a subscriber reading this basket cannot tell one oil change from four")


def test_a_visit_with_no_quantities_publishes_an_empty_map_and_not_a_missing_key():
    """The field screen knows the services and not how many of each, so empty is the ordinary
    case. A MISSING key and an empty one read the same to `.get()` and differently to anything
    that inspects the shape — and this event is the shape's only contract."""
    from app.core.models import Customer, Visit

    visit = Visit(id="vis_2", tenant="t1", customer_id="cus_1", service_ids=["svc_oil"])
    customer = Customer(id="cus_1", tenant="t1", phone="0501234567", subject_ref="sub_a")

    payload = _emit(visit, customer).published[0][1].payload

    assert payload["quantities"] == {}
