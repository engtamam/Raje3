"""HttpAssistantConnections / ensure_connection — the lazy per-tenant connection resolver."""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from app.core.assistant_connections import (
    AssistantConnectionsUnavailable,
    HttpAssistantConnections,
    ensure_connection,
)


def client():
    return HttpAssistantConnections(
        url="http://assistant-service:8000", connections_path="/internal/assistant/connections",
        token="t", timeout=8)


class _Resp:
    def __init__(self, payload, status=200):
        self._p = json.dumps(payload).encode()
        self.status = status

    def read(self):
        return self._p

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_no_existing_connection_creates_one_with_the_given_prompt_and_tools():
    calls = []

    def _urlopen(req, timeout=None):
        calls.append((req.get_method(), req.full_url, json.loads(req.data or b"{}")))
        if req.get_method() == "GET":
            return _Resp({"connections": []})
        return _Resp({"id": "conn_1"})

    with patch("urllib.request.urlopen", _urlopen):
        cid = ensure_connection(
            client(), tenant="t1", url="http://model", model="m", auth="vertex",
            credential="cred", system_prompt="prompt A", tools=[{"name": "x"}])

    assert cid == "conn_1"
    method, url, body = calls[-1]
    assert method == "POST"
    assert url.endswith("/internal/assistant/connections")
    assert body == {"tenant": "t1", "name": "whatsapp-assistant", "url": "http://model",
                    "model": "m", "auth": "vertex", "system_prompt": "prompt A",
                    "temperature": 0.2, "tools": [{"name": "x"}], "credential": "cred"}


def test_an_existing_connection_with_the_same_prompt_and_tools_is_left_alone():
    calls = []

    def _urlopen(req, timeout=None):
        calls.append(req.get_method())
        return _Resp({"connections": [{"id": "conn_9", "name": "whatsapp-assistant",
                                       "system_prompt": "same", "tools": [{"name": "x"}]}]})

    with patch("urllib.request.urlopen", _urlopen):
        cid = ensure_connection(
            client(), tenant="t1", url="http://model", model="m", auth="vertex",
            credential="cred", system_prompt="same", tools=[{"name": "x"}])

    assert cid == "conn_9"
    assert calls == ["GET"]          # no PUT — nothing changed


def test_a_changed_prompt_updates_the_existing_connection_without_resending_the_credential():
    calls = []

    def _urlopen(req, timeout=None):
        calls.append((req.get_method(), json.loads(req.data or b"{}")))
        if req.get_method() == "GET":
            return _Resp({"connections": [{"id": "conn_9", "name": "whatsapp-assistant",
                                           "system_prompt": "old", "tools": [{"name": "x"}]}]})
        return _Resp({"id": "conn_9"})

    with patch("urllib.request.urlopen", _urlopen):
        cid = ensure_connection(
            client(), tenant="t1", url="http://model", model="m", auth="vertex",
            credential="cred", system_prompt="new", tools=[{"name": "x"}])

    assert cid == "conn_9"
    put_calls = [c for c in calls if c[0] == "PUT"]
    assert len(put_calls) == 1
    assert put_calls[0][1] == {"tenant": "t1", "system_prompt": "new"}
    assert "credential" not in put_calls[0][1]


def test_changed_tools_alone_also_triggers_an_update():
    calls = []

    def _urlopen(req, timeout=None):
        calls.append((req.get_method(), json.loads(req.data or b"{}")))
        if req.get_method() == "GET":
            return _Resp({"connections": [{"id": "conn_9", "name": "whatsapp-assistant",
                                           "system_prompt": "same", "tools": [{"name": "x"}]}]})
        return _Resp({"id": "conn_9"})

    with patch("urllib.request.urlopen", _urlopen):
        ensure_connection(
            client(), tenant="t1", url="http://model", model="m", auth="vertex",
            credential="cred", system_prompt="same", tools=[{"name": "y"}])

    put_calls = [c for c in calls if c[0] == "PUT"]
    assert put_calls[0][1] == {"tenant": "t1", "tools": [{"name": "y"}]}


def test_a_second_tenants_connection_is_not_confused_with_the_first():
    """`list` is scoped by the query string's own tenant — this asserts the resolver actually
    reads the connection LIST for the tenant it was asked about, not some other cached set."""
    seen_get_tenants = []

    def _urlopen(req, timeout=None):
        if req.get_method() == "GET":
            seen_get_tenants.append(req.full_url.split("tenant=")[1])
            return _Resp({"connections": []})
        return _Resp({"id": "x"})

    with patch("urllib.request.urlopen", _urlopen):
        ensure_connection(client(), tenant="tenant_a", url="u", model="m", auth="vertex",
                          credential="c", system_prompt="p", tools=[])
        ensure_connection(client(), tenant="tenant_b", url="u", model="m", auth="vertex",
                          credential="c", system_prompt="p", tools=[])

    assert seen_get_tenants == ["tenant_a", "tenant_b"]


def test_an_unreachable_service_raises_the_named_unavailable_error():
    def _urlopen(req, timeout=None):
        raise OSError("connection refused")

    with patch("urllib.request.urlopen", _urlopen):
        with pytest.raises(AssistantConnectionsUnavailable):
            ensure_connection(client(), tenant="t1", url="u", model="m", auth="vertex",
                              credential="c", system_prompt="p", tools=[])
