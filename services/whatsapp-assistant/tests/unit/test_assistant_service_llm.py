"""AssistantServiceLlm — converts assistant-service's discriminated invoke result into LlmReply,
takes only the first tool call on a multi-call turn, and never proposes a tool this turn withheld."""
from __future__ import annotations

import asyncio
import json
from unittest.mock import patch

import pytest

from app.adapters.llm.assistant_service import AssistantServiceLlm, LlmUnavailable
from app.core.assistant_connections import HttpAssistantConnections


def run(c):
    return asyncio.run(c)


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


def llm(allowed_tools=frozenset({"check_availability", "propose_booking"})):
    connections = HttpAssistantConnections(
        url="http://assistant-service:8000", connections_path="/internal/assistant/connections",
        token="t", timeout=8)
    return AssistantServiceLlm(
        connections=connections, model_location="me-central2", model_name="m", model_auth="vertex",
        env_project="proj", env_credential="cred", allowed_tools=allowed_tools)


def _fake_transport(*, get_result=None, post_results=()):
    """GET (list) then a sequence of POSTs (create/update, then invoke) — same shape every test
    below needs, varying only what each POST answers."""
    posts = list(post_results)

    def _urlopen(req, timeout=None):
        if req.get_method() == "GET":
            return _Resp(get_result or {"connections": []})
        return _Resp(posts.pop(0))

    return _urlopen


def test_a_text_reply_carries_through_with_token_counts():
    transport = _fake_transport(
        post_results=[{"id": "conn_1"},                                     # create
                     {"kind": "text", "text": "أهلاً", "tokens_in": 12, "tokens_out": 4}])  # invoke
    with patch("urllib.request.urlopen", transport):
        reply = run(llm().respond(
            system_prompt="sp", summary="", recent_messages=[], user_message="hi",
            allowed_tools=frozenset(), tenant="t1"))
    assert reply.text == "أهلاً"
    assert reply.input_tokens == 12
    assert reply.output_tokens == 4
    assert reply.tool_call is None


def test_a_tool_call_reply_takes_only_the_first_of_several():
    transport = _fake_transport(
        post_results=[{"id": "conn_1"},
                     {"kind": "tool_call", "tokens_in": 5, "tokens_out": 2, "calls": [
                         {"id": "c1", "name": "check_availability", "arguments": {"service_id": "s1"}},
                         {"id": "c2", "name": "propose_booking", "arguments": {}},
                     ]}])
    with patch("urllib.request.urlopen", transport):
        reply = run(llm().respond(
            system_prompt="sp", summary="", recent_messages=[], user_message="hi",
            allowed_tools=frozenset({"check_availability", "propose_booking"}), tenant="t1"))
    assert reply.tool_call is not None
    assert reply.tool_call.name == "check_availability"
    assert reply.tool_call.args == {"service_id": "s1"}
    assert reply.text == ""


def test_a_tool_call_outside_this_turns_allowed_tools_is_dropped_not_trusted():
    """Defence in depth — the connection's own declared tools should already make this
    impossible, but a call outside what THIS turn allows is refused here too."""
    transport = _fake_transport(
        post_results=[{"id": "conn_1"},
                     {"kind": "tool_call", "tokens_in": 5, "tokens_out": 2,
                      "calls": [{"id": "c1", "name": "propose_booking", "arguments": {}}]}])
    with patch("urllib.request.urlopen", transport):
        reply = run(llm(allowed_tools=frozenset({"check_availability"})).respond(
            system_prompt="sp", summary="", recent_messages=[], user_message="hi",
            allowed_tools=frozenset({"check_availability"}), tenant="t1"))
    assert reply.tool_call is None
    assert reply.text == ""


def test_recent_messages_are_translated_into_role_content_turns():
    captured = {}
    transport_calls = []

    def _urlopen(req, timeout=None):
        transport_calls.append(req)
        if req.get_method() == "GET":
            return _Resp({"connections": []})
        body = json.loads(req.data or b"{}")
        if "messages" in body:
            captured["body"] = body
            return _Resp({"kind": "text", "text": "ok", "tokens_in": 1, "tokens_out": 1})
        return _Resp({"id": "conn_1"})

    with patch("urllib.request.urlopen", _urlopen):
        run(llm().respond(
            system_prompt="sp", summary="", recent_messages=[
                {"role": "user", "text": "one"}, {"role": "assistant", "text": "two"}],
            user_message="three", allowed_tools=frozenset(), tenant="t1"))

    assert captured["body"]["tenant"] == "t1"
    assert captured["body"]["messages"] == [
        {"role": "user", "content": "one"}, {"role": "assistant", "content": "two"},
        {"role": "user", "content": "three"}]


