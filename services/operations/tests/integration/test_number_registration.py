"""Finishing the connection — the step that turns «مربوط» into a number that sends.

THE FAILURE THIS CLOSES. Embedded Signup stores a token; Meta refuses to send from the number until
it is REGISTERED with the business's own 6-digit two-step-verification PIN (error 133010). Every
connection therefore ended green and mute — the escalation base-services answered in v0.16.10.

THREE REFUSALS, NEVER ONE, and the middle one is why: Meta locks a number after ten registration
attempts in 72 hours. An owner shown one generic «تعذّر» retries, and each retry spends an attempt
on a problem no attempt can fix.
"""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

from app.core import connect

PATH = "/api/v1/whatsapp/connect/register"
SECRET = "h" * 40
ISS, AUD = "iss", "aud"


@pytest.fixture(scope="module")
def client():
    """Its own app with HS256 auth wired — the shared fixture verifies no token, and this suite is
    entirely about an OWNER-authenticated act."""
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

    yield TestClient(create_app(), raise_server_exceptions=False)
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


def _headers(tenant="tnt_reg"):
    """`billing.self` — the same capability the connect route itself is gated on."""
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "u1", "iss": ISS, "aud": AUD, "caps": ["billing.self"],
                      "tenant": tenant, "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture()
def owner_headers():
    return _headers()


class FakeRegistration:
    def __init__(self, ok=True, reason=""):
        self._ok, self._reason = ok, reason
        self.calls: list[dict] = []

    @property
    def configured(self):
        return True

    async def register(self, *, tenant, phone_number_id="", pin=""):
        self.calls.append({"tenant": tenant, "phone_number_id": phone_number_id, "pin": pin})
        return self._ok, self._reason

    async def status(self, tenant, phone_number_id=""):
        return {}


@pytest.fixture()
def connected(client):
    """A shop that finished Embedded Signup — token stored, number not yet registered."""
    import asyncio

    store = connect.ConnectionStore(client.app.state.container.datastore)
    asyncio.run(store.record(connect.Attempt(
        tenant="tnt_reg", state=connect.STATE_CONNECTED,
        waba_id="waba_1", phone_number_id="pn_1")))
    return store


def _post(client, headers, **body):
    payload = {"pin": "123456"}
    payload.update(body)
    return client.post(PATH, json=payload, headers=headers)


def test_a_six_digit_pin_is_required_before_anything_travels(client, owner_headers):
    """Meta allows ten attempts per 72 hours. A malformed PIN must never spend one of them."""
    for bad in ("12345", "1234567", "12a456", ""):
        r = client.post(PATH, json={"pin": bad}, headers=owner_headers)
        assert r.status_code == 422, f"{bad!r} reached the peer"


def test_a_wrong_pin_says_so_and_does_not_read_as_our_fault(client, owner_headers, connected,
                                                            monkeypatch):
    fake = FakeRegistration(ok=False, reason="WRONG_PIN")
    monkeypatch.setattr(connect, "build_registration", lambda s: fake)

    r = _post(client, owner_headers)
    assert r.status_code == 400
    assert "الرمز غير صحيح" in r.json()["message"]


def test_the_seventy_two_hour_lock_tells_him_NOT_to_retry(client, owner_headers, connected,
                                                          monkeypatch):
    """The one refusal where the obvious reaction makes it worse."""
    fake = FakeRegistration(ok=False, reason="RATE_LIMITED")
    monkeypatch.setattr(connect, "build_registration", lambda s: fake)

    body = _post(client, owner_headers).json()
    assert "72" in body["message"]
    assert "لا تعِد المحاولة" in body["message"]


def test_success_says_the_number_can_send_now(client, owner_headers, connected, monkeypatch):
    fake = FakeRegistration(ok=True)
    monkeypatch.setattr(connect, "build_registration", lambda s: fake)

    r = _post(client, owner_headers)
    assert r.status_code == 200
    assert r.json()["registered"] is True
    assert "جاهز" in r.json()["message"]


def test_it_registers_under_the_sending_identity_not_the_bare_tenant(client, owner_headers,
                                                                     connected, monkeypatch):
    """The credentials are sealed against the sending identity (core/sending_identity.py), so the
    registration must address the same key — or a chain's second number registers over the first."""
    fake = FakeRegistration(ok=True)
    monkeypatch.setattr(connect, "build_registration", lambda s: fake)

    _post(client, owner_headers)
    assert fake.calls[0]["tenant"] == "tnt_reg"          # central shop: identity == tenant
    assert fake.calls[0]["phone_number_id"] == "pn_1"
    assert fake.calls[0]["pin"] == "123456"


def test_a_shop_that_never_connected_is_told_to_connect_first(client, monkeypatch):
    fake = FakeRegistration(ok=True)
    monkeypatch.setattr(connect, "build_registration", lambda s: fake)

    # A tenant of its own: the datastore outlives a single test, and a shop that HAS connected
    # would take the happy path no matter what branch is named.
    r = client.post(PATH, json={"pin": "123456"}, headers=_headers("tnt_never_connected"))
    assert r.status_code == 400
    assert "أكمل ربط واتساب أولاً" in r.json()["message"]
    assert fake.calls == [], "nothing may travel for a shop with no stored token"
