"""POST/GET /api/v1/referrals/campaigns[...] — real HTTP: auth, capability RBAC, tenant scoping,
and the win-win/immutability rules enforced end-to-end through the actual route, not just the
service layer test_campaigns.py already covers in isolation."""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

SECRET = "h" * 40
ISS = "iss"
AUD = "aud"


def _make_app() -> TestClient:
    from app.config import get_settings

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

    return TestClient(create_app(), raise_server_exceptions=False)


@pytest.fixture(scope="module")
def auth_env():
    from app.config import get_settings

    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


@pytest.fixture(scope="module")
def client(auth_env) -> TestClient:
    return _make_app()


def _token(*, tenant: str, caps=("referrals.manage",)) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    claims = {"sub": "owner-1", "iss": ISS, "aud": AUD, "tenant": tenant,
              "exp": now + dt.timedelta(minutes=5), "iat": now, "caps": list(caps)}
    return jwt.encode(claims, SECRET, algorithm="HS256")


def _auth(**kw) -> dict:
    return {"Authorization": f"Bearer {_token(**kw)}"}


_WIN_WIN = {"new_customer_reward_type": "discount_percent",
            "new_customer_reward_params": {"percent": 10}}


def _campaign_body(**over) -> dict:
    body = {"mode": "once", "reward_type": "fixed_points", "reward_params": {"points": 50}}
    body.update(_WIN_WIN)
    body.update(over)
    return body


# ── auth / capability RBAC ───────────────────────────────────────────────────────────────────────
def test_no_token_is_401(client):
    assert client.post("/api/v1/referrals/campaigns", json=_campaign_body()).status_code == 401


def test_token_without_the_capability_is_403(client):
    r = client.post("/api/v1/referrals/campaigns", json=_campaign_body(),
                    headers=_auth(tenant="shop-a", caps=("something.else",)))
    assert r.status_code == 403


# ── happy path + win-win rule enforced through the real route ──────────────────────────────────
def test_create_then_fetch_round_trips_through_real_http(client):
    r = client.post("/api/v1/referrals/campaigns", json=_campaign_body(),
                    headers=_auth(tenant="shop-a"))
    assert r.status_code == 200
    campaign = r.json()
    assert campaign["reward_params"] == {"points": 50}

    got = client.get(f"/api/v1/referrals/campaigns/{campaign['id']}",
                     headers=_auth(tenant="shop-a"))
    assert got.status_code == 200
    assert got.json()["id"] == campaign["id"]


def test_a_campaign_with_no_new_customer_reward_is_refused_with_400_not_500(client):
    body = _campaign_body()
    del body["new_customer_reward_type"]
    body["new_customer_reward_type"] = ""
    body["new_customer_reward_params"] = {}
    r = client.post("/api/v1/referrals/campaigns", json=body, headers=_auth(tenant="shop-a"))
    assert r.status_code == 400
    assert r.json()["error"] == "BAD_REQUEST"


def test_malformed_reward_params_is_refused_with_400_not_500(client):
    body = _campaign_body(reward_params={"points": "not-a-number"})
    r = client.post("/api/v1/referrals/campaigns", json=body, headers=_auth(tenant="shop-a"))
    assert r.status_code == 400


# ── tenant isolation, end to end over real HTTP tokens (not just the service layer) ─────────────
def test_shop_b_cannot_see_shop_as_campaign_via_get(client):
    created = client.post("/api/v1/referrals/campaigns", json=_campaign_body(),
                          headers=_auth(tenant="shop-iso-a")).json()
    r = client.get(f"/api/v1/referrals/campaigns/{created['id']}",
                   headers=_auth(tenant="shop-iso-b"))
    assert r.status_code == 404


def test_shop_b_cannot_pause_shop_as_campaign(client):
    created = client.post("/api/v1/referrals/campaigns", json=_campaign_body(),
                          headers=_auth(tenant="shop-pause-a")).json()
    r = client.put(f"/api/v1/referrals/campaigns/{created['id']}/active",
                   json={"active": False}, headers=_auth(tenant="shop-pause-b"))
    assert r.status_code == 404
    # untouched under its real tenant
    still = client.get(f"/api/v1/referrals/campaigns/{created['id']}",
                       headers=_auth(tenant="shop-pause-a")).json()
    assert still["active"] is True


def test_list_is_scoped_to_the_callers_own_tenant_only(client):
    client.post("/api/v1/referrals/campaigns", json=_campaign_body(),
               headers=_auth(tenant="shop-list-a"))
    client.post("/api/v1/referrals/campaigns", json=_campaign_body(),
               headers=_auth(tenant="shop-list-b"))
    rows = client.get("/api/v1/referrals/campaigns", headers=_auth(tenant="shop-list-a")).json()
    assert rows["campaigns"]
    assert all(c["tenant"] == "shop-list-a" for c in rows["campaigns"])


# ── immutability enforced through the real route: active is the only PUT-able field ────────────
def test_set_active_route_only_ever_changes_active(client):
    created = client.post("/api/v1/referrals/campaigns", json=_campaign_body(),
                          headers=_auth(tenant="shop-immut")).json()
    paused = client.put(f"/api/v1/referrals/campaigns/{created['id']}/active",
                        json={"active": False}, headers=_auth(tenant="shop-immut")).json()
    assert paused["active"] is False
    assert paused["reward_params"] == created["reward_params"]
    assert paused["mode"] == created["mode"]


def test_set_active_on_unknown_id_is_404_not_500(client):
    r = client.put("/api/v1/referrals/campaigns/does-not-exist/active",
                   json={"active": False}, headers=_auth(tenant="shop-a"))
    assert r.status_code == 404
