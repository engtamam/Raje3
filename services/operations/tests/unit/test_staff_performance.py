"""Operations.staff_performance / VisitStore.staff_performance — the rating app's staff-comparison
report (rating-app-feature.md phase 7): per operator, visits handled and ratings collected over a
time window, with no-show rate merged in separately by the route (see bookings' own
test_no_show_summary.py for that half)."""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.models import Operator, Visit
from app.core.operations import Operations
from app.core.stores import OperatorStore, VisitStore

SALT = "s" * 32
TENANT = "tnt_alpha"


def run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def ops():
    store = MemoryDataStore()
    return Operations(store=store, pii_salt=SALT), store


async def _seed_operator(store, ident: str, name: str) -> None:
    await OperatorStore(store).save(Operator(tenant=TENANT, id=ident, name=name))


async def _seed_visit(store, *, ident: str, operator_id: str, occurred_at: int,
                      rating: int = 0) -> None:
    v = Visit(tenant=TENANT, id=ident, customer_id="cus_1", operator_id=operator_id,
             branch_id="", created=occurred_at, occurred_at=occurred_at, rating=rating,
             rated_at=occurred_at if rating else 0)
    await VisitStore(store).save(v)


def test_two_operators_are_compared_separately_over_the_same_window(ops):
    svc, store = ops
    run(_seed_operator(store, "op_a", "سارة"))
    run(_seed_operator(store, "op_b", "منى"))
    # op_a: 2 visits, both rated (5 and 3) — average 4.0
    run(_seed_visit(store, ident="v1", operator_id="op_a", occurred_at=1000, rating=5))
    run(_seed_visit(store, ident="v2", operator_id="op_a", occurred_at=1010, rating=3))
    # op_b: 3 visits, only 1 rated (2) — average 2.0
    run(_seed_visit(store, ident="v3", operator_id="op_b", occurred_at=1020, rating=2))
    run(_seed_visit(store, ident="v4", operator_id="op_b", occurred_at=1030))
    run(_seed_visit(store, ident="v5", operator_id="op_b", occurred_at=1040))

    rows = run(svc.staff_performance(TENANT, since=0, until=2000))
    by_id = {r["operator_id"]: r for r in rows}
    assert by_id["op_a"]["visits"] == 2
    assert by_id["op_a"]["ratings"] == 2
    assert by_id["op_a"]["average_rating"] == 4.0
    assert by_id["op_b"]["visits"] == 3
    assert by_id["op_b"]["ratings"] == 1
    assert by_id["op_b"]["average_rating"] == 2.0
    # Sorted by average_rating descending — op_a (4.0) ahead of op_b (2.0).
    assert [r["operator_id"] for r in rows] == ["op_a", "op_b"]
    assert by_id["op_a"]["operator_name"] == "سارة"


def test_a_visit_outside_the_window_is_not_counted(ops):
    svc, store = ops
    run(_seed_operator(store, "op_a", "سارة"))
    run(_seed_visit(store, ident="v1", operator_id="op_a", occurred_at=500, rating=5))
    rows = run(svc.staff_performance(TENANT, since=1000, until=2000))
    assert rows == []


def test_a_visit_with_no_operator_is_excluded_entirely(ops):
    """A till's own sale carries no operator (see `_branch_for`'s own note) — it must not become a
    phantom "operator" row with a blank id in a report meant to compare NAMED staff."""
    svc, store = ops
    run(_seed_visit(store, ident="v1", operator_id="", occurred_at=1000, rating=5))
    rows = run(svc.staff_performance(TENANT, since=0, until=2000))
    assert rows == []


def test_an_unrated_visit_still_counts_toward_visits_handled_not_toward_average(ops):
    svc, store = ops
    run(_seed_operator(store, "op_a", "سارة"))
    run(_seed_visit(store, ident="v1", operator_id="op_a", occurred_at=1000))
    rows = run(svc.staff_performance(TENANT, since=0, until=2000))
    assert rows[0]["visits"] == 1
    assert rows[0]["ratings"] == 0
    assert rows[0]["average_rating"] == 0.0


def test_a_branch_filter_narrows_to_that_branchs_visits_only(ops):
    svc, store = ops
    run(_seed_operator(store, "op_a", "سارة"))
    v_a = Visit(tenant=TENANT, id="v1", customer_id="cus_1", operator_id="op_a",
               branch_id="br_1", created=1000, occurred_at=1000, rating=4, rated_at=1000)
    v_b = Visit(tenant=TENANT, id="v2", customer_id="cus_1", operator_id="op_a",
               branch_id="br_2", created=1000, occurred_at=1000, rating=2, rated_at=1000)
    run(VisitStore(store).save(v_a))
    run(VisitStore(store).save(v_b))
    rows = run(svc.staff_performance(TENANT, since=0, until=2000, branch_id="br_1"))
    assert len(rows) == 1
    assert rows[0]["visits"] == 1
    assert rows[0]["average_rating"] == 4.0


def test_another_tenants_visits_never_leak_into_this_tenants_report(ops):
    svc, store = ops
    run(_seed_operator(store, "op_a", "سارة"))
    other = Visit(tenant="tnt_other", id="v1", customer_id="cus_1", operator_id="op_a",
                 branch_id="", created=1000, occurred_at=1000, rating=5, rated_at=1000)
    run(VisitStore(store).save(other))
    rows = run(svc.staff_performance(TENANT, since=0, until=2000))
    assert rows == []
