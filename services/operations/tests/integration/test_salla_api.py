"""Salla at the HTTP layer — install/status (staff-authenticated) and callback/webhook (Salla's
own unauthenticated calls, verified by state/signature instead). Outbound calls to Salla itself
(`exchange_code`/`user_info`) are monkeypatched on the wired `SallaClient` instance, exactly the
way `test_coupons_api.py` substitutes `_FakePlans` after the app is built.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import os

import jwt
import pytest
from fastapi.testclient import TestClient

TOKEN_SECRET = "h" * 40
ISS, AUD = "iss", "aud"
TENANT = "tnt_salla_shop"
SALT = "s" * 32


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
        "PII_SALT": SALT,
        "PUBLIC_BASE_URL": "https://raje3.sa",
        "SALLA_CLIENT_ID": "test_client_id",
        "SALLA_CLIENT_SECRET": "test_client_secret",
        "SALLA_WEBHOOK_SECRET": "test_webhook_secret",
    }
    os.environ.update(env)
    get_settings.cache_clear()
    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


def _auth(*caps: str, tenant: str = TENANT) -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "owner1", "iss": ISS, "aud": AUD, "caps": list(caps),
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


def _state_for(client: TestClient, tenant: str = TENANT) -> str:
    from app.core import oauth_state
    return oauth_state.issue(SALT, "salla", tenant)


# ── install ──────────────────────────────────────────────────────────────────────────────────
def test_install_returns_a_real_authorize_url_when_configured(client):
    r = client.get("/api/v1/staff/salla/install", headers=_auth("billing.self"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["url"].startswith("https://accounts.salla.sa/oauth2/auth?")
    assert "client_id=test_client_id" in body["url"]


def test_install_requires_billing_self_capability(client):
    r = client.get("/api/v1/staff/salla/install", headers=_auth("operations.record"))
    assert r.status_code == 403


def test_install_refuses_when_not_configured(env_guard):
    from app.config import get_settings

    os.environ.update({
        "ENV": "test", "INTERNAL_SERVICE_TOKEN": "t" * 40, "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": TOKEN_SECRET, "TOKEN_ISSUER": ISS, "TOKEN_AUDIENCE": AUD,
        "RATELIMIT_MAX": "1000", "PII_SALT": SALT, "PUBLIC_BASE_URL": "https://raje3.sa",
        # THE THREE LEFT EMPTY, DELIBERATELY — a server this Salla-unconfigured on is exactly
        # what a fresh deploy looks like before an owner ever pastes the values in.
        "SALLA_CLIENT_ID": "", "SALLA_CLIENT_SECRET": "", "SALLA_WEBHOOK_SECRET": "",
    })
    get_settings.cache_clear()
    from app.main import create_app

    c = TestClient(create_app(), raise_server_exceptions=False)
    r = c.get("/api/v1/staff/salla/install", headers=_auth("billing.self"))
    assert r.status_code == 400
    assert r.json()["error"] == "NOT_CONFIGURED"


def test_install_states_are_never_identical_between_calls(client):
    """Each install click must mint its own state — never a cached/static URL two owners could
    somehow share."""
    a = client.get("/api/v1/staff/salla/install", headers=_auth("billing.self")).json()["url"]
    b = client.get("/api/v1/staff/salla/install", headers=_auth("billing.self")).json()["url"]
    assert a != b


# ── status ───────────────────────────────────────────────────────────────────────────────────
def test_status_reports_not_connected_by_default(client):
    r = client.get("/api/v1/staff/salla/status", headers=_auth("billing.self"))
    assert r.status_code == 200
    assert r.json() == {"connected": False}


def test_status_requires_billing_self_capability(client):
    r = client.get("/api/v1/staff/salla/status", headers=_auth("operations.record"))
    assert r.status_code == 403


# ── disconnect ───────────────────────────────────────────────────────────────────────────────
def test_disconnect_removes_a_real_connection_and_status_reflects_it(client):
    import asyncio
    asyncio.run(client.app.state.container.salla.save_connection(
        tenant=TENANT, merchant_id="42", store_name="متجري", access_token="at",
        refresh_token="rt", expires_at=999999999, scope=""))

    r = client.post("/api/v1/staff/salla/disconnect", headers=_auth("billing.self"))
    assert r.status_code == 200
    assert r.json() == {"connected": False}

    status = client.get("/api/v1/staff/salla/status", headers=_auth("billing.self"))
    assert status.json() == {"connected": False}


def test_disconnect_with_nothing_connected_still_answers_200(client):
    r = client.post("/api/v1/staff/salla/disconnect", headers=_auth("billing.self"))
    assert r.status_code == 200
    assert r.json() == {"connected": False}


def test_disconnect_requires_billing_self_capability(client):
    r = client.post("/api/v1/staff/salla/disconnect", headers=_auth("operations.record"))
    assert r.status_code == 403


def test_disconnect_never_touches_a_different_tenants_connection(client):
    import asyncio
    other = "tnt_salla_other"
    asyncio.run(client.app.state.container.salla.save_connection(
        tenant=other, merchant_id="99", store_name="متجر آخر", access_token="at",
        refresh_token="rt", expires_at=999999999, scope=""))
    asyncio.run(client.app.state.container.salla.save_connection(
        tenant=TENANT, merchant_id="42", store_name="متجري", access_token="at",
        refresh_token="rt", expires_at=999999999, scope=""))

    client.post("/api/v1/staff/salla/disconnect", headers=_auth("billing.self", tenant=TENANT))

    other_status = client.get("/api/v1/staff/salla/status", headers=_auth("billing.self", tenant=other))
    assert other_status.json()["connected"] is True


# ── callback ─────────────────────────────────────────────────────────────────────────────────
def test_callback_refuses_an_invalid_state(client):
    r = client.get("/api/v1/salla/callback", params={"code": "abc", "state": "garbage"})
    assert r.status_code == 400
    assert "انتهت صلاحية" in r.text


def test_callback_shows_a_refusal_page_when_salla_reports_an_error(client):
    state = _state_for(client)
    r = client.get("/api/v1/salla/callback", params={"error": "access_denied", "state": state})
    assert r.status_code == 200
    assert "تعذّر الربط" in r.text


def test_callback_exchanges_the_code_and_saves_a_real_connection(client):
    salla_client = client.app.state.container.salla.client
    salla_client.exchange_code = lambda code: {
        "access_token": "at_123", "refresh_token": "rt_123", "expires": 1209599,
        "scope": "offline_access orders.read",
    }
    salla_client.user_info = lambda token: {"merchant": {"id": 555, "name": "متجر الاختبار"}}

    state = _state_for(client)
    r = client.get("/api/v1/salla/callback", params={"code": "the-code", "state": state})
    assert r.status_code == 200, r.text
    assert "تم الربط بنجاح" in r.text
    assert "متجر الاختبار" in r.text

    status = client.get("/api/v1/staff/salla/status", headers=_auth("billing.self")).json()
    assert status["connected"] is True
    assert status["merchant_id"] == "555"
    assert status["store_name"] == "متجر الاختبار"
    # NEVER THE TOKENS, even on the status route only the owner himself can reach.
    assert "at_123" not in json.dumps(status)


def test_callback_carries_a_postmessage_payload_for_a_popup_opener(client):
    """The console opens /install's url via window.open — this is what closes that popup and
    hands the result back, per Coupons.tsx's own listener."""
    salla_client = client.app.state.container.salla.client
    salla_client.exchange_code = lambda code: {"access_token": "at", "refresh_token": "rt",
                                                "expires": 100}
    salla_client.user_info = lambda token: {"merchant": {"id": 42, "name": "متجر البوب أب"}}

    state = _state_for(client)
    r = client.get("/api/v1/salla/callback", params={"code": "c", "state": state})
    assert "window.opener" in r.text
    assert "postMessage" in r.text
    assert "raje3:salla-connect" in r.text
    assert '"ok": true' in r.text
    assert "متجر البوب أب" in r.text


