"""maybe_open_staff_menu / maybe_handle_staff_menu_reply — the symbol-triggered Interactive List
Message (## opens a menu; tapping a row opens that row's own Flow), gated by licence, owner
opt-in, and sender identity, re-checked on both the open and the tap."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from app.core.visit_trigger import maybe_handle_staff_menu_reply, maybe_open_staff_menu


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
        self.lists: list[dict] = []
        self.sent: list[dict] = []

    async def send_list(self, **kwargs):
        self.lists.append(kwargs)
        return "dlv_list"

    async def send_template(self, **kwargs):
        self.sent.append(kwargs)
        return "dlv_1"


@dataclass
class _Container:
    licence: Any = field(default_factory=_Licence)
    whatsapp_visit_gate: Any = field(default_factory=_Gate)
    operator_identity: Any = field(default_factory=_Identity)
    sender: Any = field(default_factory=_Sender)


def _open(c, *, kind="text", text="##", tenant="t1", from_number="966500000001",
          idempotency_key="staffmenu:wamid1"):
    return run(maybe_open_staff_menu(
        container=c, tenant=tenant, from_number=from_number, kind=kind, text=text,
        idempotency_key=idempotency_key))


def _tap(c, *, kind="list_reply", reply_id="staffmenu:visit", tenant="t1",
         from_number="966500000001", idempotency_key="staffmenu:wamid2"):
    return run(maybe_handle_staff_menu_reply(
        container=c, tenant=tenant, from_number=from_number, kind=kind, reply_id=reply_id,
        idempotency_key=idempotency_key))


# ── opening the menu ─────────────────────────────────────────────────────────────────────────
def test_the_exact_symbol_from_an_identified_staff_sender_opens_the_menu():
    c = _Container()
    assert _open(c) is True
    assert c.sender.lists == [{"tenant": "t1", "to": "966500000001", "body": "اختر من القائمة:",
                               "button_text": "القائمة",
                               "rows": [{"id": "staffmenu:visit", "title": "تسجيل زيارة",
                                        "description": "سجّل زيارة عميل من هنا مباشرة"}],
                               "idempotency_key": "staffmenu:wamid1"}]
    assert c.sender.sent == []


def test_the_symbol_mixed_with_other_text_never_opens_the_menu():
    c = _Container()
    assert _open(c, text="## متى نفتح اليوم؟") is False
    assert c.sender.lists == []
    assert c.operator_identity.calls == 0


def test_an_ordinary_message_from_the_same_staff_sender_never_opens_the_menu():
    c = _Container()
    assert _open(c, text="وش أوقات الدوام اليوم؟") is False
    assert c.sender.lists == []
    assert c.operator_identity.calls == 0


def test_a_button_reply_with_the_same_text_as_the_symbol_never_opens_the_menu():
    c = _Container()
    assert _open(c, kind="button_reply") is False
    assert c.sender.lists == []


def test_a_licence_that_refuses_sends_no_menu_and_never_resolves_identity():
    c = _Container(licence=_Licence(allowed=False))
    assert _open(c) is False
    assert c.sender.lists == []
    assert c.operator_identity.calls == 0


def test_a_tenant_that_never_opted_in_sends_no_menu_and_never_resolves_identity():
    c = _Container(whatsapp_visit_gate=_Gate(enabled=False))
    assert _open(c) is False
    assert c.sender.lists == []
    assert c.operator_identity.calls == 0


def test_an_unidentified_sender_sends_no_menu():
    c = _Container(operator_identity=_Identity(operator_id=""))
    assert _open(c) is False
    assert c.sender.lists == []


def test_a_missing_licence_object_defaults_to_allowed():
    c = _Container(licence=None)
    assert _open(c) is True


# ── tapping a row ────────────────────────────────────────────────────────────────────────────
def test_tapping_the_visit_row_opens_its_flow():
    c = _Container()
    assert _tap(c) is True
    assert c.sender.sent == [{"tenant": "t1", "to": "966500000001", "template_name": "visit_flow",
                              "variables": [], "idempotency_key": "staffmenu:wamid2",
                              "flow_token": "staffmenu:wamid2",
                              "flow_action_data": {"customer": "966500000001"}}]
    assert c.sender.lists == []


def test_a_reply_that_is_not_a_list_reply_never_opens_anything():
    c = _Container()
    assert _tap(c, kind="button_reply") is False
    assert c.sender.sent == []


def test_a_reply_id_outside_the_menus_own_prefix_never_opens_anything():
    """A different feature's own reply id (triage:.../branch:...) must never be read as this
    menu's — the prefix is the whole guard."""
    c = _Container()
    assert _tap(c, reply_id="triage:complaint") is False
    assert c.sender.sent == []
    assert c.operator_identity.calls == 0


def test_an_unknown_row_id_inside_the_menus_own_prefix_never_opens_anything():
    c = _Container()
    assert _tap(c, reply_id="staffmenu:not_a_real_row") is False
    assert c.sender.sent == []


def test_the_tap_re_checks_identity_never_trusts_the_reply_alone():
    """The list itself proves nothing extra — see the module docstring's own reasoning."""
    c = _Container(operator_identity=_Identity(operator_id=""))
    assert _tap(c) is False
    assert c.sender.sent == []
    assert c.operator_identity.calls == 1


def test_the_tap_re_checks_the_owners_opt_in_too():
    c = _Container(whatsapp_visit_gate=_Gate(enabled=False))
    assert _tap(c) is False
    assert c.sender.sent == []
    assert c.operator_identity.calls == 0
