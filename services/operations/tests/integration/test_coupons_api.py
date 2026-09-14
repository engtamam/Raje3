"""Shop-to-shop coupons at the HTTP layer — role gating on both doors, and the platform admin's
own settings/override routes. The billing-service leg is swapped for `FakePlans` (same contract
as `test_coupons.py`'s own fake) after the app is built, exactly the way other integration tests
here substitute a fake peer rather than opening a real socket.
"""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

TOKEN_SECRET = "h" * 40
ISS, AUD = "iss", "aud"
GRANTER = "tnt_granter"
BENEFICIARY = "tnt_beneficiary"
PHONE = "0501234567"


def _make_app() -> TestClient:
    from app.config import get_settings

    env = {
        "ENV": "test",
        "INTERNAL_SERVICE_TOKEN": "t" * 40,
        "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": TOKEN_SECRET,
        "TOKEN_ISSUER": ISS,
        "TOKEN_AUDIENCE": AUD,
        "RATELIMIT_MAX": "1000",
        "PII_SALT": "s" * 32,
    }
    os.environ.update(env)
    get_settings.cache_clear()
    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


def _auth(*caps: str, tenant: str) -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "op1", "iss": ISS, "aud": AUD, "caps": list(caps), "tenant": tenant,
                      "exp": now + dt.timedelta(minutes=5), "iat": now},
                     TOKEN_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture
def env_guard():
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)
    from app.config import get_settings
    get_settings.cache_clear()


@pytest.fixture
def client(env_guard) -> TestClient:
    return _make_app()


class _FakePlans:
    driver = "fake"

    def __init__(self) -> None:
        self.subs: dict[str, list[dict]] = {}
        self.limits_by_plan: dict[str, dict] = {}
        self.plan_for_key: dict[str, str] = {}

    async def subscriptions(self, tenant):
        return self.subs.get(tenant)

    async def limits(self, plan_id):
        return self.limits_by_plan.get(plan_id)

    async def plan_id_for_key(self, key):
        return self.plan_for_key.get(key, "")

    async def create_coupon(self, *, code, plan_id, percent, expires_at, note=""):
        return 201, {"code": code}

    async def attach_coupon(self, *, tenant, sub_id, coupon_code):
        return 200, {"status": "attached"}


def _wire_fake_billing(client: TestClient) -> _FakePlans:
    from app.core.coupons import CouponService

    fake = _FakePlans()
    fake.subs[BENEFICIARY] = [{"id": "sub_1", "plan": "plan_bookings", "status": "active"}]
    fake.limits_by_plan["plan_bookings"] = {"feature.bookings": {"kind": "boolean", "limit": 1}}
    fake.plan_for_key["feature.bookings"] = "plan_bookings"
    container = client.app.state.container
    container.coupons = CouponService(
        store=container.datastore, plans=fake, default_cc="966")
    return fake


def _register_beneficiary(client: TestClient) -> None:
    from app.core.signup import PHONE_INDEX, canonical_phone

    key = canonical_phone(PHONE, default_cc="966")
    import asyncio
    asyncio.run(
        client.app.state.container.datastore.put(
            PHONE_INDEX, key, {"id": key, "tenant": BENEFICIARY, "verified": True}))


# ── the direct-grant door is owner/manager/supervisor only ─────────────────────────────────────
def test_a_plain_operator_cannot_grant_without_a_visit(client):
    _wire_fake_billing(client)
    _register_beneficiary(client)
    r = client.post("/api/v1/staff/coupons/grant",
                    headers=_auth("operations.grant_coupon", tenant=GRANTER),
                    json={"phone": PHONE, "percent": 5, "app_keys": ["feature.bookings"]})
    assert r.status_code == 403


def test_an_owner_can_grant_directly_with_no_visit_involved(client):
    _wire_fake_billing(client)
    _register_beneficiary(client)
    r = client.post("/api/v1/staff/coupons/grant",
                    headers=_auth("operations.grant_coupon_direct", tenant=GRANTER),
                    json={"phone": PHONE, "percent": 5, "app_keys": ["feature.bookings"]})
    assert r.status_code == 200
    assert r.json()["outcome"] == "granted"


def test_the_response_never_carries_the_beneficiarys_tenant_id(client):
    _wire_fake_billing(client)
    _register_beneficiary(client)
    r = client.post("/api/v1/staff/coupons/grant",
                    headers=_auth("operations.grant_coupon_direct", tenant=GRANTER),
                    json={"phone": PHONE, "percent": 5, "app_keys": ["feature.bookings"]})
    body = r.json()
    assert BENEFICIARY not in str(body)


def test_an_unregistered_phone_is_reported_as_no_account_not_a_500(client):
    _wire_fake_billing(client)
    r = client.post("/api/v1/staff/coupons/grant",
                    headers=_auth("operations.grant_coupon_direct", tenant=GRANTER),
                    json={"phone": "0509999999", "percent": 5, "app_keys": ["feature.bookings"]})
    assert r.status_code == 200
    assert r.json()["outcome"] == "no_account"


