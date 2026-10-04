"""`/api/v1/field/visits/{visit_id}/points` (GET + POST) — proves the manual field screen is a
real, working second door onto `Operations.available_points_reward`/`redeem_points_reward`, the
exact same door `test_till_points.py` already proves for an integrated till. The business logic
itself (scoping, idempotency, the one-slot-vs-apply_offer rule) is unit-tested exhaustively in
`test_visit_points_redemption.py`; this file proves only that the wiring is real.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

SECRET = "h" * 40
ISS, AUD = "iss", "aud"
TENANT = "tnt_field_points"
RECORD_CAPS = ("operations.record",)


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


class FakeLoyaltyDesk:
    def __init__(self, rewards=None):
        self.rewards = rewards or []
        self._k: dict = {}

    async def balance(self, *, tenant, subject_ref):
        return {"rewards": self.rewards}

    async def redeem(self, *, tenant, subject_ref, reward_id, idempotency_key, actor="",
                     branch_id=""):
        if idempotency_key in self._k:
            return self._k[idempotency_key]
        reward = next((r for r in self.rewards if r["id"] == reward_id), None)
        if reward is None:
            return {"_status": 404, "_reason": "رصيدك لا يكفي لهذه المكافأة."}
        out = {"redemption": {"reward_name": reward["name"], "reward_type": reward["type"],
                              "cost": reward["cost"],
                              "discount_halalas": reward.get("discount_halalas", 0)}}
        self._k[idempotency_key] = out
        return out


@pytest.fixture
def client():
    return _make_app()


def _auth(tenant: str) -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "op1", "iss": ISS, "aud": AUD, "caps": list(RECORD_CAPS),
                      "tenant": tenant, "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


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


def test_the_field_screen_can_read_an_available_points_reward(client):
    loyalty = FakeLoyaltyDesk([{"id": "rwd_1", "name": "خصم", "cost": 50, "type": "discount",
                               "discount_halalas": 1000, "active": True}])
    visit_id = _seed_visit(client, TENANT, "0511220001", loyalty=loyalty)

    r = client.get(f"/api/v1/field/visits/{visit_id}/points", headers=_auth(TENANT))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["available"] is True
    assert body["reward"]["id"] == "rwd_1"


def test_the_field_screen_can_redeem_a_points_reward(client):
    loyalty = FakeLoyaltyDesk([{"id": "rwd_1", "name": "قهوة مجانية", "cost": 50,
                               "type": "discount", "discount_halalas": 1000, "active": True}])
    visit_id = _seed_visit(client, TENANT, "0511220002", loyalty=loyalty)

    r = client.post(f"/api/v1/field/visits/{visit_id}/points", json={"reward_id": "rwd_1"},
                    headers=_auth(TENANT))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["applied"] is True
    assert "قهوة مجانية" in body["offer"]["text"]


def test_an_unknown_reward_id_is_refused_not_a_500(client):
    loyalty = FakeLoyaltyDesk([])
    visit_id = _seed_visit(client, TENANT, "0511220003", loyalty=loyalty)

    r = client.post(f"/api/v1/field/visits/{visit_id}/points", json={"reward_id": "rwd_missing"},
                    headers=_auth(TENANT))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["applied"] is False
