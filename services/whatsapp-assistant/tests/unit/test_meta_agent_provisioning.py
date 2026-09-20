"""core/meta_agent_provisioning.py -- eligibility, agent creation, Connector/tool registration,
Skill upload, Knowledge reuse, enable, and the `provision_number` orchestrator. Stubbing follows
test_knowledge_export.py's own conventions (fake secret store, fake urlopen response object)."""
from __future__ import annotations

import asyncio
import json
import urllib.error
from unittest.mock import patch

import pytest

from app.core.meta_agent_provisioning import (
    ConnectorToolSpec,
    HttpMetaAgentProvisioner,
    MetaAgentProvisioningError,
    NullMetaAgentProvisioner,
    ProvisioningResult,
    RolloutResult,
    SECRET_AGENT_ID_NAME,
    SECRET_CONNECTOR_ID_NAME,
    SECRET_ENTITY_ID_NAME,
    SECRET_TOKEN_NAME,
    build,
    build_tool_registration_payload,
    _consent_skill_text,
    _iter_connector_tools,
    provision_number,
    set_agent_rollout,
)


def run(c):
    return asyncio.run(c)


class _FakeSecrets:
    def __init__(self, values=None):
        self._v = dict(values or {})
        self.writes = []

    async def get(self, *, tenant, name, fallback=""):
        return self._v.get(f"{tenant}|{name}", fallback)

    async def set(self, *, tenant, name, value, actor_ref=""):
        self._v[f"{tenant}|{name}"] = value
        self.writes.append((tenant, name, value))


class _Resp:
    def __init__(self, body=b"{}", status=200):
        self._body = body
        self.status = status

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _http(**kw):
    return HttpMetaAgentProvisioner(
        token="tok", graph_base_url="https://graph.facebook.com", graph_version="v26.0",
        connector_base_url="https://kobo-cloud.com", connector_auth_token="ctok", **kw)


def test_tool_registration_payload_shape():
    spec = ConnectorToolSpec(name="check_availability", description="d",
                              path="/api/v1/connectors/check_availability",
                              parameters={"type": "object", "properties": {}})
    body = build_tool_registration_payload(spec)
    assert body["name"] == "check_availability"
    assert body["request_definition"]["method"] == "POST"
    assert body["request_definition"]["path"] == spec.path
    assert body["user_auth_required"] is False


def test_iter_connector_tools_derives_from_real_router_and_schemas():
    specs = _iter_connector_tools()
    names = {s.name for s in specs}
    assert "check_availability" in names
    assert "propose_booking" in names
    assert "confirm_proposal" in names
    assert "check_consent" in names
    assert "record_consent" in names


def test_iter_connector_tools_descriptions_match_tool_schemas_source_of_truth():
    from app.adapters.llm.assistant_service import _TOOL_SCHEMAS
    specs = {s.name: s for s in _iter_connector_tools()}
    assert specs["check_availability"].description == _TOOL_SCHEMAS["check_availability"]["description"]


def test_iter_connector_tools_actually_derives_not_just_happens_to_match():
    import app.adapters.llm.assistant_service as assistant_service_module

    original = dict(assistant_service_module._TOOL_SCHEMAS)
    patched = dict(original)
    patched["check_availability"] = dict(original["check_availability"])
    patched["check_availability"]["description"] = "TOTALLY DIFFERENT TEXT FOR THE DRIFT TEST"
    with patch.object(assistant_service_module, "_TOOL_SCHEMAS", patched):
        specs = {s.name: s for s in _iter_connector_tools()}
    assert specs["check_availability"].description == "TOTALLY DIFFERENT TEXT FOR THE DRIFT TEST"
    specs_after = {s.name: s for s in _iter_connector_tools()}
    assert specs_after["check_availability"].description == original["check_availability"]["description"]


def test_iter_connector_tools_skips_route_with_no_schema_and_no_fallback():
    import app.api.v1.connectors as connectors_module

    class _FakeRoute:
        methods = {"POST"}
        path = "/api/v1/connectors/totally_unknown_op"

    with patch.object(connectors_module.router, "routes", [_FakeRoute()]):
        specs = _iter_connector_tools()
    assert specs == []


