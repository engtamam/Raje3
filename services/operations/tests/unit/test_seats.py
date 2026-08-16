"""Seats and branches as gauges — reported, never incremented, enforced at the door."""
from __future__ import annotations

import asyncio

import pytest

from app.core import seats as S

T = "shop"


def run(c):
    return asyncio.run(c)


class FakeBilling:
    """billing's gauge report and its entitlement read, with the semantics that matter.

    The gauge is STORED as whatever was last reported, so a test that deletes an employee and
    reports 4 can see the number go down — which is the difference between a gauge and a counter,
    and the defect this file exists to prevent.
    """

    def __init__(self, limit: int = 5) -> None:
        self.limit = limit
        self.value: int | None = None
        self.reports: list[int] = []
        self.unreachable = False

    def make(self) -> S.HttpGauges:
        g = S.HttpGauges(billing_url="http://b", set_path="/internal/billing/usage/set",
                         check_path="/internal/billing/entitlements/check", token="t")

        async def report(tenant, key, value):
            if self.unreachable:
                return                       # the real one swallows; see the module docstring
            self.value = int(value)
            self.reports.append(int(value))

        async def allows(tenant, key, current):
            if self.unreachable:
                return True, -1              # fails OPEN — a seat is not a message
            if self.limit < 0:
                return True, -1
            return (int(current) + 1 <= self.limit), self.limit

        g.report = report                    # type: ignore[assignment]
        g.allows_one_more = allows           # type: ignore[assignment]
        return g


# ── a gauge goes down ──────────────────────────────────────────────────────────────────────────
def test_the_gauge_reports_the_current_value_not_a_delta():
    f = FakeBilling()
    g = f.make()
    run(g.report(T, S.SEATS, 5))
    assert f.value == 5


def test_deleting_an_employee_gives_the_seat_back():
    """THE WHOLE REASON THIS IS A GAUGE. Incremented instead, the number only ever rises: a shop
    that hired and fired the same position four times is told it has four employees, and nobody
    notices until somebody cannot add a person they can see they have room for."""
    f = FakeBilling()
    g = f.make()
    run(g.report(T, S.SEATS, 5))
    run(g.report(T, S.SEATS, 4))
    assert f.value == 4


# ── the door ───────────────────────────────────────────────────────────────────────────────────
def test_one_more_is_allowed_below_the_limit():
    g = FakeBilling(limit=5).make()
    run(S.guard_and_report(g, tenant=T, key=S.SEATS, current=4))     # must not raise


def test_the_one_that_crosses_the_line_is_refused():
    g = FakeBilling(limit=5).make()
    with pytest.raises(S.SeatLimitReached):
        run(S.guard_and_report(g, tenant=T, key=S.SEATS, current=5))


def test_the_refusal_names_the_limit():
    """'Not allowed' answers nothing. He needs the number to decide whether to upgrade."""
    g = FakeBilling(limit=15).make()
    with pytest.raises(S.SeatLimitReached) as e:
        run(S.guard_and_report(g, tenant=T, key=S.SEATS, current=15))
    assert "15" in str(e.value)


def test_a_branch_refusal_talks_about_branches_and_not_employees():
    g = FakeBilling(limit=2).make()
    with pytest.raises(S.SeatLimitReached) as e:
        run(S.guard_and_report(g, tenant=T, key=S.BRANCHES, current=2))
    assert "فرع" in str(e.value) and "موظف" not in str(e.value)


def test_the_refusal_is_grammatical_at_one_which_is_the_base_plan():
    """«باقتك تسمح بـ1 فروع» was the sentence almost every shop would be shown.

    The base plan allows exactly one branch and every establishment now owns its main branch from
    signup, so the count of 1 is not an edge case — it is the common path, and the naive form was
    ungrammatical on it.
    """
    g = FakeBilling(limit=1).make()
    with pytest.raises(S.SeatLimitReached) as e:
        run(S.guard_and_report(g, tenant=T, key=S.BRANCHES, current=1))
    assert "بفرع واحد" in str(e.value) and "1" not in str(e.value)


def test_an_unlimited_plan_never_refuses():
    g = FakeBilling(limit=-1).make()
    run(S.guard_and_report(g, tenant=T, key=S.SEATS, current=9999))  # must not raise


