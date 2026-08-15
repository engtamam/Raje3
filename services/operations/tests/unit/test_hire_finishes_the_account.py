"""Hiring must produce an employee who can actually SIGN IN.

FOUND ON THE CLUSTER, NOT BY ANY TEST — which is the point of this file. identity answers
`POST /internal/tenancy/members` with 201, a `person_id`, a membership whose status is **pending**,
and an `invite_token`. A pending membership cannot mint: `/auth/tenant` answers 401 to a perfectly
correct password.

So the whole path reported success — the owner saw «تمت الإضافة», the employee appeared in «فريقي»
with his role and his branch, the seat was counted — and the man could not open the app. And the
feature that depends on employees having accounts (branch visibility, §12.4) was therefore
inert in production while every test stayed green.
"""
from __future__ import annotations

import asyncio

import pytest

from app.core import signup as S


def run(c):
    return asyncio.run(c)


class FakeHttp:
    """Records every call, and answers the two identity routes hire touches."""

    def __init__(self, *, claim_status: int = 200) -> None:
        self.calls: list[tuple[str, dict]] = []
        self._claim_status = claim_status

    def call(self, url, *, method="GET", internal=False, body=None, **kw):
        self.calls.append((url, dict(body or {})))
        if url.endswith("/internal/tenancy/members"):
            return 201, {"person_id": "prs_1", "tenant": "t1",
                         "membership": {"status": "pending", "person_id": "prs_1"},
                         "invite_token": "inv_tok_1"}
        if url.endswith("/api/v1/auth/person/claim"):
            return self._claim_status, ({"person": {"id": "prs_1"}}
                                        if self._claim_status == 200 else {})
        return 200, {}


class FakeStore:
    def __init__(self) -> None:
        self.rows: dict[tuple[str, str], dict] = {}

    async def get(self, coll, key):
        return self.rows.get((coll, key))

    async def put(self, coll, key, row):
        self.rows[(coll, key)] = row
        return row

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


def test_hiring_redeems_the_invite_so_the_employee_can_sign_in():
    http = FakeHttp()
    s = make(http)
    got = run(s.hire("t1", phone="0500000001", password="Str0ng!Password", role="operator"))

    assert got["person_id"] == "prs_1"
    claims = [(u, b) for (u, b) in http.calls if u.endswith("/auth/person/claim")]
    assert claims, "the invite was never redeemed — the membership stays pending and 401s"
    url, body = claims[0]
    assert body["token"] == "inv_tok_1"
    # THE OWNER'S PASSWORD, not a second one. He is standing next to the employee and is about to
    # hand it over; a password the employee never receives is the same locked door.
    assert body["password"] == "Str0ng!Password"


def test_a_failed_claim_is_a_refusal_rather_than_a_half_hire():
    """Half a hire is worse than none: the seat is counted, the row is in the list, and the man
    cannot work — with nothing on the screen saying so."""
    http = FakeHttp(claim_status=400)
    s = make(http)
    with pytest.raises(S.SignupRefused):
        run(s.hire("t1", phone="0500000002", password="Str0ng!Password", role="operator"))
