"""Is the link alive — and the three answers that are three different phone calls.

THE OUTAGE THIS EXISTS FOR IS SILENT ON BOTH SIDES. A shop whose point-of-sale stops posting
believes its visits are recorded; we believe the partner is healthy, because every screen we own
describes what arrived rather than what stopped arriving. The first evidence is an owner asking
months later why nobody was reminded — and the visits are gone by then, because a till that could
not post did not keep them.
"""
from __future__ import annotations

import asyncio

from app.core.till_health import TILL_HEALTH, TillHealth


class _Store:
    def __init__(self) -> None:
        self.rows: dict[tuple[str, str], dict] = {}

    async def put(self, collection, key, row):
        self.rows[(collection, key)] = row

    async def get(self, collection, key):
        return self.rows.get((collection, key))


DAY = 86_400


def test_a_shop_that_never_sent_anything_still_appears():
    """THE ABSENT ROW IS THE FINDING. A list built from what exists shows only the shops that are
    working — and the shop enrolled three weeks ago whose vendor never finished has no row at all,
    which is exactly the one somebody must call."""
    rows = asyncio.run(TillHealth(_Store()).for_tenants(["t_new"], now=1_000_000))
    assert rows == [{"tenant": "t_new", "state": "never", "last_at": 0,
                     "accepted": 0, "rejected": 0}]


def test_a_link_that_worked_and_stopped_is_told_apart_from_one_that_never_started():
    """Different faults, different calls: chase the vendor's integration, or chase the shop's
    connection. One health light for both is a shrug."""
    store = _Store()
    health = TillHealth(store)
    asyncio.run(health.record("t_old", accepted=3, rejected=0, now=1_000_000))
    rows = asyncio.run(health.for_tenants(["t_old", "t_new"],
                                          now=1_000_000 + 30 * DAY, quiet_days=7))
    states = {r["tenant"]: r["state"] for r in rows}
    assert states == {"t_old": "quiet", "t_new": "never"}


def test_a_shop_that_sent_today_is_sending():
    store = _Store()
    health = TillHealth(store)
    asyncio.run(health.record("t_a", accepted=2, rejected=0, now=1_000_000))
    rows = asyncio.run(health.for_tenants(["t_a"], now=1_000_000 + DAY, quiet_days=7))
    assert rows[0]["state"] == "sending" and rows[0]["accepted"] == 2


def test_rejections_still_count_as_a_live_link():
    """A till posting nothing but rejections is CONNECTED — the fault is a mapping bug, not a dead
    line, and treating it as an outage sends somebody to check a network that is fine."""
    store = _Store()
    health = TillHealth(store)
    asyncio.run(health.record("t_a", accepted=0, rejected=5,
                              reason="select at least one service", now=1_000_000))
    rows = asyncio.run(health.for_tenants(["t_a"], now=1_000_000 + DAY))
    assert rows[0]["state"] == "sending"
    assert rows[0]["rejected"] == 5
    assert rows[0]["last_reason"] == "select at least one service"
    # AND THE DIFFERENCE IS READABLE: it is connected, and nothing it sends is landing.
    assert rows[0]["last_accepted_at"] == 0


def test_counters_accumulate_across_batches():
    store = _Store()
    health = TillHealth(store)
    asyncio.run(health.record("t_a", accepted=2, rejected=1, now=1_000))
    asyncio.run(health.record("t_a", accepted=3, rejected=0, duplicate=4, now=2_000))
    row = asyncio.run(health.get("t_a"))
    assert (row["accepted"], row["rejected"], row["duplicate"]) == (5, 1, 4)
    assert row["first_at"] == 1_000 and row["last_at"] == 2_000


def test_only_the_most_recent_reason_is_kept():
    """A list would grow without bound on a broken integration, and the newest is the one somebody
    debugs against."""
    store = _Store()
    health = TillHealth(store)
    asyncio.run(health.record("t_a", accepted=0, rejected=1, reason="أول سبب", now=1_000))
    asyncio.run(health.record("t_a", accepted=0, rejected=1, reason="آخر سبب", now=2_000))
    assert asyncio.run(health.get("t_a"))["last_reason"] == "آخر سبب"


def test_a_batch_with_no_tenant_writes_nothing():
    """A row keyed by an empty string would be one bucket every unattributed batch shares."""
    store = _Store()
    asyncio.run(TillHealth(store).record("", accepted=1, rejected=0))
    assert not [k for k in store.rows if k[0] == TILL_HEALTH]