def test_iter_connector_tools_ignores_non_post_routes():
    import app.api.v1.connectors as connectors_module

    class _GetRoute:
        methods = {"GET"}
        path = "/api/v1/connectors/check_availability"

    with patch.object(connectors_module.router, "routes", [_GetRoute()]):
        specs = _iter_connector_tools()
    assert specs == []


def test_consent_skill_text_contains_the_real_consent_body():
    from app.core.inbound_ingest import _CONSENT_BODY
    text = _consent_skill_text()
    assert _CONSENT_BODY in text
    assert len(text) <= 20000


def test_consent_skill_text_mentions_check_consent_and_record_consent():
    text = _consent_skill_text()
    assert "check_consent" in text
    assert "record_consent" in text


def test_null_provisioner_eligibility_is_false():
    assert run(NullMetaAgentProvisioner().check_eligibility("e1")) is False


def test_null_provisioner_create_agent_raises():
    with pytest.raises(MetaAgentProvisioningError):
        run(NullMetaAgentProvisioner().create_agent("e1"))


def test_null_provisioner_enable_agent_is_false():
    assert run(NullMetaAgentProvisioner().enable_agent("e1", "a1")) is False


def test_build_returns_null_when_disabled():
    class _S:
        META_AGENT_PROVISIONING_ENABLED = False
    assert isinstance(build(_S(), secret_store=_FakeSecrets()), NullMetaAgentProvisioner)


def test_build_returns_null_without_secret_store():
    class _S:
        META_AGENT_PROVISIONING_ENABLED = True
    assert isinstance(build(_S()), NullMetaAgentProvisioner)


def test_build_returns_http_when_enabled():
    class _S:
        META_AGENT_PROVISIONING_ENABLED = True
        META_GRAPH_BASE_URL = "https://graph.facebook.com"
        META_GRAPH_API_VERSION = "v26.0"
        PUBLIC_BASE_URL = "https://kobo-cloud.com"
        CONNECTOR_API_TOKEN = "ctok"
        PEER_TIMEOUT_SECONDS = 8
    assert isinstance(build(_S(), secret_store=_FakeSecrets()), HttpMetaAgentProvisioner)


def test_check_eligibility_true():
    with patch("urllib.request.urlopen", return_value=_Resp(b'{"is_eligible": true}')):
        assert run(_http().check_eligibility("e1")) is True


def test_check_eligibility_false():
    with patch("urllib.request.urlopen", return_value=_Resp(b'{"is_eligible": false}')):
        assert run(_http().check_eligibility("e1")) is False


def test_check_eligibility_401_degrades_to_false():
    err = urllib.error.HTTPError("url", 401, "unauthorized", {}, None)
    err.read = lambda: b"forbidden"
    with patch("urllib.request.urlopen", side_effect=err):
        assert run(_http().check_eligibility("e1")) is False


def test_create_agent_returns_id():
    with patch("urllib.request.urlopen", return_value=_Resp(b'{"agent_id": "AG1"}')):
        assert run(_http().create_agent("e1")) == "AG1"


def test_create_agent_passes_catalog_id():
    captured = {}

    def _fake_urlopen(req, timeout=8):
        captured["body"] = req.data
        return _Resp(b'{"agent_id": "AG2"}')

    with patch("urllib.request.urlopen", side_effect=_fake_urlopen):
        agent_id = run(_http().create_agent("e1", catalog_id="cat1"))
    assert agent_id == "AG2"
    assert b"cat1" in captured["body"]


def test_create_agent_missing_id_raises():
    with patch("urllib.request.urlopen", return_value=_Resp(b'{}')):
        with pytest.raises(MetaAgentProvisioningError) as exc:
            run(_http().create_agent("e1"))
    assert exc.value.step == "create_agent"


def test_create_agent_422_raises_with_step_named():
    err = urllib.error.HTTPError("url", 422, "unprocessable", {}, None)
    err.read = lambda: b"bad request"
    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(MetaAgentProvisioningError):
            run(_http().create_agent("e1"))


def test_create_agent_5xx_raises():
    err = urllib.error.HTTPError("url", 500, "server error", {}, None)
    err.read = lambda: b"oops"
    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(MetaAgentProvisioningError):
            run(_http().create_agent("e1"))


