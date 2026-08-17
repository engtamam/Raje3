"""The last seat on the plan, and two people reaching for it in the same millisecond.

THE DEFECT THIS HOLDS DOWN. The cap was a count, an await, and an insert:

    current = len(live employees)          # both read 4
    await guard_and_report(..., current)   # billing is asked twice, and answers yes twice —
                                           # because at the instant each asked, it was true
    await store.save(new employee)         # both write

Five seats sold, six employees created, one of them free for ever, and nothing anywhere red. It
needs two requests overlapping, which is why it survived every test written one call at a time and
would have been found by an owner rather than by us.

WHAT MAKES THE TEST REAL. The gauge below yields to the event loop inside `allows_one_more` — one
`asyncio.sleep(0)` — which is what the HTTP entitlement read does on every real call. That single
suspension point is the whole race; without it the two coroutines never interleave and the test
passes against broken code.

SABOTAGE CHECK: replace `claiming` in staff.py with a context manager that yields unconditionally
and `test_only_one_of_two_simultaneous_hires_gets_the_last_seat` fails with 2 created on a cap
of 1.
"""
from __future__ import annotations

import asyncio

import pytest
from app.adapters.datastore.memory import MemoryDataStore
from app.core import seats as S


class _Gauge:
    """Billing, with the suspension its HTTP read really has. Answers from a fixed limit."""

    def __init__(self, limit: int) -> None:
        self.limit = limit

    async def allows_one_more(self, tenant: str, key: str, current: int) -> tuple[bool, int]:
        await asyncio.sleep(0)          # the entitlement round trip — where the race lives
        return (current + 1 <= self.limit), self.limit

    async def report(self, tenant: str, key: str, value: int) -> None:
        await asyncio.sleep(0)


async def _hire(store: MemoryDataStore, gauge: _Gauge, *, tenant: str, name: str,
                now: float) -> str:
    """The route's shape: claim the lane, count, guard, write, report."""
    async with S.claiming(store, tenant=tenant, key=S.SEATS, now=now):
        rows = await store.scan_all("operators", limit=1000)
        current = len([r for r in rows if r.get("tenant") == tenant])
        await S.guard_and_report(gauge, tenant=tenant, key=S.SEATS, current=current)
        await store.put("operators", name, {"tenant": tenant, "name": name})
        await gauge.report(tenant, S.SEATS, current + 1)
    return name


def test_only_one_of_two_simultaneous_hires_gets_the_last_seat():
    """THE DEFECT, at a cap of one so the arithmetic cannot be argued with."""

    async def run() -> tuple[int, int]:
        store, gauge = MemoryDataStore(), _Gauge(limit=1)
        out = await asyncio.gather(
            _hire(store, gauge, tenant="t1", name="a", now=1000.0),
            _hire(store, gauge, tenant="t1", name="b", now=1000.0),
            return_exceptions=True)
        rows = await store.scan_all("operators", limit=100)
        refused = [e for e in out if isinstance(e, Exception)]
        return len(rows), len(refused)

    created, refused = asyncio.run(run())

    assert created == 1, "two hires wrote two employees onto a plan that allows one"
    assert refused == 1, "the loser must be told, not silently dropped"


def test_the_refusal_is_one_of_the_two_the_owner_can_act_on():
    """Busy and full are different sentences, and both are answers. Neither is a 500."""

    async def run() -> list[BaseException]:
        store, gauge = MemoryDataStore(), _Gauge(limit=1)
        out = await asyncio.gather(
            _hire(store, gauge, tenant="t1", name="a", now=1000.0),
            _hire(store, gauge, tenant="t1", name="b", now=1000.0),
            return_exceptions=True)
        return [e for e in out if isinstance(e, BaseException)]

    errors = asyncio.run(run())

    assert len(errors) == 1
    assert isinstance(errors[0], (S.SeatClaimBusy, S.SeatLimitReached))
    assert str(errors[0]).strip(), "an empty message is a 500 wearing a status code"


def test_two_establishments_do_not_queue_behind_each_other():
    """ONE LANE PER SHOP. A global lock would make every hire in the fleet serial."""

    async def run() -> int:
        store = MemoryDataStore()
        assert await store.claim(S.CLAIMS, "t1:staff.seats", {},
                                 ttl_seconds=S.CLAIM_TTL_SECONDS, now=1000.0)
        took = await store.claim(S.CLAIMS, "t2:staff.seats", {},
                                 ttl_seconds=S.CLAIM_TTL_SECONDS, now=1000.0)
        return 1 if took else 0

    assert asyncio.run(run()) == 1


def test_seats_and_branches_are_separate_lanes():
    """Adding a branch must not be refused because somebody is hiring."""

    async def run() -> bool:
        store = MemoryDataStore()
        await store.claim(S.CLAIMS, f"t1:{S.SEATS}", {}, ttl_seconds=15.0, now=1000.0)
        return await store.claim(S.CLAIMS, f"t1:{S.BRANCHES}", {}, ttl_seconds=15.0, now=1000.0)

    assert asyncio.run(run()) is True


def test_a_claim_left_by_a_dead_process_expires():
    """A LOCK WITHOUT A TTL IS AN OUTAGE WITH NO SCREEN THAT EXPLAINS IT.

    The holder is killed mid-hire and never releases. Without expiry this establishment can never
    add an employee again, and the only symptom is a 409 nobody can account for.
    """

    async def run() -> tuple[bool, bool]:
        store = MemoryDataStore()
        await store.claim(S.CLAIMS, "t1:staff.seats", {}, ttl_seconds=15.0, now=1000.0)
        during = await store.claim(S.CLAIMS, "t1:staff.seats", {}, ttl_seconds=15.0, now=1010.0)
        after = await store.claim(S.CLAIMS, "t1:staff.seats", {}, ttl_seconds=15.0, now=1016.0)
        return during, after

    during, after = asyncio.run(run())

    assert during is False, "the lane is held while it is held"
    assert after is True, "and free once the claim has expired"


def test_the_lane_is_released_even_when_the_guard_refuses():
    """A refusal is the ordinary case, not an error path — it must not leave the shop locked."""

    async def run() -> bool:
        store, gauge = MemoryDataStore(), _Gauge(limit=0)
        with pytest.raises(S.SeatLimitReached):
            await _hire(store, gauge, tenant="t1", name="a", now=1000.0)
        # Held again immediately, at the same instant: the release happened, not the expiry.
        return await store.claim(S.CLAIMS, f"t1:{S.SEATS}", {}, ttl_seconds=15.0, now=1000.0)

    assert asyncio.run(run()) is True
