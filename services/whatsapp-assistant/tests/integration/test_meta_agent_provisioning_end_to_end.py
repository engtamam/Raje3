"""A real, permanent simulation of Meta's OWN side of the Business Agent onboarding sequence —
the counterpart to test_meta_agent_end_to_end_simulation.py, which simulates Meta CALLING us
(the Connector path). This file simulates US calling META: every real Graph API round-trip
`app/core/meta_agent_provisioning.py::provision_number` makes, through the ACTUAL route
operations' connect.py background task hits (`POST /internal/whatsapp/meta-agent/provision`),
never by calling `provision_number` directly — the point is proving the whole wire (route ->
container.secret_store -> provisioner_factory -> HttpMetaAgentProvisioner -> urlopen) works
TOGETHER, same reasoning test_meta_agent_end_to_end_simulation.py's own docstring gives for why
it goes through the real router rather than calling core functions directly.

Covers every scenario MEMORY's task-meta-agent-full-automation.md's own "update the simulator"
checklist calls for that belongs in THIS service (the provisioning sequence itself). Release-
control (after every SEND) lives in notification-service/platform, a different codebase this
session does not edit directly — see [[platform-changes-via-sister-session]]."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from unittest.mock import patch

from app.config import get_settings
from tests.conftest import INTERNAL_TOKEN

TENANT = "meta_sim_shop"
ENTITY_ID = "pn_sim_12345"


def _headers():
    return {"X-Internal-Token": INTERNAL_TOKEN}


class _FakeSecretStore:
    """Pre-loaded with a real-looking bearer token, so provision_number's own first check
    passes and the real HttpMetaAgentProvisioner path is exercised end to end."""

    def __init__(self, token: str = "fake-meta-bearer-token") -> None:
        self._token = token
        self.writes: list[tuple[str, str, str]] = []

    async def get(self, *, tenant: str, name: str) -> str:
        return self._token

    async def set(self, *, tenant: str, name: str, value: str, actor_ref: str = "") -> None:
        self.writes.append((tenant, name, value))


def _swap(client):
    c = client.app.state.container
    saved = c.secret_store
    c.secret_store = _FakeSecretStore()
    return saved


def _restore(client, saved):
    client.app.state.container.secret_store = saved


class _ScriptedMeta:
    """Answers every real Graph call `HttpMetaAgentProvisioner` makes, keyed by URL suffix —
    robust to however many Connector tools `_iter_connector_tools()` actually finds today,
    rather than a brittle fixed-length response list. Logs the call order so tests can assert
    the sequence, same as `META_AGENT_CONSENT_SKILL.md`'s own documented step order."""

    def __init__(self, *, eligible: bool = True, skill_status: str = "approved",
                 enable_ok: bool = True) -> None:
        self.eligible = eligible
        self.skill_status = skill_status
        self.enable_ok = enable_ok
        self.calls: list[str] = []
        self.tool_registrations: list[dict] = []

    def __call__(self, req: urllib.request.Request, timeout=None):
        url = req.full_url
        body = json.loads(req.data) if req.data else {}

        if url.endswith("agent_eligibility"):
            self.calls.append("eligibility")
            return _Resp(json.dumps({"is_eligible": self.eligible}).encode())
        if url.endswith("agent_onboarding"):
            self.calls.append("create_agent")
            return _Resp(json.dumps({"agent_id": "agent_sim_1"}).encode())
        if url.endswith("agent_connectors"):
            self.calls.append("register_connector")
            return _Resp(json.dumps({"id": "connector_sim_1"}).encode())
        if "/agent_connectors/" in url and url.endswith("/tools"):
            self.calls.append(f"register_tool:{body.get('name', '')}")
            self.tool_registrations.append(body)
            return _Resp(json.dumps({"id": f"tool_{len(self.tool_registrations)}"}).encode())
        if url.endswith("agent_config/skills"):
            self.calls.append("upload_skill")
            return _Resp(json.dumps({"status": self.skill_status}).encode())
        if url.endswith("agent_config/settings"):
            self.calls.append("enable_agent")
            return _Resp(json.dumps({"rollout": {"enabled": self.enable_ok}}).encode())
        raise AssertionError(f"unexpected Meta call: {req.get_method()} {url}")


class _Resp:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


