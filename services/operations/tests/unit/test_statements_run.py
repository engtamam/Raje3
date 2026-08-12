"""Issuing the statements — the caller `commission.build` never had.

THE DEFECT THESE LOCK DOWN. The engine was complete, pure and tested; `StatementStore.save`
appeared in two test files and in no route and no schedule. `GET /partner/statements` therefore
answered `[]` for ever, successfully, and a partner reading it concludes we have not issued yet.

Nothing here touches HTTP: the decisions are which period, what happens when the money cannot be
read, and whether two runs of a closed month agree.
"""
from __future__ import annotations

import asyncio
import calendar

import pytest

from app.core import statements_run
from app.core.commission import STATEMENTS


class _Store:
    """The two operations the sweep needs, over a dict."""

    def __init__(self) -> None:
        self.rows: dict[tuple[str, str], dict] = {}

    async def put(self, collection, key, row):
        self.rows[(collection, key)] = row

    async def get(self, collection, key):
        return self.rows.get((collection, key))

    async def find(self, collection, filt=None, *, limit=100, after=None, sort=None):
        out = [r for r in (v for (c, _), v in self.rows.items() if c == collection)
               if all(r.get(k) == v for k, v in (filt or {}).items())]
        return out, None


class _Money:
    def __init__(self, table=None) -> None:
        self._table = table
        self.asked: tuple = ()

    async def for_period(self, *, period_start, period_end):
        self.asked = (period_start, period_end)
        return self._table


def _seed(store, *, partner="prt_1", rate=0.25, tenants=("t_a", "t_b")):
    # KEYED THE WAY THE REGISTRY KEYS THEM — `_platform|id`, and the row carries `tenant` because
    # that is what `list()` filters on. A fake store that answers a shape the real one never
    # produces tests the fake.
    store.rows[("partners", f"_platform|{partner}")] = {
        "id": partner, "tenant": "_platform", "name": "شركة كاشير",
        "commission_rate": rate, "active": True, "created": 1}
    for t in tenants:
        store.rows[("partner_stamps", f"{t}|stamp")] = {
            "tenant": t, "partner_id": partner, "commission_rate": rate, "stamped_at": 1}


def test_the_period_is_the_last_closed_month_never_the_running_one():
    """A statement for a month still running changes every time it is read, and a number that
    changes is one a partner cannot invoice against."""
    now = calendar.timegm((2026, 8, 12, 6, 0, 0, 0, 0, 0))
    start, end = statements_run.last_closed_month(now)
    assert start == calendar.timegm((2026, 7, 1, 0, 0, 0, 0, 0, 0))
    assert end == calendar.timegm((2026, 8, 1, 0, 0, 0, 0, 0, 0))


def test_january_reaches_back_across_the_year():
    """The off-by-one that only fails once a year, in the first week of January, on the one run
    nobody is watching."""
    now = calendar.timegm((2027, 1, 3, 6, 0, 0, 0, 0, 0))
    start, end = statements_run.last_closed_month(now)
    assert start == calendar.timegm((2026, 12, 1, 0, 0, 0, 0, 0, 0))
    assert end == calendar.timegm((2027, 1, 1, 0, 0, 0, 0, 0, 0))


def test_the_period_is_half_open():
    """Inclusive ends put a payment landing at the last second into both months or neither,
    depending on a peer's rounding — and the two statements disagree by an invoice nobody finds."""
    start, end = statements_run.last_closed_month(calendar.timegm((2026, 8, 12, 0, 0, 0, 0, 0, 0)))
    assert end == calendar.timegm((2026, 8, 1, 0, 0, 0, 0, 0, 0))
    assert start < end


