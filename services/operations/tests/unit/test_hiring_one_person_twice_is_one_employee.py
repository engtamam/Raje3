"""ز-10 — one press was one employee; two presses were two seats and one man.

`hire_member` creates two things and calls them one act: a membership at identity, keyed by phone
and idempotent, and an operator row here, which is what the seat gauge counts and what a visit is
attributed to. The row was created with `new_id("opr")` — new on every call — and nothing compared
against what was already there.

    press, slow reply, press again  ->  one membership, TWO operator rows

The shop pays per seat, so the owner buys a seat for a person he hired once. His team screen lists
the same name twice with no way to tell them apart. And `verify-pin` answers with whichever row it
reaches first, so the same employee's work lands on one row today and the other tomorrow.

Nothing failed: 201, a valid row, a screen that refreshed. The second press looked exactly like the
first one working.
"""
from __future__ import annotations

import asyncio
import types

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.api.v1 import staff as ST

TENANT = "shop"


def run(c):
    return asyncio.run(c)


class _Store:
    """The shop's operator rows, as `OperatorStore` serves them."""

    def __init__(self):
        self.rows: dict[str, object] = {}

    async def list(self, tenant: str):
        return list(self.rows.values())

    async def save(self, op):
        self.rows[op.id] = op
        return op


class _Gauges:
    def __init__(self):
        self.reported: list[int] = []

    async def report(self, tenant, key, value):
        self.reported.append(value)

    async def limit(self, tenant, key):
        return 15


class _Signup:
    """Identity, which dedupes by phone — the whole reason the second press is not a second hire."""

    def __init__(self):
        self.calls = 0

    async def hire(self, tenant, *, phone, password, role):
        self.calls += 1
        return {"person_id": "per_" + phone[-4:]}


class _Auditor:
    async def record(self, *a, **kw):
        return None


@pytest.fixture
def wired(monkeypatch):
    store, gauges, signup = _Store(), _Gauges(), _Signup()
    monkeypatch.setattr(ST, "OperatorStore", lambda _ds: store)
    # The seat guard and the branch resolver are other findings' subjects; here they must not be
    # what the test is measuring.
    monkeypatch.setattr(ST.S, "guard_and_report", _passes)
    monkeypatch.setattr(ST.B, "resolve", _no_branch)

    request = types.SimpleNamespace(
        client=None,
        app=types.SimpleNamespace(state=types.SimpleNamespace(
            auditor=_Auditor(),
            container_settings=types.SimpleNamespace(PII_SALT="salt"),
            # A REAL STORE, BECAUSE THE ROUTE NOW TAKES THE SEAT LANE FROM IT. `None` was honest
            # while `OperatorStore` was the only thing built from it and this test replaces that;
            # the hire path now also claims the establishment's add-a-seat lane, which is a store
            # operation and not one worth faking (core/seats.py).
            container=types.SimpleNamespace(datastore=MemoryDataStore(), gauges=gauges,
                                            signup=signup))))
    return request, store, gauges, signup


async def _passes(gauges, *, tenant, key, current):
    return None


async def _no_branch(store, tenant, value):
    return ""


def _body(name="أحمد", phone="0555000111"):
    return ST.MemberIn(name=name, phone=phone, password="a-long-enough-password", role="operator",
                       branch_id="")


def _hire(request, body):
    return run(ST.hire_member(request, body,
                              principal=types.SimpleNamespace(tenant=TENANT, tenant_id=TENANT,
                                                              subject="owner")))


def test_pressing_hire_twice_leaves_one_employee(wired):
    """THE DEFECT. Same person, two rows, two seats — and one of them cannot be told from the other."""
    request, store, gauges, signup = wired

    first = _hire(request, _body())
    second = _hire(request, _body())

    assert len(store.rows) == 1, "the second press created a second row for the same person"
    assert first["id"] == second["id"], "and the owner's screen would show two entries"
    assert signup.calls == 2, "identity was asked twice, as it will be — it dedupes; we did not"


def test_the_seat_count_does_not_grow_when_nobody_was_hired(wired):
    """The shop pays per seat. Reporting a gauge that moved on a re-save bills for a phantom."""
    request, store, gauges, _ = wired

    _hire(request, _body())
    _hire(request, _body())

    assert gauges.reported == [1, 1], "the second report claimed an employee that does not exist"


def test_two_different_people_are_still_two_employees(wired):
    """The other direction, which is the one a careless fix breaks: a shop must be able to hire."""
    request, store, gauges, _ = wired

    _hire(request, _body(name="أحمد", phone="0555000111"))
    _hire(request, _body(name="خالد", phone="0555000222"))

    assert len(store.rows) == 2
    assert gauges.reported == [1, 2]


def test_hiring_the_same_person_again_updates_him_rather_than_duplicating(wired):
    """A real second call: the owner re-hires somebody with a corrected name or a new role."""
    request, store, _, _ = wired

    _hire(request, _body(name="أحمد"))
    again = _hire(request, _body(name="أحمد الغامدي"))

    assert len(store.rows) == 1
    assert again["name"] == "أحمد الغامدي", "the newer answer wins, and it is the same row"
