"""One shop's own connected WhatsApp number (platform v0.19.9): messaging-limit tier, subscribed
webhook fields, business verification, and the two-step PIN set/rotate write — all gated by
`platform.operations`, all peering through `container.whatsapp_admin`."""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

SECRET = "h" * 40
ISS = "iss"
AUD = "aud"


@pytest.fixture(scope="module")
def client():
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
    })
    get_settings.cache_clear()
    from app.main import create_app

    app = create_app()
    with TestClient(app) as c:
        yield c
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


def _headers(tenant: str, caps=("platform.operations",)) -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "op-1", "iss": ISS, "aud": AUD, "caps": list(caps),
                      "tenant": tenant, "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


class _Admin:
    def __init__(self, *, pin_result=None, fields_result=None, verify_result=None, limit_result=None):
        self._pin = pin_result
        self._fields = fields_result
        self._verify = verify_result
        self._limit = limit_result

    async def set_two_step_pin(self, *, tenant, phone_number_id, pin):
        return self._pin

    async def subscribed_fields(self, tenant):
        return self._fields

    async def business_verification(self, tenant):
        return self._verify

    async def messaging_limit(self, tenant):
        return self._limit


def _swap(client, admin):
    saved = client.app.state.container.whatsapp_admin
    client.app.state.container.whatsapp_admin = admin
    return saved


# ── messaging-limit ──────────────────────────────────────────────────────────────────────────

def test_messaging_limit_requires_tenant(client):
    # `tenant` is a required query param — FastAPI refuses before this route's own body runs.
    r = client.get("/api/v1/platform/whatsapp/messaging-limit", headers=_headers("_platform"))
    assert r.status_code == 422


def test_messaging_limit_requires_the_capability(client):
    r = client.get("/api/v1/platform/whatsapp/messaging-limit", params={"tenant": "tnt_x"},
                   headers=_headers("_platform", caps=("operations.manage",)))
    assert r.status_code == 403


def test_messaging_limit_returns_the_peers_own_body(client):
    saved = _swap(client, _Admin(limit_result={"ok": True, "tier": "TIER_10K", "limit": 10000}))
    try:
        r = client.get("/api/v1/platform/whatsapp/messaging-limit", params={"tenant": "tnt_x"},
                       headers=_headers("_platform"))
        assert r.status_code == 200
        assert r.json()["tier"] == "TIER_10K"
    finally:
        client.app.state.container.whatsapp_admin = saved


def test_messaging_limit_unreachable_peer_answers_honestly(client):
    saved = _swap(client, _Admin(limit_result=None))
    try:
        r = client.get("/api/v1/platform/whatsapp/messaging-limit", params={"tenant": "tnt_x"},
                       headers=_headers("_platform"))
        assert r.status_code == 502
        assert r.json()["error"] == "UNAVAILABLE"
    finally:
        client.app.state.container.whatsapp_admin = saved


# ── subscribed-fields ────────────────────────────────────────────────────────────────────────

def test_subscribed_fields_returns_apps(client):
    saved = _swap(client, _Admin(fields_result={"apps": [{"whatsapp_business_api_data": {"id": "1"}}]}))
    try:
        r = client.get("/api/v1/platform/whatsapp/subscribed-fields", params={"tenant": "tnt_x"},
                       headers=_headers("_platform"))
        assert r.status_code == 200
        assert r.json()["apps"]
    finally:
        client.app.state.container.whatsapp_admin = saved


def test_subscribed_fields_not_connected_answers_409(client):
    saved = _swap(client, _Admin(fields_result={"_status": 409, "detail": "NOT_CONNECTED"}))
    try:
        r = client.get("/api/v1/platform/whatsapp/subscribed-fields", params={"tenant": "tnt_x"},
                       headers=_headers("_platform"))
        assert r.status_code == 409
        assert r.json()["reason"] == "NOT_CONNECTED"
    finally:
        client.app.state.container.whatsapp_admin = saved


# ── business-verification ────────────────────────────────────────────────────────────────────

def test_business_verification_returns_both_fields(client):
    saved = _swap(client, _Admin(verify_result={"business_verification_status": "verified", "status": "APPROVED"}))
    try:
        r = client.get("/api/v1/platform/whatsapp/business-verification", params={"tenant": "tnt_x"},
                       headers=_headers("_platform"))
        assert r.status_code == 200
        body = r.json()
        assert body["business_verification_status"] == "verified"
        assert body["status"] == "APPROVED"
    finally:
        client.app.state.container.whatsapp_admin = saved


# ── two-step-pin (write, audited, write-only) ────────────────────────────────────────────────

def test_two_step_pin_rejects_a_non_6_digit_pin(client):
    r = client.post("/api/v1/platform/whatsapp/two-step-pin",
                    json={"tenant": "tnt_x", "pin": "12"}, headers=_headers("_platform"))
    assert r.status_code == 422


def test_two_step_pin_success_never_echoes_the_pin(client):
    saved = _swap(client, _Admin(pin_result={"ok": True}))
    try:
        r = client.post("/api/v1/platform/whatsapp/two-step-pin",
                        json={"tenant": "tnt_x", "pin": "135790"}, headers=_headers("_platform"))
        assert r.status_code == 200
        body = r.json()
        assert body == {"ok": True}
        assert "135790" not in r.text
    finally:
        client.app.state.container.whatsapp_admin = saved


def test_two_step_pin_wrong_pin_reason_is_distinct(client):
    saved = _swap(client, _Admin(pin_result={"ok": False, "reason": "WRONG_PIN"}))
    try:
        r = client.post("/api/v1/platform/whatsapp/two-step-pin",
                        json={"tenant": "tnt_x", "pin": "135790"}, headers=_headers("_platform"))
        assert r.status_code == 400
        assert r.json()["reason"] == "WRONG_PIN"
    finally:
        client.app.state.container.whatsapp_admin = saved


def test_two_step_pin_not_connected_answers_409(client):
    saved = _swap(client, _Admin(pin_result={"_status": 409, "ok": False, "reason": "NOT_CONNECTED"}))
    try:
        r = client.post("/api/v1/platform/whatsapp/two-step-pin",
                        json={"tenant": "tnt_x", "pin": "135790"}, headers=_headers("_platform"))
        assert r.status_code == 409
        assert r.json()["reason"] == "NOT_CONNECTED"
    finally:
        client.app.state.container.whatsapp_admin = saved


def test_two_step_pin_requires_the_capability(client):
    r = client.post("/api/v1/platform/whatsapp/two-step-pin",
                    json={"tenant": "tnt_x", "pin": "135790"},
                    headers=_headers("_platform", caps=("operations.manage",)))
    assert r.status_code == 403
