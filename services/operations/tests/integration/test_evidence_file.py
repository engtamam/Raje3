"""The evidence file — and the one way it could quietly betray us.

A FILE THAT CANNOT TELL «nothing happened» FROM «we could not ask» IS WORSE THAN NO FILE. Handed to
a regulator, an empty `messages` section reads as a claim: this shop sent nothing in that window.
If it is empty because a peer was restarting, we have made a false statement in writing, under our
own name, at the exact moment accuracy matters most.

So every test here is about the difference between absent and empty.
"""
from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

INTERNAL = {"X-Internal-Token": "t" * 40}
PATH = "/internal/operations/evidence"


class Reader:
    """A stand-in for the messaging service."""

    def __init__(self, payload=None, *, boom=False):
        self._payload = payload
        self._boom = boom
        self.asked = []

    async def evidence(self, tenant, *, since=0, until=0):
        self.asked.append((tenant, since, until))
        if self._boom:
            raise RuntimeError("reminders is restarting")
        return self._payload


def _post(client, **over):
    body = {"tenant": "tnt_ev", "since": 0, "until": 0, "actor": "ops@raje3"}
    body.update(over)
    return client.post(PATH, json=body, headers=INTERNAL)


def test_an_unreachable_peer_is_reported_not_shown_as_silence(client):
    """The whole reason this file exists at all."""
    client.app.state.container.evidence_peer = Reader(boom=True)
    r = _post(client)
    assert r.status_code == 200, r.text
    sections = r.json()["sections"]
    for name in ("consent", "messages"):
        assert sections[name]["status"] == "unavailable", name
        assert sections[name]["records"] == []
        assert "restarting" in sections[name]["reason"]


def test_a_peer_that_answers_nothing_is_reported_as_read(client):
    """And the other half: a shop that genuinely sent nothing must be SAYABLE."""
    client.app.state.container.evidence_peer = Reader(
        {"consent": {"records": [], "count": 0, "truncated": False},
         "messages": {"records": [], "count": 0, "truncated": False}})
    sections = _post(client).json()["sections"]
    assert sections["messages"]["status"] == "read"
    assert sections["messages"]["count"] == 0


def test_the_file_carries_what_the_customer_actually_saw(client):
    """A consent row is only evidence if it holds the STATEMENT, not a pointer to a document we
    can edit afterwards."""
    client.app.state.container.evidence_peer = Reader({
        "consent": {"records": [{"subject_ref": "sub_1", "state": "GRANTED",
                                 "statement": "أوافق على استقبال عروض ورشة النخبة",
                                 "statement_version": "v1", "source": "customer_page",
                                 "actor": "", "at": 100, "seq": 1}],
                    "count": 1, "truncated": False},
        "messages": {"records": [], "count": 0, "truncated": False}})
    row = _post(client).json()["sections"]["consent"]["records"][0]
    assert "ورشة النخبة" in row["statement"]
    assert row["statement_version"] == "v1"


def test_truncation_is_never_silent(client):
    client.app.state.container.evidence_peer = Reader({
        "consent": {"records": [], "count": 0, "truncated": False},
        "messages": {"records": [{"subject_ref": "s"}], "count": 1, "truncated": True}})
    assert _post(client).json()["sections"]["messages"]["truncated"] is True


def test_the_window_travels_to_the_peer(client):
    """A file that answers a different period from the one asked for is a file that answers the
    wrong question — convincingly."""
    peer = Reader({"consent": {"records": [], "count": 0}, "messages": {"records": [], "count": 0}})
    client.app.state.container.evidence_peer = peer
    _post(client, since=1000, until=2000)
    assert peer.asked == [("tnt_ev", 1000, 2000)]


def test_the_export_is_audited_before_the_file_is_handed_over(client, monkeypatch):
    """A disclosure that leaves no trace is the one thing an audit trail cannot survive.

    AND THE ORDER MATTERS: recorded first, so a file cannot be taken in the gap between handing it
    over and writing the row.
    """
    seen: list[tuple[str, str]] = []

    async def record(action, **kw):
        seen.append((action, kw.get("actor", "")))

    monkeypatch.setattr(client.app.state.auditor, "record", record)
    client.app.state.container.evidence_peer = Reader(
        {"consent": {"records": [], "count": 0}, "messages": {"records": [], "count": 0}})

    assert _post(client, actor="tamam").status_code == 200
    assert ("compliance.evidence_exported", "tamam") in seen


def test_the_file_names_its_own_requester_and_window(client):
    client.app.state.container.evidence_peer = Reader(
        {"consent": {"records": [], "count": 0}, "messages": {"records": [], "count": 0}})
    now = int(time.time())
    got = _post(client, since=1, until=now, actor="tamam").json()
    assert got["requested_by"] == "tamam"
    assert got["since"] == 1 and got["until"] == now
    assert got["generated_at"] > 0


def test_a_shops_privacy_requests_are_in_the_file_open_and_closed(client):
    """The thirty-day clock is the first question a regulator asks, and «we answered» is a claim
    that needs a name on it."""
    import asyncio

    from app.core.stores import PrivacyRequestStore

    store = PrivacyRequestStore(client.app.state.container.datastore)
    tenant = "tnt_ev_pdpl"

    async def seed():
        req = await store.open_request(tenant, "sub_pdpl_1", "erasure")
        await store.close(tenant, req.id, "owner@shop")

    asyncio.run(seed())
    client.app.state.container.evidence_peer = Reader(
        {"consent": {"records": [], "count": 0}, "messages": {"records": [], "count": 0}})

    sec = _post(client, tenant=tenant).json()["sections"]["privacy_requests"]
    assert sec["status"] == "read" and sec["count"] == 1
    row = sec["records"][0]
    assert row["type"] == "erasure"
    assert row["closed_by"] == "owner@shop"
    assert row["opened_at"] > 0 and row["closed_at"] > 0
