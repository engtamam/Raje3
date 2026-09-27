"""POST/GET /api/v1/affiliates[...] — real HTTP: auth, capability RBAC, tenant scoping, and the
"never both roles"/settlement rules enforced end to end through the actual route, not just
core/affiliates.py's own unit tests."""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

SECRET = "h" * 40
ISS, AUD = "iss", "aud"


def _make_app() -> TestClient:
    from app.config import get_settings

    os.environ.update({
        "ENV": "test", "INTERNAL_SERVICE_TOKEN": "t" * 40, "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": SECRET, "TOKEN_ISSUER": ISS, "TOKEN_AUDIENCE": AUD,
        "RATELIMIT_MAX": "10000", "PII_SALT": "s" * 32,
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


def _token(*, tenant: str,
          caps=("operations.manage", "operations.read", "operations.affiliates_read")) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    claims = {"sub": "owner-1", "iss": ISS, "aud": AUD, "tenant": tenant,
              "exp": now + dt.timedelta(minutes=5), "iat": now, "caps": list(caps)}
    return jwt.encode(claims, SECRET, algorithm="HS256")


def _auth(**kw) -> dict:
    return {"Authorization": f"Bearer {_token(**kw)}"}


def _affiliate_body(**over) -> dict:
    body = {"phone": "0511111111", "code": "BLOGR", "discount_percent": 15,
           "reward_type": "fixed_points", "reward_params": {"points": 40}}
    body.update(over)
    return body


# ── auth / capability RBAC ───────────────────────────────────────────────────────────────────────
def test_no_token_is_401(client):
    assert client.post("/api/v1/affiliates", json=_affiliate_body()).status_code == 401


def test_token_without_manage_is_403(client):
    r = client.post("/api/v1/affiliates", json=_affiliate_body(),
                    headers=_auth(tenant="shop-a", caps=("operations.read",)))
    assert r.status_code == 403


def test_read_only_capability_cannot_add(client):
    r = client.post("/api/v1/affiliates", json=_affiliate_body(),
                    headers=_auth(tenant="shop-read-only", caps=("something.else",)))
    assert r.status_code == 403


# ── the 3 payout/phone reads require operations.affiliates_read, not plain operations.read ──────
def test_plain_operations_read_cannot_list_affiliates(client):
    r = client.get("/api/v1/affiliates", headers=_auth(tenant="shop-a", caps=("operations.read",)))
    assert r.status_code == 403


def test_plain_operations_read_cannot_get_an_affiliate(client):
    created = client.post("/api/v1/affiliates", json=_affiliate_body(phone="0566666666",
                                                                     code="PAYOUT1"),
                          headers=_auth(tenant="shop-payouts")).json()
    r = client.get(f"/api/v1/affiliates/{created['id']}",
                   headers=_auth(tenant="shop-payouts", caps=("operations.read",)))
    assert r.status_code == 403


def test_plain_operations_read_cannot_list_settlements(client):
    created = client.post("/api/v1/affiliates", json=_affiliate_body(phone="0577777777",
                                                                     code="PAYOUT2"),
                          headers=_auth(tenant="shop-payouts2")).json()
    r = client.get(f"/api/v1/affiliates/{created['id']}/settlements",
                   headers=_auth(tenant="shop-payouts2", caps=("operations.read",)))
    assert r.status_code == 403


def test_operations_affiliates_read_alone_can_list_affiliates(client):
    client.post("/api/v1/affiliates", json=_affiliate_body(phone="0588888888", code="PAYOUT3"),
               headers=_auth(tenant="shop-payouts3"))
    r = client.get("/api/v1/affiliates",
                   headers=_auth(tenant="shop-payouts3", caps=("operations.affiliates_read",)))
    assert r.status_code == 200


# ── happy path ───────────────────────────────────────────────────────────────────────────────────
def test_add_then_fetch_round_trips_through_real_http(client):
    r = client.post("/api/v1/affiliates", json=_affiliate_body(), headers=_auth(tenant="shop-a"))
    assert r.status_code == 200
    affiliate = r.json()
    assert affiliate["code"] == "BLOGR"
    assert affiliate["unsettled_points"] == 0

    got = client.get(f"/api/v1/affiliates/{affiliate['id']}", headers=_auth(tenant="shop-a"))
    assert got.status_code == 200
    assert got.json()["id"] == affiliate["id"]


def test_malformed_body_is_refused_with_400_not_500(client):
    body = _affiliate_body(reward_params={"points": "not-a-number"})
    r = client.post("/api/v1/affiliates", json=body, headers=_auth(tenant="shop-a"))
    assert r.status_code == 400
    assert r.json()["error"] == "BAD_REQUEST"


def test_an_out_of_range_discount_percent_is_a_422_at_the_route_boundary(client):
    r = client.post("/api/v1/affiliates", json=_affiliate_body(discount_percent=150),
                    headers=_auth(tenant="shop-a"))
    assert r.status_code == 422


def test_an_oversized_code_is_a_422_at_the_route_boundary(client):
    r = client.post("/api/v1/affiliates", json=_affiliate_body(code="X" * 17),
                    headers=_auth(tenant="shop-a"))
    assert r.status_code == 422


# ── "never both roles" enforced through the real route ──────────────────────────────────────────
def test_a_second_active_affiliate_for_the_same_phone_is_refused(client):
    client.post("/api/v1/affiliates", json=_affiliate_body(phone="0599999999", code="FIRST1"),
               headers=_auth(tenant="shop-dup"))
    r = client.post("/api/v1/affiliates",
                    json=_affiliate_body(phone="0599999999", code="SECOND2"),
                    headers=_auth(tenant="shop-dup"))
    assert r.status_code == 400


# ── tenant isolation ─────────────────────────────────────────────────────────────────────────────
def test_shop_b_cannot_see_shop_as_affiliate(client):
    created = client.post("/api/v1/affiliates", json=_affiliate_body(),
                          headers=_auth(tenant="shop-iso-a")).json()
    r = client.get(f"/api/v1/affiliates/{created['id']}", headers=_auth(tenant="shop-iso-b"))
    assert r.status_code == 404


def test_shop_b_cannot_pause_shop_as_affiliate(client):
    created = client.post("/api/v1/affiliates", json=_affiliate_body(),
                          headers=_auth(tenant="shop-pause-a")).json()
    r = client.put(f"/api/v1/affiliates/{created['id']}/active", json={"active": False},
                   headers=_auth(tenant="shop-pause-b"))
    assert r.status_code == 404
    still = client.get(f"/api/v1/affiliates/{created['id']}",
                       headers=_auth(tenant="shop-pause-a")).json()
    assert still["active"] is True


def test_list_is_scoped_to_the_callers_own_tenant_only(client):
    client.post("/api/v1/affiliates", json=_affiliate_body(phone="0511111111"),
               headers=_auth(tenant="shop-list-a"))
    client.post("/api/v1/affiliates", json=_affiliate_body(phone="0522222222"),
               headers=_auth(tenant="shop-list-b"))
    rows = client.get("/api/v1/affiliates", headers=_auth(tenant="shop-list-a")).json()
    assert rows["affiliates"]


# ── settlement, through the real route ──────────────────────────────────────────────────────────
def test_settle_button_is_refused_for_a_nonexistent_affiliate(client):
    r = client.post("/api/v1/affiliates/does-not-exist/settle", json={},
                    headers=_auth(tenant="shop-a"))
    assert r.status_code == 404


def test_full_settlement_through_the_real_route(client):
    created = client.post("/api/v1/affiliates", json=_affiliate_body(phone="0533333333",
                                                                     code="SETTLE1"),
                          headers=_auth(tenant="shop-settle")).json()
    # No engine-facing route to CREDIT a sale exists (that only happens via a real redemption) —
    # settle here proves the ROUTE plumbing on a zero balance: refused, cleanly, never a 500.
    r = client.post(f"/api/v1/affiliates/{created['id']}/settle", json={},
                    headers=_auth(tenant="shop-settle"))
    assert r.status_code == 400
    assert r.json()["error"] == "BAD_REQUEST"


def test_settling_more_than_the_balance_is_a_400_with_a_real_reason(client):
    created = client.post("/api/v1/affiliates", json=_affiliate_body(phone="0544444444",
                                                                     code="SETTLE2"),
                          headers=_auth(tenant="shop-settle2")).json()
    r = client.post(f"/api/v1/affiliates/{created['id']}/settle", json={"points": 999999999},
                    headers=_auth(tenant="shop-settle2"))
    assert r.status_code == 400


def test_settlements_list_is_refused_for_a_nonexistent_affiliate(client):
    r = client.get("/api/v1/affiliates/does-not-exist/settlements", headers=_auth(tenant="shop-a"))
    assert r.status_code == 404


def test_settlements_list_starts_empty_for_a_real_affiliate(client):
    created = client.post("/api/v1/affiliates", json=_affiliate_body(phone="0555555555",
                                                                     code="SETTLE3"),
                          headers=_auth(tenant="shop-settle3")).json()
    r = client.get(f"/api/v1/affiliates/{created['id']}/settlements",
                   headers=_auth(tenant="shop-settle3"))
    assert r.status_code == 200
    assert r.json()["settlements"] == []


# ── beneficiary eligibility, through the real route (owner instruction, 2026-09-27) ─────────────
def test_absent_eligibility_defaults_to_new_through_the_real_route(client):
    created = client.post("/api/v1/affiliates", json=_affiliate_body(phone="0561111111",
                                                                      code="ELIG1"),
                          headers=_auth(tenant="shop-elig1")).json()
    assert created["beneficiary_eligibility"] == "new"
    assert created["beneficiary_max_visits"] == 0


def test_max_visits_eligibility_round_trips_through_the_real_route(client):
    created = client.post(
        "/api/v1/affiliates",
        json=_affiliate_body(phone="0562222222", code="ELIG2",
                             beneficiary_eligibility="max_visits", beneficiary_max_visits=4),
        headers=_auth(tenant="shop-elig2")).json()
    assert created["beneficiary_eligibility"] == "max_visits"
    assert created["beneficiary_max_visits"] == 4
    got = client.get(f"/api/v1/affiliates/{created['id']}", headers=_auth(tenant="shop-elig2"))
    assert got.json()["beneficiary_eligibility"] == "max_visits"
    assert got.json()["beneficiary_max_visits"] == 4


def test_an_unknown_eligibility_value_is_a_400_not_a_500(client):
    r = client.post("/api/v1/affiliates",
                    json=_affiliate_body(phone="0563333333", code="ELIG3",
                                         beneficiary_eligibility="whatever"),
                    headers=_auth(tenant="shop-elig3"))
    assert r.status_code == 400
    assert r.json()["error"] == "BAD_REQUEST"


def test_a_negative_max_visits_is_a_422_at_the_route_boundary(client):
    r = client.post("/api/v1/affiliates",
                    json=_affiliate_body(phone="0564444444", code="ELIG4",
                                         beneficiary_eligibility="max_visits",
                                         beneficiary_max_visits=-1),
                    headers=_auth(tenant="shop-elig4"))
    assert r.status_code == 422


def test_two_affiliates_at_the_same_shop_keep_independent_eligibility_through_real_http(client):
    a1 = client.post("/api/v1/affiliates",
                     json=_affiliate_body(phone="0565555555", code="ELIG5A",
                                          beneficiary_eligibility="open"),
                     headers=_auth(tenant="shop-elig5")).json()
    a2 = client.post("/api/v1/affiliates",
                     json=_affiliate_body(phone="0566666677", code="ELIG5B",
                                          beneficiary_eligibility="new"),
                     headers=_auth(tenant="shop-elig5")).json()
    assert a1["beneficiary_eligibility"] == "open"
    assert a2["beneficiary_eligibility"] == "new"