def test_a_statement_is_written_for_each_partner():
    """The whole point: something calls the engine and the row lands where the partner route
    reads it."""
    store = _Store()
    _seed(store)
    money = _Money({"t_a": {"settled_minor": 40_000, "refunded_minor": 0},
                    "t_b": {"settled_minor": 20_000, "refunded_minor": 0}})
    out = asyncio.run(statements_run.issue(store=store, settlements_source=money,
                                           now=calendar.timegm((2026, 8, 2, 0, 0, 0, 0, 0, 0))))
    assert out["issued"] == 1
    saved = [v for (c, _), v in store.rows.items() if c == STATEMENTS]
    assert len(saved) == 1
    # 25% of 60,000 halalas — computed by the engine, asserted here so a wiring change that quietly
    # stopped passing the stamps would not pass this file.
    assert saved[0]["total_minor"] == 15_000


def test_money_that_cannot_be_read_issues_nothing_and_says_why():
    """A statement of zero is not a cautious default: it is a number a partner reads, believes and
    plans around, and withdrawing it next month costs more than never sending it."""
    store = _Store()
    _seed(store)
    out = asyncio.run(statements_run.issue(store=store, settlements_source=_Money(None)))
    assert out["issued"] == 0 and out["skipped"] == "SETTLEMENTS_UNAVAILABLE"
    assert not [v for (c, _), v in store.rows.items() if c == STATEMENTS]


def test_a_shop_that_paid_nothing_is_a_line_of_zero_not_a_missing_line():
    """A partner reading a statement needs to see that a shop was counted and earned nothing, or
    they ask us why it vanished — and that conversation costs more than the line."""
    store = _Store()
    _seed(store)
    money = _Money({"t_a": {"settled_minor": 40_000, "refunded_minor": 0}})
    asyncio.run(statements_run.issue(store=store, settlements_source=money))
    row = [v for (c, _), v in store.rows.items() if c == STATEMENTS][0]
    assert {line["tenant"] for line in row["lines"]} == {"t_a", "t_b"}


def test_a_refund_in_the_period_cancels_its_own_commission():
    """Net, in the month that earned it — never a negative carried forward into a month nobody
    reconciles."""
    store = _Store()
    _seed(store, tenants=("t_a",))
    money = _Money({"t_a": {"settled_minor": 40_000, "refunded_minor": 40_000}})
    asyncio.run(statements_run.issue(store=store, settlements_source=money))
    row = [v for (c, _), v in store.rows.items() if c == STATEMENTS][0]
    assert row["total_minor"] == 0


def test_running_a_closed_month_twice_produces_the_same_row():
    """Reproducibility is what makes the number trustworthy — to the partner, to us, to an
    auditor. It holds only because the engine has no clock in it and the boundaries are passed."""
    store = _Store()
    _seed(store)
    money = _Money({"t_a": {"settled_minor": 33_333, "refunded_minor": 1_111}})
    period = (1_750_000_000, 1_752_000_000)
    asyncio.run(statements_run.issue(store=store, settlements_source=money, period=period))
    first = dict([v for (c, _), v in store.rows.items() if c == STATEMENTS][0])
    asyncio.run(statements_run.issue(store=store, settlements_source=money, period=period))
    saved = [v for (c, _), v in store.rows.items() if c == STATEMENTS]
    assert len(saved) == 1, "a second run duplicated the statement instead of overwriting it"
    assert saved[0] == first


def test_the_rate_comes_from_the_stamp_not_from_the_partner_record():
    """Renegotiating a rate next year must not silently rewrite every statement already issued."""
    store = _Store()
    _seed(store, rate=0.25, tenants=("t_a",))
    store.rows[("partners", "_platform|prt_1")]["commission_rate"] = 0.50   # renegotiated today
    money = _Money({"t_a": {"settled_minor": 10_000, "refunded_minor": 0}})
    asyncio.run(statements_run.issue(store=store, settlements_source=money))
    row = [v for (c, _), v in store.rows.items() if c == STATEMENTS][0]
    assert row["total_minor"] == 2_500


def test_a_partner_who_brought_nobody_gets_no_statement():
    """An empty statement is noise in a list somebody reads monthly."""
    store = _Store()
    store.rows[("partners", "_platform|prt_2")] = {
        "id": "prt_2", "tenant": "_platform", "name": "بلا محلات",
        "commission_rate": 0.2, "active": True, "created": 1}
    out = asyncio.run(statements_run.issue(store=store, settlements_source=_Money({})))
    assert out["issued"] == 0


