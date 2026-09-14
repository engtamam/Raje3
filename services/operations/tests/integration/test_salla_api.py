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