# ── 1. the full setup scenario, in order, exactly as the plan doc lists it ─────────────────────
def test_full_provisioning_sequence_runs_every_step_in_order(client, monkeypatch):
    monkeypatch.setenv("META_AGENT_PROVISIONING_ENABLED", "true")
    get_settings.cache_clear()
    saved = _swap(client)
    fake_store = client.app.state.container.secret_store   # captured before restore
    meta = _ScriptedMeta()
    try:
        with patch("urllib.request.urlopen", side_effect=meta):
            r = client.post("/internal/whatsapp/meta-agent/provision",
                            json={"tenant": TENANT, "entity_id": ENTITY_ID}, headers=_headers())
    finally:
        _restore(client, saved)
        get_settings.cache_clear()

    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["agent_id"] == "agent_sim_1"
    assert body["connector_id"] == "connector_sim_1"
    assert body["tool_count"] > 0
    assert body["skill_status"] == "approved"
    assert body["enabled"] is True

    # ORDER MATTERS — eligibility first, enable last, every tool registration strictly between
    # the connector and the skill upload.
    assert meta.calls[0] == "eligibility"
    assert meta.calls[1] == "create_agent"
    assert meta.calls[2] == "register_connector"
    tool_calls = [c for c in meta.calls if c.startswith("register_tool:")]
    assert len(tool_calls) == body["tool_count"]
    assert meta.calls[3:3 + len(tool_calls)] == tool_calls
    assert meta.calls[3 + len(tool_calls)] == "upload_skill"
    assert meta.calls[-1] == "enable_agent"

    # agent_id/connector_id are written to the SAME per-tenant secret store real credentials use.
    written = {name: value for _, name, value in fake_store.writes}
    assert written.get("META_AGENT_ID") == "agent_sim_1"
    assert written.get("META_CONNECTOR_ID") == "connector_sim_1"


# ── 2. eligibility false — stop clean, never fake a success ────────────────────────────────────
def test_ineligible_number_stops_before_creating_anything(client, monkeypatch):
    monkeypatch.setenv("META_AGENT_PROVISIONING_ENABLED", "true")
    get_settings.cache_clear()
    saved = _swap(client)
    meta = _ScriptedMeta(eligible=False)
    try:
        with patch("urllib.request.urlopen", side_effect=meta):
            r = client.post("/internal/whatsapp/meta-agent/provision",
                            json={"tenant": TENANT, "entity_id": ENTITY_ID}, headers=_headers())
    finally:
        _restore(client, saved)
        get_settings.cache_clear()

    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert body["failed_step"] == "check_eligibility"
    assert body["agent_id"] == ""
    # Nothing past eligibility was ever attempted — no agent, no connector, no tools.
    assert meta.calls == ["eligibility"]


# ── 3. Skill upload returns pending_review — never assumed live ────────────────────────────────
def test_skill_pending_review_completes_the_chain_and_says_so(client, monkeypatch):
    monkeypatch.setenv("META_AGENT_PROVISIONING_ENABLED", "true")
    get_settings.cache_clear()
    saved = _swap(client)
    meta = _ScriptedMeta(skill_status="pending_review")
    try:
        with patch("urllib.request.urlopen", side_effect=meta):
            r = client.post("/internal/whatsapp/meta-agent/provision",
                            json={"tenant": TENANT, "entity_id": ENTITY_ID}, headers=_headers())
    finally:
        _restore(client, saved)
        get_settings.cache_clear()

    assert r.status_code == 200
    body = r.json()
    # pending_review does not stop the sequence -- enable still runs -- but the real status is
    # reported verbatim, never silently upgraded to "approved".
    assert body["ok"] is True
    assert body["skill_status"] == "pending_review"
    assert body["enabled"] is True
    assert "enable_agent" in meta.calls


# ── 4. a mid-sequence Graph failure stops the chain and names the exact step ───────────────────
def test_a_connector_registration_failure_stops_the_chain_and_names_the_step(client, monkeypatch):
    monkeypatch.setenv("META_AGENT_PROVISIONING_ENABLED", "true")
    get_settings.cache_clear()
    saved = _swap(client)

    def _flaky(req: urllib.request.Request, timeout=None):
        if req.full_url.endswith("agent_connectors"):
            err = urllib.error.HTTPError(req.full_url, 500, "server error", {}, None)
            err.read = lambda: b"internal error"
            raise err
        return _ScriptedMeta()(req, timeout)

    try:
        with patch("urllib.request.urlopen", side_effect=_flaky):
            r = client.post("/internal/whatsapp/meta-agent/provision",
                            json={"tenant": TENANT, "entity_id": ENTITY_ID}, headers=_headers())
    finally:
        _restore(client, saved)
        get_settings.cache_clear()

    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert body["failed_step"] == "register_connector"
    # The agent WAS created before the failure -- reported, not hidden, so a retry can be
    # targeted rather than starting the whole sequence over.
    assert body["agent_id"] == "agent_sim_1"
    assert body["connector_id"] == ""


# ── 5. the flag being off never reaches Meta at all, even with a real credential present ───────
def test_flag_off_never_makes_a_single_real_graph_call(client, monkeypatch):
    monkeypatch.setenv("META_AGENT_PROVISIONING_ENABLED", "false")
    get_settings.cache_clear()
    saved = _swap(client)
    meta = _ScriptedMeta()
    try:
        with patch("urllib.request.urlopen", side_effect=meta):
            r = client.post("/internal/whatsapp/meta-agent/provision",
                            json={"tenant": TENANT, "entity_id": ENTITY_ID}, headers=_headers())
    finally:
        _restore(client, saved)
        get_settings.cache_clear()

    assert r.status_code == 200
    assert r.json()["ok"] is False
    # NullMetaAgentProvisioner never touches urlopen -- proven by the scripted responder logging
    # zero calls, not merely by the response shape.
    assert meta.calls == []
