"""core/meta_agent_rollout_trigger.py — the operations-side leg that switches an already-onboarded
number's Meta AI on or off, never a re-run of onboarding. See test_meta_agent_provision_trigger.py,
whose shape this mirrors exactly."""
from __future__ import annotations

import asyncio

from app.core.meta_agent_rollout_trigger import MetaAgentRolloutTrigger


def run(c):
    return asyncio.run(c)


def test_unconfigured_returns_false_never_raises():
    trigger = MetaAgentRolloutTrigger(base_url="", path="/x", token="t")
    assert trigger.configured is False
    out = run(trigger.trigger(tenant="t1", enabled=False))
    assert out is False


def test_configured_posts_tenant_and_enabled_and_reads_ok(monkeypatch):
    calls: list[dict] = []

    def _fake_post_json(url, body, token, timeout, **_kw):
        calls.append({"url": url, "body": body, "token": token, "timeout": timeout})
        return {"ok": True, "enabled": False}

    import app.core.meta_agent_rollout_trigger as mod

    monkeypatch.setattr(mod.internal_http, "post_json", _fake_post_json)

    trigger = MetaAgentRolloutTrigger(
        base_url="http://whatsapp-assistant:8000",
        path="/internal/whatsapp/meta-agent/rollout", token="tok")
    out = run(trigger.trigger(tenant="t1", enabled=False))

    assert out is True
    assert len(calls) == 1
    assert calls[0]["url"] == "http://whatsapp-assistant:8000/internal/whatsapp/meta-agent/rollout"
    assert calls[0]["body"] == {"tenant": "t1", "enabled": False}
    assert calls[0]["token"] == "tok"


def test_a_falsy_ok_in_the_response_reports_false():
    import app.core.meta_agent_rollout_trigger as mod

    def _fake_post_json(url, body, token, timeout, **_kw):
        return {"ok": False, "error": "no Meta credential/entity_id configured for this tenant"}

    trigger = MetaAgentRolloutTrigger(
        base_url="http://whatsapp-assistant:8000", path="/x", token="t")
    mod.internal_http.post_json = _fake_post_json
    out = run(trigger.trigger(tenant="t1", enabled=True))
    assert out is False


def test_a_transport_failure_reports_false_never_raises(monkeypatch):
    import app.core.meta_agent_rollout_trigger as mod

    def _raise(*_a, **_kw):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(mod.internal_http, "post_json", _raise)

    trigger = MetaAgentRolloutTrigger(
        base_url="http://whatsapp-assistant:8000", path="/x", token="t")
    out = run(trigger.trigger(tenant="t1", enabled=True))
    assert out is False
