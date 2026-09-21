"""Referral partnership at the HTTP layer — role gating, and the adversarial cross-tenant reads
the task's own security bar requires: a third tenant, a wrong-role staff member, and the two
parties trying to read/act outside their own side. billing-service is swapped for a fake, same
technique `test_coupons_api.py` already uses for the same reason (no real socket in a unit/
integration test)."""
from __future__ import annotations

import asyncio
import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

TOKEN_SECRET = "h" * 40
ISS, AUD = "iss", "aud"
A = "tnt_ref_a"
B = "tnt_ref_b"
C = "tnt_ref_c"
B_PHONE = "0501234567"


def _make_app() -> TestClient:
    from app.config import get_settings

    os.environ.update({
        "ENV": "test", "INTERNAL_SERVICE_TOKEN": "t" * 40, "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": TOKEN_SECRET, "TOKEN_ISSUER": ISS, "TOKEN_AUDIENCE": AUD,
        "RATELIMIT_MAX": "1000", "PII_SALT": "s" * 32,
    })
    get_settings.cache_clear()
    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


def _auth(*caps: str, tenant: str, subject: str = "op1") -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": subject, "iss": ISS, "aud": AUD, "caps": list(caps),
                      "tenant": tenant, "exp": now + dt.timedelta(minutes=5), "iat": now},
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
        self.plan_for_key = {"feature.referral_partnership": "plan_referral"}

    async def subscriptions(self, tenant):
        return self.subs.get(tenant, [])

    async def plan_id_for_key(self, key):
        return self.plan_for_key.get(key, "")

    async def limits(self, plan_id):
        return {}


def _subscribe(fake: _FakePlans, tenant: str) -> None:
    fake.subs[tenant] = [{"id": f"sub_{tenant}", "plan": "plan_referral", "status": "active"}]


def _wire(client: TestClient) -> _FakePlans:
    from app.core.referral_partnership import ReferralPartnershipEngine

    fake = _FakePlans()
    container = client.app.state.container
    engine = ReferralPartnershipEngine(
        store=container.datastore, plans=fake, notifier=container.inapp_notifier,
        authz=container.authz_desk, default_cc="966")
    container.referral_partnership = engine
    container.operations.with_referral_engine(engine)
    return fake


def _register_phone(client: TestClient, phone: str, tenant: str) -> None:
    from app.core.signup import PHONE_INDEX, canonical_phone

    key = canonical_phone(phone, default_cc="966")
    asyncio.run(client.app.state.container.datastore.put(
        PHONE_INDEX, key, {"id": key, "tenant": tenant, "verified": True}))


def _propose(client: TestClient) -> str:
    resp = client.post("/api/v1/staff/referral-partnership/agreements",
                       headers=_auth("operations.manage", tenant=A),
                       json={"shop_b_phone": B_PHONE, "condition_type": "min_total_minor",
                            "condition_value": "1000", "grant_validity_days": 3, "agreement_duration_days": 90})
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


@pytest.fixture
def wired(client: TestClient) -> TestClient:
    fake = _wire(client)
    _register_phone(client, B_PHONE, B)
    _subscribe(fake, A)
    _subscribe(fake, B)
    return client


def test_a_plain_operator_cannot_propose(wired: TestClient):
    resp = wired.post("/api/v1/staff/referral-partnership/agreements",
                      headers=_auth("operations.record", tenant=A),
                      json={"shop_b_phone": B_PHONE, "condition_type": "min_total_minor",
                           "condition_value": "1000", "grant_validity_days": 3,
                           "agreement_duration_days": 90})
    assert resp.status_code == 403


def test_propose_then_accept_over_http(wired: TestClient):
    agreement_id = _propose(wired)
    resp = wired.post(f"/api/v1/staff/referral-partnership/agreements/{agreement_id}/accept",
                      headers=_auth("operations.manage", tenant=B))
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "active"


def test_a_third_tenant_gets_404_not_someone_elses_data(wired: TestClient):
    agreement_id = _propose(wired)
    resp = wired.get(f"/api/v1/staff/referral-partnership/agreements/{agreement_id}",
                     headers=_auth("operations.manage", tenant=C))
    assert resp.status_code == 404


def test_a_third_tenant_listing_sees_nothing(wired: TestClient):
    _propose(wired)
    resp = wired.get("/api/v1/staff/referral-partnership/agreements",
                     headers=_auth("operations.manage", tenant=C))
    assert resp.status_code == 200
    assert resp.json()["agreements"] == []


def test_the_proposer_cannot_accept_its_own_proposal(wired: TestClient):
    agreement_id = _propose(wired)
    resp = wired.post(f"/api/v1/staff/referral-partnership/agreements/{agreement_id}/accept",
                      headers=_auth("operations.manage", tenant=A))
    assert resp.status_code == 403


def test_a_third_tenant_cannot_accept_someone_elses_proposal(wired: TestClient):
    agreement_id = _propose(wired)
    resp = wired.post(f"/api/v1/staff/referral-partnership/agreements/{agreement_id}/accept",
                      headers=_auth("operations.manage", tenant=C))
    assert resp.status_code in (403, 404)


def test_no_auth_token_at_all_is_refused(wired: TestClient):
    resp = wired.get("/api/v1/staff/referral-partnership/kpis")
    assert resp.status_code in (401, 403)


def test_kpis_are_per_tenant_isolated_over_http(wired: TestClient):
    agreement_id = _propose(wired)
    wired.post(f"/api/v1/staff/referral-partnership/agreements/{agreement_id}/accept",
              headers=_auth("operations.manage", tenant=B))
    resp_c = wired.get("/api/v1/staff/referral-partnership/kpis",
                       headers=_auth("operations.manage", tenant=C))
    assert resp_c.status_code == 200
    assert resp_c.json()["as_referrer"]["referrals_sent"] == 0


def test_a_shop_without_the_paid_feature_cannot_propose_over_http(client: TestClient):
    fake = _wire(client)
    _register_phone(client, B_PHONE, B)
    _subscribe(fake, B)
    # A never subscribed
    resp = client.post("/api/v1/staff/referral-partnership/agreements",
                       headers=_auth("operations.manage", tenant=A),
                       json={"shop_b_phone": B_PHONE, "condition_type": "min_total_minor",
                            "condition_value": "1000", "grant_validity_days": 3,
                            "agreement_duration_days": 90})
    assert resp.status_code == 402