def test_the_deploy_time_max_reply_tokens_is_sent_on_every_invoke():
    """No runtime_config wired — MAX_REPLY_TOKENS falls back to whatever the adapter was built
    with, same shape as model_name's own deploy-time default."""
    captured = {}

    def _urlopen(req, timeout=None):
        if req.get_method() == "GET":
            return _Resp({"connections": []})
        body = json.loads(req.data or b"{}")
        if "messages" in body:
            captured["body"] = body
            return _Resp({"kind": "text", "text": "ok", "tokens_in": 1, "tokens_out": 1})
        return _Resp({"id": "conn_1"})

    connections = HttpAssistantConnections(
        url="http://assistant-service:8000", connections_path="/internal/assistant/connections",
        token="t", timeout=8)
    adapter = AssistantServiceLlm(
        connections=connections, model_location="me-central2", model_name="m", model_auth="vertex",
        env_project="proj", env_credential="cred", allowed_tools=frozenset(),
        max_reply_tokens=250)

    with patch("urllib.request.urlopen", _urlopen):
        run(adapter.respond(system_prompt="sp", summary="", recent_messages=[],
                            user_message="hi", allowed_tools=frozenset(), tenant="t1"))

    assert captured["body"]["max_tokens"] == 250


def test_max_reply_tokens_is_read_live_from_runtime_config_when_wired():
    """A technical safety cap, not a shop setting — see config.py's own MAX_REPLY_TOKENS note.
    Overridable live by an operator the same way ASSISTANT_MODEL_NAME already is."""
    class _FakeRuntimeConfig:
        async def get(self, *, tenant: str, key: str, default):
            if key == "MAX_REPLY_TOKENS":
                return 900
            return default  # ASSISTANT_MODEL_NAME — not what this test is about

    captured = {}

    def _urlopen(req, timeout=None):
        if req.get_method() == "GET":
            return _Resp({"connections": []})
        body = json.loads(req.data or b"{}")
        if "messages" in body:
            captured["body"] = body
            return _Resp({"kind": "text", "text": "ok", "tokens_in": 1, "tokens_out": 1})
        return _Resp({"id": "conn_1"})

    connections = HttpAssistantConnections(
        url="http://assistant-service:8000", connections_path="/internal/assistant/connections",
        token="t", timeout=8)
    adapter = AssistantServiceLlm(
        connections=connections, model_location="me-central2", model_name="m", model_auth="vertex",
        env_project="proj", env_credential="cred", allowed_tools=frozenset(),
        runtime_config=_FakeRuntimeConfig(), max_reply_tokens=500)

    with patch("urllib.request.urlopen", _urlopen):
        run(adapter.respond(system_prompt="sp", summary="", recent_messages=[],
                            user_message="hi", allowed_tools=frozenset(), tenant="t1"))

    assert captured["body"]["max_tokens"] == 900


def test_an_unreachable_assistant_service_raises_llm_unavailable_not_a_bare_network_error():
    def _urlopen(req, timeout=None):
        raise OSError("connection refused")

    with patch("urllib.request.urlopen", _urlopen):
        with pytest.raises(LlmUnavailable):
            run(llm().respond(system_prompt="sp", summary="", recent_messages=[],
                              user_message="hi", allowed_tools=frozenset(), tenant="t1"))


def test_no_project_or_credential_configured_refuses_without_ever_calling_out():
    """No GCP project/credential exists yet — refused as LlmUnavailable (the same debounce-and-
    retry path a transient failure takes) rather than attempting a call that can only fail."""
    connections = HttpAssistantConnections(
        url="http://assistant-service:8000", connections_path="/internal/assistant/connections",
        token="t", timeout=8)
    unconfigured = AssistantServiceLlm(
        connections=connections, model_location="me-central2", model_name="m", model_auth="vertex",
        env_project="", env_credential="", allowed_tools=frozenset())

    def _urlopen(req, timeout=None):
        raise AssertionError("must not touch the network with no project/credential configured")

    with patch("urllib.request.urlopen", _urlopen):
        with pytest.raises(LlmUnavailable):
            run(unconfigured.respond(system_prompt="sp", summary="", recent_messages=[],
                                     user_message="hi", allowed_tools=frozenset(), tenant="t1"))


