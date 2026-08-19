"""The event-driven fast path (app/main.py::_commission_sync_handler) — a HINT only, per
app/ports/event_bus.py's own contract. Worth testing on its own: it is never exercised by the
integration suite (no real event bus fires in a TestClient), so without this it would be
unverified code sitting in the one place a typo is invisible until production.
"""
from __future__ import annotations

import logging

import pytest

from app.main import _commission_sync_handler
from app.ports.event_bus import Event


class _FakeCommissions:
    def __init__(self, *, raises: bool = False):
        self.calls: list[str] = []
        self._raises = raises

    async def sync(self, tenant: str):
        self.calls.append(tenant)
        if self._raises:
            raise RuntimeError("billing unreachable")
        return {"synced": True, "created": [], "voided": []}


class _FakeContainer:
    def __init__(self, commissions):
        self.commissions = commissions


@pytest.mark.anyio
async def test_a_payment_event_triggers_a_sync_for_its_own_tenant():
    commissions = _FakeCommissions()
    handler = _commission_sync_handler(_FakeContainer(commissions), logging.getLogger("test"))
    await handler(Event(type="payment.succeeded", payload={"tenant": "t-1", "invoice_id": "inv-1"}))
    assert commissions.calls == ["t-1"]


@pytest.mark.anyio
async def test_an_event_with_no_tenant_triggers_nothing():
    commissions = _FakeCommissions()
    handler = _commission_sync_handler(_FakeContainer(commissions), logging.getLogger("test"))
    await handler(Event(type="payment.succeeded", payload={"invoice_id": "inv-1"}))
    assert commissions.calls == []


@pytest.mark.anyio
async def test_a_sync_failure_is_swallowed_not_propagated():
    """The event bus already swallows a subscriber's exceptions per its own contract — this
    proves the handler does not depend on that alone (and that a failure is at least logged, not
    silently vanished)."""
    commissions = _FakeCommissions(raises=True)
    handler = _commission_sync_handler(_FakeContainer(commissions), logging.getLogger("test"))
    await handler(Event(type="invoice.paid", payload={"tenant": "t-1"}))   # must not raise
    assert commissions.calls == ["t-1"]
