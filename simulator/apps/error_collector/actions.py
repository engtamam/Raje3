"""App-specific Actions for services/error-collector — real HTTP against a real, spawned instance.
Two doors, two different privileges (that route file's own module docstring): reporting needs only
a valid session (any authenticated caller), reading the cross-tenant stream needs a real platform
capability, never a tenant one — the stream "spans every tenant on the platform by construction".
"""
from __future__ import annotations

from dataclasses import dataclass

from simulator.common import httpclient
from simulator.common.action import ActionResult, Context
from simulator.shared.auth import auth_header

_OBSERVE_CAP = "platform.observability"


@dataclass
class ReportSignalAction:
    """`POST /api/v1/signals/report` — any authenticated caller, no capability (the module's own
    reasoning: gating this behind a capability would mean the only errors ever heard about are
    the ones that happen to operators)."""

    base_url: str
    tenant: str
    source: str = "sim"
    severity: str = "error"
    service: str = "sim-service"
    message: str = "something broke"
    name: str = "report_signal"

    async def run(self, ctx: Context) -> ActionResult:
        headers = auth_header(tenant=self.tenant, caps=())
        body = {"source": self.source, "severity": self.severity, "service": self.service,
               "message": self.message}
        r = await httpclient.request("POST", f"{self.base_url}/api/v1/signals/report", json=body,
                                     headers=headers, timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"report_signal: unexpected HTTP "
                                                  f"{r.status_code} {r.text}")
        return ActionResult(ok=True, detail="signal reported", data=r.json())


@dataclass
class ListSignalsAction:
    """`GET /api/v1/signals` — `platform.observability`, a PLATFORM capability, never a tenant
    one: a shop owner reading this would be a cross-tenant read wearing a support screen's
    clothes (that route's own module docstring)."""

    base_url: str
    tenant_filter: str = ""
    service_filter: str = ""
    name: str = "list_signals"

    async def run(self, ctx: Context) -> ActionResult:
        # PLATFORM-TIER, deliberately no tenant on the token itself — the stream crosses every
        # tenant by construction.
        headers = auth_header(tenant="", caps=(_OBSERVE_CAP,))
        params: dict[str, str] = {}
        if self.tenant_filter:
            params["tenant"] = self.tenant_filter
        if self.service_filter:
            params["service"] = self.service_filter
        r = await httpclient.request("GET", f"{self.base_url}/api/v1/signals", params=params,
                                     headers=headers, timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"list_signals refused: {r.status_code} "
                                                  f"{r.text}")
        return ActionResult(ok=True, detail="signals read", data=r.json())
