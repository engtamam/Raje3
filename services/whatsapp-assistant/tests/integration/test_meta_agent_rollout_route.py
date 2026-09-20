"""Integration: /internal/whatsapp/meta-agent/rollout -- the on/off switch for Meta's OWN AI on
a number that already went through /internal/whatsapp/meta-agent/provision once. Called from
operations by the owner's own AI kill switch (staff.py::set_ai_toggle, instant); never touches
this file's own connection or handover mode -- see app/core/meta_agent_provisioning.py::
set_agent_rollout's own docstring for why."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from unittest.mock import patch

from app.config import get_settings
from tests.conftest import INTERNAL_TOKEN

TENANT = "meta_rollout_shop"
ENTITY_ID = "pn_rollout_12345"


def _headers():
    return {"X-Internal-Token": INTERNAL_TOKEN}


class _FakeSecretStore:
    """Keyed by (tenant, name) like a real one, so the token and entity_id can differ and the
    request actually asked for the right names -- unlike the provision-route tests' single-value
    stub, this route reads BOTH from the store rather than taking entity_id from the caller."""

    def __init__(self, values: dict[str, str] | None = None) -> None:
        self._v = dict(values or {})
        self.writes: list[tuple[str, str, str]] = []

    async def get(self, *, tenant: str, name: str) -> str:
        return self._v.get(f"{tenant}|{name}", "")

    async def set(self, *, tenant: str, name: str, value: str, actor_ref: str = "") -> None:
        self.writes.append((tenant, name, value))


def _swap(client, values: dict[str, str] | None = None):
    c = client.app.state.container
    saved = c.secret_store
    c.secret_store = _FakeSecretStore(values)
    return saved


def _restore(client, saved):
    client.app.state.container.secret_store = saved


class _Resp:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


def _settings_responder(enabled_back: bool):
    def _respond(req: urllib.request.Request, timeout=None):
        assert req.full_url.endswith(f"{ENTITY_ID}/agent_config/settings")
        assert req.get_method() == "PUT"
        return _Resp(json.dumps({"rollout": {"enabled": enabled_back}}).encode())
    return _respond


def test_flag_off_reports_disabled_and_never_calls_meta(client, monkeypatch):
    monkeypatch.setenv("META_AGENT_PROVISIONING_ENABLED", "false")
    get_settings.cache_clear()
    saved = _swap(client, {"meta_rollout_shop|META_KNOWLEDGE_TOKEN": "tok",
                           "meta_rollout_shop|META_WA_PHONE_NUMBER_ID": ENTITY_ID})
    try:
        with patch("urllib.request.urlopen",
                   side_effect=AssertionError("must never call Meta with the flag off")):
            r = client.post("/internal/whatsapp/meta-agent/rollout",
                            json={"tenant": TENANT, "enabled": False}, headers=_headers())
    finally:
        _restore(client, saved)
        get_settings.cache_clear()
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert "off" in body["error"]


def test_a_tenant_never_provisioned_is_a_clean_reported_noop(client, monkeypatch):
    """No META_KNOWLEDGE_TOKEN/META_WA_PHONE_NUMBER_ID on file -- the ordinary case for a shop
    that has feature.whatsapp but never went through Meta Business Agent onboarding, never an
    alarm-worthy failure."""
    monkeypatch.setenv("META_AGENT_PROVISIONING_ENABLED", "true")
    get_settings.cache_clear()
    saved = _swap(client, {})
    try:
        r = client.post("/internal/whatsapp/meta-agent/rollout",
                        json={"tenant": TENANT, "enabled": False}, headers=_headers())
    finally:
        _restore(client, saved)
        get_settings.cache_clear()
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert "credential" in body["error"] or "entity_id" in body["error"]


def test_disabling_flips_meta_off_and_leaves_the_connection_untouched(client, monkeypatch):
    """The real request goes through with enabled=false -- the whole point: the number stays
    connected, only Meta's own AI stops."""
    monkeypatch.setenv("META_AGENT_PROVISIONING_ENABLED", "true")
    get_settings.cache_clear()
    saved = _swap(client, {"meta_rollout_shop|META_KNOWLEDGE_TOKEN": "tok",
                           "meta_rollout_shop|META_WA_PHONE_NUMBER_ID": ENTITY_ID})
    try:
        with patch("urllib.request.urlopen", side_effect=_settings_responder(False)):
            r = client.post("/internal/whatsapp/meta-agent/rollout",
                            json={"tenant": TENANT, "enabled": False}, headers=_headers())
    finally:
        _restore(client, saved)
        get_settings.cache_clear()
    assert r.status_code == 200
    body = r.json()
    assert body == {"ok": True, "enabled": False, "error": ""}


def test_re_enabling_flips_meta_back_on(client, monkeypatch):
    monkeypatch.setenv("META_AGENT_PROVISIONING_ENABLED", "true")
    get_settings.cache_clear()
    saved = _swap(client, {"meta_rollout_shop|META_KNOWLEDGE_TOKEN": "tok",
                           "meta_rollout_shop|META_WA_PHONE_NUMBER_ID": ENTITY_ID})
    try:
        with patch("urllib.request.urlopen", side_effect=_settings_responder(True)):
            r = client.post("/internal/whatsapp/meta-agent/rollout",
                            json={"tenant": TENANT, "enabled": True}, headers=_headers())
    finally:
        _restore(client, saved)
        get_settings.cache_clear()
    assert r.status_code == 200
    body = r.json()
    assert body == {"ok": True, "enabled": True, "error": ""}


def test_a_graph_error_is_reported_not_500(client, monkeypatch):
    monkeypatch.setenv("META_AGENT_PROVISIONING_ENABLED", "true")
    get_settings.cache_clear()
    saved = _swap(client, {"meta_rollout_shop|META_KNOWLEDGE_TOKEN": "tok",
                           "meta_rollout_shop|META_WA_PHONE_NUMBER_ID": ENTITY_ID})
    err = urllib.error.HTTPError("url", 500, "server error", {}, None)
    err.read = lambda: b"oops"
    try:
        with patch("urllib.request.urlopen", side_effect=err):
            r = client.post("/internal/whatsapp/meta-agent/rollout",
                            json={"tenant": TENANT, "enabled": False}, headers=_headers())
    finally:
        _restore(client, saved)
        get_settings.cache_clear()
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True   # the CALL was made and answered -- Meta just said no
    assert body["enabled"] is False


def test_refuses_without_the_internal_token(client):
    r = client.post("/internal/whatsapp/meta-agent/rollout",
                    json={"tenant": TENANT, "enabled": False})
    assert r.status_code in (401, 403)


def test_refuses_a_missing_tenant(client):
    r = client.post("/internal/whatsapp/meta-agent/rollout",
                    json={"enabled": False}, headers=_headers())
    assert r.status_code == 422


def test_refuses_a_missing_enabled(client):
    r = client.post("/internal/whatsapp/meta-agent/rollout",
                    json={"tenant": TENANT}, headers=_headers())
    assert r.status_code == 422
