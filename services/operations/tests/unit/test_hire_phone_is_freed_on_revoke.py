"""A dismissed employee's phone number must not be locked out of the whole platform forever.

FOUND LIVE (owner's own report, 2026-10-03), not by any test — the closest-named test used a
fake `signup` double that never touched `PHONE_INDEX` at all, so this exact gap went unverified.

`hire` writes `PHONE_INDEX` so our own sign-in can resolve a phone number to its tenant.
`revoke` deleted the membership at identity but never touched that index — so `tenant_of_phone`
kept answering the OLD tenant for a number forever, and a second `hire` (anywhere, including the
very same tenant trying to rehire him) refused with «هذا الرقم مسجّل في منشأة أخرى», with no
self-service way out.
"""
from __future__ import annotations

import asyncio

import pytest

from app.core import signup as S


def run(c):
    return asyncio.run(c)


class FakeHttp:
    """Answers the three identity routes hire/revoke touch, with a stable person_id per phone."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict]] = []
        self._next = 1

    def call(self, url, *, method="GET", internal=False, body=None, **kw):
        self.calls.append((method, url, dict(body or {})))
        if url.endswith("/internal/tenancy/members") and method == "POST":
            pid = f"prs_{self._next}"
            self._next += 1
            return 201, {"person_id": pid, "membership": {"status": "pending"},
                         "invite_token": f"inv_{pid}"}
        if url.endswith("/api/v1/auth/person/claim"):
            return 200, {"person": {"id": "irrelevant"}}
        if "/internal/tenancy/membership/" in url and method == "DELETE":
            return 204, {}
        return 200, {}


class FakeStore:
    def __init__(self) -> None:
        self.rows: dict[tuple[str, str], dict] = {}

    async def get(self, coll, key):
        return self.rows.get((coll, key))

    async def put(self, coll, key, row):
        self.rows[(coll, key)] = row
        return row

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


def test_a_second_shop_cannot_hire_a_number_already_active_elsewhere():
    http = FakeHttp()
    s = make(http)
    run(s.hire("t_first", phone="0500000010", password="Str0ng!Password", role="operator"))

    with pytest.raises(S.SignupRefused, match="منشأة أخرى"):
        run(s.hire("t_second", phone="0500000010", password="Other!Password1", role="operator"))


def test_revoke_frees_the_number_so_a_different_shop_can_hire_him_next():
    http = FakeHttp()
    s = make(http)
    got = run(s.hire("t_first", phone="0500000011", password="Str0ng!Password", role="operator"))

    # Confirmed blocked while still active at the first shop.
    with pytest.raises(S.SignupRefused, match="منشأة أخرى"):
        run(s.hire("t_second", phone="0500000011", password="Other!Password1", role="operator"))

    ok = run(s.revoke("t_first", got["person_id"], phone="0500000011"))
    assert ok is True

    # THE WHOLE POINT: a different shop can now hire the same number — he is not locked out of
    # the platform forever just because he was let go from the first one.
    second = run(s.hire("t_second", phone="0500000011", password="Other!Password1", role="operator"))
    assert second["person_id"], "the second hire must actually go through, not silently no-op"


def test_revoke_never_deletes_a_number_re_claimed_by_someone_else_in_the_meantime():
    """If the number was already re-hired elsewhere by the time an interrupted dismissal is
    retried, that NEW claim must survive — deleting it here would un-register a live, unrelated
    account for the sentence "undo what I did"."""
    http = FakeHttp()
    s = make(http)
    first = run(s.hire("t_first", phone="0500000012", password="Str0ng!Password", role="operator"))

    # Someone else's dismissal process already freed it and a second shop re-claimed it for real
    # (simulated directly: revoke at t_first, then hire at t_second).
    run(s.revoke("t_first", first["person_id"], phone="0500000012"))
    run(s.hire("t_second", phone="0500000012", password="Other!Password1", role="operator"))

    # A late/retried revoke for the ORIGINAL (t_first) dismissal must not touch t_second's claim.
    run(s.revoke("t_first", first["person_id"], phone="0500000012"))
    row = run(s._store.get(S.PHONE_INDEX, "+966500000012"))
    assert row is not None and row["tenant"] == "t_second", \
        "a stale revoke for the old tenant must never delete a different tenant's live claim"
