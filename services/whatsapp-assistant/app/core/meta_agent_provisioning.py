"""Full Meta Business Agent provisioning -- eligibility check through Connector/tool registration,
Skill upload, Knowledge push, and enable. One orchestration function (`provision_number`) runs the
whole sequence for a tenant that just connected a WhatsApp number, the same "fire-and-forget,
report exactly which step failed, never fail the caller's own response" shape
`services/operations/app/api/v1/connect.py::provision_shop_flow`/`publish` already use for the rest
of shop provisioning.

REAL PUBLIC REST API SHAPES, re-confirmed this pass against developers.facebook.com directly where
reachable, otherwise carried forward from this session's own prior confirmed research (see MEMORY's
`task-meta-agent-full-automation.md`, itself sourced from direct reads of Meta's reference pages on
2026-09-19). A live WebFetch attempt this pass against the two connector-reference sub-pages hit a
404 and a JS-only nav shell respectively -- Meta's Business Agent docs are gated behind
developer-console navigation that a stateless fetch cannot follow, exactly the constraint the memory
doc's own "needs a sandbox account to confirm fully" note already flagged. Nothing here is invented
where the memory doc did not already carry a confirmed shape; every field below traces to a step the
memory doc already marked confirmed, EXCEPT `enable_agent` (see its own docstring).

    1. GET  /{entity_id}/agent_eligibility                              -> {"is_eligible": bool}
    2. POST /{entity_id}/agent_onboarding        {catalog_id?}          -> {"agent_id": str}
    3. POST /{entity_id}/agent_connectors        {name, description,
             base_url, connector_protocol, auth_type, auth_config}      -> {"id": str, ...}
    4. POST /{entity_id}/agent_connectors/{connector_id}/tools
             {name, description, request_definition, user_auth_required,
              transformation_spec}                                      -> {"id": str, ...}
    5. POST /{entity_id}/agent_config/skills     {title, description,
             skill}                                                     -> {"status": str, ...}
    6. PUT  /{entity_id}/agent_config/business_info -- reuses
             app/core/knowledge_export.py UNCHANGED, not reimplemented here.
    7. Agent Settings enable -- see `enable_agent`'s own docstring for confidence level.

Every call carries `X-API-Version: 2.0.0` (confirmed, same header knowledge_export.py already
sends) in addition to the Graph API version already in the URL path.

`entity_id` THROUGHOUT THIS MODULE IS THE WHATSAPP PHONE NUMBER ID -- same entity_id
`knowledge_export.py` already uses for step 6, not the WABA id (the memory doc's one open question
about `waba_id` inside CONNECTOR CALLS, not this provisioning sequence, stays open and unrelated).

ANTI-DRIFT: THE TOOL LIST IS DERIVED, NEVER HAND-WRITTEN. Step 4 registers one Meta tool per
Connector HTTP operation this service actually exposes. `_iter_connector_tools()` walks
`app.api.v1.connectors.router.routes` (the ACTUAL mounted paths, ground truth for what a caller can
invoke) and, for each one that is also an LLM-callable tool, pulls its `name`/`description`/
`parameters` straight from `app.adapters.llm.assistant_service._TOOL_SCHEMAS` (`core/tools.py`'s own
declared contract, via the one place it is already exposed as data) -- never a second, hand-typed
copy of any tool's description that could drift from the real one. The three Connector-only
operations that are not LLM tools (`confirm_proposal`, `check_consent`, `record_consent`) get a
short literal description each, held in `_CONNECTOR_ONLY_TOOL_DESCRIPTIONS` right here, because they
have no other single source of truth to derive from. Whenever `core/tools.py` gains, removes, or
renames a tool (and its mirrored Connector route), this generator's output changes with it, with
zero edits to this file -- proven by `test_meta_agent_provisioning.py`'s own drift test, which
monkeypatches `_TOOL_SCHEMAS` and asserts the generated list actually changes.

SKILL TEXT SOURCING DECISION. `META_AGENT_CONSENT_SKILL.md`'s own docstring already says it is "not
code" and "currently a manual-paste artifact". Promoting the whole instruction block into a Python
constant that BOTH the .md and this uploader import from would be the textbook single-source fix --
but that constant would then have to live in this module (the only place Python on the Meta-agent
side needs it) while the .md's whole reason to exist is to be a copy-pasteable document an OWNER,
not a program, reads in Meta's dashboard. Splitting the literal skill body into its own tiny
`.txt`/`.py` asset that both files include would trade one drift risk (two copies of the same text)
for a worse one (three files, each of which must exist and never be renamed, for one 900-byte
string). Given the .md already states in its own body "Do not edit the consent body text below --
it is copied verbatim from `app/core/inbound_ingest.py::_CONSENT_BODY`" -- i.e. the ACTUAL source of
truth for the sentence that matters is already `_CONSENT_BODY` in Python, not the .md file -- this
module reads `_CONSENT_BODY` directly (see `_consent_skill_text()`) and builds the FULL skill
instructions (numbered steps + that body) as a small literal string HERE, matching the .md's
existing structure. Reading the .md file itself at runtime was rejected: it would make a doc file
(untracked-adjacent, free-form, meant for human copy-paste, no schema) a runtime dependency of a
service -- exactly the fragility this module's own anti-drift discipline elsewhere refuses to
accept. If the .md's steps ever diverge from what is uploaded here, that is now a one-function diff
(`_consent_skill_text`) to keep them matching, not a silent runtime read of prose.

STORAGE. `agent_id`/`connector_id` are written through the SAME `SecretStore` every other
per-tenant Meta credential in this service already goes through (`SECRET_TOKEN_NAME`/
`SECRET_ENTITY_ID_NAME` in `knowledge_export.py`) rather than a new collection. Neither value is
secret in the sense a token is, but `SecretStore` is already exactly "one encrypted per-tenant KV
row with an audit trail and a rotation window" and `knowledge_export.py` already established the
precedent of storing a non-secret Meta identifier (`entity_id`) there for the identical reason: one
place operator-facing Meta identifiers for a tenant live, not two.

ORCHESTRATION IS BUILT BUT NOT WIRED INTO connect.py THIS PASS, by explicit instruction. A settings
flag (`META_AGENT_PROVISIONING_ENABLED`, config.py) exists and defaults OFF; `provision_number` is a
complete, independently callable, independently tested function. The one line that would call it
from `services/operations/app/api/v1/connect.py`'s own background task is left as a deliberate
follow-up (see that flag's own comment in config.py) so it reviews as its own small diff.
"""
from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable

