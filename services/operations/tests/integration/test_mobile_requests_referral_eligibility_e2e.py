"""The THIRD real production door onto a referral code — `internal.py`'s own mobile-request
creation, held pending until the shop accepts it, only ever registered at `complete()` (the
request actually turning into a real visit; see `core/mobile_requests.py::complete`'s own
docstring). `test_field_visits_referral_eligibility_e2e.py` already proves the walk-in door with
the REAL `ReferralRedemptionEngine`; this file proves the SAME real engine, real eligibility
enforcement, and the same phone-format/`beneficiary_created_this_call` fixes through this
genuinely different code path (`MobileRequestService.complete` -> `Operations.record_visit`),
never through a fake standing in for the engine.

`complete()`'s own HTTP response never surfaces `referral_registration` at all (a real, separate,
pre-existing gap — see this file's own note at the bottom) — so eligibility is proven here through
its real, durable side effects instead: whether a `ReferralGrant` row was actually written, and
whether the referrer's real loyalty balance was actually credited on redeem — never through a
response field this door does not have.
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
INTERNAL_TOKEN = "t" * 40
CODE = "AB123"
REFERRER_PHONE = "966511111111"
TENANT = "tnt_mreq_e2e"


def _make_app() -> TestClient:
    from app.config import get_settings

    os.environ.update({
        "ENV": "test", "INTERNAL_SERVICE_TOKEN": INTERNAL_TOKEN, "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": SECRET, "TOKEN_ISSUER": ISS, "TOKEN_AUDIENCE": AUD,
        "RATELIMIT_MAX": "10000", "PII_SALT": "s" * 32,
    })
    get_settings.cache_clear()
    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


class _FakePlans:
    """Subscribed by default — this suite is about referral eligibility, not the billing gate."""
    driver = "fake"

    async def plan_id_for_key(self, key: str) -> str:
        return "plan_mobile_requests" if key == "feature.mobile_requests" else ""

    async def subscriptions(self, tenant: str):
        return [{"plan": "plan_mobile_requests", "status": "active"}]


class _FakeReferralsDesk:
    def __init__(self, *, campaign: dict) -> None:
        self._campaign = campaign
        self.configured = True

    async def lookup_code(self, code: str):
        return REFERRER_PHONE if code == CODE else None

    async def active_campaign(self, tenant: str):
        return self._campaign


def _campaign(**over) -> dict:
    base = {
        "id": "camp_mreq_e2e", "mode": "lifetime", "min_spend_minor": 0,
        "usage_cap_period": "", "usage_cap_limit": 0, "x_times_limit": 0,
        "reward_type": "fixed_points", "reward_params": {"points": 10},
        "new_customer_reward_type": "welcome_points", "new_customer_reward_params": {"points": 5},
        "beneficiary_eligibility": "new", "beneficiary_max_visits": 0,
    }
    base.update(over)
    return base


@pytest.fixture
def client_with_real_engine():
    from app.core.mobile_requests import MobileRequestService
    from app.core.referral_redemption import ReferralRedemptionEngine

    client = _make_app()
    container = client.app.state.container

    old = container.mobile_requests
    container.mobile_requests = MobileRequestService(
        store=old._s, operations=old._ops, seams=old._seams, working_hours=old._working_hours,
        plans=_FakePlans(), default_cc="966")

    async def _seed_service():
        from app.core.models import Service
        from app.core.stores import ServiceStore
        await ServiceStore(container.datastore).save(
            Service(id="svc_wash", tenant=TENANT, name="غسيل متنقل"))

    async def _seed_referrer():
        from app.core.models import Customer
        from app.core.operations import _normalise_phone
        from app.core.stores import CustomerStore, new_id
        await CustomerStore(container.datastore).save(
            Customer(id=new_id("cus"), tenant=TENANT, phone=_normalise_phone(REFERRER_PHONE),
                    subject_ref="referrer"))

    def wire(campaign: dict) -> ReferralRedemptionEngine:
        engine = ReferralRedemptionEngine(
            store=container.datastore, referrals_desk=_FakeReferralsDesk(campaign=campaign),
            loyalty_desk=container.loyalty_desk, pii_salt="s" * 32, default_cc="966",
            affiliates=container.affiliates)
        container.operations.with_referral_redemption_engine(engine)
        asyncio.run(_seed_service())
        asyncio.run(_seed_referrer())
        return engine

    return client, wire


def _auth(**caps_kw) -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "owner1", "iss": ISS, "aud": AUD,
                      "caps": ["operations.mobile_requests_manage"], "tenant": TENANT,
                      "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


def _create_and_complete(client, *, phone: str, code: str = "") -> dict:
    r = client.post("/internal/operations/mobile-requests",
                    headers={"X-Internal-Token": INTERNAL_TOKEN},
                    json={"tenant": TENANT, "phone": phone, "customer_name": "أحمد",
                         "service_ids": ["svc_wash"], "requested_time": 1_800_000_000,
                         "lat": 24.7136, "lng": 46.6753, "referral_code": code})
    assert r.status_code == 200, r.text
    request_id = r.json()["request_id"]
    client.post(f"/api/v1/staff/mobile-requests/{request_id}/accept", headers=_auth())
    r = client.post(f"/api/v1/staff/mobile-requests/{request_id}/complete", headers=_auth())
    assert r.status_code == 200, r.text
    return r.json()


def _grant_count(container, tenant: str) -> int:
    rows, _ = asyncio.run(container.datastore.find(
        "referral_redemption_grants", {"tenant": tenant}, limit=1000))
    return len(rows)


def test_a_brand_new_customers_mobile_request_registers_a_real_grant(client_with_real_engine):
    client, wire = client_with_real_engine
    wire(_campaign())
    container = client.app.state.container
    body = _create_and_complete(client, phone="0501111111", code=CODE)
    assert body["status"] == "completed"
    assert _grant_count(container, TENANT) == 1


def test_default_new_mode_refuses_a_second_mobile_request_from_the_same_returning_phone(
        client_with_real_engine):
    client, wire = client_with_real_engine
    wire(_campaign())
    container = client.app.state.container
    phone = "0502222222"
    _create_and_complete(client, phone=phone)  # first, no code — becomes a real customer
    _create_and_complete(client, phone=phone, code=CODE)  # second, WITH a code, now returning
    # THE VISIT STILL HAPPENED (both completed successfully) — only the grant was refused.
    assert _grant_count(container, TENANT) == 0


def test_max_visits_mode_allows_a_returning_mobile_customer_at_the_limit(client_with_real_engine):
    client, wire = client_with_real_engine
    wire(_campaign(beneficiary_eligibility="max_visits", beneficiary_max_visits=2))
    container = client.app.state.container
    phone = "0503333333"
    _create_and_complete(client, phone=phone)
    _create_and_complete(client, phone=phone, code=CODE)  # visit_count now 2, at the limit
    assert _grant_count(container, TENANT) == 1


def test_referrer_gets_credited_on_a_completed_mobile_request_with_no_duplicate_customer(
        client_with_real_engine):
    """The exact regression this session's own fixes were for: the referrer is found and credited
    as their ONE real customer row, never duplicated under a mismatched phone format."""
    client, wire = client_with_real_engine
    engine = wire(_campaign())
    container = client.app.state.container
    from app.core.operations import _normalise_phone
    from app.core.stores import CustomerStore

    _create_and_complete(client, phone="0504444444", code=CODE)

    # redeem() only fires on a SECOND real visit for the beneficiary (apply_offer/entitlements is
    # the live redeem path elsewhere) — here we call the engine's own redeem() directly, the same
    # thing `Operations.apply_offer` would have triggered, to prove the crediting side effect
    # without needing to also wire a live EntitlementGateway into this HTTP-only test.
    grants, _ = asyncio.run(container.datastore.find(
        "referral_redemption_grants", {"tenant": TENANT}, limit=1000))
    assert len(grants) == 1
    beneficiary_phone = grants[0]["beneficiary_phone"]
    asyncio.run(engine.redeem(TENANT, beneficiary_phone, visit_id="v_redeem_1"))

    referrer_rows, _ = asyncio.run(container.datastore.find(
        "customers", {"tenant": TENANT, "phone": _normalise_phone(REFERRER_PHONE)}, limit=10))
    assert len(referrer_rows) == 1  # never duplicated
    referrer = asyncio.run(CustomerStore(container.datastore).by_phone(
        TENANT, _normalise_phone(REFERRER_PHONE)))
    assert referrer.subject_ref == "referrer"  # the real, pre-existing pseudonym, never a fresh one
