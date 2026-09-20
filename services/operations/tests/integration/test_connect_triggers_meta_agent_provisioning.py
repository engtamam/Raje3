"""A successful WhatsApp connect schedules the Meta Business Agent onboarding trigger with the
SAME phone_number_id Embedded Signup just handed back — see core/meta_agent_provision_trigger.py
and app/api/v1/connect.py's own comment on why this sits alongside the Flow/library provisioning
tasks (after the response, never inside it)."""
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


def _headers(tenant="tnt_meta_trigger"):
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "u1", "iss": ISS, "aud": AUD, "caps": ["billing.self"],
                      "tenant": tenant, "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


class _FakeExchange:
    async def exchange(self, *, tenant, code, waba_id, phone_number_id, branch_id="", root_tenant=""):
        return True, ""


def test_meta_agent_trigger_is_scheduled_with_the_real_entity_id(client, monkeypatch):
    calls: list[dict] = []

    async def _fake_trigger(*, tenant, entity_id):
        calls.append({"tenant": tenant, "entity_id": entity_id})
        return True

    import app.core.connect as connect_module

    monkeypatch.setattr(connect_module, "build_exchange", lambda settings: _FakeExchange())
    client.app.state.container.meta_agent_provision_trigger.trigger = _fake_trigger

    r = client.post("/api/v1/whatsapp/connect", json={
        "event": "FINISH", "code": "a-code", "waba_id": "waba_meta",
        "phone_number_id": "pn_meta_agent_123", "business_id": "biz_meta",
    }, headers=_headers())
    assert r.status_code == 200, r.text
    assert len(calls) == 1
    # ENTITY_ID IS THE PHONE NUMBER ID, NOT THE WABA ID -- same value
    # meta_agent_provisioning.py's own docstring insists on throughout that module.
    assert calls[0]["entity_id"] == "pn_meta_agent_123"


class _FakeWhatsappLicence:
    def __init__(self, allowed: bool | None) -> None:
        self._allowed = allowed

    async def allowed(self, tenant: str) -> bool | None:
        return self._allowed


def test_connecting_without_the_ai_assistant_app_never_schedules_the_trigger(client, monkeypatch):
    """The owner's own question, verified directly (2026-09-20): "shouldn't Meta provisioning
    depend on the shop actually holding بوت خدمة العملاء الذكي (feature.whatsapp), not just on
    connecting a number?" It already does — `/whatsapp/connect` itself is gated
    `Depends(subscribed_write_or_whatsapp)`, which requires `whatsapp_licence` alone (not the
    generic any-app OR). A tenant without it never reaches the connect handler at all, so the
    Meta trigger can never fire for one either — the whole route refuses with 402 first. This is
    what proves that finding, rather than adding a second, unreachable check inside the handler
    that would only repeat a question the route dependency already answered for the same
    request."""
    calls: list[dict] = []

    async def _fake_trigger(*, tenant, entity_id):
        calls.append({"tenant": tenant, "entity_id": entity_id})
        return True

    import app.core.connect as connect_module

    monkeypatch.setattr(connect_module, "build_exchange", lambda settings: _FakeExchange())
    c = client.app.state.container
    saved_trigger, saved_licence = c.meta_agent_provision_trigger.trigger, c.whatsapp_licence
    c.meta_agent_provision_trigger.trigger = _fake_trigger
    c.whatsapp_licence = _FakeWhatsappLicence(False)
    try:
        r = client.post("/api/v1/whatsapp/connect", json={
            "event": "FINISH", "code": "a-code", "waba_id": "waba_no_ai",
            "phone_number_id": "pn_no_ai_123", "business_id": "biz_no_ai",
        }, headers=_headers(tenant="tnt_meta_trigger_no_ai"))
    finally:
        c.meta_agent_provision_trigger.trigger = saved_trigger
        c.whatsapp_licence = saved_licence
    assert r.status_code == 402, r.text
    assert calls == []


def test_a_finish_with_no_phone_number_never_schedules_the_trigger(client, monkeypatch):
    """No number, no connection recorded as connected -- see connect.py's own STATE_FINISHED_
    UNCONFIRMED branch. Provisioning a Meta agent for a number we never actually connected would
    be worse than doing nothing."""
    calls: list[dict] = []

    async def _fake_trigger(*, tenant, entity_id):
        calls.append({"tenant": tenant, "entity_id": entity_id})
        return True

    client.app.state.container.meta_agent_provision_trigger.trigger = _fake_trigger

    r = client.post("/api/v1/whatsapp/connect", json={
        "event": "FINISH", "code": "a-code", "waba_id": "waba_no_number", "business_id": "biz_x",
    }, headers=_headers(tenant="tnt_meta_trigger_no_number"))
    assert r.status_code == 200, r.text
    assert calls == []