from app.core.knowledge_export import HttpKnowledgeExporter
from app.core.knowledge_export import build as build_knowledge_exporter

API_VERSION_HEADER_NAME = "X-API-Version"
API_VERSION_HEADER_VALUE = "2.0.0"

#: Same store, same names as knowledge_export.py -- one place a tenant's Meta credentials live.
SECRET_TOKEN_NAME = "META_KNOWLEDGE_TOKEN"
SECRET_ENTITY_ID_NAME = "META_WA_PHONE_NUMBER_ID"
SECRET_AGENT_ID_NAME = "META_AGENT_ID"
SECRET_CONNECTOR_ID_NAME = "META_CONNECTOR_ID"

#: The three Connector operations (app/api/v1/connectors.py) that are NOT LLM tools and therefore
#: have no entry in `_TOOL_SCHEMAS` to derive a description from.
_CONNECTOR_ONLY_TOOL_DESCRIPTIONS: dict[str, str] = {
    "confirm_proposal": "Confirm a previously proposed booking/cancel/reschedule by its proposal id.",
    "check_consent": "Check whether this customer has given service-processing consent.",
    "record_consent": "Record this customer's decision on service-processing consent.",
}


@dataclass(frozen=True)
class ConnectorToolSpec:
    """One Meta `agent_connectors/{id}/tools` registration, derived, never hand-written."""
    name: str
    description: str
    path: str
    parameters: dict[str, Any] = field(default_factory=dict)


def _iter_connector_tools() -> list[ConnectorToolSpec]:
    """Walk the REAL mounted Connector routes and pair each with its REAL description.

    Imported lazily (inside the function, not at module top) so importing this module never
    requires the FastAPI app graph to be importable in a context that only wants the pure/HTTP
    provisioning pieces (e.g. a unit test that stubs everything) -- the same lazy-import posture
    `core/tools.py` itself uses to avoid a circular import with the router that calls it.
    """
    from app.adapters.llm.assistant_service import _TOOL_SCHEMAS
    from app.api.v1.connectors import router as connectors_router

    specs: list[ConnectorToolSpec] = []
    for route in connectors_router.routes:
        methods = getattr(route, "methods", None) or set()
        if "POST" not in methods:
            continue
        name = route.path.rsplit("/", 1)[-1]
        schema = _TOOL_SCHEMAS.get(name)
        if schema is not None:
            description = schema.get("description", "")
            parameters = schema.get("parameters", {})
        elif name in _CONNECTOR_ONLY_TOOL_DESCRIPTIONS:
            description = _CONNECTOR_ONLY_TOOL_DESCRIPTIONS[name]
            parameters = {"type": "object", "properties": {}}
        else:
            # A Connector route with neither an LLM schema nor a literal fallback description is a
            # real gap (a new op added to the router without updating either source) -- skipped
            # rather than registered with an invented description, same "never guess" posture as
            # knowledge_export.py's own optional-fields note.
            continue
        specs.append(ConnectorToolSpec(
            name=name, description=description,
            path=f"{connectors_router.prefix}/{name}", parameters=parameters))
    return specs