# ── the outage, and why it fails the other way from messages ───────────────────────────────────
def test_an_unreachable_billing_still_lets_a_shop_hire():
    """FAILS OPEN, deliberately the opposite of the message quota. One seat over the line for an
    hour costs nothing and the next report corrects it; a shop that cannot add an employee during
    our outage is a support call and a customer who stops trusting the product. A message fails
    closed because each one costs real money."""
    f = FakeBilling(limit=1)
    f.unreachable = True
    run(S.guard_and_report(f.make(), tenant=T, key=S.SEATS, current=50))   # must not raise


def test_a_failed_report_does_not_raise():
    """The employee has already been created. Failing the request now would leave him created and
    the caller told it failed — the worst of both."""
    f = FakeBilling()
    f.unreachable = True
    run(f.make().report(T, S.SEATS, 3))     # must not raise


# ── the downgrade ──────────────────────────────────────────────────────────────────────────────
def test_a_shop_over_its_new_limit_is_reported_honestly_rather_than_trimmed():
    """A shop on 15 seats with 12 employees moves to a plan allowing 5. We do not choose which
    seven to deactivate — it is his shop — and we do not refuse the downgrade, which would trap
    him on a plan he told us he cannot afford. The gauge reports 12 against a limit of 5, which is
    a true statement, and he decides."""
    f = FakeBilling(limit=5)
    g = f.make()
    run(g.report(T, S.SEATS, 12))
    assert f.value == 12


def test_but_nobody_new_may_be_added_while_over_the_line():
    """That is a decision he is making NOW, rather than one he already made."""
    g = FakeBilling(limit=5).make()
    with pytest.raises(S.SeatLimitReached):
        run(S.guard_and_report(g, tenant=T, key=S.SEATS, current=12))


def test_the_keys_are_named_once():
    """A typo creates a second gauge with no limit, which resolves deny-by-default and looks
    exactly like a full plan."""
    assert S.SEATS == "staff.seats" and S.BRANCHES == "branches"


# ── the correction the fail-open was promised on ───────────────────────────────────────────────
def test_the_nightly_pass_corrects_a_count_that_an_outage_let_through():
    """THE DEFECT. `allows_one_more` fails OPEN on purpose — a billing outage must not stop a shop
    hiring somebody — and its own comment justified that with «the next report corrects the count
    anyway». There was no next report: `report()` ran only on the write path, during the same
    outage, swallowing its own errors. A five-seat shop that hired during a hiccup kept seats six
    and seven for ever, and billing never learned.

    A reason given for a decision has to be a mechanism, or it is a hope."""
    from app.adapters.datastore.memory import MemoryDataStore
    from app.core.models import Branch, Operator
    from app.core.stores import BranchStore, OperatorStore

    st = MemoryDataStore()
    ops, branches = OperatorStore(st), BranchStore(st)
    f = FakeBilling()
    g = f.make()

    # Seven live operators and two live branches — the state after an outage let the extras in.
    for i in range(7):
        run(ops.save(Operator(id=f"op_{i}", tenant=T, name=f"موظف {i}", role="operator")))
    for i in range(2):
        run(branches.save(Branch(id=f"br_{i}", tenant=T, name=f"فرع {i}")))
    # And one that is gone: a gauge counts the LIVE ones, or a shop pays for people who left.
    run(ops.save(Operator(id="op_gone", tenant=T, name="مغادر", role="operator", active=False)))

    out = run(S.reconcile(datastore=st, gauges=g, tenants=[T]))
    assert out["seats"] == 7 and out["branches"] == 2 and out["failed"] == 0
    assert f.reports[-2:] == [7, 2], f.reports


def test_one_unreadable_establishment_does_not_stop_the_rest():
    """A repair that aborts on the first bad row repairs the least when there is most to repair."""
    from app.adapters.datastore.memory import MemoryDataStore
    from app.core.models import Operator
    from app.core.stores import OperatorStore

    st = MemoryDataStore()
    run(OperatorStore(st).save(Operator(id="op_1", tenant=T, name="أحمد", role="operator")))
    f = FakeBilling()
    g = f.make()
    original = g.report

    async def report(tenant, key, value):
        if tenant == "broken":
            raise OSError("billing said no")
        await original(tenant, key, value)

    g.report = report                        # type: ignore[assignment]
    out = run(S.reconcile(datastore=st, gauges=g, tenants=["broken", T]))
    assert out["failed"] == 1 and out["seats"] == 1
