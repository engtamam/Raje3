"""`/goals`'s own "استُخدمت N مرة"/"N وصلهم" — the side counter, wired end to end: a real create
bumps `uses`, a real inline fire bumps `reach`, and the next `/goals` read reflects both without
ever scanning this tenant's campaign history (see app/core/goal_stats.py's own docstring).
"""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

SECRET = "k" * 40
ISS, AUD, TENANT = "iss", "aud", "tnt_goal_stats"


@pytest.fixture()
def client():
    from app.config import get_settings

    saved = dict(os.environ)
    os.environ.update({
        "ENV": "test", "INTERNAL_SERVICE_TOKEN": "t" * 40,
        "TOKEN_VERIFIER_DRIVER": "hs256", "TOKEN_HS256_SECRET": SECRET,
        "TOKEN_ISSUER": ISS, "TOKEN_AUDIENCE": AUD, "RATELIMIT_MAX": "1000",
    })
    get_settings.cache_clear()
    from app.main import create_app

    app = create_app()
    from app.adapters.peers import NullTemplates
    app.state.container.templates = NullTemplates([
        {"type": "mkt_announcement", "name": "mkt_announcement", "fills": ["owner"],
         "body": "{{1}}"},
    ])
    yield TestClient(app, raise_server_exceptions=False)
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


def _auth() -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "u1", "iss": ISS, "aud": AUD, "tenant": TENANT,
                      "caps": ["campaigns.read", "campaigns.manage"],
                      "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


def test_a_never_used_goal_carries_no_stats(client):
    r = client.get("/api/v1/campaigns/goals", headers=_auth())
    assert r.status_code == 200, r.text
    card = next(g for g in r.json()["goals"] if g["goal"] == "announce")
    assert card["uses"] == 0
    assert card["reach"] == 0


def test_a_real_creation_is_counted_as_a_use(client):
    r = client.post("/api/v1/campaigns", json={"goal": "announce", "owner_text": "خبر جديد"},
                    headers=_auth())
    assert r.status_code in (200, 201), r.text

    goals = client.get("/api/v1/campaigns/goals", headers=_auth()).json()["goals"]
    card = next(g for g in goals if g["goal"] == "announce")
    assert card["uses"] == 1


def test_a_second_creation_of_the_same_goal_accumulates(client):
    # DIFFERENT `owner_text` EACH TIME, DELIBERATELY — press.py's own idempotency key is derived
    # from the campaign's fields, so two identical presses are (rightly) one campaign, not two
    # uses; this proves the accumulation across two genuinely DIFFERENT campaigns of one goal.
    for text in ("خبر آخر تماماً", "خبر ثانٍ مختلف كليا"):
        r = client.post("/api/v1/campaigns", json={"goal": "announce", "owner_text": text},
                        headers=_auth())
        assert r.status_code in (200, 201), r.text

    goals = client.get("/api/v1/campaigns/goals", headers=_auth()).json()["goals"]
    card = next(g for g in goals if g["goal"] == "announce")
    assert card["uses"] == 2


def test_a_future_fire_at_still_counts_as_a_use_even_though_nothing_sent_yet(client):
    """Created, handed to job-service for later — a real use of the goal regardless of whether it
    has fired even once."""
    future = int(dt.datetime.now(dt.timezone.utc).timestamp()) + 3600
    r = client.post("/api/v1/campaigns",
                    json={"goal": "announce", "owner_text": "احتفال قادم", "fire_at": future},
                    headers=_auth())
    assert r.status_code in (200, 201), r.text
    assert r.json()["run"] is None

    goals = client.get("/api/v1/campaigns/goals", headers=_auth()).json()["goals"]
    card = next(g for g in goals if g["goal"] == "announce")
    assert card["uses"] == 1
    assert card["reach"] == 0
