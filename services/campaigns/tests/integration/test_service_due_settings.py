"""«حان وقت الخدمة»'s own settings record (2026-09-13) — on/off and reward choice, never a
launched campaign. Proves: the public route upserts one row per tenant, the internal route
reminders will call answers the right defaults and the right custom values, and a `gift` reward
(disallowed for this goal — see service_due_settings.py's own note) is refused.
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
INTERNAL_TOKEN = "t" * 40


@pytest.fixture
def client():
    from app.config import get_settings

    saved = dict(os.environ)
    os.environ.update({
        "ENV": "test", "INTERNAL_SERVICE_TOKEN": INTERNAL_TOKEN,
        "TOKEN_VERIFIER_DRIVER": "hs256", "TOKEN_HS256_SECRET": SECRET,
        "TOKEN_ISSUER": ISS, "TOKEN_AUDIENCE": AUD, "RATELIMIT_MAX": "1000",
    })
    get_settings.cache_clear()
    from app.main import create_app

    app = create_app()
    yield app, TestClient(app, raise_server_exceptions=False)
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


def _auth(tenant="tnt_due"):
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "u1", "iss": ISS, "aud": AUD, "tenant": tenant,
                      "caps": ["campaigns.read", "campaigns.manage"],
                      "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


def test_a_tenant_that_never_touched_it_reads_todays_untouched_default(client):
    _app, http = client
    r = http.get("/api/v1/campaigns/service-due-settings", headers=_auth("tnt_fresh"))
    assert r.status_code == 200, r.text
    assert r.json() == {"active": True, "reward_type": "discount", "reward_points": 0}


def test_the_internal_route_matches_the_owner_facing_default_for_an_untouched_tenant(client):
    _app, http = client
    r = http.get("/internal/campaigns/service-due-settings",
                params={"tenant": "tnt_fresh_2"},
                headers={"X-Internal-Token": INTERNAL_TOKEN})
    assert r.status_code == 200, r.text
    assert r.json() == {"active": True, "reward_type": "discount", "reward_points": 0}


def test_turning_it_off_is_read_back_by_the_owner_and_by_the_internal_route(client):
    _app, http = client
    tenant = "tnt_off"
    r = http.put("/api/v1/campaigns/service-due-settings",
                json={"active": False}, headers=_auth(tenant))
    assert r.status_code == 200, r.text
    assert r.json()["active"] is False

    own = http.get("/api/v1/campaigns/service-due-settings", headers=_auth(tenant))
    assert own.json()["active"] is False

    internal = http.get("/internal/campaigns/service-due-settings", params={"tenant": tenant},
                        headers={"X-Internal-Token": INTERNAL_TOKEN})
    assert internal.json() == {"active": False, "reward_type": "discount", "reward_points": 0}


def test_a_points_reward_is_stored_and_read_back(client):
    _app, http = client
    tenant = "tnt_points"
    r = http.put("/api/v1/campaigns/service-due-settings",
                json={"active": True, "reward_type": "points", "reward_points": 15},
                headers=_auth(tenant))
    assert r.status_code == 200, r.text
    assert r.json() == {"active": True, "reward_type": "points", "reward_points": 15}

    internal = http.get("/internal/campaigns/service-due-settings", params={"tenant": tenant},
                        headers={"X-Internal-Token": INTERNAL_TOKEN})
    assert internal.json() == {"active": True, "reward_type": "points", "reward_points": 15}


def test_a_points_reward_with_no_points_is_refused(client):
    _app, http = client
    r = http.put("/api/v1/campaigns/service-due-settings",
                json={"active": True, "reward_type": "points", "reward_points": 0},
                headers=_auth("tnt_bad_points"))
    assert r.status_code == 400
    assert r.json()["error"] == "BAD_REQUEST"


def test_a_gift_reward_is_refused_for_this_goal(client):
    """`gift` is not in `service_due_settings.REWARD_TYPES` — see its own docstring on why a
    reminder about one specific service does not also gift that same service."""
    _app, http = client
    r = http.put("/api/v1/campaigns/service-due-settings",
                json={"active": True, "reward_type": "gift"},
                headers=_auth("tnt_gift"))
    assert r.status_code == 400
    assert r.json()["error"] == "BAD_REQUEST"


def test_a_second_save_upserts_the_same_row_rather_than_creating_a_second_one(client):
    _app, http = client
    tenant = "tnt_upsert"
    http.put("/api/v1/campaigns/service-due-settings", json={"active": False},
            headers=_auth(tenant))
    http.put("/api/v1/campaigns/service-due-settings",
            json={"active": True, "reward_type": "points", "reward_points": 5},
            headers=_auth(tenant))
    listed = http.get("/api/v1/campaigns", headers=_auth(tenant))
    rows = [c for c in listed.json()["campaigns"] if c["goal"] == "service_due"]
    assert len(rows) == 1
    assert rows[0]["reward_points"] == 5


def test_the_internal_route_without_a_token_is_refused(client):
    _app, http = client
    r = http.get("/internal/campaigns/service-due-settings", params={"tenant": "tnt_due"})
    assert r.status_code == 401