# ── the state on a statement, and the trap the schedule introduced ────────────────────────────


def _statement(store, *, money, period=(1_750_000_000, 1_752_000_000)):
    asyncio.run(statements_run.issue(store=store, settlements_source=_Money(money), period=period))
    return [v for (c, _), v in store.rows.items() if c == STATEMENTS][0]


def test_a_fresh_statement_is_issued_not_paid():
    """Payment is a fact that happens later, on somebody else's timetable."""
    store = _Store()
    _seed(store, tenants=("t_a",))
    row = _statement(store, money={"t_a": {"settled_minor": 10_000, "refunded_minor": 0}})
    assert row["status"] == "issued"


def test_a_paid_statement_survives_the_monthly_re_run():
    """THE TRAP THE SCHEDULE INTRODUCED, and the reason `save` reads before it writes: the sweep
    re-runs whatever it is pointed at, and without this one re-run of a settled month resets
    `paid` to `issued` and rewrites the amount — so the panel shows money owed that we already
    sent, and somebody sends it twice."""
    from app.core.commission import StatementStore

    store = _Store()
    _seed(store, tenants=("t_a",))
    period = (1_750_000_000, 1_752_000_000)
    _statement(store, money={"t_a": {"settled_minor": 10_000, "refunded_minor": 0}}, period=period)
    asyncio.run(StatementStore(store).set_state("prt_1", period[0], state="paid",
                                                actor="u_ops", reference="WIRE-9", at=123))
    # The sweep runs again, and the settlements have since moved.
    _statement(store, money={"t_a": {"settled_minor": 99_000, "refunded_minor": 0}}, period=period)
    row = [v for (c, _), v in store.rows.items() if c == STATEMENTS][0]
    assert row["status"] == "paid"
    assert row["settled_ref"] == "WIRE-9"
    assert row["total_minor"] == 2_500, "a settled month was recomputed after the money moved"


def test_a_dispute_survives_the_recompute_that_it_caused():
    """Re-running is exactly what a disputed month needs — and the dispute is the reason it was
    re-run, so clearing the flag would erase the record of why the number changed."""
    from app.core.commission import StatementStore

    store = _Store()
    _seed(store, tenants=("t_a",))
    period = (1_750_000_000, 1_752_000_000)
    _statement(store, money={"t_a": {"settled_minor": 10_000, "refunded_minor": 0}}, period=period)
    asyncio.run(StatementStore(store).set_state("prt_1", period[0], state="disputed",
                                                actor="u_ops", note="ينقص محل"))
    _statement(store, money={"t_a": {"settled_minor": 20_000, "refunded_minor": 0}}, period=period)
    row = [v for (c, _), v in store.rows.items() if c == STATEMENTS][0]
    assert row["status"] == "disputed" and row["note"] == "ينقص محل"
    # The figure DID move — a disputed statement is the one case a recompute is meant to change.
    assert row["total_minor"] == 5_000


def test_an_unknown_state_is_refused_rather_than_written():
    """A typo that reaches the row makes a statement nothing can filter for — invisible on the one
    screen that exists to find it."""
    from app.core.commission import StatementStore

    store = _Store()
    _seed(store, tenants=("t_a",))
    _statement(store, money={"t_a": {"settled_minor": 10_000, "refunded_minor": 0}})
    out = asyncio.run(StatementStore(store).set_state("prt_1", 1_750_000_000, state="settled",
                                                      actor="u"))
    assert out is None


def test_marking_a_statement_that_does_not_exist_answers_none():
    """A period guessed in a URL must not create a row — timestamps are guessable by design."""
    from app.core.commission import StatementStore

    out = asyncio.run(StatementStore(_Store()).set_state("prt_x", 1, state="paid", actor="u"))
    assert out is None