def test_create_agent_timeout_raises():
    with patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")):
        with pytest.raises(MetaAgentProvisioningError):
            run(_http().create_agent("e1"))


def test_register_connector_returns_id():
    with patch("urllib.request.urlopen",
               return_value=_Resp(b'{"id": "CONN1", "connection_status": "active"}')):
        cid = run(_http().register_connector("e1", "https://x.com", "API_KEY", {"token": "t"}))
    assert cid == "CONN1"


def test_register_connector_missing_id_raises():
    with patch("urllib.request.urlopen", return_value=_Resp(b'{}')):
        with pytest.raises(MetaAgentProvisioningError):
            run(_http().register_connector("e1", "https://x.com", "API_KEY", {}))


def test_register_connector_403_raises():
    err = urllib.error.HTTPError("url", 403, "forbidden", {}, None)
    err.read = lambda: b"no"
    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(MetaAgentProvisioningError):
            run(_http().register_connector("e1", "https://x.com", "API_KEY", {}))


def test_register_tool_returns_id():
    spec = ConnectorToolSpec(name="check_availability", description="d", path="/p")
    with patch("urllib.request.urlopen", return_value=_Resp(b'{"id": "TOOL1"}')):
        tid = run(_http().register_tool("e1", "CONN1", spec))
    assert tid == "TOOL1"


def test_register_tool_missing_id_names_tool_in_error():
    spec = ConnectorToolSpec(name="check_availability", description="d", path="/p")
    with patch("urllib.request.urlopen", return_value=_Resp(b'{}')):
        with pytest.raises(MetaAgentProvisioningError) as exc:
            run(_http().register_tool("e1", "CONN1", spec))
    assert "check_availability" in str(exc.value)


def test_upload_skill_returns_status():
    with patch("urllib.request.urlopen", return_value=_Resp(b'{"status": "active"}')):
        resp = run(_http().upload_skill("e1", "t", "d", "skill text"))
    assert resp["status"] == "active"


def test_upload_skill_pending_review_is_surfaced_not_hidden():
    with patch("urllib.request.urlopen", return_value=_Resp(b'{"status": "pending_review"}')):
        resp = run(_http().upload_skill("e1", "t", "d", "skill text"))
    assert resp["status"] == "pending_review"


def test_upload_skill_truncates_oversize_fields():
    captured = {}

    def _fake_urlopen(req, timeout=8):
        captured["body"] = req.data
        return _Resp(b'{"status": "active"}')

    with patch("urllib.request.urlopen", side_effect=_fake_urlopen):
        run(_http().upload_skill("e1", "t" * 100, "d" * 2000, "s" * 30000))
    import json as _json
    body = _json.loads(captured["body"])
    assert len(body["title"]) <= 64
    assert len(body["description"]) <= 1024
    assert len(body["skill"]) <= 20000


def test_enable_agent_true_on_rollout_enabled_field():
    with patch("urllib.request.urlopen",
              return_value=_Resp(b'{"rollout": {"enabled": true}}')):
        assert run(_http().enable_agent("e1", "a1")) is True


def test_enable_agent_calls_the_confirmed_settings_endpoint():
    """PUT /{entity_id}/agent_config/settings {rollout: {enabled: true}} -- confirmed against
    developers.facebook.com's own Agent Settings reference page, 2026-09-20."""
    captured = {}

    def _capture(req, timeout=None):
        captured["url"] = req.full_url
        captured["method"] = req.get_method()
        captured["body"] = json.loads(req.data)
        return _Resp(b'{"rollout": {"enabled": true}}')

    with patch("urllib.request.urlopen", side_effect=_capture):
        run(_http().enable_agent("e1", "a1"))
    assert captured["method"] == "PUT"
    assert captured["url"].endswith("e1/agent_config/settings")
    assert captured["body"] == {"rollout": {"enabled": True}}


def test_enable_agent_false_on_error():
    err = urllib.error.HTTPError("url", 500, "server error", {}, None)
    err.read = lambda: b"oops"
    with patch("urllib.request.urlopen", side_effect=err):
        assert run(_http().enable_agent("e1", "a1")) is False