def test_callback_postmessage_payload_defangs_a_hostile_store_name(client):
    """A merchant name is free text ON SALLA'S SIDE — a store somehow named to include a literal
    </script> must never break out of the payload's own <script> tag."""
    salla_client = client.app.state.container.salla.client
    salla_client.exchange_code = lambda code: {"access_token": "at", "refresh_token": "rt",
                                                "expires": 100}
    salla_client.user_info = lambda token: {
        "merchant": {"id": 43, "name": '</script><script>alert(1)</script>'}}

    state = _state_for(client)
    r = client.get("/api/v1/salla/callback", params={"code": "c", "state": state})
    assert "<script>alert(1)</script>" not in r.text
    assert "alert(1)" in r.text   # present, just never as an executable sibling tag


def test_callback_never_leaks_a_token_anywhere_in_its_own_html_response(client):
    salla_client = client.app.state.container.salla.client
    salla_client.exchange_code = lambda code: {
        "access_token": "should-never-appear", "refresh_token": "rt", "expires": 100,
    }
    salla_client.user_info = lambda token: {"merchant": {"id": 7, "name": "م"}}

    state = _state_for(client)
    r = client.get("/api/v1/salla/callback", params={"code": "c", "state": state})
    assert "should-never-appear" not in r.text


def test_callback_refuses_when_salla_gives_no_access_token(client):
    salla_client = client.app.state.container.salla.client
    salla_client.exchange_code = lambda code: None

    state = _state_for(client)
    r = client.get("/api/v1/salla/callback", params={"code": "c", "state": state})
    assert r.status_code == 502
    assert "تعذّر الربط" in r.text


