"""POST /api/v1/till/referral/register — real HTTP, real auth, the till route Phase 3 adds. The engine
itself (validation, usage caps, crediting) is unit-tested directly in
tests/unit/test_referral_redemption.py; this file proves the ROUTE plumbing — auth, capability,
request/response shape, and that a `ReferralRedemptionError` becomes a clean refusal, never a 500
— by swapping in a fake engine on the already-built container, same technique
test_till_coupons.py's own fixtures use for `container.coupons`."""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

SECRET = "h" * 40
ISS, AUD = "iss", "aud"
TENANT = "tnt_till_ref"


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
        new_customer_reward_type = "discount_percent"
        new_customer_reward_params = {"percent": 10}

    class FakeEngine:
        def __init__(self) -> None:
            self.calls: list[dict] = []
            self.refuse_with: str | None = None

        async def register(self, tenant, *, code, beneficiary_phone, invoice_minor, actor,
                           beneficiary_created_this_call=False):
            self.calls.append({"tenant": tenant, "code": code, "phone": beneficiary_phone,
                              "invoice_minor": invoice_minor})
            if self.refuse_with:
                raise ReferralRedemptionError(self.refuse_with)
            return FakeGrant()

    engine = FakeEngine()
    client.app.state.container.referral_redemption = engine
    return client, engine


def _auth(*, tenant: str) -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "till1", "iss": ISS, "aud": AUD, "caps": ["operations.record"],
                      "tenant": tenant, "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


def test_no_token_is_401(client_and_engine):
    client, _ = client_and_engine
    r = client.post("/api/v1/till/referral/register", json={"code": "AB123", "phone": "0501234567"})
    assert r.status_code == 401


def test_a_clean_registration_returns_the_new_customer_reward(client_and_engine):
    client, engine = client_and_engine
    r = client.post("/api/v1/till/referral/register",
                    json={"code": "AB123", "phone": "0501234567", "invoice_minor": 5000},
                    headers=_auth(tenant=TENANT))
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["new_customer_reward_type"] == "discount_percent"
    assert engine.calls[0]["tenant"] == TENANT
    assert engine.calls[0]["code"] == "AB123"


def test_an_engine_refusal_is_a_clean_ok_false_never_a_500(client_and_engine):
    client, engine = client_and_engine
    engine.refuse_with = "كود الإحالة غير صالح"
    r = client.post("/api/v1/till/referral/register", json={"code": "ZZZZZ", "phone": "0501234567"},
                    headers=_auth(tenant=TENANT))
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert body["message"] == "كود الإحالة غير صالح"


def test_a_credential_with_no_tenant_is_refused_before_reaching_the_engine(client_and_engine):
    """`subscribed_write` itself refuses a tenant-less credential before the route body ever
    runs — same behaviour every sibling till route (`/coupons/grant`, `/offer/apply`) already
    has; the route's own `if not principal.tenant` guard is a second, defence-in-depth check that
    only a caller bypassing that dependency would ever reach."""
    client, engine = client_and_engine
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "till1", "iss": ISS, "aud": AUD, "caps": ["operations.record"],
                      "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    r = client.post("/api/v1/till/referral/register", json={"code": "AB123", "phone": "0501234567"},
                    headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 403
    assert engine.calls == []


def test_missing_required_fields_is_a_422_not_a_500(client_and_engine):
    client, _ = client_and_engine
    r = client.post("/api/v1/till/referral/register", json={}, headers=_auth(tenant=TENANT))
    assert r.status_code == 422


def test_a_credential_missing_operations_record_is_403(client_and_engine):
    client, engine = client_and_engine
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "someone", "iss": ISS, "aud": AUD, "caps": ["something.else"],
                      "tenant": TENANT, "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    r = client.post("/api/v1/till/referral/register", json={"code": "AB123", "phone": "0501234567"},
                    headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 403
    assert engine.calls == []


def test_an_oversized_code_is_a_422_not_forwarded_to_the_engine(client_and_engine):
    client, engine = client_and_engine
    r = client.post("/api/v1/till/referral/register",
                    json={"code": "X" * 17, "phone": "0501234567"}, headers=_auth(tenant=TENANT))
    assert r.status_code == 422
    assert engine.calls == []


def test_an_oversized_phone_is_a_422_not_forwarded_to_the_engine(client_and_engine):
    client, engine = client_and_engine
    r = client.post("/api/v1/till/referral/register",
                    json={"code": "AB123", "phone": "0" * 33}, headers=_auth(tenant=TENANT))
    assert r.status_code == 422
    assert engine.calls == []


def test_a_negative_invoice_minor_is_a_422_not_forwarded_to_the_engine(client_and_engine):
    client, engine = client_and_engine
    r = client.post("/api/v1/till/referral/register",
                    json={"code": "AB123", "phone": "0501234567", "invoice_minor": -1},
                    headers=_auth(tenant=TENANT))
    assert r.status_code == 422
    assert engine.calls == []


def test_a_code_shaped_like_an_injection_attempt_reaches_the_engine_as_inert_text(
        client_and_engine):
    # Nothing downstream treats `code` as anything but an opaque string key (see
    # adapters/referrals_desk.py's own docstring) — this proves the till route itself does no
    # parsing/interpolation of it either; a hostile-looking string is just refused like any other
    # unknown code, never a crash.
    client, engine = client_and_engine
    engine.refuse_with = "كود الإحالة غير صالح"
    hostile = "1' OR '1'='1"  # 12 chars — stays within the code's own max_length=16
    r = client.post("/api/v1/till/referral/register",
                    json={"code": hostile, "phone": "0501234567"}, headers=_auth(tenant=TENANT))
    assert r.status_code == 200
    assert r.json()["ok"] is False
    assert engine.calls[0]["code"] == hostile


def test_a_tenant_cannot_register_a_code_against_another_tenant_via_the_body(client_and_engine):
    # The route only ever reads the tenant off the VERIFIED principal (`principal.tenant`) — a
    # request body has no tenant field at all for a caller to smuggle a different one through.
    client, engine = client_and_engine
    r = client.post("/api/v1/till/referral/register",
                    json={"code": "AB123", "phone": "0501234567", "tenant": "someone-elses-shop"},
                    headers=_auth(tenant=TENANT))
    assert r.status_code == 200
    assert engine.calls[0]["tenant"] == TENANT


def test_register_attempt_is_audited_on_both_success_and_refusal(client_and_engine):
    client, engine = client_and_engine

    recorded: list[dict] = []

    class FakeAuditor:
        async def record(self, action, **kw):
            recorded.append({"action": action, **kw})

    client.app.state.auditor = FakeAuditor()

    r1 = client.post("/api/v1/till/referral/register",
                     json={"code": "AB123", "phone": "0501234567"}, headers=_auth(tenant=TENANT))
    assert r1.status_code == 200

    engine.refuse_with = "كود الإحالة غير صالح"
    r2 = client.post("/api/v1/till/referral/register",
                     json={"code": "ZZZZZ", "phone": "0501234567"}, headers=_auth(tenant=TENANT))
    assert r2.status_code == 200

    actions = [r["action"] for r in recorded]
    assert actions.count("referral.register_attempt") == 2