def test_enable_agent_false_when_field_absent():
    with patch("urllib.request.urlopen", return_value=_Resp(b'{}')):
        assert run(_http().enable_agent("e1", "a1")) is False


# ── set_rollout: the on/off switch, same resource as enable_agent, either direction ────────────

def test_set_rollout_true_calls_the_same_confirmed_endpoint_as_enable_agent():
    captured = {}

    def _capture(req, timeout=None):
        captured["url"] = req.full_url
        captured["method"] = req.get_method()
        captured["body"] = json.loads(req.data)
        return _Resp(b'{"rollout": {"enabled": true}}')

    with patch("urllib.request.urlopen", side_effect=_capture):
        assert run(_http().set_rollout("e1", True)) is True
    assert captured["method"] == "PUT"
    assert captured["url"].endswith("e1/agent_config/settings")
    assert captured["body"] == {"rollout": {"enabled": True}}


def test_set_rollout_false_sends_false_and_reports_false_back():
    captured = {}

    def _capture(req, timeout=None):
        captured["body"] = json.loads(req.data)
        return _Resp(b'{"rollout": {"enabled": false}}')

    with patch("urllib.request.urlopen", side_effect=_capture):
        assert run(_http().set_rollout("e1", False)) is False
    assert captured["body"] == {"rollout": {"enabled": False}}


def test_set_rollout_false_on_transport_error():
    err = urllib.error.HTTPError("url", 500, "server error", {}, None)
    err.read = lambda: b"oops"
    with patch("urllib.request.urlopen", side_effect=err):
        assert run(_http().set_rollout("e1", False)) is False


def test_null_provisioner_set_rollout_is_false():
    assert run(NullMetaAgentProvisioner().set_rollout("e1", True)) is False


# ── set_agent_rollout: the tenant-level orchestration ai_toggle calls ──────────────────────────

def test_set_agent_rollout_reads_entity_id_back_from_secret_store_and_flips_it():
    secrets = _FakeSecrets({"t1|META_KNOWLEDGE_TOKEN": "tok",
                            f"t1|{SECRET_ENTITY_ID_NAME}": "pn_123"})
    seen = {}

    class _FakeProvisioner:
        async def set_rollout(self, entity_id, enabled):
            seen["entity_id"], seen["enabled"] = entity_id, enabled
            return enabled

    result = run(set_agent_rollout(
        tenant="t1", enabled=False, secret_store=secrets, settings=object(),
        provisioner_factory=lambda token: _FakeProvisioner()))
    assert isinstance(result, RolloutResult)
    assert result.ok is True
    assert result.enabled is False
    assert seen == {"entity_id": "pn_123", "enabled": False}


def test_set_agent_rollout_is_a_reported_noop_with_no_credential_on_file():
    secrets = _FakeSecrets({})
    result = run(set_agent_rollout(
        tenant="t_never_provisioned", enabled=True, secret_store=secrets, settings=object(),
        provisioner_factory=lambda token: pytest.fail("must never build a provisioner")))
    assert result.ok is False
    assert "no Meta credential" in result.error


def test_set_agent_rollout_never_raises_on_a_graph_error():
    secrets = _FakeSecrets({"t1|META_KNOWLEDGE_TOKEN": "tok",
                            f"t1|{SECRET_ENTITY_ID_NAME}": "pn_123"})

    class _FailingProvisioner:
        async def set_rollout(self, entity_id, enabled):
            raise MetaAgentProvisioningError("set_rollout", "boom")

    result = run(set_agent_rollout(
        tenant="t1", enabled=True, secret_store=secrets, settings=object(),
        provisioner_factory=lambda token: _FailingProvisioner()))
    assert result.ok is False
    assert "boom" in result.error


