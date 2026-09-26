"""`POST /campaigns` and `/preview`, for the "جماعي" goal — the create/preview surface the shared
counter (core/milestone.py) needed to become usable through the same screens every other goal
already has, rather than only reachable by writing a row directly.
"""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest

SECRET = "m" * 40
ISS, AUD = "iss", "aud"
TENANT = "tnt_milestone"


@pytest.fixture(scope="module")
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
    from fastapi.testclient import TestClient

    app = create_app()
    from app.adapters.peers import NullTemplates
    app.state.container.templates = NullTemplates([
        {"type": "mkt_community_milestone", "name": "mkt_community_milestone",
         "fills": ["reward"], "variables": [3], "body": "وصلنا الهدف! {{3}}"},
    ])
    yield TestClient(app, raise_server_exceptions=False)
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


def _auth(caps=("campaigns.read", "campaigns.manage")):
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "u1", "iss": ISS, "aud": AUD, "tenant": TENANT,
                      "caps": list(caps), "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


def _body(**kw):
    body = {"goal": "community_milestone", "milestone_threshold": 100,
           "reward_type": "discount", "offer_value": "20%"}
    body.update(kw)
    return body


# ── preview ───────────────────────────────────────────────────────────────────────────────────
def test_preview_never_matches_real_customers_for_a_milestone_goal(client):
    r = client.post("/api/v1/campaigns/preview", json=_body(), headers=_auth())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["reaches"] == 0
    assert body["excluded"] == 0
    assert body["truncated"] is False


def test_preview_describes_waiting_for_the_shared_goal_not_sending_now(client):
    r = client.post("/api/v1/campaigns/preview", json=_body(), headers=_auth())
    assert r.status_code == 200, r.text
    assert "دفعة واحدة" in r.json()["when"]


def test_preview_refuses_a_threshold_below_the_minimum(client):
    r = client.post("/api/v1/campaigns/preview", json=_body(milestone_threshold=1),
                    headers=_auth())
    assert r.status_code == 400, r.text
    assert r.json()["error"] == "BAD_REQUEST"


def test_preview_still_composes_the_reward_sentence(client):
    r = client.post("/api/v1/campaigns/preview", json=_body(), headers=_auth())
    assert r.status_code == 200, r.text
    assert "20%" in r.json()["message"]


# ── create ────────────────────────────────────────────────────────────────────────────────────
def test_creating_a_milestone_campaign_stores_its_threshold(client):
    r = client.post("/api/v1/campaigns", json=_body(milestone_threshold=50), headers=_auth())
    assert r.status_code in (200, 201), r.text
    cid = (r.json().get("campaign") or r.json()).get("id")

    listed = client.get("/api/v1/campaigns", headers=_auth())
    row = next(c for c in listed.json()["campaigns"] if c["id"] == cid)
    assert row["milestone_threshold"] == 50
    assert row["trigger"] == "milestone"
    assert row["state"] == "active"


def test_creating_a_milestone_campaign_never_fires_inline(client):
    """Unlike a `manual` goal — a milestone campaign accumulates; nothing is sent at creation,
    regardless of how many real customers already exist."""
    r = client.post("/api/v1/campaigns", json=_body(milestone_threshold=50), headers=_auth())
    assert r.status_code in (200, 201), r.text
    assert r.json()["run"] is None


def test_create_refuses_a_threshold_below_the_minimum(client):
    r = client.post("/api/v1/campaigns", json=_body(milestone_threshold=1), headers=_auth())
    assert r.status_code == 400, r.text
    assert r.json()["error"] == "BAD_REQUEST"


def test_create_refuses_with_no_active_template(client):
    from app.adapters.peers import NullTemplates
    empty_templates = client.app.state.container.templates
    client.app.state.container.templates = NullTemplates([])
    try:
        r = client.post("/api/v1/campaigns", json=_body(), headers=_auth())
        assert r.status_code == 400, r.text
    finally:
        client.app.state.container.templates = empty_templates


def test_two_different_thresholds_are_two_different_campaigns_not_one_repress(client):
    """press.key_for's own milestone_threshold join — two distinct milestone campaigns with
    every other field identical must not collide onto the same idempotency key."""
    r1 = client.post("/api/v1/campaigns", json=_body(milestone_threshold=50), headers=_auth())
    r2 = client.post("/api/v1/campaigns", json=_body(milestone_threshold=75), headers=_auth())
    assert r1.status_code in (200, 201) and r2.status_code in (200, 201)
    id1 = (r1.json().get("campaign") or r1.json()).get("id")
    id2 = (r2.json().get("campaign") or r2.json()).get("id")
    assert id1 != id2


def test_a_repeated_press_with_the_same_threshold_is_the_same_campaign(client):
    r1 = client.post("/api/v1/campaigns",
                     json=_body(milestone_threshold=63, owner_text=""), headers=_auth())
    r2 = client.post("/api/v1/campaigns",
                     json=_body(milestone_threshold=63, owner_text=""), headers=_auth())
    id1 = (r1.json().get("campaign") or r1.json()).get("id")
    id2 = (r2.json().get("campaign") or r2.json()).get("id")
    assert id1 == id2
    assert r2.json().get("duplicate") is True
