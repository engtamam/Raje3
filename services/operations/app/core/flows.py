"""Giving a shop its own copy of the rating Flow — the same shape as `core/library.py`'s publish.

WHY A FLOW AT ALL. The rating message is a WhatsApp TEMPLATE with a Flow button (ح-2's
`flow_button`, referencing a Flow by NAME); the Flow itself is the actual star-rating screen Meta
renders inside the chat. A template can be registered without ever having a live Flow behind its
button, and Meta then refuses to send it — so the Flow must exist on THIS SHOP'S OWN WABA before
its templates are registered, exactly as the template library must exist before it can be drained.

ONE MASTER, CLONED PER SHOP. A Flow is WABA-scoped and every shop connects its own WABA, so a
platform-wide Flow cannot be referenced by every shop — each needs its own copy. Authoring the
same screen sixty-six times is not the answer: the master is authored ONCE (see
`deploy/seed/bootstrap-rating-flow.py`, which mints it under the platform's own WABA and stores the
resulting id), and every shop's copy is a Meta-side CLONE of that master, requested here with
`clone_flow_id`. Clones share the FLOW NAME (`RATING_FLOW_NAME`) — never the id — because the
template's `flow_button` references a Flow by name, and that name must resolve on every shop's own
WABA to ITS OWN clone.

IDEMPOTENT BY NAME, on notification-service's side (`ensure_flow`) — a re-run (a shop reconnecting,
a retried background task) finds the shop's existing clone by name rather than making a second one.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

#: The stable name every shop's clone carries — templates reference the Flow by THIS, never by id,
#: because the id differs per shop while the name does not (see the module docstring above).
RATING_FLOW_NAME = "rating_flow"

#: Meta's fixed category set requires at least one; a rating screen is a survey and nothing else.
RATING_FLOW_CATEGORIES = ["SURVEY"]


class NullFlows:
    """No notification-service peer configured. Says so, provisions nothing.

    Mirrors `NullLibrary` on purpose — a deployment with no notification-service has no WABA to put
    a Flow on, and reporting a plausible "provisioned" here would hide a missing configuration
    behind a number that never happened.
    """

    driver = "null"

    def __init__(self) -> None:
        self.provisioned: list[str] = []

    async def provision(self, tenant: str, *, clone_flow_id: str) -> dict[str, Any]:
        self.provisioned.append(tenant)
        return {"ok": False, "reason": "flow provisioning is not configured"}


class HttpFlows:
    """notification-service's internal Flow-provisioning twin."""

    driver = "http"

    def __init__(self, *, notify_url: str, provision_path: str, token: str,
                 timeout: int = 8) -> None:
        base = notify_url.rstrip("/")
        self._provision = base + provision_path
        self._token = token
        self._timeout = timeout

    def _post(self, body: dict[str, Any]) -> tuple[int, Any]:
        data = json.dumps(body).encode()
        req = urllib.request.Request(
            self._provision, data=data, method="POST",
            headers={"X-Internal-Token": self._token, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                return resp.status, json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as exc:
            return exc.code, {"detail": exc.read().decode()[:200]}
        except (urllib.error.URLError, OSError, ValueError) as exc:
            return 503, {"detail": str(exc)[:120]}

    async def provision(self, tenant: str, *, clone_flow_id: str) -> dict[str, Any]:
        """Ensure THIS shop's WABA has a published clone of the master Flow, named `RATING_FLOW_NAME`.

        NO MASTER, NO CALL. `clone_flow_id` is resolved by the caller (connect.py) from the stored
        setting the bootstrap script writes once — see its module docstring. Calling Meta with an
        empty clone id would either be refused there or, worse, misread as "author from scratch",
        which is not what an empty configuration means.
        """
        if not clone_flow_id:
            return {"ok": False, "reason": "no master rating flow configured"}
        status, out = self._post({
            "tenant": tenant, "name": RATING_FLOW_NAME, "categories": RATING_FLOW_CATEGORIES,
            "clone_flow_id": clone_flow_id, "publish": True,
        })
        if status >= 400:
            return {"ok": False, "reason": str(out.get("detail", ""))[:160]}
        return {"ok": True, **(out if isinstance(out, dict) else {})}


def build_flows(settings: Any) -> Any:
    url = getattr(settings, "NOTIFICATION_SERVICE_URL", "") or ""
    path = getattr(settings, "WHATSAPP_FLOW_PROVISION_PATH", "") or ""
    if not url or not path:
        return NullFlows()
    return HttpFlows(notify_url=url, provision_path=path,
                     token=getattr(settings, "INTERNAL_SERVICE_TOKEN", "") or "",
                     timeout=int(getattr(settings, "PEER_TIMEOUT_SECONDS", 8) or 8))


async def provision_shop_flow(flows: Any, tenant: str, master_flow_id: str) -> dict[str, Any]:
    """The one call connect.py's background task makes — mirrors `library.publish`'s free-function
    shape so the two background tasks read the same way at the call site."""
    return await flows.provision(tenant, clone_flow_id=master_flow_id)
