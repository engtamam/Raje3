"""A successful WhatsApp connect schedules the Meta Commerce Catalog provisioning trigger with the
SAME business_id/waba_id/phone_number_id Embedded Signup just handed back — see
core/catalog_provision_trigger.py and app/api/v1/connect.py's own comment on why it fires
unconditionally (not gated on feature.whatsapp, unlike the Meta Business Agent trigger)."""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

SECRET = "h" * 40
ISS, AUD = "iss", "aud"


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

    yield TestClient(create_app(), raise_server_exceptions=False)
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


def _headers(tenant="tnt_catalog_trigger"):
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "u1", "iss": ISS, "aud": AUD, "caps": ["billing.self"],
                      "tenant": tenant, "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


class _FakeExchange:
    async def exchange(self, *, tenant, code, waba_id, phone_number_id, branch_id="", root_tenant=""):
        return True, ""


class _FakeWhatsappLicence:
    def __init__(self, allowed: bool | None) -> None:
        self._allowed = allowed

    async def allowed(self, tenant: str) -> bool | None:
        return self._allowed


def test_catalog_trigger_is_scheduled_with_all_three_real_ids(client, monkeypatch):
    calls: list[dict] = []

    async def _fake_trigger(*, tenant, business_id, waba_id, phone_number_id):
        calls.append({"tenant": tenant, "business_id": business_id, "waba_id": waba_id,
                     "phone_number_id": phone_number_id})
        return True

    import app.core.connect as connect_module

    monkeypatch.setattr(connect_module, "build_exchange", lambda settings: _FakeExchange())
    client.app.state.container.catalog_provision_trigger.trigger = _fake_trigger

    r = client.post("/api/v1/whatsapp/connect", json={
        "event": "FINISH", "code": "a-code", "waba_id": "waba_catalog",
        "phone_number_id": "pn_catalog_123", "business_id": "biz_catalog",
    }, headers=_headers())
    assert r.status_code == 200, r.text
    assert len(calls) == 1
    assert calls[0]["business_id"] == "biz_catalog"
    assert calls[0]["waba_id"] == "waba_catalog"
    assert calls[0]["phone_number_id"] == "pn_catalog_123"


def test_catalog_trigger_fires_even_without_the_ai_assistant_app(client, monkeypatch):
    """UNLIKE the Meta Business Agent trigger: ordering is not sold as part of feature.whatsapp,
    so a shop with no AI assistant subscription still gets its catalog provisioned."""
    calls: list[dict] = []

    async def _fake_trigger(*, tenant, business_id, waba_id, phone_number_id):
        calls.append({"tenant": tenant})
        return True

    import app.core.connect as connect_module

    monkeypatch.setattr(connect_module, "build_exchange", lambda settings: _FakeExchange())
    c = client.app.state.container
    saved_trigger, saved_licence = c.catalog_provision_trigger.trigger, c.whatsapp_licence
    c.catalog_provision_trigger.trigger = _fake_trigger
    c.whatsapp_licence = _FakeWhatsappLicence(False)
    try:
        r = client.post("/api/v1/whatsapp/connect", json={
            "event": "FINISH", "code": "a-code", "waba_id": "waba_catalog_no_ai",
            "phone_number_id": "pn_catalog_no_ai_123", "business_id": "biz_catalog_no_ai",
        }, headers=_headers(tenant="tnt_catalog_trigger_no_ai"))
    finally:
        c.catalog_provision_trigger.trigger = saved_trigger
        c.whatsapp_licence = saved_licence
    assert r.status_code == 200, r.text
    assert len(calls) == 1


def test_a_finish_with_no_phone_number_never_schedules_the_catalog_trigger(client):
    """No number, no connection recorded as connected -- same posture as the Meta Business Agent
    trigger's own identical test. Provisioning a catalog for a number we never actually connected
    would be worse than doing nothing."""
    calls: list[dict] = []

    async def _fake_trigger(*, tenant, business_id, waba_id, phone_number_id):
        calls.append({"tenant": tenant})
        return True

    client.app.state.container.catalog_provision_trigger.trigger = _fake_trigger

    r = client.post("/api/v1/whatsapp/connect", json={
        "event": "FINISH", "code": "a-code", "waba_id": "waba_catalog_no_number",
        "business_id": "biz_catalog_x",
    }, headers=_headers(tenant="tnt_catalog_trigger_no_number"))
    assert r.status_code == 200, r.text
    assert calls == []
