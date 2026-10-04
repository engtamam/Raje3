"""App-specific Actions for services/whatsapp-assistant — real HTTP against a real, spawned
instance. Two doors: the ordinary tenant-token surface (`/api/v1/assistant/*`) and the connector
door (`/api/v1/connectors/*`) — the "tools" Meta's own agent calls, gated by a SEPARATE
`CONNECTOR_API_TOKEN` secret (never `INTERNAL_SERVICE_TOKEN` — see `service.py`'s own docstring).
"""
from __future__ import annotations

from dataclasses import dataclass

from simulator.common import httpclient
from simulator.common.action import ActionResult, Context
from simulator.shared.auth import auth_header

from .service import CONNECTOR_API_TOKEN


@dataclass
class AssistantFeaturesAction:
    """`GET /api/v1/assistant/features` — `require_user` alone (any signed-in caller, no specific
    capability): the same static catalog every caller reads, tenant or not."""

    base_url: str
    tenant: str
    name: str = "assistant_features"

    async def run(self, ctx: Context) -> ActionResult:
        headers = auth_header(tenant=self.tenant, caps=())
        r = await httpclient.request("GET", f"{self.base_url}/api/v1/assistant/features",
                                     headers=headers, timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"assistant_features refused: {r.status_code} "
                                                  f"{r.text}")
        return ActionResult(ok=True, detail="features read", data=r.json())


@dataclass
class CheckConsentAction:
    """`POST /api/v1/connectors/check_consent` — one of the real "tools" Meta's own agent calls;
    never raises (a consent-gate error still answers `{"ok": True, "status": "unknown"}`, so the
    agent gets an honest answer it has an instruction for, never a crash it does not).

    ALWAYS ANSWERS "unknown" IN THIS SIMULATOR: `CONSENT_GATE_DRIVER` defaults to `"null"` outside
    production, and consent is genuinely tracked by a real `COMPLIANCE_SERVICE_URL` peer no fleet
    here spawns yet — a real, documented environmental limit, the same recurring shape
    `mutual_benefit_actions.py`/`campaigns/actions.py` already name for their own different
    peers."""

    base_url: str
    tenant: str
    from_number: str
    conversation_id: str = "conv-simulated"
    name: str = "check_consent"

    async def run(self, ctx: Context) -> ActionResult:
        body = {"tenant": self.tenant, "from_number": self.from_number,
               "conversation_id": self.conversation_id}
        r = await httpclient.request(
            "POST", f"{self.base_url}/api/v1/connectors/check_consent", json=body,
            headers={"Authorization": f"Bearer {CONNECTOR_API_TOKEN}"}, timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"check_consent: unexpected HTTP "
                                                  f"{r.status_code} {r.text}")
        return ActionResult(ok=True, detail="consent checked", data=r.json())


@dataclass
class RecordConsentAction:
    """`POST /api/v1/connectors/record_consent`."""

    base_url: str
    tenant: str
    from_number: str
    granted: bool
    conversation_id: str = "conv-simulated"
    name: str = "record_consent"

    async def run(self, ctx: Context) -> ActionResult:
        body = {"tenant": self.tenant, "from_number": self.from_number, "granted": self.granted,
               "conversation_id": self.conversation_id}
        r = await httpclient.request(
            "POST", f"{self.base_url}/api/v1/connectors/record_consent", json=body,
            headers={"Authorization": f"Bearer {CONNECTOR_API_TOKEN}"}, timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"record_consent: unexpected HTTP "
                                                  f"{r.status_code} {r.text}")
        return ActionResult(ok=True, detail="consent recorded", data=r.json())
