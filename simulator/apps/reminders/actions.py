"""App-specific Actions for services/reminders — real HTTP against a real, spawned instance. See
`service.py`'s own module docstring for the scope this session wires in: the customer's own,
unauthenticated prefs page and the owner's own schedule/rules reads and writes — no real visit
event bus and no operations peer needed for any of these.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from simulator.common import httpclient
from simulator.common.action import ActionResult, Context
from simulator.shared.auth import auth_header

_READ_CAP = "reminders.read"
_MANAGE_CAP = "reminders.manage"


@dataclass
class GetPrefsAction:
    """`GET /api/v1/prefs/{tenant}.{subject_ref}` — public, no token: the reference itself IS the
    credential (an opaque HMAC, this route's own module docstring). Never 404s — an unknown
    reference reads the same as a known one, on purpose, to avoid an existence oracle."""

    base_url: str
    tenant: str
    subject_ref: str
    name: str = "get_prefs"

    async def run(self, ctx: Context) -> ActionResult:
        ref = f"{self.tenant}.{self.subject_ref}"
        r = await httpclient.request("GET", f"{self.base_url}/api/v1/prefs/{ref}", timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"get_prefs: unexpected HTTP {r.status_code} "
                                                  f"{r.text}")
        return ActionResult(ok=True, detail="prefs read", data=r.json())


@dataclass
class SetPrefsAction:
    """`PUT /api/v1/prefs/{tenant}.{subject_ref}` — `stopped` names the WHOLE set of classes to
    stop each time (never one switch alone — that route's own docstring: a partial update from a
    stale open tab would silently re-enable what the customer just turned off)."""

    base_url: str
    tenant: str
    subject_ref: str
    stopped: list[str] = field(default_factory=list)
    name: str = "set_prefs"

    async def run(self, ctx: Context) -> ActionResult:
        ref = f"{self.tenant}.{self.subject_ref}"
        r = await httpclient.request("PUT", f"{self.base_url}/api/v1/prefs/{ref}",
                                     json={"stopped": self.stopped}, timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"set_prefs: unexpected HTTP {r.status_code} "
                                                  f"{r.text}")
        return ActionResult(ok=True, detail="prefs set", data=r.json())


@dataclass
class ListScheduleAction:
    """`GET /api/v1/reminders/schedule` — the owner's own upcoming-sends queue. Empty for a
    fresh tenant that never had a real visit event scheduled anything — a real, honest answer,
    not a gap (see `service.py`'s own module docstring on why no event bus is wired here)."""

    base_url: str
    tenant: str
    state: str = "pending"
    name: str = "list_schedule"

    async def run(self, ctx: Context) -> ActionResult:
        headers = auth_header(tenant=self.tenant, caps=(_READ_CAP,))
        r = await httpclient.request(
            "GET", f"{self.base_url}/api/v1/reminders/schedule",
            params={"state": self.state}, headers=headers, timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"list_schedule refused: {r.status_code} "
                                                  f"{r.text}")
        return ActionResult(ok=True, detail="schedule read", data=r.json())


@dataclass
class SetRuleAction:
    """`PUT /api/v1/reminders/rules/{rule_key}` — OVERRIDES an already-learned rule row; it never
    creates one from scratch (`RuleStore.get` first, 404 if nothing is there yet). A service with
    no real visit-event history behind it (this simulator wires no real visit-event bus into
    reminders — see `service.py`'s own module docstring) has no row to override, so this action
    correctly refuses for such a service — a real, honest result, not a bug in this action."""

    base_url: str
    tenant: str
    service_id: str
    interval_days: float
    lead_days: float = 7
    name: str = "set_rule"

    async def run(self, ctx: Context) -> ActionResult:
        headers = auth_header(tenant=self.tenant, caps=(_MANAGE_CAP,))
        body = {"interval_days": self.interval_days, "lead_days": self.lead_days}
        r = await httpclient.request(
            "PUT", f"{self.base_url}/api/v1/reminders/rules/{self.service_id}", json=body,
            headers=headers, timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"set_rule: unexpected HTTP {r.status_code} "
                                                  f"{r.text}")
        return ActionResult(ok=True, detail="rule set", data=r.json())


@dataclass
class ListRulesAction:
    """`GET /api/v1/reminders/rules?service_id=` — the learned/set interval, reported alongside
    whether it is still the service's own default or a real, observed value
    (`is_learned`/`AdaptiveConfig`)."""

    base_url: str
    tenant: str
    service_id: str = ""
    subject_ref: str = ""
    name: str = "list_rules"

    async def run(self, ctx: Context) -> ActionResult:
        headers = auth_header(tenant=self.tenant, caps=(_READ_CAP,))
        params = {}
        if self.service_id:
            params["service_id"] = self.service_id
        if self.subject_ref:
            params["subject_ref"] = self.subject_ref
        r = await httpclient.request(
            "GET", f"{self.base_url}/api/v1/reminders/rules", params=params,
            headers=headers, timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"list_rules refused: {r.status_code} {r.text}")
        return ActionResult(ok=True, detail="rules read", data=r.json())
