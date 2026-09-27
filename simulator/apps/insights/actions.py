"""App-specific Actions for services/insights — real HTTP against a real, spawned instance."""
from __future__ import annotations

from dataclasses import dataclass

from simulator.common import httpclient
from simulator.common.action import ActionResult, Context
from simulator.shared.auth import auth_header

_READ_CAP = "insights.read"


@dataclass
class DashboardAction:
    """`GET /api/v1/insights/dashboard` — the whole panel in one read. A fresh tenant with no real
    visit-event history behind it (this simulator wires no real visit-event bus into insights)
    reads real, honest zeros/empties, not an error."""

    base_url: str
    tenant: str
    branch_id: str = ""
    name: str = "insights_dashboard"

    async def run(self, ctx: Context) -> ActionResult:
        headers = auth_header(tenant=self.tenant, caps=(_READ_CAP,))
        params = {"branch_id": self.branch_id} if self.branch_id else {}
        r = await httpclient.request("GET", f"{self.base_url}/api/v1/insights/dashboard",
                                     params=params, headers=headers, timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"insights_dashboard refused: {r.status_code} "
                                                  f"{r.text}")
        return ActionResult(ok=True, detail="dashboard read", data=r.json())


@dataclass
class BranchesAction:
    """`GET /api/v1/insights/branches` — the per-branch comparison, empty for a tenant with no
    branches/visit history yet."""

    base_url: str
    tenant: str
    name: str = "insights_branches"

    async def run(self, ctx: Context) -> ActionResult:
        headers = auth_header(tenant=self.tenant, caps=(_READ_CAP,))
        r = await httpclient.request("GET", f"{self.base_url}/api/v1/insights/branches",
                                     headers=headers, timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"insights_branches refused: {r.status_code} "
                                                  f"{r.text}")
        return ActionResult(ok=True, detail="branches read", data=r.json())


@dataclass
class RefreshAction:
    """`POST /api/v1/insights/refresh` — recompute this tenant's own snapshot on demand."""

    base_url: str
    tenant: str
    name: str = "insights_refresh"

    async def run(self, ctx: Context) -> ActionResult:
        headers = auth_header(tenant=self.tenant, caps=(_READ_CAP,))
        r = await httpclient.request("POST", f"{self.base_url}/api/v1/insights/refresh",
                                     headers=headers, timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"insights_refresh: unexpected HTTP "
                                                  f"{r.status_code} {r.text}")
        return ActionResult(ok=True, detail="refreshed", data=r.json())
