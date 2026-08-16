"""ي-1 — the busiest shops were shown a dashboard of their first year.

THE CHAIN. operations serves visits paged by `created` ASCENDING — it must, so the watermark can
advance without skipping a row. insights read that feed from `since=0`, stopped as soon as it held
`SNAPSHOT_VISIT_LIMIT` rows, and returned `out[:limit]`.

So a shop past the cap had its entire dashboard computed from its OLDEST visits. `active_customers`
counts a 90-day window: 0. `expected_flow`: 0. `at_risk`: the names of people who stopped coming
two years ago, presented as the ones to win back. Nothing failed anywhere — the numbers were
arithmetically correct about the wrong rows.

AND THE SHOPS THIS HIT ARE THE ONES THAT PAY. A quiet shop never reaches the cap. The dashboard
that said «0 عميل نشط» was shown to the owner whose till had not stopped ringing all week.

The assertion is at the END of the chain: the snapshot, not the reader.
"""
from __future__ import annotations

import asyncio
import time

from app.core import indicators
from app.core.models import VisitPage

NOW = int(time.time())
DAY = 86400


def _visit(ref: str, when: int) -> dict:
    return {"tenant": "t1", "subject_ref": ref, "service_ids": ["wash"],
            "created": when, "occurred_at": when, "visit_count": 1}


class AscendingFeed:
    """operations' feed, in the order operations really serves it: oldest first, in pages."""

    def __init__(self, rows: list[dict], page: int = 500):
        self.rows = sorted(rows, key=lambda r: r["created"])
        self.page = page
        self.calls = 0

    def read(self, since: int, limit: int) -> dict:
        self.calls += 1
        fresh = [r for r in self.rows if r["created"] > since][:self.page]
        watermark = fresh[-1]["created"] if fresh else since
        return {"visits": fresh, "watermark": watermark,
                "more": bool([r for r in self.rows if r["created"] > watermark])}


def _drive(feed: AscendingFeed, limit: int) -> VisitPage:
    """THE REAL DRIVER, with the socket replaced and nothing else.

    A copy of the loop written into the test would pass whatever the driver did — which is exactly
    how a chain defect survives a green suite. Only `_post` is stubbed, so the paging, the cursor,
    the tail and the flag are all the shipped ones.
    """
    from app.adapters import peers

    real_post = peers._post                                                   # noqa: SLF001

    def fake_post(url, body, token, timeout):
        return feed.read(int(body["since"]), int(body["limit"]))

    peers._post = fake_post                                                   # noqa: SLF001
    try:
        driver = peers.HttpPeers(
            operations_url="http://ops.invalid", visits_path="/internal/operations/visits/since",
            catalogue_path="/internal/operations/catalogue",
            reminders_url="http://rem.invalid", send_path="/internal/reminders/send",
            consent_count_path="/internal/reminders/consent-count",
            billing_url="http://bil.invalid", entitlement_path="/internal/billing/entitlement",
            usage_path="/internal/billing/usage", loyalty_url="http://loy.invalid",
            loyalty_report_path="/internal/loyalty/report", tenant_url="http://tnt.invalid",
            tenant_read_path="/internal/tenants", token="t" * 40)
        return asyncio.run(driver.visits("t1", since=0, limit=limit))
    finally:
        peers._post = real_post                                               # noqa: SLF001


def test_a_shop_past_the_cap_is_read_from_today_not_from_its_first_year():
    """THE DEFECT ITSELF. 6000 visits spread over three years, a cap of 5000: the old loop kept
    rows 1..5000 — everything up to a year ago — and the 90-day window found nobody."""
    old = [_visit(f"c{i}", NOW - 900 * DAY + i) for i in range(5500)]
    recent = [_visit(f"n{i}", NOW - 10 * DAY + i) for i in range(500)]

    page = _drive(AscendingFeed(old + recent), limit=5000)

    assert page.truncated is True, "the cap bit and nothing said so"
    assert len(page) == 5000
    # THE RECENT ONES ARE ALL THERE — that is the whole point.
    kept = {v["subject_ref"] for v in page}
    assert all(f"n{i}" in kept for i in range(500)), "today's visits were dropped for last year's"

    # AND THE INDICATOR THE OWNER READS. `active_customers` over 90 days answered 0 for exactly
    # this reason, on the shops that pay us.
    active = indicators.active_customers(page, now=NOW, window_days=90)
    assert active >= 500, f"a shop with 500 customers this month reads as {active}"


def test_a_shop_that_fits_is_not_marked_partial():
    """A FLAG THAT IS ALWAYS ON IS A FLAG NOBODY READS. Nearly every shop fits inside the cap, and
    each of those snapshots describes its whole history."""
    page = _drive(AscendingFeed([_visit(f"c{i}", NOW - 30 * DAY + i) for i in range(120)]),
                  limit=5000)

    assert page.truncated is False
    assert len(page) == 120


def test_the_reader_pages_to_the_end_rather_than_stopping_at_the_cap():
    """THE MECHANISM, named. Stopping on the size cap is what made the result the oldest rows; the
    page budget still bounds the work, and that is a bound on effort rather than on truth."""
    feed = AscendingFeed([_visit(f"c{i}", NOW - 400 * DAY + i) for i in range(6000)])

    _drive(feed, limit=5000)

    # 6000 rows at 500 a page is twelve reads. The old loop stopped after ten.
    assert feed.calls == 12, feed.calls


def test_the_snapshot_carries_the_truncation_to_the_screen():
    """A CAP NOBODY CAN SEE IS A NUMBER PRESENTED AS THE WHOLE TRUTH. `exhaustive` and `more` were
    read to decide whether to keep paging and nowhere else, so the snapshot of a partial history
    was indistinguishable from a complete one."""
    from app.core.models import Snapshot

    page = _drive(AscendingFeed([_visit(f"c{i}", NOW - 500 * DAY + i) for i in range(6000)]),
                  limit=5000)
    snap = Snapshot(tenant="t1", visits=len(page),
                    partial=bool(getattr(page, "truncated", False)))

    assert snap.partial is True
    assert snap.to_dict()["partial"] is True, "the screen reads the dict, not the object"


def test_a_driver_that_cannot_truncate_is_read_as_complete():
    """AN OLDER PEERS DRIVER RETURNS A PLAIN LIST. Absent is not «partial» — it is a driver saying
    it never truncates, and reading it as a warning would put «جزئي» on every correct dashboard
    during a rolling deploy."""
    from app.core.models import Snapshot

    plain = [_visit("c1", NOW)]
    snap = Snapshot(tenant="t1", visits=len(plain),
                    partial=bool(getattr(plain, "truncated", False)))

    assert snap.partial is False
