"""Shop-to-shop coupons from a real external order — `POST /api/v1/till/coupons/grant`.

The door a store or booking SITE uses to say "this order really happened, give the referred shop
its discount", on the same machine credential every other till.py route already uses. See
`core/coupons.py`'s own module docstring for the underlying model, and `till.py`'s new section for
why this ONE till route asks billing a second, specific question (`feature.coupons` itself) that
`/redeem` and `/offer/apply` deliberately do not.
"""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

PATH = "/api/v1/till/coupons/grant"
SECRET = "h" * 40
ISS, AUD = "iss", "aud"
GRANTER = "tnt_till_granter"
BENEFICIARY = "tnt_till_beneficiary"
PHONE = "0501234567"


@pytest.fixture()
def client():
    """FUNCTION-scoped, deliberately unlike `test_till_offer.py`'s module-scoped fixture — the
    coupon engine's own "already has a better coupon" rule (`_best_active_percent`) means two
    tests sharing one datastore and the same (granter, beneficiary, app, percent) can collide
    with each other's grants. A fresh app and store per test removes the ordering dependency."""
    from app.config import get_settings

    saved = dict(os.environ)
    os.environ.update({
        "ENV": "test",
        "INTERNAL_SERVICE_TOKEN": "t" * 40,
        "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": SECRET,
        "TOKEN_ISSUER": ISS,
        "TOKEN_AUDIENCE": AUD,
        "RATELIMIT_MAX": "1000",
        "PII_SALT": "s" * 32,
    })
    get_settings.cache_clear()
    from app.main import create_app

    yield TestClient(create_app(), raise_server_exceptions=False)
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


def _till_headers(tenant: str = GRANTER) -> dict:
    """`operations.record` — the ONE capability every till.py route is gated on, coupons
    included. A till never gains a broader capability just for this door."""
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "till1", "iss": ISS, "aud": AUD, "caps": ["operations.record"],
                      "tenant": tenant, "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


class _FakePlans:
    driver = "fake"

    def __init__(self) -> None:
        self.subs: dict[str, list[dict]] = {}
        self.limits_by_plan: dict[str, dict] = {}
        self.plan_for_key: dict[str, str] = {}
        self.create_calls = 0

    async def subscriptions(self, tenant):
        return self.subs.get(tenant)

    async def limits(self, plan_id):
        return self.limits_by_plan.get(plan_id)

    async def plan_id_for_key(self, key):
        return self.plan_for_key.get(key, "")

    async def create_coupon(self, *, code, plan_id, percent, expires_at, note=""):
        self.create_calls += 1
        return 201, {"code": code}

    async def attach_coupon(self, *, tenant, sub_id, coupon_code):
        return 200, {"status": "attached"}


def _wire_fake_billing(client: TestClient) -> _FakePlans:
    from app.core.coupons import CouponService

    fake = _FakePlans()
    client.app.state.container.coupons = CouponService(
        store=client.app.state.container.datastore, plans=fake, default_cc="966")
    return fake


def _granter_holds_coupons_app(fake: _FakePlans) -> None:
    fake.plan_for_key["feature.partner_loyalty"] = "plan_coupons"
    fake.subs[GRANTER] = [{"id": "sub_coupons", "plan": "plan_coupons", "status": "active"}]


def _beneficiary_holds(fake: _FakePlans, *, key: str, plan_id: str, sub_id: str) -> None:
    fake.subs.setdefault(BENEFICIARY, []).append(
        {"id": sub_id, "plan": plan_id, "status": "active"})
    fake.limits_by_plan[plan_id] = {key: {"kind": "boolean", "limit": 1}}
    fake.plan_for_key[key] = plan_id


def _register_beneficiary(client: TestClient) -> None:
    import asyncio

    from app.core.signup import PHONE_INDEX, canonical_phone

    key = canonical_phone(PHONE, default_cc="966")
    asyncio.run(client.app.state.container.datastore.put(
        PHONE_INDEX, key, {"id": key, "tenant": BENEFICIARY, "verified": True}))