# ── history is visible to either door's holder ──────────────────────────────────────────────────
def test_history_is_visible_to_the_visit_linked_capability_too(client):
    _wire_fake_billing(client)
    _register_beneficiary(client)
    client.post("/api/v1/staff/coupons/grant",
               headers=_auth("operations.grant_coupon_direct", tenant=GRANTER),
               json={"phone": PHONE, "percent": 5, "app_keys": ["feature.bookings"]})
    r = client.get("/api/v1/staff/coupons/history",
                   headers=_auth("operations.grant_coupon", tenant=GRANTER))
    assert r.status_code == 200
    assert len(r.json()["attempts"]) == 1


def test_a_capability_holder_only_sees_his_own_tenants_history(client):
    _wire_fake_billing(client)
    _register_beneficiary(client)
    client.post("/api/v1/staff/coupons/grant",
               headers=_auth("operations.grant_coupon_direct", tenant=GRANTER),
               json={"phone": PHONE, "percent": 5, "app_keys": ["feature.bookings"]})
    r = client.get("/api/v1/staff/coupons/history",
                   headers=_auth("operations.grant_coupon_direct", tenant="tnt_someone_else"))
    assert r.json()["attempts"] == []


# ── the visit-recording checkbox ────────────────────────────────────────────────────────────────
def test_a_coupon_grant_riding_on_a_real_visit_is_attempted(client):
    _wire_fake_billing(client)
    _register_beneficiary(client)
    r = client.post("/api/v1/field/visits",
                    headers=_auth("operations.record", "operations.grant_coupon", tenant=GRANTER),
                    json={"phone": "0512345678", "service_ids": ["srv_1"],
                         "idempotency_key": "idem1",
                         "coupon_phone": PHONE, "coupon_percent": 5,
                         "coupon_app_keys": ["feature.bookings"]})
    assert r.status_code == 201
    assert r.json()["coupon_attempt"]["outcome"] == "granted"


def test_a_visit_still_saves_even_when_the_operator_lacks_the_coupon_capability(client):
    _wire_fake_billing(client)
    _register_beneficiary(client)
    r = client.post("/api/v1/field/visits",
                    headers=_auth("operations.record", tenant=GRANTER),
                    json={"phone": "0512345678", "service_ids": ["srv_1"],
                         "idempotency_key": "idem2",
                         "coupon_phone": PHONE, "coupon_percent": 5,
                         "coupon_app_keys": ["feature.bookings"]})
    assert r.status_code == 201
    assert "coupon_attempt" not in r.json()


# ── the platform admin's own settings/override routes ───────────────────────────────────────────
def test_settings_round_trip(client):
    r = client.patch("/api/v1/platform/coupons/settings",
                     headers=_auth("platform.operations", tenant=""),
                     json={"ceiling_percent": 30, "base_percent": 8,
                          "tiers": [{"max_grants": 50, "percent": 20}]})
    assert r.status_code == 200
    r2 = client.get("/api/v1/platform/coupons/settings",
                    headers=_auth("platform.operations", tenant=""))
    body = r2.json()
    assert body["ceiling_percent"] == 30
    assert body["tiers"] == [{"max_grants": 50, "percent": 20}]


def test_settings_refuses_an_invalid_ceiling(client):
    r = client.patch("/api/v1/platform/coupons/settings",
                     headers=_auth("platform.operations", tenant=""),
                     json={"ceiling_percent": 0, "base_percent": 5})
    assert r.status_code == 422


def test_a_tenant_override_raises_a_shops_own_cap_and_is_clamped_by_the_ceiling(client):
    client.patch("/api/v1/platform/coupons/settings",
                headers=_auth("platform.operations", tenant=""),
                json={"ceiling_percent": 35, "base_percent": 5})
    r = client.patch(f"/api/v1/platform/coupons/tenants/{GRANTER}",
                     headers=_auth("platform.operations", tenant=""),
                     json={"tenant": GRANTER, "percent": 30, "note": "reward"})
    assert r.status_code == 200
    assert r.json()["percent"] == 30

    r2 = client.patch(f"/api/v1/platform/coupons/tenants/{GRANTER}",
                      headers=_auth("platform.operations", tenant=""),
                      json={"tenant": GRANTER, "percent": 40, "note": "too high"})
    assert r2.status_code == 422


def test_a_body_tenant_mismatch_is_refused(client):
    r = client.patch(f"/api/v1/platform/coupons/tenants/{GRANTER}",
                     headers=_auth("platform.operations", tenant=""),
                     json={"tenant": "tnt_someone_else", "percent": 10})
    assert r.status_code == 400


def test_a_plain_tenant_token_cannot_reach_the_platform_settings(client):
    r = client.get("/api/v1/platform/coupons/settings",
                   headers=_auth("operations.manage", tenant=GRANTER))
    assert r.status_code == 403
