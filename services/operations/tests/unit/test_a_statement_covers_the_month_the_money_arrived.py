"""ح-4 — the same month produced two different statements depending on the day it was run.

`billing.browse_platform` says it plainly: `since`/`until` bound the ISSUE date. The commission
engine says the opposite, at length: commission is on money that ARRIVED. Nothing sat between the
two claims, so an invoice issued 29 June and paid 4 July fell out of both months a partner could
recognise:

    June's statement, run 1 July   ->  the invoice is not `paid` yet    ->  0.00 SAR
    June re-run in September       ->  it is `paid` now, and it was ISSUED in June  ->  74.75 SAR

The second number is not a correction — it is a different answer to the same question, and which
one the partner keeps depends on the day somebody pressed the button, because `save()` refuses to
overwrite a statement that has already been issued.

THE FIX IS THE WINDOW, NOT THE ARITHMETIC. We read wider by issue date and narrow by `paid_at`,
which billing has been projecting all along.
"""
from __future__ import annotations

import asyncio

from app.adapters.settlements import LOOKBACK_SECONDS, SettlementsSource, paid_instant

JUNE_START = 1_780_272_000        # 2026-06-01T00:00:00Z
JULY_START = 1_782_864_000        # 2026-07-01T00:00:00Z
AUGUST_START = 1_785_542_400      # 2026-08-01T00:00:00Z


def _row(tenant: str, minor: int, paid_at: str) -> dict:
    """One invoice as billing's platform projection really sends it.

    `subtotal_minor` IS PART OF THE ROW, and this fixture was written before it was (ح-2). The
    figure a partner earns on is the net one — our prices include VAT — so a fixture carrying only
    `total_minor` describes a projection that no longer exists, and the adapter is right to refuse
    it. The window logic under test is unchanged: these numbers are already the net ones.
    """
    return {"tenant": tenant, "subtotal_minor": minor, "total_minor": minor,
            "status": "paid", "paid_at": paid_at}


class _Billing(SettlementsSource):
    """The real adapter with only the HTTP call replaced, so the window logic under test is ours."""

    def __init__(self, paid: list[dict], void: list[dict] | None = None):
        super().__init__(billing_url="http://billing", identity_url="http://identity",
                         client_id="id", client_secret="secret")
        self._paid, self._void = paid, list(void or [])
        self.asked: list[tuple[str, int, int]] = []

    def _invoices(self, *, status: str, since: int, until: int) -> list[dict]:
        self.asked.append((status, since, until))
        return list(self._paid if status == "paid" else self._void)


def _for(source, start, end):
    return asyncio.run(source.for_period(period_start=start, period_end=end))


def test_an_invoice_issued_in_june_and_paid_in_july_belongs_to_july():
    """THE DEFECT. 74.75 SAR of settled money, and the only question is which month owns it."""
    src = _Billing([_row("shop_1", 7_475, "2026-07-04T09:30:00Z")])

    assert _for(src, JULY_START, AUGUST_START) == {
        "shop_1": {"settled_minor": 7_475, "refunded_minor": 0}}


def test_and_it_does_not_also_belong_to_june():
    """The re-run of June in September must not find it. Otherwise we pay the same money twice."""
    assert _for(_Billing([_row("shop_1", 7_475, "2026-07-04T09:30:00Z")]),
                JUNE_START, JULY_START) == {}


def test_the_read_reaches_back_past_the_period_or_it_cannot_see_the_invoice():
    """The narrowing is only possible if the row was fetched. billing filters on the issue date."""
    src = _Billing([])
    _for(src, JULY_START, AUGUST_START)
    status, since, until = src.asked[0]
    assert status == "paid"
    assert since == JULY_START - LOOKBACK_SECONDS, "a June invoice would never have been returned"
    assert until == AUGUST_START


def test_a_paid_invoice_that_will_not_say_when_stops_the_whole_statement():
    """Neither counting it nor dropping it is honest, and both are silent. So: no statement.

    This is the same failing-closed the adapter already does when billing cannot be read at all —
    a statement of zero is a number a partner reads, believes, and plans around.
    """
    src = _Billing([_row("shop_1", 7_475, ""), _row("shop_2", 1_000, "2026-07-04T09:30:00Z")])
    assert _for(src, JULY_START, AUGUST_START) is None


def test_a_payment_on_the_last_instant_of_the_month_is_in_that_month_and_not_the_next():
    """Half-open, and stated once here rather than discovered twice at a month boundary."""
    src = _Billing([_row("shop_1", 500, "2026-07-31T23:59:59Z"),
                    _row("shop_2", 900, "2026-08-01T00:00:00Z")])
    assert _for(src, JULY_START, AUGUST_START) == {
        "shop_1": {"settled_minor": 500, "refunded_minor": 0}}


def test_the_timestamp_is_read_as_utc_whatever_shape_billing_writes_it_in():
    assert paid_instant({"paid_at": "2026-07-01T00:00:00Z"}) == JULY_START
    assert paid_instant({"paid_at": "2026-07-01T00:00:00+00:00"}) == JULY_START
    assert paid_instant({"paid_at": "2026-07-01T00:00:00"}) == JULY_START, "naive means UTC here"
    assert paid_instant({"paid_at": "not a time"}) is None
    assert paid_instant({}) is None
