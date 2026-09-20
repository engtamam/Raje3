"""The owner's own kill switch for the WhatsApp AI assistant — read/write from his own token, plus
the internal peer route whatsapp-assistant calls to learn it (the same one `ai_notes`/
`msg_word_limit` already ride, extended 2026-09-13).

THE ACTUAL ENFORCEMENT — closing the AI exactly as if unsubscribed — lives on whatsapp-assistant's
own side (core/licence.py::ToggleGatedLicence); this file only proves the value this service stores
and hands over is correct.
"""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

PATH = "/api/v1/staff/ai-toggle"
SECRET = "h" * 40
ISS, AUD = "iss", "aud"


def _make_app(**env_over):
    from app.config import get_settings

    env = {
        "ENV": "test", "INTERNAL_SERVICE_TOKEN": "t" * 40,
        "TOKEN_VERIFIER_DRIVER": "hs256", "TOKEN_HS256_SECRET": SECRET,
        "TOKEN_ISSUER": ISS, "TOKEN_AUDIENCE": AUD, "RATELIMIT_MAX": "1000",
    }
    env.update(env_over)
    os.environ.update(env)
    get_settings.cache_clear()
    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


@pytest.fixture()
def client():
    saved = dict(os.environ)
    yield _make_app()
    os.environ.clear()
    os.environ.update(saved)
    from app.config import get_settings
    get_settings.cache_clear()


def _headers(tenant="tnt_toggle", *, caps=("operations.manage", "operations.read")) -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "u_owner", "iss": ISS, "aud": AUD,
                      "caps": list(caps), "tenant": tenant,
                      "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


def test_a_shop_that_never_touched_it_reads_back_enabled(client):
    r = client.get(PATH, headers=_headers())
    assert r.status_code == 200
    assert r.json() == {"enabled": True}


def test_the_owner_switches_it_off_and_reads_it_back(client):
    put = client.put(PATH, json={"enabled": False}, headers=_headers())
    assert put.status_code == 200, put.text
    assert put.json()["enabled"] is False

    got = client.get(PATH, headers=_headers())
    assert got.json()["enabled"] is False


def test_switching_it_back_on_is_the_same_door_no_one_way_ratchet(client):
    client.put(PATH, json={"enabled": False}, headers=_headers())
    put = client.put(PATH, json={"enabled": True}, headers=_headers())
    assert put.json()["enabled"] is True
    assert client.get(PATH, headers=_headers()).json()["enabled"] is True


def test_one_shops_switch_is_not_readable_or_flippable_from_another(client):
    client.put(PATH, json={"enabled": False}, headers=_headers("tnt_a"))
    r = client.get(PATH, headers=_headers("tnt_b"))
    assert r.json()["enabled"] is True


def test_a_reader_without_manage_capability_cannot_flip_it(client):
    r = client.put(PATH, json={"enabled": False}, headers=_headers(caps=("operations.read",)))
    assert r.status_code == 403


# ── the internal peer route whatsapp-assistant calls ──────────────────────────
def test_the_internal_shop_name_route_also_returns_ai_enabled(client):
    r = client.post("/internal/operations/shop-name", json={"tenant": "tnt_peer_on"},
                    headers={"X-Internal-Token": "t" * 40})
    assert r.status_code == 200, r.text
    assert r.json()["ai_enabled"] is True

    client.put(PATH, json={"enabled": False}, headers=_headers("tnt_peer_off"))
    r2 = client.post("/internal/operations/shop-name", json={"tenant": "tnt_peer_off"},
                     headers={"X-Internal-Token": "t" * 40})
    assert r2.json()["ai_enabled"] is False


# ── cuts Meta's own AI too, not just this service's own reply engine ──────────────────────────
class _FakeWhatsappLicence:
    def __init__(self, allowed: bool | None) -> None:
        self._allowed = allowed

    async def allowed(self, tenant: str) -> bool | None:
        return self._allowed


def test_switching_off_fires_the_meta_rollout_trigger_with_enabled_false(client):
    calls: list[dict] = []

    async def _fake_trigger(*, tenant, enabled):
        calls.append({"tenant": tenant, "enabled": enabled})
        return True

    c = client.app.state.container
    saved = c.meta_agent_rollout_trigger.trigger
    c.meta_agent_rollout_trigger.trigger = _fake_trigger
    try:
        r = client.put(PATH, json={"enabled": False}, headers=_headers("tnt_toggle_off"))
    finally:
        c.meta_agent_rollout_trigger.trigger = saved
    assert r.status_code == 200
    assert calls == [{"tenant": "tnt_toggle_off", "enabled": False}]


def test_switching_on_fires_the_meta_rollout_trigger_only_if_still_entitled(client):
    calls: list[dict] = []

    async def _fake_trigger(*, tenant, enabled):
        calls.append({"tenant": tenant, "enabled": enabled})
        return True

    c = client.app.state.container
    saved_trigger, saved_licence = c.meta_agent_rollout_trigger.trigger, c.whatsapp_licence
    c.meta_agent_rollout_trigger.trigger = _fake_trigger
    c.whatsapp_licence = _FakeWhatsappLicence(False)
    try:
        r = client.put(PATH, json={"enabled": True}, headers=_headers("tnt_toggle_on_no_app"))
    finally:
        c.meta_agent_rollout_trigger.trigger = saved_trigger
        c.whatsapp_licence = saved_licence
    assert r.status_code == 200
    # NOT ENTITLED — flipping the switch back on must never be a backdoor into Meta's AI for a
    # shop that does not (or no longer) holds feature.whatsapp.
    assert calls == []


def test_switching_on_fires_the_trigger_with_enabled_true_when_still_entitled(client):
    calls: list[dict] = []

    async def _fake_trigger(*, tenant, enabled):
        calls.append({"tenant": tenant, "enabled": enabled})
        return True

    c = client.app.state.container
    saved_trigger, saved_licence = c.meta_agent_rollout_trigger.trigger, c.whatsapp_licence
    c.meta_agent_rollout_trigger.trigger = _fake_trigger
    c.whatsapp_licence = _FakeWhatsappLicence(True)
    try:
        r = client.put(PATH, json={"enabled": True}, headers=_headers("tnt_toggle_on_entitled"))
    finally:
        c.meta_agent_rollout_trigger.trigger = saved_trigger
        c.whatsapp_licence = saved_licence
    assert r.status_code == 200
    assert calls == [{"tenant": "tnt_toggle_on_entitled", "enabled": True}]
