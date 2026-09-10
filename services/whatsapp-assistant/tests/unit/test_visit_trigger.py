"""maybe_open_visit_flow — the keyword gate (never an ordinary message), then the three-gate check
(licence, owner opt-in, sender identity) before a visit-registration Flow ever opens."""
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


def _call(c, *, kind="text", text="##", tenant="t1", from_number="966500000001",
         idempotency_key="visit:wamid1"):
    return run(maybe_open_visit_flow(
        container=c, tenant=tenant, from_number=from_number, kind=kind, text=text,
        idempotency_key=idempotency_key))


def test_the_exact_keyword_from_an_identified_staff_sender_opens_the_flow():
    c = _Container()
    assert _call(c) is True
    assert c.sender.sent == [{"tenant": "t1", "to": "966500000001",
                              "template_name": "visit_flow", "variables": [],
                              "idempotency_key": "visit:wamid1", "flow_token": "visit:wamid1",
                              "flow_action_data": {"customer": "966500000001"}}]


def test_the_symbol_mixed_with_other_text_never_opens_the_flow():
    """Exact match only — "##" has to be the WHOLE message, never a fragment of a real sentence
    ("## متى نفتح اليوم؟") that happens to contain it."""
    c = _Container()
    assert _call(c, text="## متى نفتح اليوم؟") is False
    assert c.sender.sent == []
    assert c.operator_identity.calls == 0


def test_an_ordinary_message_from_the_same_staff_sender_never_opens_the_flow():
    """The whole point of the keyword: a staff member texting the shop about anything else must
    reach the ordinary conversation untouched, never be hijacked into a Flow."""
    c = _Container()
    assert _call(c, text="وش أوقات الدوام اليوم؟") is False
    assert c.sender.sent == []
    assert c.operator_identity.calls == 0


def test_a_button_reply_with_the_same_text_as_the_keyword_never_opens_the_flow():
    c = _Container()
    assert _call(c, kind="button_reply") is False
    assert c.sender.sent == []


def test_the_keyword_check_costs_nothing_extra_before_the_real_gates():
    c = _Container(licence=_Licence(allowed=False))
    assert _call(c, text="مو الكلمة") is False
    assert c.operator_identity.calls == 0


def test_a_licence_that_refuses_sends_nothing_and_never_resolves_identity():
    c = _Container(licence=_Licence(allowed=False))
    assert _call(c) is False
    assert c.sender.sent == []
    assert c.operator_identity.calls == 0


def test_a_tenant_that_never_opted_in_sends_nothing_and_never_resolves_identity():
    c = _Container(whatsapp_visit_gate=_Gate(enabled=False))
    assert _call(c) is False
    assert c.sender.sent == []
    assert c.operator_identity.calls == 0


def test_an_unidentified_sender_sends_nothing_falls_through():
    """A customer who happens to type the same keyword resolves to no operator and falls through
    exactly like an ordinary message would."""
    c = _Container(operator_identity=_Identity(operator_id=""))
    assert _call(c) is False
    assert c.sender.sent == []


def test_a_missing_licence_object_defaults_to_allowed():
    """Some deployments wire no licence gate at all (container.licence stays None) — same
    fail-open posture the rest of this service holds when a licence object was never configured."""
    c = _Container(licence=None)
    assert _call(c) is True
