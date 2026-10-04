"""POST /api/v1/field/visits — REAL engine, real HTTP, real CustomerStore, end to end.

`test_field_visits_referral_code.py` proves the wiring (route -> `Operations.record_visit` ->
whatever engine is installed) using a `FakeEngine` that never actually implements eligibility —
it just returns whatever `refuse_with` says. That leaves a real gap: nothing proves the REAL
`ReferralRedemptionEngine` (with its real `_check_beneficiary_eligibility`) actually drives an
accept/refuse decision when reached through the real HTTP route on a RETURNING customer, which is
exactly the scenario this whole feature (owner instruction, 2026-09-27) exists for.

Only the `referrals` peer itself is faked here (an out-of-process HTTP service this test suite
does not run) — the engine, the affiliate service, and the customer store are all the real
classes, wired the same way `app/container.py` wires them at boot.
"""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

SECRET = "h" * 40
ISS, AUD = "iss", "aud"
CODE = "AB123"
REFERRER_PHONE = "966511111111"
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


class _FakeReferralsDesk:
    """Same shape `test_referral_redemption.py`'s own fake takes — only the peer, never the
    engine, is stood in for."""

    def __init__(self, *, campaign: dict) -> None:
        self._campaign = campaign
        self.configured = True

    async def lookup_code(self, code: str):
        return REFERRER_PHONE if code == CODE else None

    async def active_campaign(self, tenant: str):
        return self._campaign


def _campaign(**over) -> dict:
    base = {
        "id": "camp_e2e", "mode": "lifetime", "min_spend_minor": 0,
        "usage_cap_period": "", "usage_cap_limit": 0, "x_times_limit": 0,
        "reward_type": "fixed_points", "reward_params": {"points": 10},
        "new_customer_reward_type": "welcome_points", "new_customer_reward_params": {"points": 5},
        "beneficiary_eligibility": "new", "beneficiary_max_visits": 0,
    }
    base.update(over)
    return base


async def _seed_referrer(container, tenant: str) -> None:
    # THE ORDINARY GLOBAL CODE IS ONLY EVER HONOURED AT A SHOP THE REFERRER IS ALREADY A REAL
    # CUSTOMER OF (referral_redemption.py's own deep-review Phase 5c rule) — every tenant this
    # file registers CODE against needs REFERRER_PHONE seeded as a customer first, or the real
    # engine refuses the code outright regardless of the beneficiary's own eligibility.
    #
    # SEEDED IN THE REAL STORAGE FORM (`_normalise_phone`, no leading "+") — every real writer of
    # a Customer row (record_visit, ensure_customer, mobile_requests) stores it that way; seeding
    # with `canonical_phone`'s "+966..." form instead would silently pass only because it matched
    # a bug in the engine's own by_phone lookups (fixed in referral_redemption.py — see that
    # module's own import-time note), never because it matched anything real.
    from app.core.models import Customer
    from app.core.operations import _normalise_phone
    from app.core.stores import CustomerStore, new_id

    await CustomerStore(container.datastore).save(
        Customer(id=new_id("cus"), tenant=tenant,
                phone=_normalise_phone(REFERRER_PHONE), subject_ref="referrer"))


@pytest.fixture
def client_with_real_engine():
    import asyncio

    from app.core.referral_redemption import ReferralRedemptionEngine

    client = _make_app()
    container = client.app.state.container

    def wire(campaign: dict, *, tenants: tuple[str, ...] = ()) -> ReferralRedemptionEngine:
        engine = ReferralRedemptionEngine(
            store=container.datastore, referrals_desk=_FakeReferralsDesk(campaign=campaign),
            loyalty_desk=container.loyalty_desk, pii_salt="s" * 32, default_cc="966",
            affiliates=container.affiliates)
        container.operations.with_referral_redemption_engine(engine)
        for tenant in tenants:
            asyncio.run(_seed_referrer(container, tenant))
        return engine

    return client, wire


def _auth(*, tenant: str) -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "op1", "iss": ISS, "aud": AUD, "caps": list(RECORD_CAPS),
                      "tenant": tenant, "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


def _visit(client, *, tenant: str, phone: str, code: str = "", idem: str = "") -> dict:
    body: dict = {"phone": phone, "service_ids": ["srv_1"]}
    if code:
        body["referral_code"] = code
    if idem:
        body["idempotency_key"] = idem
    r = client.post("/api/v1/field/visits", headers=_auth(tenant=tenant), json=body)
    assert r.status_code == 201, r.text
    return r.json()


