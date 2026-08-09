"""Commission — the difference between a business and a slow leak."""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.commission import StatementStore, build

JAN = 1_767_225_600
FEB = 1_769_904_000


def run(c):
    return asyncio.run(c)


def stamp(tenant, rate=0.25):
    return {"tenant": tenant, "partner_id": "prt_1", "commission_rate": rate}


def paid(settled, refunded=0):
    return {"settled_minor": settled, "refunded_minor": refunded}


def st(stamps, settlements):
    return build(partner_id="prt_1", period_start=JAN, period_end=FEB,
                 stamps=stamps, settlements=settlements)


def test_commission_is_on_money_that_actually_arrived():
    """Paying on what was billed means every unpaid invoice is our money gone — and the worse our
    collection gets, the more we pay out."""
    s = st([stamp("shop1"), stamp("shop2")], {"shop1": paid(20000)})
    assert s.total_minor == 5000
    assert [line.commission_minor for line in s.lines] == [5000, 0]


def test_a_shop_that_paid_nothing_still_appears_as_a_zero_line():
    """A partner reading a statement needs to see the shop was counted and earned nothing, or
    they will ask us why it vanished."""
    s = st([stamp("shop1")], {})
    assert len(s.lines) == 1 and s.lines[0].commission_minor == 0


def test_a_refund_inside_the_period_claws_back_in_the_same_statement():
    """A carried negative is a number somebody reconciles by hand once, and then stops."""
    s = st([stamp("shop1")], {"shop1": paid(20000, refunded=20000)})
    assert s.total_minor == 0 and s.net_minor == 0


def test_a_partial_refund_reduces_the_commission_proportionally():
    s = st([stamp("shop1")], {"shop1": paid(20000, refunded=8000)})
    assert s.lines[0].net_minor == 12000 and s.total_minor == 3000


def test_a_refund_larger_than_the_payment_never_goes_negative():
    """A negative commission is a debt we would have to collect from a partner, which is a
    conversation nobody wins."""
    s = st([stamp("shop1")], {"shop1": paid(5000, refunded=9000)})
    assert s.total_minor == 0


def test_the_rate_comes_from_the_stamp_not_from_todays_partner_record():
    """Renegotiating next year must not silently rewrite every statement we ever issued."""
    s = st([stamp("shop1", rate=0.30), stamp("shop2", rate=0.20)],
           {"shop1": paid(10000), "shop2": paid(10000)})
    assert [line.commission_minor for line in s.lines] == [3000, 2000]


def test_running_the_same_closed_month_twice_returns_the_identical_number():
    """Nobody can trust a statement that changes when you look at it again — not the partner, not
    us, not an auditor."""
    stamps = [stamp("shop2"), stamp("shop1"), stamp("shop3")]
    money = {"shop1": paid(13333), "shop2": paid(7777), "shop3": paid(1)}
    a, b = st(stamps, money).as_row(), st(stamps, money).as_row()
    assert a == b


def test_the_lines_are_ordered_so_two_runs_diff_cleanly():
    """A diff is how anybody checks a number they do not trust."""
    s = st([stamp("z"), stamp("a"), stamp("m")], {})
    assert [line.tenant for line in s.lines] == ["a", "m", "z"]


def test_the_total_is_the_sum_of_the_rounded_lines_not_a_rounded_sum():
    """The partner adds up the lines; a total computed separately would disagree with them."""
    s = st([stamp("s1"), stamp("s2"), stamp("s3")],
           {"s1": paid(333), "s2": paid(333), "s3": paid(333)})
    # 3 x floor(333 x 0.25) = 3 x 83 = 249. A rounded SUM would be floor(999 x 0.25) = 249 here
    # too, so the assertion that matters is the identity, not the constant: the total must be
    # built from the lines the partner can add up, whatever the arithmetic happens to agree on.
    assert s.total_minor == sum(line.commission_minor for line in s.lines) == 249


def test_rounding_is_down_so_we_never_overpay_by_a_fraction():
    """A halala per shop per month across a thousand shops is money that has to come from
    somewhere."""
    s = st([stamp("s1", rate=0.25)], {"s1": paid(999)})
    assert s.lines[0].commission_minor == 249


def test_recomputing_a_month_overwrites_rather_than_duplicating():
    store = StatementStore(MemoryDataStore())
    s = st([stamp("shop1")], {"shop1": paid(20000)})
    run(store.save(s))
    run(store.save(s))
    assert len(run(store.for_partner("prt_1"))) == 1


def test_a_stamp_with_no_tenant_is_skipped_rather_than_crashing_the_run():
    s = st([{"partner_id": "prt_1", "commission_rate": 0.25}, stamp("shop1")],
           {"shop1": paid(10000)})
    assert len(s.lines) == 1