class _StepProvisioner:
    def __init__(self, *, eligible=True, agent_id="AG1", connector_id="CONN1",
                 tool_ids=None, skill_status="active", enabled=True, fail_at=None):
        self.eligible = eligible
        self.agent_id = agent_id
        self.connector_id = connector_id
        self.tool_ids = tool_ids if tool_ids is not None else ["T1"]
        self.skill_status = skill_status
        self.enabled = enabled
        self.fail_at = fail_at
        self.calls = []

    def _maybe_fail(self, step):
        if self.fail_at == step:
            raise MetaAgentProvisioningError(step, "boom")

    async def check_eligibility(self, entity_id):
        self.calls.append("check_eligibility")
        self._maybe_fail("check_eligibility")
        return self.eligible

    async def create_agent(self, entity_id, catalog_id=None):
        self.calls.append("create_agent")
        self._maybe_fail("create_agent")
        return self.agent_id

    async def register_connector(self, entity_id, base_url, auth_type, auth_config):
        self.calls.append("register_connector")
        self._maybe_fail("register_connector")
        return self.connector_id

    async def register_tool(self, entity_id, connector_id, spec):
        self.calls.append(f"register_tool:{spec.name}")
        self._maybe_fail(f"register_tool:{spec.name}")
        return self.tool_ids[0] if self.tool_ids else "T1"

    async def upload_skill(self, entity_id, title, description, skill_text):
        self.calls.append("upload_skill")
        self._maybe_fail("upload_skill")
        return {"status": self.skill_status}

    async def enable_agent(self, entity_id, agent_id):
        self.calls.append("enable_agent")
        self._maybe_fail("enable_agent")
        return self.enabled


class _S:
    META_AGENT_PROVISIONING_ENABLED = True
    KNOWLEDGE_EXPORT_ENABLED = False
    PUBLIC_BASE_URL = "https://kobo-cloud.com"
    CONNECTOR_API_TOKEN = "ctok"


def _run_provision(provisioner, secrets=None):
    secrets = secrets or _FakeSecrets({"t1|" + SECRET_TOKEN_NAME: "tok"})
    return run(provision_number(
        tenant="t1", entity_id="e1", secret_store=secrets, settings=_S(),
        provisioner_factory=lambda token: provisioner))


def test_provision_number_happy_path_runs_all_steps_in_order():
    p = _StepProvisioner()
    result = _run_provision(p)
    assert result.ok is True
    assert result.agent_id == "AG1"
    assert result.connector_id == "CONN1"
    assert result.enabled is True
    order = [c for c in p.calls if not c.startswith("register_tool")]
    assert order == ["check_eligibility", "create_agent", "register_connector",
                      "upload_skill", "enable_agent"]


def test_provision_number_stores_agent_and_connector_ids():
    p = _StepProvisioner()
    secrets = _FakeSecrets({"t1|" + SECRET_TOKEN_NAME: "tok"})
    _run_provision(p, secrets)
    written = {(t, n): v for t, n, v in secrets.writes}
    assert written[("t1", SECRET_AGENT_ID_NAME)] == "AG1"
    assert written[("t1", SECRET_CONNECTOR_ID_NAME)] == "CONN1"


def test_provision_number_pushes_real_owner_notes_via_shop_identity():
    """FOUND DURING REVIEW: this step used to read owner_notes from SecretStore under a key
    ("OWNER_NOTES") nothing ever wrote there — an always-empty read that made knowledge_pushed
    report normally while never sending real content. No existing test caught it because every
    other test runs with KNOWLEDGE_EXPORT_ENABLED=False (the Http exporter branch never ran at
    all). This test turns it on and asserts the REAL owner_notes (from shop_identity, the same
    source api/v1/operator.py::sync_business_info already uses) is what actually gets sent."""
    from app.core.knowledge_export import HttpKnowledgeExporter

    class _S2(_S):
        KNOWLEDGE_EXPORT_ENABLED = True

    class _Ctx:
        ai_notes = "نغسل السيارات من الداخل والخارج"

    class _FakeShopIdentity:
        def __init__(self):
            self.asked = []

        async def resolve(self, tenant):
            self.asked.append(tenant)
            return _Ctx()

    exported = {}

    class _FakeExporter(HttpKnowledgeExporter):
        def __init__(self):
            pass

        async def export(self, *, tenant, owner_notes):
            exported["tenant"] = tenant
            exported["owner_notes"] = owner_notes
            return True

    p = _StepProvisioner()
    secrets = _FakeSecrets({"t1|" + SECRET_TOKEN_NAME: "tok"})
    identity = _FakeShopIdentity()
    with patch("app.core.meta_agent_provisioning.build_knowledge_exporter",
              return_value=_FakeExporter()):
        result = asyncio.run(provision_number(
            tenant="t1", entity_id="e1", secret_store=secrets, settings=_S2(),
            provisioner_factory=lambda token: p, shop_identity=identity))
    assert result.ok is True
    assert result.knowledge_pushed is True
    assert identity.asked == ["t1"]
    assert exported == {"tenant": "t1", "owner_notes": "نغسل السيارات من الداخل والخارج"}


