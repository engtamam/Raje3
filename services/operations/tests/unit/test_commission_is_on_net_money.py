"""ح-2 and ح-3: a partner earns on what the shop kept paying us, net of the state's tax.

TWO DEFECTS THAT COMPOSE, AND BOTH ARE MONEY LEAVING EVERY MONTH.

  ح-2 · Our prices INCLUDE VAT — the owner is quoted 299 and pays 299 — and the commission was a
        percentage of that inclusive figure. At 25% the partner was handed 7475 halalas where
        6500 was owed: 975 of the 3900 we collect for ZATCA, per shop, per month. Five hundred
        shops is 4,875 riyals a month of tax revenue paid out as commission.

  ح-3 · A PARTIAL refund leaves the invoice `paid`. It never enters the void list, so 150 riyals
        returned to the shop earned the partner full commission on 299.

The arithmetic below is the register's own worked example, and the answer to the second is NOT
the 3725 that finding predicted: that number was computed before the tax fix. Net of VAT and net
of the refund, the partner earns 3239 — the two corrections multiply rather than sit side by side,
which is exactly why they are tested together.
"""
from __future__ import annotations

import asyncio

from app.adapters.settlements import SettlementsSource, _net_of_tax, _net_share

RATE = 0.25
INCLUSIVE = 29900   # 299.00 SAR as quoted
NET = 26000         # what is ours
TAX = 3900          # what ZATCA's is


def _commission(net_minor: int) -> int:
    from decimal import ROUND_DOWN, Decimal
    return int((Decimal(net_minor) * Decimal(str(RATE))).quantize(Decimal(1), rounding=ROUND_DOWN))


def test_the_partner_is_not_paid_a_share_of_the_states_tax():
    net = _net_of_tax({"subtotal_minor": NET, "tax_minor": TAX, "total_minor": INCLUSIVE})

    assert net == NET
    assert _commission(net) == 6500, "commission on the VAT-inclusive total is 7475 — 975 of it tax"


def test_a_partial_refund_reduces_the_base_although_the_invoice_stays_paid():
    row = {"subtotal_minor": NET, "tax_minor": TAX, "total_minor": INCLUSIVE,
           "refunded_minor": 15000}

    back = _net_share(row["refunded_minor"], net=NET, total=INCLUSIVE)

    assert back == 13043
    assert _commission(NET - back) == 3239


def test_an_invoice_that_will_not_say_its_tax_fails_the_sweep_rather_than_guessing():
    """THE FALLBACK IS THE DEFECT WEARING A DEFAULT'S COSTUME.

    «Use total when subtotal is missing» would restore the 15% overpayment silently, on exactly
    the rows nobody can check. This adapter already fails closed when billing cannot be read; a
    row that will not say what the tax was is the same situation one invoice at a time.
    """
    assert _net_of_tax({"total_minor": INCLUSIVE}) is None


def test_the_period_read_returns_nothing_when_a_row_hides_its_tax(monkeypatch):
    src = SettlementsSource(billing_url="http://b", identity_url="http://i",
                            client_id="c", client_secret="s")
    rows = {"paid": [{"tenant": "t1", "paid_at": "2026-06-15T10:00:00Z",
                      "total_minor": INCLUSIVE}],       # no subtotal_minor
            "void": []}
    monkeypatch.setattr(src, "_invoices",
                        lambda *, status, since, until: rows[status])

    out = asyncio.run(src.for_period(period_start=1_780_272_000, period_end=1_782_864_000))

    assert out is None, "a statement 15% high is worse than no statement"


def test_a_clean_period_still_settles(monkeypatch):
    """The guard must not swallow the ordinary case — a gate that fails everything is an outage."""
    src = SettlementsSource(billing_url="http://b", identity_url="http://i",
                            client_id="c", client_secret="s")
    rows = {"paid": [{"tenant": "t1", "paid_at": "2026-06-15T10:00:00Z",
                      "subtotal_minor": NET, "tax_minor": TAX, "total_minor": INCLUSIVE,
                      "refunded_minor": 15000}],
            "void": []}
    monkeypatch.setattr(src, "_invoices",
                        lambda *, status, since, until: rows[status])

    out = asyncio.run(src.for_period(period_start=1_780_272_000, period_end=1_782_864_000))

    assert out == {"t1": {"settled_minor": NET, "refunded_minor": 13043}}
