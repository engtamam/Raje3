"""The owner's own time window (2026-09-12) — offer goals only, checked at creation, at preview,
and re-checked on every dispatch pass.
"""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

SECRET = "h" * 40
ISS = "iss"
AUD = "aud"


@pytest.fixture
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
        {"type": "mkt_offer", "name": "mkt_offer",
         "fills": ["system", "system", "amount", "catalogue", "date"],
         "variables": [1, 2, 3, 4, 5],
         "body": "{{1}} — {{2}}: خصم {{3}} على {{4}} حتى {{5}}"},
        {"type": "mkt_announcement", "name": "mkt_announcement", "fills": ["owner"],
         "body": "{{1}} — {{2}}"},
    ])
    yield app, TestClient(app, raise_server_exceptions=False)
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


def _auth(tenant="tnt_window"):
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "u1", "iss": ISS, "aud": AUD, "tenant": tenant,
                      "caps": ["campaigns.read", "campaigns.manage"],
                      "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


def _offer_body(**over):
    body = {"goal": "service_offer", "owner_text": "", "service_id": "svc1",
           "service_name": "غسيل السيارة", "offer_value": "20%",
           "expires_at": int(dt.datetime.now(dt.timezone.utc).timestamp()) + 604_800}
    body.update(over)
    return body


def test_a_non_offer_goal_may_also_carry_a_window(client):
    # 2026-09-12 revision — the owner's own correction: an announcement wanting to go out only
    # Thursday/Friday for a weekend opening is as real a want as an offer's own hours. Every goal
    # may set a window now; only its coherence is checked, never its goal.
    _, http = client
    body = {"goal": "announce", "owner_text": "افتتحنا اليوم", "window_start_hour": 8,
           "window_end_hour": 20}
    r = http.post("/api/v1/campaigns", json=body, headers=_auth())
    assert r.status_code in (200, 201), r.text


def test_an_incoherent_window_is_refused_at_creation(client):
    _, http = client
    r = http.post("/api/v1/campaigns", json=_offer_body(window_start_hour=20, window_end_hour=8),
                  headers=_auth())
    assert r.status_code == 400
    assert r.json()["error"] == "BAD_REQUEST"


def test_an_incoherent_window_is_also_refused_at_preview(client):
    _, http = client
    r = http.post("/api/v1/campaigns/preview",
                  json=_offer_body(window_start_hour=20, window_end_hour=8), headers=_auth())
    assert r.status_code == 400


def test_a_coherent_window_is_stored_on_the_campaign(client):
    _, http = client
    r = http.post("/api/v1/campaigns", json=_offer_body(window_start_hour=8, window_end_hour=20,
                                                        window_weekdays=[4, 5]), headers=_auth())
    assert r.status_code in (200, 201), r.text
    cid = (r.json().get("campaign") or r.json()).get("id")
    listed = http.get("/api/v1/campaigns", headers=_auth())
    row = next(c for c in listed.json()["campaigns"] if c["id"] == cid)
    assert row["window_start_hour"] == 8
    assert row["window_end_hour"] == 20
    assert row["window_weekdays"] == [4, 5]


def test_the_preview_names_the_window_in_the_owner_s_own_words(client):
    _, http = client
    r = http.post("/api/v1/campaigns/preview",
                  json=_offer_body(window_start_hour=8, window_end_hour=20), headers=_auth())
    assert r.status_code == 200, r.text
    assert "8" in r.json()["when"] and "20" in r.json()["when"]


def test_a_campaign_created_outside_its_own_window_stays_active_not_stranded(client):
    """The real regression: creation used to stamp `last_evaluated` unconditionally after the
    inline manual fire, even when that fire sent nothing because the window refused it — which
    silenced tick.py's own manual-rescue (`last_evaluated == 0`) forever. A campaign born outside
    its window must remain retryable by the ordinary 15-minute tick once the window opens."""
    _, http = client
    # A window that cannot possibly contain "now" — refuses at every hour of every day, so the
    # inline fire is guaranteed to skip regardless of when this test runs.
    r = http.post("/api/v1/campaigns", json=_offer_body(window_start_hour=0, window_end_hour=1),
                  headers=_auth())
    assert r.status_code in (200, 201), r.text
    body = r.json()
    cid = (body.get("campaign") or body).get("id")
    assert body.get("run") is None or body["run"]["sent"] == 0

    listed = http.get("/api/v1/campaigns", headers=_auth())
    row = next(c for c in listed.json()["campaigns"] if c["id"] == cid)
    assert row["state"] == "active"
    assert row["last_evaluated"] == 0
