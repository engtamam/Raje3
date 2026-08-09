"""Every core rule reached THROUGH ITS ROUTE, with the real request model in the way.

THIS FILE EXISTS BECAUSE OF §4.20. `fills` was enforced in operations' core and silently dropped by
its pydantic model, so the endpoint returned 200 having done nothing. Both layers read correctly in
isolation. The only thing that finds it is a test that goes through the door.
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
    """Exactly what the field employee holds: read and redeem, never manage."""
    return _auth("loyalty.read", "loyalty.redeem")


INTERNAL = {"X-Internal-Token": "t" * 40}


def _reward(client, owner, name="قهوة", cost=50, type="item", **kw) -> str:
    r = client.post("/api/v1/loyalty/rewards",
                    json={"name": name, "cost": cost, "type": type, **kw}, headers=owner)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _earn(client, points=500, visit="v1", subject=S):
    client.put("/api/v1/loyalty/settings/general", json={"points": points},
               headers=_auth("loyalty.manage"))
    r = client.post("/internal/loyalty/earn",
                    json={"tenant": TENANT, "visit_id": visit, "subject_ref": subject,
                          "service_ids": ["wash"]}, headers=INTERNAL)
    assert r.status_code == 200, r.text
    return r.json()


# ── the field screen ───────────────────────────────────────────────────────────────────────────
def test_a_customer_with_nothing_reads_as_zero_rather_than_404(client, operator):
    r = client.get("/api/v1/loyalty/balance/ref_nobody00000", headers=operator)
    assert r.status_code == 200
    assert r.json()["points"] == 0 and r.json()["rewards"] == []


def test_the_balance_shows_only_affordable_rewards(client, owner, operator):
    _reward(client, owner, name="قهوة", cost=50)
    _reward(client, owner, name="غسلة كاملة", cost=5000)
    _earn(client, points=100, visit="v-afford")
    got = client.get(f"/api/v1/loyalty/balance/{S}", headers=operator).json()
    assert [r["name"] for r in got["rewards"]] == ["قهوة"]
    assert got["to_next_reward"] == 4900


def test_the_operator_can_redeem_and_the_manager_is_not_required(client, owner, operator):
    rid = _reward(client, owner, name="معطر", cost=30)
    _earn(client, points=100, visit="v-op")
    r = client.post("/api/v1/loyalty/redeem",
                    json={"subject_ref": S, "reward_id": rid, "idempotency_key": "k-op"},
                    headers=operator)
    assert r.status_code == 200, r.text
    assert r.json()["redemption"]["actor"] == "emp-7"


def test_the_same_key_twice_spends_once_through_the_route(client, owner, operator):
    rid = _reward(client, owner, name="شاي", cost=20)
    _earn(client, points=100, visit="v-idem")
    first = client.post("/api/v1/loyalty/redeem",
                        json={"subject_ref": S, "reward_id": rid, "idempotency_key": "k-twice"},
                        headers=operator).json()
    second = client.post("/api/v1/loyalty/redeem",
                         json={"subject_ref": S, "reward_id": rid, "idempotency_key": "k-twice"},
                         headers=operator).json()
    assert second["duplicate"] is True
    assert first["balance"] == second["balance"]


def test_an_overdraft_is_a_409_with_a_reason_the_operator_can_read(client, owner, operator):
    rid = _reward(client, owner, name="باقة", cost=9999)
    r = client.post("/api/v1/loyalty/redeem",
                    json={"subject_ref": "ref_broke00000000", "reward_id": rid,
                          "idempotency_key": "k-over"}, headers=operator)
    assert r.status_code == 409
    assert "9999" in r.text


def test_the_idempotency_key_is_required_by_the_model(client, operator):
    """Optional would mean the careful clients are safe and the hurried one is not."""
    r = client.post("/api/v1/loyalty/redeem",
                    json={"subject_ref": S, "reward_id": "rwd_x"}, headers=operator)
    assert r.status_code == 422


def test_an_operator_cannot_reprice_the_rewards_he_spends_against(client, operator):
    r = client.post("/api/v1/loyalty/rewards",
                    json={"name": "مجاني", "cost": 1, "type": "item"}, headers=operator)
    assert r.status_code == 403


# ── the rewards catalogue, through the door ────────────────────────────────────────────────────
def test_a_name_too_long_is_refused_by_the_model_before_the_core(client, owner):
    r = client.post("/api/v1/loyalty/rewards",
                    json={"name": "غ" * 60, "cost": 10, "type": "item"}, headers=owner)
    assert r.status_code == 422


def test_a_name_with_a_newline_is_refused_by_the_core_through_the_route(client, owner):
    """Length is the model's job; CONTENT is the core's — and the core must be reachable."""
    r = client.post("/api/v1/loyalty/rewards",
                    json={"name": "قهوة\nمجانية", "cost": 10, "type": "item"}, headers=owner)
    assert r.status_code == 400
    assert "واتساب" in r.text or "سطر" in r.text


def test_a_service_reward_without_its_service_is_refused_through_the_route(client, owner):
    r = client.post("/api/v1/loyalty/rewards",
                    json={"name": "غسلة", "cost": 200, "type": "service"}, headers=owner)
    assert r.status_code == 400


# ── the settings tree, through the door ────────────────────────────────────────────────────────
def test_the_tree_reports_where_every_number_came_from(client, owner):
    client.put("/api/v1/loyalty/settings/general", json={"points": 7}, headers=owner)
    client.put("/api/v1/loyalty/settings/service/oil", json={"points": 40}, headers=owner)
    got = client.get("/api/v1/loyalty/settings", headers=owner).json()
    assert got["general"]["points"] == 7
    assert got["services"]["oil"]["points"] == 40


def test_following_again_through_the_route_deletes_the_override(client, owner):
    client.put("/api/v1/loyalty/settings/general", json={"points": 7}, headers=owner)
    client.put("/api/v1/loyalty/settings/service/wax", json={"points": 40}, headers=owner)
    client.delete("/api/v1/loyalty/settings/service/wax", headers=owner)
    client.put("/api/v1/loyalty/settings/general", json={"points": 11}, headers=owner)
    got = client.get("/api/v1/loyalty/settings", headers=owner).json()
    assert "wax" not in got["services"]


def test_invoice_mode_is_refused_for_a_shop_with_no_till_with_the_reason(client, owner):
    r = client.put("/api/v1/loyalty/settings/mode",
                   json={"mode": "invoice", "points_per_riyal": 1}, headers=owner)
    assert r.status_code == 400
    assert "9.3" in r.text or "till" in r.text


# ── the till and the tick ──────────────────────────────────────────────────────────────────────
def test_the_till_redeems_and_returns_what_the_receipt_must_carry(client, owner):
    rid = _reward(client, owner, name="خصم", cost=40, type="discount", discount_halalas=5000)
    _earn(client, points=200, visit="v-till", subject="ref_tillcust0001")
    r = client.post("/internal/loyalty/redeem",
                    json={"tenant": TENANT, "subject_ref": "ref_tillcust0001",
                          "reward_id": rid, "idempotency_key": "inv-991",
                          "actor": "cashier-3"}, headers=INTERNAL)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["discount_halalas"] == 5000
    assert body["transaction_ref"].startswith("rdm_")


def test_the_till_needs_the_internal_token(client):
    r = client.post("/internal/loyalty/redeem",
                    json={"tenant": TENANT, "subject_ref": S, "reward_id": "x",
                          "idempotency_key": "k"})
    assert r.status_code in (401, 403)


def test_the_tick_runs_and_reports_what_it_did(client):
    r = client.post("/internal/loyalty/tick", json={"tenant": TENANT}, headers=INTERNAL)
    assert r.status_code == 200, r.text
    assert set(r.json()) >= {"expired", "warned_sent", "seen", "more"}


def test_reconcile_repairs_through_the_route(client, owner, operator):
    _earn(client, points=60, visit="v-recon", subject="ref_driftcust001")
    r = client.post("/internal/loyalty/reconcile",
                    json={"tenant": TENANT, "subject_ref": "ref_driftcust001"},
                    headers=INTERNAL)
    assert r.status_code == 200
    assert r.json()["ledger"] == 60 and r.json()["repaired"] is False


# ── erasure ────────────────────────────────────────────────────────────────────────────────────
def test_erasure_removes_the_balance_and_is_idempotent(client, owner, operator):
    _earn(client, points=80, visit="v-erase", subject="ref_erasecust001")
    first = client.post("/internal/privacy/erase",
                        json={"tenant": TENANT, "subject": "ref_erasecust001"},
                        headers=INTERNAL)
    assert first.status_code == 200, first.text
    assert first.json()["erased"]
    assert client.get("/api/v1/loyalty/balance/ref_erasecust001",
                      headers=operator).json()["points"] == 0
    # A DSAR retries. Failing the second time would stall a fan-out designed to repeat.
    second = client.post("/internal/privacy/erase",
                         json={"tenant": TENANT, "subject": "ref_erasecust001"},
                         headers=INTERNAL)
    assert second.status_code == 200 and second.json()["already_absent"] is True


# ── isolation ──────────────────────────────────────────────────────────────────────────────────
def test_another_establishment_sees_none_of_this(client, owner):
    _reward(client, owner, name="سرّي", cost=10)
    other = _auth("loyalty.read", "loyalty.manage", tenant="other-shop")
    assert client.get("/api/v1/loyalty/rewards", headers=other).json()["rewards"] == []


def test_a_token_with_no_establishment_is_refused(client):
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "x", "iss": ISS, "aud": AUD, "caps": ["loyalty.read"],
                      "exp": now + dt.timedelta(minutes=5), "iat": now},
                     TOKEN_SECRET, algorithm="HS256")
    r = client.get(f"/api/v1/loyalty/balance/{S}",
                   headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 403
