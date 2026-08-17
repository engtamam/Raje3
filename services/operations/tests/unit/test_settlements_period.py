"""The period bound as billing-service actually reads it — a string, never an epoch.

THE DEFECT THIS LOCKS DOWN PAID EVERY PARTNER ZERO, EVERY MONTH, WITHOUT AN ERROR.

`for_period` was handed epochs by `statements_run` and passed them straight into the query.
`billing_service.browse_platform` filters with `created > until` / `created < since`, where
`created` is ISO-8601 TEXT. Comparing "2026-06-15T09:00:00Z" against "1780272000" is lexicographic
and decides on the first character — '2' > '1' — so every real invoice read as newer than the
window and was skipped. The map came back empty, every partner settled at zero, and a statement
for 0.00 SAR looks exactly like an honest statement for a partner who earned nothing.

So the test asserts the WIRE, not the return value. A test that only checked `for_period`'s output
would have passed against a stub that ignores the bounds entirely — which is precisely the shape
of the bug: both ends were individually reasonable and nobody looked at the thing in between.
"""
from __future__ import annotations

import asyncio
import calendar

from app.adapters.settlements import SettlementsSource, platform_instant

JUNE_START = calendar.timegm((2026, 6, 1, 0, 0, 0))
JUNE_END = calendar.timegm((2026, 6, 30, 23, 59, 59))


def test_the_bound_is_the_shape_billing_compares_against() -> None:
    """An ISO instant, so a string comparison against `created` orders correctly."""
    bound = platform_instant(JUNE_START)
    assert bound == "2026-06-01T00:00:00Z"

    # THE COMPARISON BILLING ACTUALLY PERFORMS, spelled out. This is the assertion that fails the
    # moment somebody sends an epoch again: an invoice inside the window must NOT read as outside
    # it. With "1780272000" as the bound this is False, and the row is dropped.
    created = "2026-06-15T09:00:00Z"
    assert not created > platform_instant(JUNE_END)
    assert not created < platform_instant(JUNE_START)


def test_an_epoch_bound_would_have_skipped_every_row() -> None:
    """The failure itself, asserted — so nobody re-derives «it looked fine» from a green suite."""
    created = "2026-06-15T09:00:00Z"
    # This is what the code used to send. `'2' > '1'`, so the row reads as newer than the window's
    # end and `browse_platform` skips it — and it skips EVERY row, because they all start with '2'.
    assert created > str(JUNE_END)


def test_the_query_carries_strings(monkeypatch) -> None:
    """End of the chain: what leaves this process for billing."""
    seen: list[str] = []

    src = SettlementsSource(billing_url="http://billing:8000", identity_url="http://identity:8000",
                            client_id="x", client_secret="y")

    # No token round trip, no HTTP — the seam under test is the URL, so stub either side of it.
    monkeypatch.setattr(SettlementsSource, "_mint", lambda self: "tok")

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        @staticmethod
        def read():
            return b'{"invoices": []}'

    def _urlopen(req, timeout=0):
        seen.append(req.full_url)
        return _Resp()

    monkeypatch.setattr("urllib.request.urlopen", _urlopen)

    asyncio.run(src.for_period(period_start=JUNE_START, period_end=JUNE_END))

    assert seen, "nothing was requested — the test proved nothing"
    for url in seen:
        assert "since=2026-06-01T00%3A00%3A00Z" in url, url
        assert "until=2026-06-30T23%3A59%3A59Z" in url, url
        # The old shape, named so the failure message says what went wrong rather than «not in».
        assert f"since={JUNE_START}" not in url, "an epoch bound reached billing again"