def test_provision_number_no_shop_identity_skips_knowledge_push_cleanly():
    """No shop_identity wired (e.g. the connect-time call site hasn't been added yet) must not
    crash — the step is simply skipped, never a fabricated success."""
    from app.core.knowledge_export import HttpKnowledgeExporter

    class _S2(_S):
        KNOWLEDGE_EXPORT_ENABLED = True

    with patch("app.core.meta_agent_provisioning.build_knowledge_exporter",
              return_value=HttpKnowledgeExporter(
                  secret_store=_FakeSecrets(), graph_base_url="https://graph.facebook.com",
                  graph_version="v26.0")):
        result = _run_provision(_StepProvisioner())
    assert result.ok is True
    assert result.knowledge_pushed is False


def test_provision_number_no_token_configured_stops_before_any_call():
    p = _StepProvisioner()
    secrets = _FakeSecrets({})
    result = run(provision_number(tenant="t1", entity_id="e1", secret_store=secrets,
                                   settings=_S(), provisioner_factory=lambda token: p))
    assert result.ok is False
    assert p.calls == []


def test_provision_number_ineligible_stops_and_reports_step():
    p = _StepProvisioner(eligible=False)
    result = _run_provision(p)
    assert result.ok is False
    assert result.failed_step == "check_eligibility"
    assert p.calls == ["check_eligibility"]


def test_provision_number_create_agent_failure_stops_chain():
    p = _StepProvisioner(fail_at="create_agent")
    result = _run_provision(p)
    assert result.ok is False
    assert result.failed_step == "create_agent"
    assert p.calls == ["check_eligibility", "create_agent"]


def test_provision_number_register_connector_failure_stops_chain():
    p = _StepProvisioner(fail_at="register_connector")
    result = _run_provision(p)
    assert result.ok is False
    assert result.failed_step == "register_connector"
    assert result.agent_id == "AG1"


def test_provision_number_register_tool_failure_names_the_tool():
    p = _StepProvisioner(fail_at="register_tool:check_availability")
    result = _run_provision(p)
    assert result.ok is False
    assert result.failed_step == "register_tool:check_availability"


def test_provision_number_upload_skill_failure_stops_chain():
    p = _StepProvisioner(fail_at="upload_skill")
    result = _run_provision(p)
    assert result.ok is False
    assert result.failed_step == "upload_skill"
    assert "enable_agent" not in p.calls


def test_provision_number_enable_agent_failure_still_reports_success_of_earlier_steps():
    p = _StepProvisioner(fail_at="enable_agent")
    result = _run_provision(p)
    assert result.ok is False
    assert result.failed_step == "enable_agent"
    assert result.agent_id == "AG1"
    assert result.connector_id == "CONN1"


def test_provision_number_skill_pending_review_does_not_fail_the_chain():
    p = _StepProvisioner(skill_status="pending_review")
    result = _run_provision(p)
    assert result.ok is True
    assert result.skill_status == "pending_review"


def test_provision_number_registers_one_tool_per_connector_route():
    p = _StepProvisioner()
    result = _run_provision(p)
    expected = {s.name for s in _iter_connector_tools()}
    called_tools = {c.split(":", 1)[1] for c in p.calls if c.startswith("register_tool:")}
    assert called_tools == expected
    assert len(result.tool_ids) == len(expected)


def test_provision_number_never_raises_on_unexpected_exception():
    class _Boom(_StepProvisioner):
        async def create_agent(self, entity_id, catalog_id=None):
            raise ValueError("unexpected")
    result = _run_provision(_Boom())
    assert result.ok is False
    assert result.failed_step == "create_agent"


def test_provisioning_result_defaults():
    r = ProvisioningResult(ok=False)
    assert r.tool_ids == []
    assert r.knowledge_pushed is False
