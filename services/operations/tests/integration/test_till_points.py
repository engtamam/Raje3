"""The till's own «استبدال نقاط» door — same shape as `test_till_offer.py`'s own `/offer/apply`
coverage, for the new `/points/available` and `/points/redeem` routes (2026-10-04)."""
from __future__ import annotations

import asyncio
import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

AVAILABLE_PATH = "/api/v1/till/points/available"
REDEEM_PATH = "/api/v1/till/points/redeem"
SECRET = "h" * 40
ISS, AUD = "iss", "aud"
TENANT = "tnt_till_points"


@pytest.fixture(scope="module")
def client():
    from app.config import get_settings

    saved = dict(os.environ)
    os.environ.update({
        "ENV": "test", "INTERNAL_SERVICE_TOKEN": "t" * 40, "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": SECRET, "TOKEN_ISSUER": ISS, "TOKEN_AUDIENCE": AUD,
        "RATELIMIT_MAX": "1000", "PII_SALT": "s" * 32, "API_LINK_ENABLED": "true",
    })
    get_settings.cache_clear()
    from app.main import create_app

    yield TestClient(create_app(), raise_server_exceptions=False)
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


@pytest.fixture()
def till_headers():
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "till1", "iss": ISS, "aud": AUD, "caps": ["operations.record"],
                      "tenant": TENANT, "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    return {"headers": {"Authorization": f"Bearer {tok}"}, "tenant": TENANT}


class FakeLoyaltyDesk:
    def __init__(self, rewards=None):
        self.rewards = rewards or []
        self.redeemed: list[dict] = []
        self._redeemed_keys: dict = {}

    async def balance(self, *, tenant, subject_ref):
        return {"has_programme": True, "points": 500, "rewards": self.rewards,
               "to_next_reward": 0, "expires_at": 0}

    async def redeem(self, *, tenant, subject_ref, reward_id, idempotency_key, actor="",
                     branch_id=""):
        if idempotency_key in self._redeemed_keys:
            return self._redeemed_keys[idempotency_key]
        reward = next((r for r in self.rewards if r["id"] == reward_id), None)
        if reward is None:
            return {"_status": 404, "_reason": "رصيدك لا يكفي لهذه المكافأة."}
        out = {"redemption": {"reward_name": reward["name"], "reward_type": reward["type"],
                              "cost": reward["cost"],
                              "discount_halalas": reward.get("discount_halalas", 0)},
              "balance": 500 - reward["cost"], "duplicate": False}
        self.redeemed.append({"reward_id": reward_id, "idempotency_key": idempotency_key})
        self._redeemed_keys[idempotency_key] = out
        return out


def _seed_visit(client, tenant: str, phone: str, *, loyalty=None) -> str:
    from app.core.models import Service
    from app.core.stores import ServiceStore

    ops = client.app.state.container.operations
    ds = client.app.state.container.datastore
    if loyalty is not None:
        ops.with_loyalty_desk(loyalty)

    async def go():
        await ServiceStore(ds).save(Service(id="svc_a", tenant=tenant, name="غسيل"))
        v = await ops.record_visit(tenant=tenant, phone=phone, service_ids=["svc_a"])
        return v.visit.id

    return asyncio.run(go())


def test_the_till_can_read_an_available_points_reward(till_headers, client):
    tenant = till_headers["tenant"]
    loyalty = FakeLoyaltyDesk([{"id": "rwd_1", "name": "خصم 10 ريال", "cost": 50,
                               "type": "discount", "discount_halalas": 1000, "active": True}])
    visit_id = _seed_visit(client, tenant, "0502220001", loyalty=loyalty)

    r = client.get(AVAILABLE_PATH, params={"visit_id": visit_id, "phone": "0502220001"},
                   headers=till_headers["headers"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["available"] is True
    assert body["reward"]["id"] == "rwd_1"


def test_nothing_affordable_answers_available_false_not_an_error(till_headers, client):
    tenant = till_headers["tenant"]
    loyalty = FakeLoyaltyDesk([])
    visit_id = _seed_visit(client, tenant, "0502220002", loyalty=loyalty)

    r = client.get(AVAILABLE_PATH, params={"visit_id": visit_id, "phone": "0502220002"},
                   headers=till_headers["headers"])
    assert r.status_code == 200, r.text
    assert r.json() == {"available": False}


def test_the_till_can_redeem_a_points_reward(till_headers, client):
    tenant = till_headers["tenant"]
    loyalty = FakeLoyaltyDesk([{"id": "rwd_1", "name": "قهوة مجانية", "cost": 50,
                               "type": "discount", "discount_halalas": 1000, "active": True}])
    visit_id = _seed_visit(client, tenant, "0502220003", loyalty=loyalty)

    r = client.post(REDEEM_PATH, json={"visit_id": visit_id, "reward_id": "rwd_1",
                                       "actor": "cashier"}, headers=till_headers["headers"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["applied"] is True
    assert "قهوة مجانية" in body["offer"]["text"]


def test_a_second_redeem_tap_spends_nothing_more(till_headers, client):
    tenant = till_headers["tenant"]
    loyalty = FakeLoyaltyDesk([{"id": "rwd_1", "name": "مكافأة", "cost": 50, "type": "discount",
                               "discount_halalas": 500, "active": True}])
    visit_id = _seed_visit(client, tenant, "0502220004", loyalty=loyalty)

    first = client.post(REDEEM_PATH, json={"visit_id": visit_id, "reward_id": "rwd_1"},
                        headers=till_headers["headers"]).json()
    second = client.post(REDEEM_PATH, json={"visit_id": visit_id, "reward_id": "rwd_1"},
                         headers=till_headers["headers"]).json()
    assert first["offer"]["ref"] == second["offer"]["ref"]
    assert len(loyalty.redeemed) == 1


def test_an_unknown_reward_id_is_refused_in_words_the_cashier_can_read(till_headers, client):
    tenant = till_headers["tenant"]
    loyalty = FakeLoyaltyDesk([])
    visit_id = _seed_visit(client, tenant, "0502220005", loyalty=loyalty)

    r = client.post(REDEEM_PATH, json={"visit_id": visit_id, "reward_id": "rwd_missing"},
                    headers=till_headers["headers"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["applied"] is False
    assert "رصيدك لا يكفي" in body["reason"]
