"""core/meta_agent_provision_trigger.py — the operations-side leg that fires whatsapp-assistant's
own Meta Business Agent onboarding sequence right after a number connects."""
from __future__ import annotations

import asyncio

from app.core.meta_agent_provision_trigger import MetaAgentProvisionTrigger


def run(c):
    return asyncio.run(c)


def test_unconfigured_returns_false_never_raises():
    trigger = MetaAgentProvisionTrigger(base_url="", path="/x", token="t")
    assert trigger.configured is False
    out = run(trigger.trigger(tenant="t1", entity_id="pn_1"))
    assert out is False


def test_configured_posts_tenant_and_entity_id_and_reads_ok(monkeypatch):
    calls: list[dict] = []

    def _fake_post_json(url, body, token, timeout, **_kw):
        calls.append({"url": url, "body": body, "token": token, "timeout": timeout})
        return {"ok": True, "agent_id": "agent_1"}

    import app.core.meta_agent_provision_trigger as mod

    monkeypatch.setattr(mod.internal_http, "post_json", _fake_post_json)

    trigger = MetaAgentProvisionTrigger(
        base_url="http://whatsapp-assistant:8000",
        path="/internal/whatsapp/meta-agent/provision", token="tok")
    out = run(trigger.trigger(tenant="t1", entity_id="pn_1"))

    assert out is True
    assert len(calls) == 1
    assert calls[0]["url"] == (
        "http://whatsapp-assistant:8000/internal/whatsapp/meta-agent/provision")
    assert calls[0]["body"] == {"tenant": "t1", "entity_id": "pn_1"}
    assert calls[0]["token"] == "tok"


def test_a_falsy_ok_in_the_response_reports_false():
    import app.core.meta_agent_provision_trigger as mod

    def _fake_post_json(url, body, token, timeout, **_kw):
        return {"ok": False, "failed_step": "check_eligibility"}

    trigger = MetaAgentProvisionTrigger(
        base_url="http://whatsapp-assistant:8000", path="/x", token="t")
    mod.internal_http.post_json = _fake_post_json
    out = run(trigger.trigger(tenant="t1", entity_id="pn_1"))
    assert out is False


def test_a_transport_failure_reports_false_never_raises(monkeypatch):
    import app.core.meta_agent_provision_trigger as mod

    def _raise(*_a, **_kw):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(mod.internal_http, "post_json", _raise)

    trigger = MetaAgentProvisionTrigger(
        base_url="http://whatsapp-assistant:8000", path="/x", token="t")
    out = run(trigger.trigger(tenant="t1", entity_id="pn_1"))
    assert out is False
