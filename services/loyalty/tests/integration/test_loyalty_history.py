"""`/internal/loyalty/history` — the FULL movement + redemption record for one member, for the
ops-mcp case-timeline investigation tool. `portal_balance` deliberately carries no history (a
customer's own page shows a current balance); this is the opposite, internal-only trade.
"""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

TOKEN_SECRET = "k" * 40
ISS, AUD, TENANT = "iss", "aud", "shop"
S = "ref_abcdef123456"
INTERNAL = {"X-Internal-Token": "t" * 40}


def _make_app() -> TestClient:
    from app.config import get_settings

    os.environ.update({
        "ENV": "test", "INTERNAL_SERVICE_TOKEN": "t" * 40,
        "TOKEN_VERIFIER_DRIVER": "hs256", "TOKEN_HS256_SECRET": TOKEN_SECRET,
        "TOKEN_ISSUER": ISS, "TOKEN_AUDIENCE": AUD, "RATELIMIT_MAX": "5000",
        "SECRETS_KEK": "K" * 44, "PII_SALT": "s" * 32,
    })
    get_settings.cache_clear()
    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


def _auth(*caps: str, tenant: str = TENANT) -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "emp-7", "iss": ISS, "aud": AUD, "caps": list(caps),
                      "tenant": tenant, "exp": now + dt.timedelta(minutes=5), "iat": now},
                     TOKEN_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def env_guard():
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)
    from app.config import get_settings
    get_settings.cache_clear()


@pytest.fixture(scope="module")
def client(env_guard) -> TestClient:
    return _make_app()


@pytest.fixture
def owner() -> dict:
    return _auth("loyalty.read", "loyalty.manage", "loyalty.redeem")


@pytest.fixture
def operator() -> dict:
    return _auth("loyalty.read", "loyalty.redeem")


def _reward(client, owner, name="قهوة", cost=50, type="item", **kw) -> str:
    r = client.post("/api/v1/loyalty/rewards",
                    json={"name": name, "cost": cost, "type": type, **kw}, headers=owner)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _earn(client, points=500, visit="v1", subject=S, tenant=TENANT):
    client.put("/api/v1/loyalty/settings/general", json={"points": points},
              headers=_auth("loyalty.manage", tenant=tenant))
    r = client.post("/internal/loyalty/earn",
                    json={"tenant": tenant, "visit_id": visit, "subject_ref": subject,
                         "service_ids": ["wash"]}, headers=INTERNAL)
    assert r.status_code == 200, r.text
    return r.json()


def test_refuses_without_the_internal_token(client):
    r = client.get("/internal/loyalty/history", params={"tenant": TENANT, "subject_ref": S})
    assert r.status_code == 401


def test_reports_both_the_movement_and_the_redemption_for_a_real_spend(client, owner, operator):
    rid = _reward(client, owner, name="عصير", cost=30)
    _earn(client, points=100, visit="v-hist-1", subject="ref_hist_spend")
    client.post("/api/v1/loyalty/redeem",
               json={"subject_ref": "ref_hist_spend", "reward_id": rid,
                    "idempotency_key": "k-hist-1"}, headers=operator)
    r = client.get("/internal/loyalty/history",
                   params={"tenant": TENANT, "subject_ref": "ref_hist_spend"}, headers=INTERNAL)
    assert r.status_code == 200, r.text
    body = r.json()
    reasons = [m["reason"] for m in body["movements"]]
    assert "earn" in reasons and "redeem" in reasons
    assert len(body["redemptions"]) == 1
    assert body["redemptions"][0]["reward_name"] == "عصير"
    assert body["redemptions"][0]["cost"] == 30


def test_returns_empty_lists_never_an_error_for_an_unknown_subject(client):
    r = client.get("/internal/loyalty/history",
                   params={"tenant": TENANT, "subject_ref": "ref_never_existed"}, headers=INTERNAL)
    assert r.status_code == 200
    assert r.json() == {"movements": [], "redemptions": []}


def test_isolated_per_tenant(client, owner, operator):
    _earn(client, points=100, visit="v-iso-a", subject="ref_iso_shared", tenant="tnt_loy_a")
    _earn(client, points=100, visit="v-iso-b", subject="ref_iso_shared", tenant="tnt_loy_b")
    r = client.get("/internal/loyalty/history",
                   params={"tenant": "tnt_loy_a", "subject_ref": "ref_iso_shared"},
                   headers=INTERNAL)
    assert len(r.json()["movements"]) == 1


def test_refuses_a_malformed_query_rather_than_500ing(client):
    r = client.get("/internal/loyalty/history", params={"tenant": TENANT}, headers=INTERNAL)
    assert r.status_code == 422   # subject_ref missing
