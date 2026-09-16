"""TikTok Shop at the HTTP layer — install/status/disconnect (staff-authenticated) and
callback/webhook (TikTok's own unauthenticated calls, verified by state/signature instead).
Outbound calls to TikTok itself (`exchange_code`/`get_order_detail`) are monkeypatched on the
wired `TikTokShopClient` instance — same technique `test_salla_api.py` uses.
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
TENANT = "tnt_tiktok_shop"
SALT = "s" * 32
APP_KEY = "test_app_key"
APP_SECRET = "test_app_secret"


def _make_app() -> TestClient:
    from app.config import get_settings

    os.environ.update({
        "ENV": "test", "INTERNAL_SERVICE_TOKEN": "t" * 40, "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": TOKEN_SECRET, "TOKEN_ISSUER": ISS, "TOKEN_AUDIENCE": AUD,
        "RATELIMIT_MAX": "1000", "PII_SALT": SALT, "PUBLIC_BASE_URL": "https://raje3.sa",
        "TIKTOK_SHOP_APP_KEY": APP_KEY, "TIKTOK_SHOP_APP_SECRET": APP_SECRET,
        "TIKTOK_SHOP_SERVICE_ID": "svc_123",
    })
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


def _state_for(tenant: str = TENANT) -> str:
    from app.core import oauth_state
    return oauth_state.issue(SALT, "tiktok_shop", tenant)


# ── install ──────────────────────────────────────────────────────────────────────────────────
def test_install_returns_a_real_authorize_url_when_configured(client):
    r = client.get("/api/v1/staff/tiktok-shop/install", headers=_auth("billing.self"))
    assert r.status_code == 200, r.text
    url = r.json()["url"]
    assert url.startswith("https://services.tiktokshop.com/open/authorize?")
    assert "service_id=svc_123" in url


def test_install_requires_billing_self_capability(client):
    r = client.get("/api/v1/staff/tiktok-shop/install", headers=_auth("operations.record"))
    assert r.status_code == 403


def test_install_refuses_when_not_configured(env_guard):
    from app.config import get_settings

    os.environ.update({
        "ENV": "test", "INTERNAL_SERVICE_TOKEN": "t" * 40, "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": TOKEN_SECRET, "TOKEN_ISSUER": ISS, "TOKEN_AUDIENCE": AUD,
        "RATELIMIT_MAX": "1000", "PII_SALT": SALT, "PUBLIC_BASE_URL": "https://raje3.sa",
        "TIKTOK_SHOP_APP_KEY": "", "TIKTOK_SHOP_APP_SECRET": "", "TIKTOK_SHOP_SERVICE_ID": "",
    })
    get_settings.cache_clear()
    from app.main import create_app

    c = TestClient(create_app(), raise_server_exceptions=False)
    r = c.get("/api/v1/staff/tiktok-shop/install", headers=_auth("billing.self"))
    assert r.status_code == 200
    assert r.json()["error"] == "NOT_CONFIGURED"


# ── status / disconnect ─────────────────────────────────────────────────────────────────────
def test_status_reports_not_connected_by_default(client):
    r = client.get("/api/v1/staff/tiktok-shop/status", headers=_auth("billing.self"))
    assert r.status_code == 200
    assert r.json() == {"connected": False}


def _connect(client: TestClient, *, tenant: str, shop_id: str) -> None:
    import asyncio
    asyncio.run(client.app.state.container.tiktok_shop.save_connection(
        tenant=tenant, shop_id=shop_id, seller_name="متجري", access_token="at",
        refresh_token="rt", access_token_expires_at=9999999999,
        refresh_token_expires_at=9999999999, scope="seller.order.info"))


def test_disconnect_removes_a_real_connection_and_never_leaks_tokens(client):
    _connect(client, tenant=TENANT, shop_id="shop_1")

    status = client.get("/api/v1/staff/tiktok-shop/status", headers=_auth("billing.self")).json()
    assert status["connected"] is True
    assert "access_token" not in status
    assert "refresh_token" not in status

    r = client.post("/api/v1/staff/tiktok-shop/disconnect", headers=_auth("billing.self"))
    assert r.json() == {"connected": False}


def test_disconnect_never_touches_a_different_tenants_connection(client):
    other = "tnt_tiktok_other"
    _connect(client, tenant=other, shop_id="shop_other")
    _connect(client, tenant=TENANT, shop_id="shop_mine")

    client.post("/api/v1/staff/tiktok-shop/disconnect", headers=_auth("billing.self"))

    other_status = client.get("/api/v1/staff/tiktok-shop/status",
                              headers=_auth("billing.self", tenant=other)).json()
    assert other_status["connected"] is True


# ── callback ─────────────────────────────────────────────────────────────────────────────────
def test_callback_refuses_an_invalid_state(client):
    r = client.get("/api/v1/tiktok-shop/callback", params={"code": "abc", "state": "garbage"})
    assert r.json()["ok"] is False


def test_callback_reports_an_error_from_tiktok(client):
    r = client.get("/api/v1/tiktok-shop/callback",
                   params={"error": "auth_denied", "state": _state_for()})
    assert r.json()["ok"] is False


def test_callback_exchanges_the_code_and_saves_a_real_connection(client):
    tt_client = client.app.state.container.tiktok_shop.client
    tt_client.exchange_code = lambda auth_code: {
        "access_token": "at_123", "refresh_token": "rt_123",
        "access_token_expire_in": 9999999999, "refresh_token_expire_in": 9999999999,
        "open_id": "shop_555", "seller_name": "متجر الاختبار", "user_type": 0,
        "granted_scopes": ["seller.order.info"],
    }
    r = client.get("/api/v1/tiktok-shop/callback",
                   params={"code": "the-code", "state": _state_for()})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["seller_name"] == "متجر الاختبار"
    assert "at_123" not in json.dumps(body)

    status = client.get("/api/v1/staff/tiktok-shop/status", headers=_auth("billing.self")).json()
    assert status["connected"] is True
    assert status["shop_id"] == "shop_555"


def test_callback_refuses_a_non_seller_user_type(client):
    tt_client = client.app.state.container.tiktok_shop.client
    tt_client.exchange_code = lambda auth_code: {
        "access_token": "at", "refresh_token": "rt", "access_token_expire_in": 1,
        "refresh_token_expire_in": 1, "open_id": "creator_1", "user_type": 1,
    }
    r = client.get("/api/v1/tiktok-shop/callback", params={"code": "c", "state": _state_for()})
    assert r.json()["ok"] is False

    status = client.get("/api/v1/staff/tiktok-shop/status", headers=_auth("billing.self")).json()
    assert status["connected"] is False


def test_callback_refuses_when_tiktok_gives_no_access_token(client):
    tt_client = client.app.state.container.tiktok_shop.client
    tt_client.exchange_code = lambda auth_code: None
    r = client.get("/api/v1/tiktok-shop/callback", params={"code": "c", "state": _state_for()})
    assert r.json()["ok"] is False


def test_reconnecting_keeps_the_link_scoped_to_the_tenant_who_started_it(client):
    other = "tnt_tiktok_someone_else"
    tt_client = client.app.state.container.tiktok_shop.client
    tt_client.exchange_code = lambda auth_code: {
        "access_token": "at", "refresh_token": "rt", "access_token_expire_in": 1,
        "refresh_token_expire_in": 1, "open_id": "shop_999", "user_type": 0,
    }
    client.get("/api/v1/tiktok-shop/callback",
              params={"code": "c", "state": _state_for(tenant=other)})

    mine = client.get("/api/v1/staff/tiktok-shop/status", headers=_auth("billing.self")).json()
    assert mine["connected"] is False


# ── webhook signature ────────────────────────────────────────────────────────────────────────
def _sign_webhook(app_key: str, app_secret: str, body: bytes) -> str:
    return hmac.new(app_secret.encode(), app_key.encode() + body, hashlib.sha256).hexdigest()


def test_a_correctly_signed_unrecognised_shape_is_acked_and_logged(client):
    body = json.dumps({"type": 5, "tts_notification_id": "n1", "shop_id": "shop_x",
                       "timestamp": 1, "data": {"anything": True}}).encode()
    sig = _sign_webhook(APP_KEY, APP_SECRET, body)
    r = client.post("/api/v1/tiktok-shop/webhook", data=body,
                    headers={"Content-Type": "application/json", "Authorization": sig})
    assert r.status_code == 200
    assert r.json() == {"received": True}


def test_a_badly_signed_webhook_still_acks_200_but_is_not_trusted(client):
    body = json.dumps({"type": 1, "tts_notification_id": "n2", "shop_id": "shop_x",
                       "data": {"order_id": "1", "order_status": "UNPAID"}}).encode()
    r = client.post("/api/v1/tiktok-shop/webhook", data=body,
                    headers={"Content-Type": "application/json", "Authorization": "0" * 64})
    assert r.status_code == 200
    assert r.json() == {"received": True}


def test_a_webhook_with_no_signature_header_at_all_still_acks_200(client):
    body = json.dumps({"type": 1, "tts_notification_id": "n3", "shop_id": "shop_x",
                       "data": {}}).encode()
    r = client.post("/api/v1/tiktok-shop/webhook", data=body,
                    headers={"Content-Type": "application/json"})
    assert r.status_code == 200


def test_a_malformed_json_body_does_not_crash_the_route(client):
    r = client.post("/api/v1/tiktok-shop/webhook", data=b"not json at all",
                    headers={"Content-Type": "application/json", "Authorization": "0" * 64})
    assert r.status_code == 200


# ── the actual recording trigger — ORDER_STATUS_CHANGE + a fetched, paid order ─────────────────
def _order_body(*, shop_id: str, order_id: str, notification_id: str,
                status_value: str = "UNPAID") -> bytes:
    return json.dumps({
        "type": 1, "tts_notification_id": notification_id, "shop_id": shop_id,
        "timestamp": 1718305585,
        "data": {"order_id": order_id, "order_status": status_value, "update_time": 1},
    }).encode()


def _post_webhook(client: TestClient, body: bytes) -> object:
    sig = _sign_webhook(APP_KEY, APP_SECRET, body)
    return client.post("/api/v1/tiktok-shop/webhook", data=body,
                       headers={"Content-Type": "application/json", "Authorization": sig})


def _fake_order(*, order_id: str, status: str = "AWAITING_SHIPMENT",
               phone: str = "0501234567") -> dict:
    return {
        "id": order_id, "status": status, "user_id": "7021436810468230477",
        "create_time": 1719999999,
        "recipient_address": {"phone_number": phone, "name": "أحمد"},
        "line_items": [{"product_id": "", "product_name": "غسيل خارجي", "sale_price": "30.00"}],
        "payment": {"currency": "SAR", "total_amount": "30.00"},
    }


def _seed_catchall(client: TestClient, tenant: str) -> None:
    import asyncio

    from app.core.models import Service
    from app.core.stores import ServiceStore

    asyncio.run(ServiceStore(client.app.state.container.datastore).save(
        Service(id="svc_catchall_tt", tenant=tenant, name="خدمة أخرى", catchall=True)))


def test_an_unpaid_order_status_change_never_records_a_visit(client):
    _connect(client, tenant=TENANT, shop_id="shop_unpaid")
    _seed_catchall(client, TENANT)
    tt_client = client.app.state.container.tiktok_shop.client
    tt_client.get_order_detail = lambda **kw: _fake_order(order_id="o1", status="UNPAID")

    body = _order_body(shop_id="shop_unpaid", order_id="o1", notification_id="notif-1",
                       status_value="UNPAID")
    r = _post_webhook(client, body)
    assert r.status_code == 200

    import asyncio
    ops = client.app.state.container.operations
    cust = asyncio.run(ops.customer_by_phone(TENANT, "0501234567"))
    assert cust is None


def test_a_paid_order_status_change_records_a_real_visit(client):
    _connect(client, tenant=TENANT, shop_id="shop_paid")
    _seed_catchall(client, TENANT)
    tt_client = client.app.state.container.tiktok_shop.client
    tt_client.get_order_detail = lambda **kw: _fake_order(order_id="o2")

    body = _order_body(shop_id="shop_paid", order_id="o2", notification_id="notif-2",
                       status_value="AWAITING_SHIPMENT")
    r = _post_webhook(client, body)
    assert r.status_code == 200

    import asyncio
    ops = client.app.state.container.operations
    cust = asyncio.run(ops.customer_by_phone(TENANT, "0501234567"))
    assert cust is not None and cust.name == "أحمد"


def test_a_webhook_driven_paid_order_rings_the_seams_too(client):
    """The seams fix applies through the webhook path too — it shares `_record_tiktok_order`
    with the manual `/orders` door, and this confirms that sharing actually holds."""
    _connect(client, tenant=TENANT, shop_id="shop_paid_seam")
    _seed_catchall(client, TENANT)
    tt_client = client.app.state.container.tiktok_shop.client
    tt_client.get_order_detail = lambda **kw: _fake_order(order_id="o2b")
    seen = []

    async def after_visit(result):
        seen.append(result)

    client.app.state.container.seams.after_visit = after_visit

    body = _order_body(shop_id="shop_paid_seam", order_id="o2b", notification_id="notif-2b",
                       status_value="AWAITING_SHIPMENT")
    _post_webhook(client, body)
    assert len(seen) == 1


def test_a_masked_phone_on_the_fetched_order_lands_on_the_anonymous_placeholder(client):
    _connect(client, tenant=TENANT, shop_id="shop_masked")
    _seed_catchall(client, TENANT)
    tt_client = client.app.state.container.tiktok_shop.client
    tt_client.get_order_detail = lambda **kw: _fake_order(
        order_id="o3", phone="(+1)213-***-1234")

    body = _order_body(shop_id="shop_masked", order_id="o3", notification_id="notif-3",
                       status_value="AWAITING_SHIPMENT")
    _post_webhook(client, body)

    import asyncio
    from app.core.stores import CustomerStore
    anon = asyncio.run(CustomerStore(client.app.state.container.datastore).anonymous(TENANT))
    assert anon is not None


def test_a_repeated_notification_id_is_deduped_before_any_fetch(client):
    _connect(client, tenant=TENANT, shop_id="shop_dup")
    _seed_catchall(client, TENANT)
    tt_client = client.app.state.container.tiktok_shop.client
    calls = []
    tt_client.get_order_detail = lambda **kw: (calls.append(1), _fake_order(order_id="o4"))[1]

    body = _order_body(shop_id="shop_dup", order_id="o4", notification_id="notif-dup")
    _post_webhook(client, body)
    _post_webhook(client, body)
    assert len(calls) == 1


def test_an_order_event_for_an_unconnected_shop_never_calls_the_api(client):
    tt_client = client.app.state.container.tiktok_shop.client
    calls = []
    tt_client.get_order_detail = lambda **kw: calls.append(1)

    body = _order_body(shop_id="shop_never_connected", order_id="o5", notification_id="notif-5")
    r = _post_webhook(client, body)
    assert r.status_code == 200
    assert calls == []


# ── CANCELLED — the points reversal path (owner's own 2026-09-16 call to allow debt) ───────────
class _FakeLoyaltyDesk:
    configured = True

    def __init__(self) -> None:
        self.reverse_calls: list[dict] = []

    async def reverse_earn(self, *, tenant, subject_ref, visit_id, actor="", branch_id=""):
        self.reverse_calls.append({"tenant": tenant, "subject_ref": subject_ref,
                                   "visit_id": visit_id, "actor": actor})
        return {"reversed": 200, "balance": -50, "entry_id": "led_x"}


def _wire_fake_loyalty(client: TestClient) -> _FakeLoyaltyDesk:
    fake = _FakeLoyaltyDesk()
    client.app.state.container.loyalty_desk = fake
    return fake


def _no_op_seams(client: TestClient) -> None:
    async def after_visit(result):
        return None
    client.app.state.container.seams.after_visit = after_visit


def test_a_cancelled_order_reverses_the_points_it_earned(client):
    _connect(client, tenant=TENANT, shop_id="shop_cancel1")
    _seed_catchall(client, TENANT)
    _no_op_seams(client)
    tt_client = client.app.state.container.tiktok_shop.client
    fake_loyalty = _wire_fake_loyalty(client)

    # First: a real, paid order arrives and is recorded (the visit that will be cancelled).
    tt_client.get_order_detail = lambda **kw: _fake_order(order_id="o-cancel-1",
                                                          status="AWAITING_SHIPMENT")
    _post_webhook(client, _order_body(shop_id="shop_cancel1", order_id="o-cancel-1",
                                      notification_id="notif-cancel-a"))

    import asyncio
    ops = client.app.state.container.operations
    cust = asyncio.run(ops.customer_by_phone(TENANT, "0501234567"))
    assert cust is not None

    # Then: the SAME order is cancelled.
    tt_client.get_order_detail = lambda **kw: _fake_order(order_id="o-cancel-1",
                                                          status="CANCELLED")
    r = _post_webhook(client, _order_body(shop_id="shop_cancel1", order_id="o-cancel-1",
                                          notification_id="notif-cancel-b"))
    assert r.status_code == 200

    assert len(fake_loyalty.reverse_calls) == 1
    assert fake_loyalty.reverse_calls[0]["subject_ref"] == cust.subject_ref


def test_a_cancelled_order_that_was_never_recorded_reverses_nothing(client):
    """A CANCELLED event for an order we never saw paid (arrived UNPAID then cancelled, or the
    original webhook was lost) must find nothing to reverse — never invented."""
    _connect(client, tenant=TENANT, shop_id="shop_cancel2")
    _seed_catchall(client, TENANT)
    fake_loyalty = _wire_fake_loyalty(client)
    tt_client = client.app.state.container.tiktok_shop.client
    tt_client.get_order_detail = lambda **kw: _fake_order(order_id="o-cancel-2",
                                                          status="CANCELLED")

    r = _post_webhook(client, _order_body(shop_id="shop_cancel2", order_id="o-cancel-2",
                                          notification_id="notif-cancel-c"))
    assert r.status_code == 200
    assert fake_loyalty.reverse_calls == []


def test_an_anonymous_orders_cancellation_never_reverses_anything(client):
    """The anonymous placeholder has no real subject_ref of its own to spend or reverse points
    against — same "never for the shared row" rule the seams fix already established."""
    _connect(client, tenant=TENANT, shop_id="shop_cancel3")
    _seed_catchall(client, TENANT)
    _no_op_seams(client)
    fake_loyalty = _wire_fake_loyalty(client)
    tt_client = client.app.state.container.tiktok_shop.client

    tt_client.get_order_detail = lambda **kw: _fake_order(
        order_id="o-cancel-3", status="AWAITING_SHIPMENT", phone="1**-***-**23")
    _post_webhook(client, _order_body(shop_id="shop_cancel3", order_id="o-cancel-3",
                                      notification_id="notif-cancel-d"))

    tt_client.get_order_detail = lambda **kw: _fake_order(
        order_id="o-cancel-3", status="CANCELLED", phone="1**-***-**23")
    _post_webhook(client, _order_body(shop_id="shop_cancel3", order_id="o-cancel-3",
                                      notification_id="notif-cancel-e"))
    assert fake_loyalty.reverse_calls == []


def test_a_cancelled_order_for_an_unconnected_shop_never_reverses_anything(client):
    fake_loyalty = _wire_fake_loyalty(client)
    r = _post_webhook(client, _order_body(shop_id="shop_cancel_never_connected",
                                          order_id="o-cancel-4", notification_id="notif-cancel-f"))
    assert r.status_code == 200
    assert fake_loyalty.reverse_calls == []