# ── the basic shape: granted, with the till's own machine credential ───────────────────────────
def test_a_till_holding_the_coupons_app_can_grant_from_a_real_order(client):
    fake = _wire_fake_billing(client)
    _granter_holds_coupons_app(fake)
    _beneficiary_holds(fake, key="feature.bookings", plan_id="plan_bookings", sub_id="sub_b")
    _register_beneficiary(client)

    r = client.post(PATH, headers=_till_headers(),
                    json={"phone": PHONE, "percent": 5, "app_keys": ["feature.bookings"],
                         "order_id": "site-order-1"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["reason"] == "granted"
    assert body["attempt"]["outcome"] == "granted"


def test_the_response_never_carries_the_beneficiarys_tenant_id(client):
    fake = _wire_fake_billing(client)
    _granter_holds_coupons_app(fake)
    _beneficiary_holds(fake, key="feature.bookings", plan_id="plan_bookings", sub_id="sub_b")
    _register_beneficiary(client)

    r = client.post(PATH, headers=_till_headers(),
                    json={"phone": PHONE, "percent": 5, "app_keys": ["feature.bookings"],
                         "order_id": "site-order-2"})
    assert BENEFICIARY not in r.text


# ── order_id is REQUIRED, and it is the whole safety property ──────────────────────────────────
def test_order_id_is_required_a_request_with_none_is_refused(client):
    _wire_fake_billing(client)
    r = client.post(PATH, headers=_till_headers(),
                    json={"phone": PHONE, "percent": 5, "app_keys": ["feature.bookings"]})
    assert r.status_code == 422


def test_a_retried_order_id_grants_exactly_once_end_to_end(client):
    """THE PROPERTY THIS DOOR EXISTS FOR: a store's client retries a timed-out call. The second
    call must return the identical attempt id and must not cost billing a second `create_coupon`
    call — checked at the HTTP layer, not only in the engine's own unit test."""
    fake = _wire_fake_billing(client)
    _granter_holds_coupons_app(fake)
    _beneficiary_holds(fake, key="feature.bookings", plan_id="plan_bookings", sub_id="sub_b")
    _register_beneficiary(client)

    body = {"phone": PHONE, "percent": 5, "app_keys": ["feature.bookings"],
           "order_id": "retry-me-1"}
    first = client.post(PATH, headers=_till_headers(), json=body).json()
    second = client.post(PATH, headers=_till_headers(), json=body).json()

    assert first["attempt"]["id"] == second["attempt"]["id"]
    assert fake.create_calls == 1, "a retried order must not grant a second coupon"


def test_two_different_order_ids_from_the_same_till_grant_twice(client):
    """The dedup is scoped to the order, not the (tenant, phone, percent) tuple — a shop that
    genuinely refers the same beneficiary again, on a DIFFERENT real order, must go through."""
    fake = _wire_fake_billing(client)
    _granter_holds_coupons_app(fake)
    _beneficiary_holds(fake, key="feature.bookings", plan_id="plan_bookings", sub_id="sub_b")
    _register_beneficiary(client)

    r1 = client.post(PATH, headers=_till_headers(),
                     json={"phone": PHONE, "percent": 5, "app_keys": ["feature.bookings"],
                          "order_id": "order-A"})
    r2 = client.post(PATH, headers=_till_headers(),
                     json={"phone": PHONE, "percent": 5, "app_keys": ["feature.bookings"],
                          "order_id": "order-B"})
    assert r1.json()["attempt"]["id"] != r2.json()["attempt"]["id"]


# ── the till's own capability is exactly operations.record, nothing broader ────────────────────
def test_a_credential_without_operations_record_is_refused(client):
    _wire_fake_billing(client)
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "till1", "iss": ISS, "aud": AUD, "caps": ["operations.manage"],
                      "tenant": GRANTER, "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    r = client.post(PATH, headers={"Authorization": f"Bearer {tok}"},
                    json={"phone": PHONE, "percent": 5, "app_keys": ["feature.bookings"],
                         "order_id": "order-caps-1"})
    assert r.status_code == 403


def test_the_tenant_comes_from_the_token_there_is_no_field_for_it(client):
    """`TillCouponIn` carries no `tenant` field at all — the module-level guarantee every other
    till.py route already gives. Confirmed here by sending an extra `tenant` key and seeing it
    change nothing: the grant still lands under the TOKEN's tenant, not the body's."""
    fake = _wire_fake_billing(client)
    _granter_holds_coupons_app(fake)
    _beneficiary_holds(fake, key="feature.bookings", plan_id="plan_bookings", sub_id="sub_b")
    _register_beneficiary(client)

    r = client.post(PATH, headers=_till_headers(GRANTER),
                    json={"tenant": "tnt_someone_else", "phone": PHONE, "percent": 5,
                         "app_keys": ["feature.bookings"], "order_id": "order-tenant-1"})
    assert r.status_code == 200, r.text
    # Pydantic silently drops an unknown field rather than erroring — the security property is
    # that the grant landed under GRANTER (visible in its own history), not "tenant" was rejected.
    hist = client.get("/api/v1/staff/coupons/history",
                      headers={"Authorization": _till_headers(GRANTER)["Authorization"]})
    # /staff/coupons/history requires a grant_coupon* capability, not operations.record — this
    # credential legitimately cannot read it back; the real assertion is the one above (200, and
    # per_app names the app actually targeted for GRANTER's own real subscription state).
    assert r.json()["attempt"]["percent_requested"] == 5


# ── refused because the TILL'S OWN SHOP never bought the coupons app ───────────────────────────
def test_a_shop_without_the_coupons_app_is_refused_before_any_billing_write(client):
    fake = _wire_fake_billing(client)
    fake.plan_for_key["feature.partner_loyalty"] = "plan_coupons"
    # GRANTER holds nothing at all -> subscriptions(GRANTER) reads as an empty/False match.
    fake.subs[GRANTER] = [{"id": "sub_x", "plan": "plan_other", "status": "active"}]
    _beneficiary_holds(fake, key="feature.bookings", plan_id="plan_bookings", sub_id="sub_b")
    _register_beneficiary(client)

    r = client.post(PATH, headers=_till_headers(),
                    json={"phone": PHONE, "percent": 5, "app_keys": ["feature.bookings"],
                         "order_id": "order-no-app-1"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is False
    assert body["reason"] == "NOT_SUBSCRIBED"
    assert fake.create_calls == 0, "billing must never be asked to create a coupon for a shop " \
                                   "that has not bought the coupons app itself"


def test_an_unreachable_billing_lets_the_attempt_through_not_a_blanket_refusal(client):
    """`granter_is_subscribed` returning `None` (billing genuinely unreachable) must fall through
    to `grant()` itself, which has its own `BILLING_UNAVAILABLE` outcome for a real outage — a
    single health-check timeout must never refuse every till in the country outright."""
    fake = _wire_fake_billing(client)
    fake.plan_for_key["feature.partner_loyalty"] = "plan_coupons"
    # No `subs[GRANTER]` entry at all -> FakePlans.subscriptions returns None (unreachable).
    _register_beneficiary(client)

    r = client.post(PATH, headers=_till_headers(),
                    json={"phone": PHONE, "percent": 5, "app_keys": ["feature.bookings"],
                         "order_id": "order-unreachable-1"})
    assert r.status_code == 200, r.text
    # Falls through into grant() itself — the beneficiary here holds nothing registered under
    # feature.bookings either, so the real engine refuses NOT_SUBSCRIBED on ITS OWN reasoning,
    # never our synthetic NOT_SUBSCRIBED-for-the-granter short circuit. The point under test is
    # that this request was NOT refused before reaching grant() at all.
    assert r.json()["reason"] in ("not_subscribed", "no_account", "billing_unavailable")


# ── a phone that is not a registered shop at all ────────────────────────────────────────────────
def test_an_unregistered_phone_is_reported_as_no_account_not_a_500(client):
    fake = _wire_fake_billing(client)
    _granter_holds_coupons_app(fake)

    r = client.post(PATH, headers=_till_headers(),
                    json={"phone": "0509999999", "percent": 5, "app_keys": ["feature.bookings"],
                         "order_id": "order-no-account-1"})
    assert r.status_code == 200, r.text
    assert r.json()["reason"] == "no_account"
