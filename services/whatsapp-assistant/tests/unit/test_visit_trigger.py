"""maybe_open_visit_flow — the three-gate check (licence, owner opt-in, sender identity) before a
visit-registration Flow ever opens for an inbound staff message."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from app.core.visit_trigger import maybe_open_visit_flow


def run(c):
    return asyncio.run(c)


class _Licence:
    def __init__(self, allowed: bool = True) -> None:
        self._allowed = allowed

    async def allowed(self, tenant: str) -> bool:
        return self._allowed


class _Gate:
    def __init__(self, enabled: bool = True) -> None:
        self._enabled = enabled

    async def enabled(self, tenant: str) -> bool:
        return self._enabled


class _Identity:
    def __init__(self, operator_id: str = "op_1") -> None:
        self._id = operator_id
        self.calls = 0

    async def resolve(self, *, tenant: str, from_number: str) -> str:
        self.calls += 1
        return self._id


class _Sender:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_template(self, **kwargs):
        self.sent.append(kwargs)
        return "dlv_1"


@dataclass
class _Container:
    licence: Any = field(default_factory=_Licence)
    whatsapp_visit_gate: Any = field(default_factory=_Gate)
    operator_identity: Any = field(default_factory=_Identity)
    sender: Any = field(default_factory=_Sender)


def test_an_identified_staff_sender_opens_the_flow():
    c = _Container()
    ok = run(maybe_open_visit_flow(
        container=c, tenant="t1", from_number="966500000001", idempotency_key="visit:wamid1"))
    assert ok is True
    assert c.sender.sent == [{"tenant": "t1", "to": "966500000001",
                              "template_name": "visit_flow", "variables": [],
                              "idempotency_key": "visit:wamid1", "flow_token": "visit:wamid1",
                              "flow_action_data": {"customer": "966500000001"}}]


def test_a_licence_that_refuses_sends_nothing_and_never_resolves_identity():
    c = _Container(licence=_Licence(allowed=False))
    ok = run(maybe_open_visit_flow(
        container=c, tenant="t1", from_number="966500000001", idempotency_key="visit:wamid2"))
    assert ok is False
    assert c.sender.sent == []
    assert c.operator_identity.calls == 0


def test_a_tenant_that_never_opted_in_sends_nothing_and_never_resolves_identity():
    c = _Container(whatsapp_visit_gate=_Gate(enabled=False))
    ok = run(maybe_open_visit_flow(
        container=c, tenant="t1", from_number="966500000001", idempotency_key="visit:wamid3"))
    assert ok is False
    assert c.sender.sent == []
    assert c.operator_identity.calls == 0


def test_an_unidentified_sender_sends_nothing_falls_through():
    c = _Container(operator_identity=_Identity(operator_id=""))
    ok = run(maybe_open_visit_flow(
        container=c, tenant="t1", from_number="966500000001", idempotency_key="visit:wamid4"))
    assert ok is False
    assert c.sender.sent == []


def test_a_missing_licence_object_defaults_to_allowed():
    """Some deployments wire no licence gate at all (container.licence stays None) — same
    fail-open posture the rest of this service holds when a licence object was never configured."""
    c = _Container(licence=None)
    ok = run(maybe_open_visit_flow(
        container=c, tenant="t1", from_number="966500000001", idempotency_key="visit:wamid5"))
    assert ok is True