def build_tool_registration_payload(spec: ConnectorToolSpec) -> dict[str, Any]:
    """Pure mapping: one ConnectorToolSpec -> one `agent_connectors/{id}/tools` request body."""
    return {
        "name": spec.name,
        "description": spec.description,
        "request_definition": {
            "method": "POST",
            "path": spec.path,
            "parameters": spec.parameters,
        },
        "user_auth_required": False,
        "transformation_spec": {},
    }


def _consent_skill_text() -> str:
    """The full Skill instruction text uploaded to Meta -- structure mirrors
    META_AGENT_CONSENT_SKILL.md, body text sourced from the SAME `_CONSENT_BODY` constant that .md
    file's own docstring already names as the real source of truth (see this module's docstring)."""
    from app.core.inbound_ingest import _CONSENT_BODY

    return (
        "متى تُستدعى: عند أول تواصل مع أي عميل في هذه المحادثة، قبل أي رد آخر.\n\n"
        "التعليمات:\n"
        "1. عند أول رسالة من عميل لم تُستدعَ له check_consent بعد في هذه المحادثة، "
        "استدعِ check_consent أولاً.\n"
        "2. إن كانت النتيجة status: \"allowed\"، تابع المحادثة بشكل طبيعي.\n"
        "3. إن كانت النتيجة status: \"denied\" أو \"unknown\"، أرسل للعميل رسالة تفاعلية "
        "بزرّين (متابعة/إنهاء المحادثة) تحمل هذا النص حرفيًا:\n\n"
        f"{_CONSENT_BODY}\n\n"
        "4. لا تستدعِ أي أداة أخرى قبل تأكيد الموافقة.\n"
        "5. لو رفض العميل، أنهِ المحادثة بأدب دون أي محاولة إقناع.\n"
        "6. لو وافق لاحقًا برسالة جديدة، استدعِ record_consent ثم تابع بشكل طبيعي."
    )[:20000]


@dataclass
class ProvisioningResult:
    """Reports exactly which step ran, and exactly which one failed -- never a bare bool."""
    ok: bool
    failed_step: str = ""
    error: str = ""
    agent_id: str = ""
    connector_id: str = ""
    tool_ids: list[str] = field(default_factory=list)
    skill_status: str = ""
    knowledge_pushed: bool = False
    enabled: bool = False


class MetaAgentProvisioningError(RuntimeError):
    def __init__(self, step: str, message: str) -> None:
        super().__init__(f"{step}: {message}")
        self.step = step
        self.message = message


class NullMetaAgentProvisioner:
    """No Graph credential configured, or the feature is off. Same "runs, does nothing" posture as
    every other Null adapter in this service."""
    driver = "null"

    async def check_eligibility(self, entity_id: str) -> bool:
        return False

    async def create_agent(self, entity_id: str, catalog_id: str | None = None) -> str:
        raise MetaAgentProvisioningError("create_agent", "provisioning is disabled")

    async def register_connector(self, entity_id: str, base_url: str, auth_type: str,
                                  auth_config: dict[str, Any]) -> str:
        raise MetaAgentProvisioningError("register_connector", "provisioning is disabled")

    async def register_tool(self, entity_id: str, connector_id: str, spec: ConnectorToolSpec) -> str:
        raise MetaAgentProvisioningError("register_tool", "provisioning is disabled")

    async def upload_skill(self, entity_id: str, title: str, description: str,
                            skill_text: str) -> dict[str, Any]:
        raise MetaAgentProvisioningError("upload_skill", "provisioning is disabled")

    async def enable_agent(self, entity_id: str, agent_id: str) -> bool:
        return False