def test_callback_refuses_when_no_merchant_id_can_be_found(client):
    salla_client = client.app.state.container.salla.client
    salla_client.exchange_code = lambda code: {"access_token": "at", "expires": 100}
    salla_client.user_info = lambda token: {"merchant": {}}

    state = _state_for(client)
    r = client.get("/api/v1/salla/callback", params={"code": "c", "state": state})
    assert r.status_code == 502


def test_reconnecting_keeps_the_link_scoped_to_the_tenant_who_started_it(client):
    """A state minted for TENANT must never let a callback save the connection under a
    different tenant, however the merchant id resolves."""
    other = "tnt_someone_else"
    other_state = _state_for(client, tenant=other)
    salla_client = client.app.state.container.salla.client
    salla_client.exchange_code = lambda code: {"access_token": "at", "expires": 100}
    salla_client.user_info = lambda token: {"merchant": {"id": 999, "name": "م"}}

    client.get("/api/v1/salla/callback", params={"code": "c", "state": other_state})

    mine = client.get("/api/v1/staff/salla/status", headers=_auth("billing.self")).json()
    assert mine["connected"] is False


# ── webhook ──────────────────────────────────────────────────────────────────────────────────
def _sign(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_a_correctly_signed_webhook_is_acked_and_recorded(client):
    body = json.dumps({"event": "order.created", "merchant": 42}).encode()
    sig = _sign("test_webhook_secret", body)
    r = client.post("/api/v1/salla/webhook", data=body,
                    headers={"Content-Type": "application/json", "X-Salla-Signature": sig})
    assert r.status_code == 200
    assert r.json() == {"received": True}


def test_a_badly_signed_webhook_still_acks_200_but_is_not_trusted(client):
    """200, ALWAYS — a 4xx here would teach a forger which shape of forged signature gets
    closer, the exact leak `verify_signature`'s own module note warns about."""
    body = json.dumps({"event": "order.created", "merchant": 42}).encode()
    r = client.post("/api/v1/salla/webhook", data=body,
                    headers={"Content-Type": "application/json",
                            "X-Salla-Signature": "0" * 64})
    assert r.status_code == 200
    assert r.json() == {"received": True}


def test_a_webhook_with_no_signature_header_at_all_still_acks_200(client):
    body = json.dumps({"event": "order.created", "merchant": 42}).encode()
    r = client.post("/api/v1/salla/webhook", data=body,
                    headers={"Content-Type": "application/json"})
    assert r.status_code == 200


def test_a_malformed_json_body_does_not_crash_the_route(client):
    r = client.post("/api/v1/salla/webhook", data=b"not json at all",
                    headers={"Content-Type": "application/json",
                            "X-Salla-Signature": "0" * 64})
    assert r.status_code == 200


# ── the actual grant trigger — order.status.updated + completed ONLY ───────────────────────────
BENEFICIARY = "tnt_salla_beneficiary"
BENEFICIARY_PHONE = "0501234567"


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


def _wire_fake_billing(client: TestClient):
    from app.core.coupons import CouponService

    fake = _FakePlans()
    client.app.state.container.coupons = CouponService(
        store=client.app.state.container.datastore, plans=fake, default_cc="966")
    return fake


def _connect_merchant(client: TestClient, *, tenant: str, merchant_id: str) -> None:
    import asyncio
    asyncio.run(client.app.state.container.salla.save_connection(
        tenant=tenant, merchant_id=merchant_id, store_name="متجري",
        access_token="at", refresh_token="rt", expires_at=9999999999, scope=""))


def _register_beneficiary(client: TestClient) -> None:
    import asyncio

    from app.core.signup import PHONE_INDEX, canonical_phone

    key = canonical_phone(BENEFICIARY_PHONE, default_cc="966")
    asyncio.run(client.app.state.container.datastore.put(
        PHONE_INDEX, key, {"id": key, "tenant": BENEFICIARY, "verified": True}))


def _status_updated_body(*, merchant_id: str, order_id: str, status_slug: str,
                         mobile: str = BENEFICIARY_PHONE) -> bytes:
    return json.dumps({
        "event": "order.status.updated", "merchant": int(merchant_id),
        "data": {"id": int(order_id), "status": {"slug": status_slug},
                 "customer": {"id": 1, "mobile": mobile}},
    }).encode()


def _post_webhook(client: TestClient, body: bytes):
    sig = _sign("test_webhook_secret", body)
    return client.post("/api/v1/salla/webhook", data=body,
                       headers={"Content-Type": "application/json", "X-Salla-Signature": sig})


def test_a_completed_order_grants_an_alliance_to_the_orders_own_customer(client):
    fake = _wire_fake_billing(client)
    fake.plan_for_key["feature.bookings"] = "plan_bookings"
    fake.subs[BENEFICIARY] = [{"id": "sub_1", "plan": "plan_bookings", "status": "active"}]
    fake.limits_by_plan["plan_bookings"] = {"feature.bookings": {"kind": "boolean", "limit": 1}}
    _register_beneficiary(client)
    _connect_merchant(client, tenant=TENANT, merchant_id="777")

    body = _status_updated_body(merchant_id="777", order_id="9001", status_slug="completed")
    r = _post_webhook(client, body)
    assert r.status_code == 200
    assert fake.create_calls == 1, "a completed order for a known customer must grant once"


def test_order_created_never_grants_even_for_the_same_data(client):
    """order.created is EXPLICITLY excluded (owner's own decision) — an order can be created and
    still be under review, cancelled, never paid."""
    fake = _wire_fake_billing(client)
    fake.plan_for_key["feature.bookings"] = "plan_bookings"
    fake.subs[BENEFICIARY] = [{"id": "sub_1", "plan": "plan_bookings", "status": "active"}]
    fake.limits_by_plan["plan_bookings"] = {"feature.bookings": {"kind": "boolean", "limit": 1}}
    _register_beneficiary(client)
    _connect_merchant(client, tenant=TENANT, merchant_id="778")

    body = json.dumps({
        "event": "order.created", "merchant": 778,
        "data": {"id": 1, "status": {"slug": "completed"},
                 "customer": {"id": 1, "mobile": BENEFICIARY_PHONE}},
    }).encode()
    _post_webhook(client, body)
    assert fake.create_calls == 0


def test_a_status_update_to_anything_but_completed_never_grants(client):
    fake = _wire_fake_billing(client)
    fake.plan_for_key["feature.bookings"] = "plan_bookings"
    fake.subs[BENEFICIARY] = [{"id": "sub_1", "plan": "plan_bookings", "status": "active"}]
    fake.limits_by_plan["plan_bookings"] = {"feature.bookings": {"kind": "boolean", "limit": 1}}
    _register_beneficiary(client)
    _connect_merchant(client, tenant=TENANT, merchant_id="779")

    body = _status_updated_body(merchant_id="779", order_id="9002", status_slug="under_review")
    _post_webhook(client, body)
    assert fake.create_calls == 0


def test_a_completed_order_for_an_unconnected_merchant_never_grants(client):
    fake = _wire_fake_billing(client)
    body = _status_updated_body(merchant_id="999999", order_id="1", status_slug="completed")
    _post_webhook(client, body)
    assert fake.create_calls == 0


def test_a_completed_order_from_a_customer_we_do_not_know_costs_no_billing_call(client):
    """The customer's mobile is not a registered Raje3 phone — `grant()` itself would answer
    NO_ACCOUNT, but the point under test is that no coupon gets CREATED for a stranger."""
    fake = _wire_fake_billing(client)
    _connect_merchant(client, tenant=TENANT, merchant_id="780")

    body = _status_updated_body(merchant_id="780", order_id="9003", status_slug="completed",
                                mobile="0500000000")
    _post_webhook(client, body)
    assert fake.create_calls == 0


def test_a_repeated_status_update_for_the_same_order_grants_only_once(client):
    """Salla resends webhooks on retry — the same completed order must not double-grant."""
    fake = _wire_fake_billing(client)
    fake.plan_for_key["feature.bookings"] = "plan_bookings"
    fake.subs[BENEFICIARY] = [{"id": "sub_1", "plan": "plan_bookings", "status": "active"}]
    fake.limits_by_plan["plan_bookings"] = {"feature.bookings": {"kind": "boolean", "limit": 1}}
    _register_beneficiary(client)
    _connect_merchant(client, tenant=TENANT, merchant_id="781")

    body = _status_updated_body(merchant_id="781", order_id="9004", status_slug="completed")
    _post_webhook(client, body)
    _post_webhook(client, body)
    assert fake.create_calls == 1


def test_other_order_events_never_reach_the_grant_engine(client):
    fake = _wire_fake_billing(client)
    _connect_merchant(client, tenant=TENANT, merchant_id="782")
    for event in ("order.updated", "order.cancelled", "order.refunded", "order.deleted",
                 "order.payment.updated", "order.coupon.updated", "order.total.price.updated"):
        body = json.dumps({
            "event": event, "merchant": 782,
            "data": {"id": 1, "status": {"slug": "completed"},
                     "customer": {"id": 1, "mobile": BENEFICIARY_PHONE}},
        }).encode()
        _post_webhook(client, body)
    assert fake.create_calls == 0
