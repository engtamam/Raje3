"""د-19 · the repair only ever swept establishments that already had a balance.

The work list came from `scan_all(BALANCES)`, and a balance row is written by the FIRST POINT EVER
AWARDED. So a shop whose very first visit event was the one the bus dropped has no balance row, is
not in the list, and is invisible to the repair for ever — while the docstring above it claimed it
could find «a shop whose very first visit event was the one that was dropped».

Its first customers are exactly the people who lost their points, and nothing anywhere says so: the
balance reads zero, which is what a new shop's balance reads anyway.

The work list now comes from the visits themselves — `operations` answers with no tenant filter for
precisely this reason — merged with what we already hold.
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    from app.config import get_settings

    saved = dict(os.environ)
    os.environ.update({"ENV": "test", "INTERNAL_SERVICE_TOKEN": "t" * 40,
                       "RATELIMIT_MAX": "1000", "SECRETS_KEK": "unit-test-kek-not-a-real-key"})
    get_settings.cache_clear()
    from app.main import create_app

    yield TestClient(create_app(), raise_server_exceptions=False)
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


class _Feed:
    """The peer read, standing in for `operations`: which shops have visits, and what they are."""

    configured = True

    def __init__(self, tenants: list[str]) -> None:
        self._tenants = tenants
        self.asked: list[str] = []

    async def tenants(self, limit: int = 500) -> list[str]:
        return list(self._tenants)

    async def since(self, tenant: str, mark: int) -> dict:
        self.asked.append(tenant)
        return {"visits": [], "watermark": mark, "more": False}


class _Recovery:
    def __init__(self, feed: _Feed) -> None:
        self._feed = feed
        self.ran: list[str] = []

    async def run(self, tenant: str) -> dict:
        self.ran.append(tenant)
        return {"read": 0, "awarded": 0, "configured": True}


def _push_headers(body: bytes) -> dict[str, str]:
    """A genuine job-service push signature over `body`, verifiable against
    INTERNAL_SERVICE_TOKEN — needed on top of X-Internal-Token since 2026-09-16's push-dispatch
    migration."""
    import hashlib
    import hmac
    import time

    from app.core.push_verify import SIGNATURE_HEADER, TIMESTAMP_HEADER

    ts = int(time.time())
    signed = f"{ts}.".encode("utf-8") + body
    sig = hmac.new(("t" * 40).encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return {SIGNATURE_HEADER: sig, TIMESTAMP_HEADER: str(ts)}


def _recover(client) -> dict:
    r = client.post("/internal/loyalty/recover",
                    headers={"X-Internal-Token": "t" * 40, **_push_headers(b"{}")}, json={})
    assert r.status_code == 200, r.text
    return r.json()


def test_a_shop_with_no_balance_row_is_still_swept(client):
    """THE WHOLE DEFECT. This shop has visits and not one point — which is the state the repair is
    for — and it was the one state the repair could not see."""
    c = client.app.state.container
    feed = _Feed(["t_brand_new"])
    c.visit_feed = feed
    recovery = _Recovery(feed)
    c.recovery = recovery

    out = _recover(client)

    assert recovery.ran == ["t_brand_new"], "a shop whose first event was dropped must be swept"
    assert out["tenants"] == 1


def test_an_unreadable_peer_narrows_the_pass_and_does_not_empty_it(client):
    """A peer we could not reach is «we could not ask», not «nobody has visits». The shops we
    already hold points for must still be walked — their windows still expire."""
    from app.core.models import BALANCES

    c = client.app.state.container
    import asyncio

    asyncio.run(c.datastore.put(BALANCES, "t_known|sub_a",
                                {"id": "t_known|sub_a", "tenant": "t_known", "points": 10}))
    c.visit_feed = _Feed([])          # the peer answered with nothing at all
    recovery = _Recovery(_Feed([]))
    c.recovery = recovery

    _recover(client)

    assert recovery.ran == ["t_known"]


def test_a_shop_is_not_swept_twice_when_it_appears_in_both(client):
    """The lists overlap for every established shop in the product — which is the normal case, not
    the edge one. Sweeping it twice would double every count in the report."""
    from app.core.models import BALANCES

    c = client.app.state.container
    import asyncio

    asyncio.run(c.datastore.put(BALANCES, "t_both|sub_a",
                                {"id": "t_both|sub_a", "tenant": "t_both", "points": 10}))
    c.visit_feed = _Feed(["t_both", "t_new"])
    recovery = _Recovery(_Feed([]))
    c.recovery = recovery

    out = _recover(client)

    assert recovery.ran == ["t_both", "t_new"]
    assert out["tenants"] == 2