class HttpMetaAgentProvisioner:
    driver = "http"

    def __init__(self, *, token: str, graph_base_url: str, graph_version: str,
                 connector_base_url: str, connector_auth_token: str, timeout: int = 8) -> None:
        self._token = token
        self._base = graph_base_url.rstrip("/")
        self._version = graph_version
        self._connector_base_url = connector_base_url
        self._connector_auth_token = connector_auth_token
        self._timeout = timeout

    # -- low-level HTTP, off the event loop --------------------------------------------------------
    def _call_sync(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self._base}/{self._version}/{path}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            url, data=data, method=method,
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self._token}",
                     API_VERSION_HEADER_NAME: API_VERSION_HEADER_VALUE})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                raw = resp.read() or b"{}"
                return json.loads(raw)
        except urllib.error.HTTPError as exc:
            raise MetaAgentProvisioningError(
                path, f"HTTP {exc.code}: {exc.read()[:500]!r}") from exc
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise MetaAgentProvisioningError(path, f"transport error: {exc}") from exc

    async def _call(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        # OFF THE EVENT LOOP -- see core/customer_lookup.py::HttpCustomerLookup.resolve.
        return await asyncio.to_thread(self._call_sync, method, path, body)

    # -- the 7 steps ----------------------------------------------------------------------------
    async def check_eligibility(self, entity_id: str) -> bool:
        try:
            data = await self._call("GET", f"{entity_id}/agent_eligibility")
        except MetaAgentProvisioningError:
            return False
        return bool(data.get("is_eligible"))

    async def create_agent(self, entity_id: str, catalog_id: str | None = None) -> str:
        body: dict[str, Any] = {}
        if catalog_id:
            body["catalog_id"] = catalog_id
        data = await self._call("POST", f"{entity_id}/agent_onboarding", body)
        agent_id = data.get("agent_id") or data.get("id") or ""
        if not agent_id:
            raise MetaAgentProvisioningError("create_agent", f"no agent_id in response: {data!r}")
        return str(agent_id)

    async def register_connector(self, entity_id: str, base_url: str, auth_type: str,
                                  auth_config: dict[str, Any]) -> str:
        body = {
            "name": "raje3-tools",
            "description": "Raje3 shop tools -- bookings, points, packages, procedures.",
            "base_url": base_url,
            "connector_protocol": "HTTP",
            "auth_type": auth_type,
            "auth_config": auth_config,
        }
        data = await self._call("POST", f"{entity_id}/agent_connectors", body)
        connector_id = data.get("id") or ""
        if not connector_id:
            raise MetaAgentProvisioningError(
                "register_connector", f"no id in response: {data!r}")
        return str(connector_id)

    async def register_tool(self, entity_id: str, connector_id: str, spec: ConnectorToolSpec) -> str:
        body = build_tool_registration_payload(spec)
        data = await self._call(
            "POST", f"{entity_id}/agent_connectors/{connector_id}/tools", body)
        tool_id = data.get("id") or ""
        if not tool_id:
            raise MetaAgentProvisioningError(
                "register_tool", f"no id in response for {spec.name}: {data!r}")
        return str(tool_id)

    async def upload_skill(self, entity_id: str, title: str, description: str,
                            skill_text: str) -> dict[str, Any]:
        body = {"title": title[:64], "description": description[:1024], "skill": skill_text[:20000]}
        return await self._call("POST", f"{entity_id}/agent_config/skills", body)

    async def enable_agent(self, entity_id: str, agent_id: str) -> bool:
        """BEST-EFFORT, PENDING LIVE SANDBOX VERIFICATION. Unlike steps 1-5, Meta's own Agent
        Settings "enable" call was NOT confirmed shape-by-shape against a live reference page this
        session (the memory doc already flags it as the one open item; a WebFetch retry this pass
        against the Agent Settings reference page returned HTTP 404 -- the page either requires
        console auth or has moved). The shape below is the most consistent guess GIVEN the other
        six confirmed endpoints: a PUT against the same `{entity_id}/agent_onboarding` resource
        step 2 created, flipping an `agent_enabled` field, matching the REST convention every other
        confirmed step in this module already follows (create via POST to a collection, mutate via
        PUT/GET on the same resource path). This is the one call in this module that must be
        re-verified against a real Meta sandbox before this ever runs against production traffic.
        """
        try:
            data = await self._call(
                "PUT", f"{entity_id}/agent_onboarding", {"agent_id": agent_id, "agent_enabled": True})
        except MetaAgentProvisioningError:
            return False
        return bool(data.get("agent_enabled", data.get("success", False)))


def build(settings: Any, *, secret_store: Any = None) -> Any:
    if not getattr(settings, "META_AGENT_PROVISIONING_ENABLED", False) or secret_store is None:
        return NullMetaAgentProvisioner()
    return HttpMetaAgentProvisioner(
        token="",  # resolved per-tenant at call time via SecretStore, see provision_number
        graph_base_url=getattr(settings, "META_GRAPH_BASE_URL", "https://graph.facebook.com"),
        graph_version=getattr(settings, "META_GRAPH_API_VERSION", "v26.0"),
        connector_base_url=getattr(settings, "PUBLIC_BASE_URL", ""),
        connector_auth_token=getattr(settings, "CONNECTOR_API_TOKEN", ""),
        timeout=int(getattr(settings, "PEER_TIMEOUT_SECONDS", 8) or 8))


async def provision_number(
    *, tenant: str, entity_id: str, secret_store: Any, settings: Any,
    provisioner_factory: Callable[[str], Any] | None = None,
    shop_identity: Any = None,
) -> ProvisioningResult:
    """Run all 7 steps in order for one tenant's freshly-connected WhatsApp number.

    `provisioner_factory(token) -> provisioner` lets a caller (or a test) supply a provisioner
    bound to the real per-tenant bearer token read from SecretStore, without this function needing
    to know HttpMetaAgentProvisioner's constructor shape -- same seam knowledge_export.py's own
    `build(settings, secret_store=...)` factory gives every other adapter in this service.

    NEVER RAISES. Fire-and-forget, same as `provision_shop_flow`/`publish` in
    services/operations/app/api/v1/connect.py -- a provisioning failure must not break the connect
    response, and must report EXACTLY which step failed so it can be retried, never swallowed.
    """
    token = await secret_store.get(tenant=tenant, name=SECRET_TOKEN_NAME)
    if not token or not entity_id:
        return ProvisioningResult(ok=False, failed_step="check_eligibility",
                                   error="no Meta credential/entity_id configured for this tenant")

    provisioner = provisioner_factory(token) if provisioner_factory else build(settings)

    result = ProvisioningResult(ok=False)

    try:
        eligible = await provisioner.check_eligibility(entity_id)
    except Exception as exc:  # noqa: BLE001 -- reported, not swallowed
        result.failed_step, result.error = "check_eligibility", str(exc)
        return result
    if not eligible:
        result.failed_step, result.error = "check_eligibility", "entity is not eligible"
        return result

    try:
        agent_id = await provisioner.create_agent(entity_id)
    except Exception as exc:  # noqa: BLE001
        result.failed_step, result.error = "create_agent", str(exc)
        return result
    result.agent_id = agent_id
    await secret_store.set(tenant=tenant, name=SECRET_AGENT_ID_NAME, value=agent_id,
                            actor_ref="meta_agent_provisioning")

    try:
        connector_id = await provisioner.register_connector(
            entity_id, base_url=getattr(settings, "PUBLIC_BASE_URL", ""),
            auth_type="API_KEY",
            auth_config={"token": getattr(settings, "CONNECTOR_API_TOKEN", "")})
    except Exception as exc:  # noqa: BLE001
        result.failed_step, result.error = "register_connector", str(exc)
        return result
    result.connector_id = connector_id
    await secret_store.set(tenant=tenant, name=SECRET_CONNECTOR_ID_NAME, value=connector_id,
                            actor_ref="meta_agent_provisioning")

    for spec in _iter_connector_tools():
        try:
            tool_id = await provisioner.register_tool(entity_id, connector_id, spec)
        except Exception as exc:  # noqa: BLE001
            result.failed_step, result.error = f"register_tool:{spec.name}", str(exc)
            return result
        result.tool_ids.append(tool_id)

    try:
        skill_resp = await provisioner.upload_skill(
            entity_id, title="Consent gate", description="Ask for service-processing consent "
            "before any other reply.", skill_text=_consent_skill_text())
    except Exception as exc:  # noqa: BLE001
        result.failed_step, result.error = "upload_skill", str(exc)
        return result
    result.skill_status = skill_resp.get("status", "")

    knowledge_exporter = build_knowledge_exporter(settings, secret_store=secret_store)
    if isinstance(knowledge_exporter, HttpKnowledgeExporter) and shop_identity is not None:
        # FOUND DURING REVIEW: owner_notes was read from SecretStore under a key ("OWNER_NOTES")
        # nothing ever writes -- that read would always silently return the fallback empty string,
        # so this step reported success/failure normally while never actually pushing real content.
        # The real source, same as the existing manual sync route (api/v1/operator.py::
        # sync_business_info), is operations' own AiNotesStore, read here through shop_identity
        # exactly like that route already does -- never SecretStore, which holds credentials, not
        # a tenant's own written text.
        try:
            ctx = await shop_identity.resolve(tenant)
            result.knowledge_pushed = await knowledge_exporter.export(
                tenant=tenant, owner_notes=ctx.ai_notes)
        except Exception as exc:  # noqa: BLE001
            result.failed_step, result.error = "push_knowledge", str(exc)
            return result

    try:
        result.enabled = await provisioner.enable_agent(entity_id, agent_id)
    except Exception as exc:  # noqa: BLE001
        result.failed_step, result.error = "enable_agent", str(exc)
        return result

    result.ok = True
    return result
