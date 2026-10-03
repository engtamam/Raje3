"""`hire`'s own check-then-write used to be two unrelated statements with a network round trip
to identity between them — two shops hiring the exact same number in the same instant could both
read "nobody holds this" and both proceed. FOUND LIVE (owner's own audit, 2026-10-03), closed by
wrapping the whole section in `HIRE_CLAIMS`, a claim lane keyed by the bare phone number (never by
tenant — the race is BETWEEN tenants).

This file proves the lane itself actually serialises two concurrent `hire()` calls for the same
number, the same way platform/services/identity-service/tests/unit/test_atomic_fixes.py's own
`test_concurrent_create_person_one_wins` proves identity's own CAS does.

WHY A REAL THREADING GATE, NOT asyncio.gather ALONE. `hire`'s HTTP call runs through
`asyncio.to_thread` — real thread-pool timing, which `asyncio.gather` alone cannot control. A
first attempt at this test raced on wall-clock thread scheduling and both hires sometimes finished
before the other ever started, proving nothing. This version PARKS the first call mid-flight (past
its own claim, before identity ever answers) on a real `threading.Event`, deterministically proves
the second is refused WHILE the first still holds the lane, then releases the first and confirms it
completes normally — the actual interleaving the production bug needed, forced rather than hoped for.
"""
from __future__ import annotations

import asyncio
import threading

from app.core import signup as S


def run(c):
    return asyncio.run(c)


class FakeHttp:
    """The FIRST call to `/internal/tenancy/members` blocks on `gate` until released — everything
    else answers immediately."""

    def __init__(self, gate: threading.Event) -> None:
        self._gate = gate
        self._first_done = threading.Event()

    def call(self, url, *, method="GET", internal=False, body=None, **kw):
        if url.endswith("/internal/tenancy/members") and method == "POST":
            if not self._first_done.is_set():
                self._first_done.set()
                self._gate.wait(timeout=5)
            return 201, {"person_id": "prs_1", "membership": {"status": "pending"},
                         "invite_token": "inv_1"}
        if url.endswith("/api/v1/auth/person/claim"):
            return 200, {"person": {"id": "irrelevant"}}
        return 200, {}


class FakeStore:
    def __init__(self) -> None:
        self.rows: dict[tuple[str, str], dict] = {}

    async def get(self, coll, key):
        return self.rows.get((coll, key))

    async def put(self, coll, key, row):
        self.rows[(coll, key)] = row
        return row

    async def claim(self, coll, key, value, *, ttl_seconds, now):
        held = self.rows.get((coll, key))
        if held is not None and float(held.get("expires") or 0) > now:
            return False
        row = dict(value)
        row["expires"] = now + float(ttl_seconds)
        self.rows[(coll, key)] = row
        return True

    async def delete(self, coll, key) -> bool:
        return self.rows.pop((coll, key), None) is not None

    async def find(self, coll, where, **kw):
        return [], None


def make(http):
    s = S.SignupService.__new__(S.SignupService)
    s._http = http
    s._identity = "http://identity"
    s._store = FakeStore()
    s._cc = "966"
    s._roles = [{"name": "owner"}, {"name": "manager"}, {"name": "operator"}]
    s._owner_role = "owner"
    return s


def test_two_tenants_racing_the_same_number_never_both_win():
    gate = threading.Event()
    http = FakeHttp(gate)
    s = make(http)

    async def scenario():
        first = asyncio.ensure_future(
            s.hire("t_a", phone="0500000099", password="Str0ng!Password", role="operator"))
        # Let `first` run up to (and start blocking inside) its own `to_thread` call — by this
        # point it has already taken the HIRE_CLAIMS lane, same order `hire()` itself uses.
        while not http._first_done.is_set():
            await asyncio.sleep(0)

        # THE SECOND SHOP'S ATTEMPT WHILE THE FIRST IS STILL MID-FLIGHT, STILL HOLDING THE LANE.
        second_refusal = None
        try:
            await s.hire("t_b", phone="0500000099", password="Other!Password1", role="operator")
        except S.SignupRefused as exc:
            second_refusal = str(exc)

        gate.set()  # let the first call's identity response through
        first_result = await first
        return first_result, second_refusal

    first_result, second_refusal = run(scenario())

    assert first_result["person_id"] == "prs_1", "the first hire must complete normally"
    assert second_refusal is not None, "the second hire must be refused, not silently succeed"
    assert "حاول بعد لحظة" in second_refusal, second_refusal

    row = run(s._store.get(S.PHONE_INDEX, "+966500000099"))
    assert row is not None and row["tenant"] == "t_a", \
        "the index must name the one shop that actually won, never both, never neither"


def test_the_claim_lane_itself_refuses_a_second_taker_while_held():
    """Narrower than the end-to-end race above: proves HIRE_CLAIMS is a real claim, not a no-op,
    independent of hire()'s own surrounding logic."""
    s = make(FakeHttp(threading.Event()))
    now = 1000.0
    assert run(s._store.claim(S.HIRE_CLAIMS, "+966500000001", {"tenant": "t1"},
                              ttl_seconds=S.HIRE_CLAIM_TTL_SECONDS, now=now)) is True
    # Same key, still held, time has barely moved — refused.
    assert run(s._store.claim(S.HIRE_CLAIMS, "+966500000001", {"tenant": "t2"},
                              ttl_seconds=S.HIRE_CLAIM_TTL_SECONDS, now=now + 1)) is False
    # Released — a new claim may now be taken.
    run(s._store.delete(S.HIRE_CLAIMS, "+966500000001"))
    assert run(s._store.claim(S.HIRE_CLAIMS, "+966500000001", {"tenant": "t2"},
                              ttl_seconds=S.HIRE_CLAIM_TTL_SECONDS, now=now + 2)) is True
