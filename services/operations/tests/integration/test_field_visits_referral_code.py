"""POST /api/v1/field/visits — real HTTP, real auth — proves `referral_code` actually reaches
`Operations.record_visit` and its result surfaces on the response, exactly like the till's own
`/referral/register` (`test_till_referral_register.py`) proves the same wiring for its own door.
The engine's own validation logic is unit-tested elsewhere (`test_referral_redemption.py`); this
file proves only that the walk-in visit screen is a real, working second door onto it.
"""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

SECRET = "h" * 40
ISS, AUD = "iss", "aud"
TENANT = "tnt_field_visit_ref"
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


@pytest.fixture
def client_and_engine():
    from app.core.referral_redemption import ReferralRedemptionError

    client = _make_app()

    class FakeGrant:
        new_customer_reward_type = "welcome_points"
        new_customer_reward_params = {"points": 50}

    class FakeEngine:
        def __init__(self) -> None:
            self.calls: list[dict] = []
            self.refuse_with: str | None = None

        async def register(self, tenant, *, code, beneficiary_phone, invoice_minor, actor):
            self.calls.append({"tenant": tenant, "code": code, "phone": beneficiary_phone,
                               "invoice_minor": invoice_minor})
            if self.refuse_with:
                raise ReferralRedemptionError(self.refuse_with)
            return FakeGrant()

    engine = FakeEngine()
    # SAME TECHNIQUE `test_till_referral_register.py` uses — swap the fake onto the already-built
    # container, then wire it into the already-built `Operations` instance's own setter, exactly
    # what `container.py` itself does at boot.
    client.app.state.container.referral_redemption = engine
    client.app.state.container.operations.with_referral_redemption_engine(engine)
    return client, engine


def _auth(*, tenant: str) -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "op1", "iss": ISS, "aud": AUD, "caps": list(RECORD_CAPS),
                      "tenant": tenant, "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


def test_a_new_customers_visit_with_a_code_surfaces_the_grant_on_the_response(client_and_engine):
    client, engine = client_and_engine
    r = client.post("/api/v1/field/visits", headers=_auth(tenant=TENANT),
                    json={"phone": "0501234567", "service_ids": ["srv_1"],
                         "referral_code": "AB123"})
    assert r.status_code == 201
    body = r.json()
    assert body["created_customer"] is True
    assert body["referral_registration"] == {
        "ok": True, "new_customer_reward_type": "welcome_points",
        "new_customer_reward_params": {"points": 50}}
    assert engine.calls[0]["tenant"] == TENANT
    assert engine.calls[0]["code"] == "AB123"


def test_a_visit_with_no_code_never_mentions_referral_registration_at_all(client_and_engine):
    client, engine = client_and_engine
    r = client.post("/api/v1/field/visits", headers=_auth(tenant=TENANT),
                    json={"phone": "0501234567", "service_ids": ["srv_1"]})
    assert r.status_code == 201
    assert "referral_registration" not in r.json()
    assert engine.calls == []


def test_a_rejected_code_still_saves_the_visit_and_reports_the_refusal(client_and_engine):
    client, engine = client_and_engine
    engine.refuse_with = "كود الإحالة غير صالح"
    r = client.post("/api/v1/field/visits", headers=_auth(tenant=TENANT),
                    json={"phone": "0501234567", "service_ids": ["srv_1"],
                         "referral_code": "ZZZZZ"})
    assert r.status_code == 201
    body = r.json()
    assert body["visit"]["id"]
    assert body["referral_registration"] == {"ok": False, "message": "كود الإحالة غير صالح"}


def test_an_oversized_referral_code_is_a_422_not_forwarded_to_the_engine(client_and_engine):
    client, engine = client_and_engine
    r = client.post("/api/v1/field/visits", headers=_auth(tenant=TENANT),
                    json={"phone": "0501234567", "service_ids": ["srv_1"],
                         "referral_code": "X" * 17})
    assert r.status_code == 422
    assert engine.calls == []