def test_the_model_name_is_read_live_from_runtime_config_when_wired():
    """app/runtime_policy.py's ASSISTANT_MODEL_NAME override — read fresh every call (never
    cached), so a switch from the console takes effect on the very next turn."""
    class _FakeRuntimeConfig:
        async def get(self, *, tenant: str, key: str, default):
            if key == "ASSISTANT_MODEL_NAME":
                return "gemini-overridden-model"
            return default  # MAX_REPLY_TOKENS — not what this test is about

    connections = HttpAssistantConnections(
        url="http://assistant-service:8000", connections_path="/internal/assistant/connections",
        token="t", timeout=8)
    adapter = AssistantServiceLlm(
        connections=connections, model_location="me-central2", model_name="the-constructor-default",
        model_auth="vertex", env_project="proj", env_credential="cred",
        allowed_tools=frozenset(), runtime_config=_FakeRuntimeConfig())

    captured_urls = []

    def _urlopen(req, timeout=None):
        if req.get_method() == "GET":
            return _Resp({"connections": []})
        body = json.loads(req.data or b"{}")
        if "url" in body:
            captured_urls.append(body["url"])
        if "messages" in body:
            return _Resp({"kind": "text", "text": "ok", "tokens_in": 1, "tokens_out": 1})
        return _Resp({"id": "conn_1"})

    with patch("urllib.request.urlopen", _urlopen):
        run(adapter.respond(system_prompt="sp", summary="", recent_messages=[],
                            user_message="hi", allowed_tools=frozenset(), tenant="t1"))

    assert captured_urls, "the create/update call never carried a url to inspect"
    assert "gemini-overridden-model" in captured_urls[0]
    assert "the-constructor-default" not in captured_urls[0]


def test_no_runtime_config_wired_uses_the_constructor_model_name():
    """None (no panel wired, or an older call site) must behave exactly as before this field
    existed — the same None-safe shape every other optional peer in this service follows."""
    connections = HttpAssistantConnections(
        url="http://assistant-service:8000", connections_path="/internal/assistant/connections",
        token="t", timeout=8)
    adapter = AssistantServiceLlm(
        connections=connections, model_location="me-central2", model_name="the-constructor-default",
        model_auth="vertex", env_project="proj", env_credential="cred", allowed_tools=frozenset())

    captured_urls = []

    def _urlopen(req, timeout=None):
        if req.get_method() == "GET":
            return _Resp({"connections": []})
        body = json.loads(req.data or b"{}")
        if "url" in body:
            captured_urls.append(body["url"])
        if "messages" in body:
            return _Resp({"kind": "text", "text": "ok", "tokens_in": 1, "tokens_out": 1})
        return _Resp({"id": "conn_1"})

    with patch("urllib.request.urlopen", _urlopen):
        run(adapter.respond(system_prompt="sp", summary="", recent_messages=[],
                            user_message="hi", allowed_tools=frozenset(), tenant="t1"))

    assert "the-constructor-default" in captured_urls[0]


def test_a_rotated_credential_is_re_resolved_after_invalidate_key_cache():
    """Mirrors GEMINI_API_KEY's own rotation contract: app/api/v1/operator.py calls
    invalidate_key_cache() generically after a PUT, and the next turn must see the new value."""

    class _FakeStore:
        def __init__(self):
            self.value = "first"

        async def get(self, *, tenant, name, fallback):
            return self.value

    store = _FakeStore()
    connections = HttpAssistantConnections(
        url="http://assistant-service:8000", connections_path="/internal/assistant/connections",
        token="t", timeout=8)
    adapter = AssistantServiceLlm(
        connections=connections, model_location="me-central2", model_name="m", model_auth="vertex",
        env_project="proj", env_credential="", allowed_tools=frozenset(), secret_store=store)

    assert run(adapter._resolve_credential()) == "first"
    store.value = "second"
    # STILL CACHED — a rotation must not silently apply until invalidated.
    assert run(adapter._resolve_credential()) == "first"
    adapter.invalidate_key_cache()
    assert run(adapter._resolve_credential()) == "second"