# ── default "new" mode, through the real route + real engine ───────────────────────────────────
def test_default_new_mode_accepts_a_brand_new_customer_through_the_real_route(client_with_real_engine):
    client, wire = client_with_real_engine
    tenant = "tnt_e2e_new_ok"
    wire(_campaign(), tenants=(tenant,))
    body = _visit(client, tenant=tenant, phone="0501111111", code=CODE)
    assert body["referral_registration"] == {
        "ok": True, "new_customer_reward_type": "welcome_points",
        "new_customer_reward_params": {"points": 5}}


def test_default_new_mode_refuses_a_returning_customer_through_the_real_route(client_with_real_engine):
    client, wire = client_with_real_engine
    tenant = "tnt_e2e_new_refuse"
    wire(_campaign(), tenants=(tenant,))
    _visit(client, tenant=tenant, phone="0502222222", idem="v1")
    second = _visit(client, tenant=tenant, phone="0502222222", code=CODE, idem="v2")
    assert second["referral_registration"]["ok"] is False
    # AND THE VISIT ITSELF STILL RECORDED — a rejected code never blocks the real transaction.
    assert second["visit"]["id"]


# ── "max_visits" mode, through the real route + real engine + real Customer.visit_count ────────
def test_max_visits_mode_accepts_a_returning_customer_at_or_under_the_limit(client_with_real_engine):
    client, wire = client_with_real_engine
    tenant = "tnt_e2e_maxvisits_ok"
    wire(_campaign(beneficiary_eligibility="max_visits", beneficiary_max_visits=2), tenants=(tenant,))
    phone = "0503333333"
    _visit(client, tenant=tenant, phone=phone, idem="v1")
    second = _visit(client, tenant=tenant, phone=phone, code=CODE, idem="v2")
    # SECOND real visit -> visit_count is now 2, exactly at the configured limit -> still eligible.
    assert second["referral_registration"]["ok"] is True, second["referral_registration"]


def test_max_visits_mode_refuses_a_returning_customer_over_the_limit(client_with_real_engine):
    client, wire = client_with_real_engine
    tenant = "tnt_e2e_maxvisits_refuse"
    wire(_campaign(beneficiary_eligibility="max_visits", beneficiary_max_visits=1), tenants=(tenant,))
    phone = "0504444444"
    _visit(client, tenant=tenant, phone=phone, idem="v1")
    _visit(client, tenant=tenant, phone=phone, idem="v2")
    # THIRD real visit -> visit_count is now 3, past the configured limit of 1.
    third = _visit(client, tenant=tenant, phone=phone, code=CODE, idem="v3")
    assert third["referral_registration"]["ok"] is False


# ── "open" mode, through the real route + real engine ───────────────────────────────────────────
def test_open_mode_accepts_any_returning_customer_through_the_real_route(client_with_real_engine):
    client, wire = client_with_real_engine
    tenant = "tnt_e2e_open"
    wire(_campaign(beneficiary_eligibility="open"), tenants=(tenant,))
    phone = "0505555555"
    for i in range(5):
        _visit(client, tenant=tenant, phone=phone, idem=f"v{i}")
    last = _visit(client, tenant=tenant, phone=phone, code=CODE, idem="v-last")
    assert last["referral_registration"]["ok"] is True


# ── each tenant's own campaign setting is truly independent through the real route ──────────────
def test_two_tenants_get_different_real_outcomes_from_the_same_stock_returning_customer_shape(
        client_with_real_engine):
    client, wire = client_with_real_engine
    phone = "0506666666"

    strict_tenant = "tnt_e2e_cmp_strict"
    wire(_campaign(beneficiary_eligibility="new"), tenants=(strict_tenant,))
    _visit(client, tenant=strict_tenant, phone=phone, idem="s1")
    strict_second = _visit(client, tenant=strict_tenant, phone=phone, code=CODE, idem="s2")
    assert strict_second["referral_registration"]["ok"] is False

    open_tenant = "tnt_e2e_cmp_open"
    wire(_campaign(beneficiary_eligibility="open"), tenants=(open_tenant,))
    _visit(client, tenant=open_tenant, phone=phone, idem="o1")
    open_second = _visit(client, tenant=open_tenant, phone=phone, code=CODE, idem="o2")
    assert open_second["referral_registration"]["ok"] is True
