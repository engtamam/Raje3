"""Resolves the ONE assistant-service AI connection each tenant's bot runs on, creating or
updating it lazily — the same "provision on first need, then keep in step" pattern
core/flows.py::provision_shop_flow already uses for a shop's WhatsApp Flow clone.

WHY ONE CONNECTION PER TENANT, NOT ONE FOR THE WHOLE SERVICE. assistant-service's own AiConnection
carries a FIXED `system_prompt` at the row level — there is no per-invoke override. Our own prompt
is per-tenant and can change any time an owner edits their shop name or their AI notes
(app/core/shop_identity.py, AiNotesCard). A single shared connection would mean every tenant's turn
overwriting every other tenant's prompt in a race, or all tenants sharing one owner's notes. So each
tenant gets its own row, named identically ("whatsapp-assistant") and distinguished by tenant alone —
assistant-service's own `list_connections(tenant)` already scopes by tenant, so the name need not be
unique across tenants, only within one.

LAZY, NOT ONE-SHOT AT CONNECT TIME. Unlike a Flow (authored once, rarely touched again), the prompt
changes on an ordinary product action (saving a note) that has nothing to do with WhatsApp
connection state — provisioning it at connect time would leave it correct only until the first edit.
So this resolves fresh on ~every call: `respond()` in app/adapters/llm/assistant_service.py calls
it every turn, and the "is anything actually different" check below is what keeps that cheap (one
list + maybe one create/update HTTP call, no local cache to go stale).

TOOLS ARE DECLARED AT CREATE/UPDATE TIME, NOT PER INVOKE (see app/adapters/llm/assistant_service.py's
own module docstring for the accepted trade-off this implies — core/tools.py's own
`allowed_tools`/`validate_and_render` re-check is what actually enforces per-turn narrowing; a model
being ABLE to attempt a tool it should not currently see is not a new privilege, since the same
server-side check already exists for exactly this reason).
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

_CONNECTION_NAME = "whatsapp-assistant"


class AssistantConnectionsUnavailable(Exception):
    """Transient — assistant-service could not be reached or refused the request. The caller
    (app/adapters/llm/assistant_service.py) surfaces this the same way GeminiLlm surfaces a
    network failure: the debounce tick retries, no message is dropped."""


class HttpAssistantConnections:
    """assistant-service's own /internal/assistant/connections routes, under the internal token."""

    def __init__(self, *, url: str, connections_path: str, token: str, timeout: int = 8) -> None:
        self._base = url.rstrip("/")
        self._path = connections_path
        self._token = token
        self._timeout = timeout

    def _call(self, method: str, path: str, *, query: dict[str, str] | None = None,
              body: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self._base}{path}"
        if query:
            url += "?" + urllib.parse.urlencode(query)
        req = urllib.request.Request(
            url, data=json.dumps(body).encode() if body is not None else None, method=method,
            headers={"Content-Type": "application/json", "X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                return json.loads(resp.read() or b"{}")
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError) as exc:
            raise AssistantConnectionsUnavailable(str(exc)) from exc

    def list(self, tenant: str) -> list[dict[str, Any]]:
        return self._call("GET", self._path, query={"tenant": tenant}).get("connections") or []

    def create(self, **body: Any) -> dict[str, Any]:
        return self._call("POST", self._path, body=body)

    def update(self, cid: str, **body: Any) -> dict[str, Any]:
        return self._call("PUT", f"{self._path}/{cid}", body=body)

    def invoke(self, cid: str, *, tenant: str, messages: list[dict[str, str]]) -> dict[str, Any]:
        return self._call("POST", f"{self._path}/{cid}/invoke",
                          body={"tenant": tenant, "messages": messages})


def ensure_connection(client: HttpAssistantConnections, *, tenant: str, url: str, model: str,
                      auth: str, credential: str, system_prompt: str, tools: list[dict[str, Any]],
                      temperature: float = 0.2) -> str:
    """The tenant's connection id, creating or updating it as needed. Never re-sends `credential`
    on an update — assistant-service's own PUT route does not accept one (see internal.py's
    ConnUpdateIn: the credential is write-only at create time, rotated by recreating the
    connection), and there is nothing to rotate here since every tenant shares one platform-wide
    GCP credential.
    """
    existing = next((c for c in client.list(tenant) if c.get("name") == _CONNECTION_NAME), None)
    if existing is None:
        conn = client.create(tenant=tenant, name=_CONNECTION_NAME, url=url, model=model, auth=auth,
                             system_prompt=system_prompt, temperature=temperature, tools=tools,
                             credential=credential)
        return str(conn["id"])

    cid = str(existing["id"])
    # ONLY WHAT ACTUALLY CHANGED — an update call every single turn regardless would be a wasted
    # round trip on every message this service ever handles, for no benefit: the prompt/tools are
    # already correct the overwhelming majority of the time.
    changes: dict[str, Any] = {}
    if existing.get("system_prompt") != system_prompt:
        changes["system_prompt"] = system_prompt
    if existing.get("tools") != tools:
        changes["tools"] = tools
    if changes:
        client.update(cid, tenant=tenant, **changes)
    return cid
