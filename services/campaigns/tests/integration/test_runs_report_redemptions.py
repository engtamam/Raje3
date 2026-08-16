"""ط-3: «كم واحداً رجع وصرف؟» — the run report's totals never answered it.

`campaign_reached` already names every recipient a campaign sent to and when; operations already
records every offer spend on the visit it happened on. `GET /campaigns/{id}/runs` is where the two
had to meet — the totals block whose own comment already promised «this campaign has brought back
61 customers» and never computed one.
"""
from __future__ import annotations

import datetime as dt
import os
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient

SECRET = "h" * 40
ISS, AUD = "iss", "aud"
TENANT = "tnt_redeemed_report"
CAPS = ["campaigns.read", "campaigns.manage"]


class FakeAudience:
    """Stands in for operations — the peer `redeemed()` actually calls."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.answer = 0

    async def customers(self, tenant, *, service_id="", branch_id=""):
        return []

    async def allows(self, tenant, subject_ref, cls):
        return True

    async def redeemed(self, tenant, reached):
        self.calls.append({"tenant": tenant, "reached": reached})
        return self.answer


@pytest.fixture()
def client():
    from app.config import get_settings

    saved = dict(os.environ)
    os.environ.update({
        "ENV": "test",
        "INTERNAL_SERVICE_TOKEN": "t" * 40,
        "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": SECRET,
        "TOKEN_ISSUER": ISS,
        "TOKEN_AUDIENCE": AUD,
        "RATELIMIT_MAX": "1000",
    })
    get_settings.cache_clear()
    from app.main import create_app

    app = create_app()
    fake = FakeAudience()
    # THE FACADE WRAPS WHATEVER `peers["audience"]` IS — see container.py's `_AudienceFacade`.
    # Swapping the client it holds, not the facade, keeps `resolve_for`'s own wiring untouched.
    app.state.container.audience._c = fake
    app.state.audience_fake = fake
    yield TestClient(app, raise_server_exceptions=False)
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


def _auth(tenant=TENANT):
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "u1", "iss": ISS, "aud": AUD, "tenant": tenant,
                      "caps": CAPS, "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


async def _seed_reached(app, tenant: str, campaign_id: str, rows: list[tuple[str, int]]) -> None:
    ds = app.state.container.datastore
    for subject_ref, at in rows:
        key = f"{tenant}|{campaign_id}|{subject_ref}"
        await ds.put("campaign_reached", key, {
            "id": key, "tenant": tenant, "campaign_id": campaign_id,
            "subject_ref": subject_ref, "at": at})


def test_totals_carries_how_many_of_the_reached_actually_redeemed(client):
    import asyncio

    app = client.app
    app.state.audience_fake.answer = 7
    asyncio.run(_seed_reached(app, TENANT, "cmp_1",
                              [("subj_a", 1000), ("subj_b", 1200)]))

    r = client.get("/api/v1/campaigns/cmp_1/runs", headers=_auth())
    assert r.status_code == 200, r.text
    assert r.json()["totals"]["redeemed"] == 7


def test_asks_the_peer_with_who_this_campaign_reached_and_when(client):
    import asyncio

    app = client.app
    asyncio.run(_seed_reached(app, TENANT, "cmp_2", [("subj_x", 555)]))

    client.get("/api/v1/campaigns/cmp_2/runs", headers=_auth())

    calls = app.state.audience_fake.calls
    assert calls, 'the route never asked "who did we reach and when"'
    reached = calls[-1]["reached"]
    assert {"subject_ref": "subj_x", "since": 555} in reached


def test_a_campaign_nobody_was_reached_by_yet_never_calls_the_peer(client):
    r = client.get("/api/v1/campaigns/cmp_never_ran/runs", headers=_auth())
    assert r.status_code == 200, r.text
    assert r.json()["totals"]["redeemed"] == 0
    assert client.app.state.audience_fake.calls == []
