"""POST /internal/whatsapp-flow/booking used to have NO licence check at all — notification-
service's Flow engine calls this route directly, completely bypassing conversation.py's own door
gate, so an unsubscribed/toggled-off tenant's WhatsApp booking Flow could still read real
availability and create real bookings through `core/flow_booking_backend.py`. This proves the fix:
`app/api/internal.py::whatsapp_flow_booking` now refuses BEFORE the backend is ever touched, in the
same shape each op already degrades to (see `flow_booking_backend.py`'s own single-branch-shops-only
note: "options/calendar/slots all return empty ... and reserve refuses with a reason a customer can
read"), and proceeds unchanged when the licence allows it.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from app.api.internal import FlowBookingIn, whatsapp_flow_booking


def run(c):
    return asyncio.run(c)


class _ScriptedLicence:
    def __init__(self, allowed: bool):
        self._allowed = allowed
        self.asked: list[str] = []

    async def allowed(self, tenant: str) -> bool:
        self.asked.append(tenant)
        return self._allowed


class _RecordingBackend:
    """Would prove the bug if ever reached while the licence refuses — every method records that
    it was called at all."""
    def __init__(self):
        self.calls: list[str] = []

    async def options(self, **kwargs):
        self.calls.append("options")
        return [{"id": "svc1", "title": "Haircut"}]

    async def calendar(self, **kwargs):
        self.calls.append("calendar")
        return {"min_date": "2026-09-19", "max_date": "2026-10-02", "unavailable_dates": [],
                "include_days": ["Sun"]}

    async def slots(self, **kwargs):
        self.calls.append("slots")
        return [{"id": "123", "title": "10:00"}]

    async def reserve(self, **kwargs):
        self.calls.append("reserve")
        return {"ok": True, "ref": "bk_1"}


@dataclass
class _App:
    state: Any


@dataclass
class _State:
    container: Any


@dataclass
class _Request:
    app: Any


@dataclass
class _Container:
    flow_booking_provider: Any
    licence: Any


def _request(backend, licence):
    container = _Container(flow_booking_provider=backend, licence=licence)
    return _Request(app=_App(state=_State(container=container)))


def _body(op: str, **kwargs) -> FlowBookingIn:
    return FlowBookingIn(op=op, tenant="shop1", customer="+966500000000", **kwargs)


def test_licence_off_refuses_options_with_an_empty_list_never_touching_the_backend():
    backend = _RecordingBackend()
    licence = _ScriptedLicence(allowed=False)
    result = run(whatsapp_flow_booking(_body("options", dimension="service"),
                                       _request(backend, licence)))
    assert result == {"options": []}
    assert backend.calls == []
    assert licence.asked == ["shop1"]


def test_licence_off_refuses_calendar_with_an_empty_dict():
    backend = _RecordingBackend()
    licence = _ScriptedLicence(allowed=False)
    result = run(whatsapp_flow_booking(_body("calendar"), _request(backend, licence)))
    assert result == {}
    assert backend.calls == []


def test_licence_off_refuses_slots_with_an_empty_list():
    backend = _RecordingBackend()
    licence = _ScriptedLicence(allowed=False)
    result = run(whatsapp_flow_booking(_body("slots", date="2026-09-20"),
                                       _request(backend, licence)))
    assert result == {"slots": []}
    assert backend.calls == []


def test_licence_off_refuses_reserve_with_a_readable_reason_never_creating_a_booking():
    backend = _RecordingBackend()
    licence = _ScriptedLicence(allowed=False)
    result = run(whatsapp_flow_booking(_body("reserve", selection={"service": "svc1"},
                                             idempotency_key="idem1"),
                                       _request(backend, licence)))
    assert result["ok"] is False
    assert result["reason"]
    assert backend.calls == []


def test_licence_on_proceeds_exactly_as_before_for_every_op():
    backend = _RecordingBackend()
    licence = _ScriptedLicence(allowed=True)
    req = _request(backend, licence)

    assert run(whatsapp_flow_booking(_body("options", dimension="service"), req)) == {
        "options": [{"id": "svc1", "title": "Haircut"}]}
    assert run(whatsapp_flow_booking(_body("calendar"), req)) == {
        "min_date": "2026-09-19", "max_date": "2026-10-02", "unavailable_dates": [],
        "include_days": ["Sun"]}
    assert run(whatsapp_flow_booking(_body("slots", date="2026-09-20"), req)) == {
        "slots": [{"id": "123", "title": "10:00"}]}
    assert run(whatsapp_flow_booking(_body("reserve", selection={"service": "svc1"},
                                          idempotency_key="idem1"), req)) == {
        "ok": True, "ref": "bk_1"}
    assert backend.calls == ["options", "calendar", "slots", "reserve"]
    assert licence.asked == ["shop1", "shop1", "shop1", "shop1"]


def test_no_licence_wired_behaves_exactly_as_before_this_fix():
    backend = _RecordingBackend()
    result = run(whatsapp_flow_booking(_body("options", dimension="service"),
                                       _request(backend, licence=None)))
    assert result == {"options": [{"id": "svc1", "title": "Haircut"}]}
    assert backend.calls == ["options"]
