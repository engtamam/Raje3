"""The catch-up read, and the moment it stopped catching up.

WHAT THIS IS FOR. The event bus is at-most-once by contract: a pod restarting through a delivery
never hears about that visit again. `/internal/operations/visits/since` is the safety net — the
bounded, ordered read a consumer uses to recover everything it missed. If it fails, customers are
never reminded, and nothing anywhere records that they were skipped.

HOW IT FAILED. It read ONE page of the tenant's visits and then filtered `created > since` in
memory. The datastore's `where` is equality only, so the filter cannot be a query — but the read
was still capped at one page. Once a shop passed that page size in LIFETIME visits, the first page
was entirely older than the watermark, the filtered result was empty, and the catch-up returned
«nothing new» for ever.

It fails silently, it fails permanently, and it fails FIRST for the busiest shops — the ones whose
missed reminders cost the most. That is the worst possible ordering.
"""
from __future__ import annotations

import time

INTERNAL = {"X-Internal-Token": "t" * 40}
PATH = "/internal/operations/visits/since"


def _seed(client, count: int, *, base: int, tenant: str) -> list[int]:
    """`count` visits with strictly increasing `created`, written straight to the store.

    A TENANT PER TEST. The datastore outlives a single test, so a shared one leaves the previous
    test's rows in the next one's answers — which is how a passing assertion can be about data
    nobody in this file wrote.
    """
    import asyncio

    from app.core.stores import VISITS

    ds = client.app.state.container.datastore
    stamps = [base + i for i in range(count)]

    async def go():
        for i, created in enumerate(stamps):
            await ds.put(VISITS, f"{tenant}|vis_{i:05d}", {
                "id": f"vis_{i:05d}", "tenant": tenant, "customer_id": f"cus_{i:05d}",
                "service_ids": ["svc_a"], "created": created, "occurred_at": created})

    asyncio.run(go())
    return stamps


def _since(client, since: int, limit: int = 10, *, tenant: str):
    return client.post(PATH, json={"tenant": tenant, "since": since, "limit": limit},
                       headers=INTERNAL).json()


def test_a_shop_past_the_page_size_still_gets_its_new_visits(client):
    """THE DEFECT ITSELF. Twenty-five visits, a page of ten, a watermark near the end: the fresh
    ones live beyond the first page and used to be invisible."""
    base = int(time.time()) - 10_000
    stamps = _seed(client, 25, base=base, tenant="tnt_pg_past_page")

    got = _since(client, since=stamps[21], limit=10, tenant="tnt_pg_past_page")

    assert got["count"] == 3, "the last three visits are newer than the watermark"
    assert [v["created"] for v in got["visits"]] == stamps[22:]


def test_the_watermark_advances_only_over_what_was_returned(client):
    """A cursor that runs ahead of the rows is the same as dropping them."""
    base = int(time.time()) - 20_000
    stamps = _seed(client, 25, base=base, tenant="tnt_pg_watermark")

    got = _since(client, since=stamps[21], limit=10, tenant="tnt_pg_watermark")

    assert got["watermark"] == stamps[-1]
    assert got["watermark"] == max(v["created"] for v in got["visits"])


def test_reading_from_zero_returns_a_full_page_and_says_there_is_more(client):
    base = int(time.time()) - 30_000
    _seed(client, 25, base=base, tenant="tnt_pg_full_page")

    got = _since(client, since=0, limit=10, tenant="tnt_pg_full_page")

    assert got["count"] == 10
    assert got["more"] is True, "a caller that cannot see there is more will stop early"


def test_the_answer_says_whether_it_is_the_whole_answer(client):
    """`exhaustive` is the difference between «nothing new» and «we could not read it all» — the
    three-state rule applied to a machine caller instead of a screen."""
    base = int(time.time()) - 40_000
    _seed(client, 5, base=base, tenant="tnt_pg_exhaustive")

    got = _since(client, since=0, limit=10, tenant="tnt_pg_exhaustive")

    assert got["exhaustive"] is True
    assert got["count"] == 5


def test_a_watermark_past_everything_returns_nothing_and_holds_its_place(client):
    base = int(time.time()) - 50_000
    stamps = _seed(client, 5, base=base, tenant="tnt_pg_at_end")

    got = _since(client, since=stamps[-1], limit=10, tenant="tnt_pg_at_end")

    assert got["count"] == 0
    assert got["watermark"] == stamps[-1], "an empty page must not move the cursor backwards"
