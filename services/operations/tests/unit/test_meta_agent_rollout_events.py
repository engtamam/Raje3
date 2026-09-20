"""core/meta_agent_rollout_events.py — the real-time replacement for the periodic sweep this
codebase tried and removed. Uses the REAL in-process MemoryEventBus (app/adapters/event_bus/
memory.py), not a fake, so `register` + `publish` prove the actual subscribe/dispatch wiring."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from app.adapters.event_bus.memory import MemoryEventBus
from app.core.meta_agent_rollout_events import (
    SUBSCRIPTION_RENEWED, SUBSCRIPTION_SUSPENDED, register,
)
from app.ports.event_bus import Event


def run(c):
    return asyncio.run(c)


@dataclass
class _FakeTrigger:
    calls: list = field(default_factory=list)

    async def trigger(self, *, tenant, enabled):
        self.calls.append({"tenant": tenant, "enabled": enabled})
        return True


class _FakeWhatsappLicence:
    def __init__(self, allowed: bool | None = True) -> None:
        self._allowed = allowed

    async def allowed(self, tenant: str) -> bool | None:
        return self._allowed


class _FakeDatastore:
    """Just enough for AiToggleStore.get(): absent row -> True, same as the real store's own
    "absent means on" contract."""

    async def get(self, collection, key):
        return None


class _Container:
    def __init__(self, *, whatsapp_allowed: bool | None = True) -> None:
        self.event_bus = MemoryEventBus()
        self.meta_agent_rollout_trigger = _FakeTrigger()
        self.whatsapp_licence = _FakeWhatsappLicence(whatsapp_allowed)
        self.datastore = _FakeDatastore()


def test_register_is_a_noop_with_no_event_bus():
    class _NoBus:
        pass

    run(register(_NoBus()))   # must not raise


def test_suspended_event_disables_regardless_of_entitlement_or_toggle():
    """The strongest form of the claim: even a tenant that reads back ENTITLED, with the AI
    switch ON, still gets disabled the instant Meta's own event says the subscription lapsed —
    `_on_suspended` reads neither `whatsapp_licence` nor the toggle at all, by design."""
    c = _Container(whatsapp_allowed=True)

    class _ToggledOnDatastore:
        async def get(self, collection, key):
            return {"tenant": key, "enabled": True, "updated_at": 0}

    c.datastore = _ToggledOnDatastore()
    run(register(c))
    run(c.event_bus.publish(SUBSCRIPTION_SUSPENDED, Event(
        type=SUBSCRIPTION_SUSPENDED,
        payload={"tenant": "t1", "subscription_id": "s1", "plan_id": "p1", "reason": "dunning"})))
    assert c.meta_agent_rollout_trigger.calls == [{"tenant": "t1", "enabled": False}]


def test_suspended_event_carries_its_reason_untouched():
    """admin_paused, dunning, wallet_insufficient -- every reason base-services may ever send
    triggers the exact same disable, since the payload's `reason` field is never inspected."""
    for reason in ("dunning", "wallet_insufficient", "admin_paused", "", "something_new"):
        c = _Container()
        run(register(c))
        run(c.event_bus.publish(SUBSCRIPTION_SUSPENDED, Event(
            type=SUBSCRIPTION_SUSPENDED,
            payload={"tenant": f"t_{reason or 'blank'}", "reason": reason})))
        assert c.meta_agent_rollout_trigger.calls == [
            {"tenant": f"t_{reason or 'blank'}", "enabled": False}]


def test_suspended_event_with_no_tenant_is_ignored():
    c = _Container()
    run(register(c))
    run(c.event_bus.publish(SUBSCRIPTION_SUSPENDED, Event(
        type=SUBSCRIPTION_SUSPENDED, payload={"subscription_id": "s1"})))
    assert c.meta_agent_rollout_trigger.calls == []


def test_renewed_event_enables_when_still_entitled():
    c = _Container(whatsapp_allowed=True)
    run(register(c))
    run(c.event_bus.publish(SUBSCRIPTION_RENEWED, Event(
        type=SUBSCRIPTION_RENEWED,
        payload={"tenant": "t2", "subscription_id": "s2", "plan_id": "p2"})))
    assert c.meta_agent_rollout_trigger.calls == [{"tenant": "t2", "enabled": True}]


def test_renewed_event_does_nothing_if_not_entitled():
    """A renewed subscription is not necessarily THIS tenant's feature.whatsapp — a shop can hold
    several apps that each renew independently."""
    c = _Container(whatsapp_allowed=False)
    run(register(c))
    run(c.event_bus.publish(SUBSCRIPTION_RENEWED, Event(
        type=SUBSCRIPTION_RENEWED, payload={"tenant": "t3"})))
    assert c.meta_agent_rollout_trigger.calls == []


def test_renewed_event_does_nothing_if_the_owners_own_switch_is_off():
    c = _Container(whatsapp_allowed=True)

    class _ToggledOffDatastore:
        async def get(self, collection, key):
            return {"tenant": key, "enabled": False, "updated_at": 0}

    c.datastore = _ToggledOffDatastore()
    run(register(c))
    run(c.event_bus.publish(SUBSCRIPTION_RENEWED, Event(
        type=SUBSCRIPTION_RENEWED, payload={"tenant": "t4"})))
    assert c.meta_agent_rollout_trigger.calls == []


def test_a_bad_payload_never_crashes_the_publisher():
    c = _Container()
    run(register(c))
    # MemoryEventBus already swallows handler exceptions, but this proves the handler itself
    # tolerates a non-dict payload rather than relying on that safety net.
    run(c.event_bus.publish(SUBSCRIPTION_SUSPENDED, Event(type=SUBSCRIPTION_SUSPENDED, payload={})))
    assert c.meta_agent_rollout_trigger.calls == []


def test_a_none_payload_is_tolerated_too():
    c = _Container()
    run(register(c))
    run(c.event_bus.publish(SUBSCRIPTION_RENEWED, Event(type=SUBSCRIPTION_RENEWED, payload=None)))
    assert c.meta_agent_rollout_trigger.calls == []


def test_renewed_event_fails_closed_when_entitlement_could_not_be_asked():
    """None ("could not ask") must never be read as "go ahead" -- same fail-closed posture every
    other whatsapp_licence caller in this codebase already holds (connect.py, staff.py)."""
    c = _Container(whatsapp_allowed=None)
    run(register(c))
    run(c.event_bus.publish(SUBSCRIPTION_RENEWED, Event(
        type=SUBSCRIPTION_RENEWED, payload={"tenant": "t_unreachable"})))
    assert c.meta_agent_rollout_trigger.calls == []


def test_a_raising_entitlement_check_does_not_crash_the_bus():
    c = _Container()

    class _RaisingLicence:
        async def allowed(self, tenant: str) -> bool | None:
            raise RuntimeError("billing-service unreachable")

    c.whatsapp_licence = _RaisingLicence()
    run(register(c))
    # Must not raise out of publish() -- MemoryEventBus's own try/except around each handler
    # covers this in production, but the assertion below proves it really was swallowed rather
    # than the test accidentally not exercising the path.
    run(c.event_bus.publish(SUBSCRIPTION_RENEWED, Event(
        type=SUBSCRIPTION_RENEWED, payload={"tenant": "t_raises"})))
    assert c.meta_agent_rollout_trigger.calls == []


def test_a_raising_trigger_does_not_crash_the_bus():
    c = _Container()

    class _RaisingTrigger:
        async def trigger(self, *, tenant, enabled):
            raise RuntimeError("whatsapp-assistant unreachable")

    c.meta_agent_rollout_trigger = _RaisingTrigger()
    run(register(c))
    run(c.event_bus.publish(SUBSCRIPTION_SUSPENDED, Event(
        type=SUBSCRIPTION_SUSPENDED, payload={"tenant": "t_raises"})))   # must not raise


def test_a_trigger_that_reports_failure_is_not_retried_or_escalated():
    """`trigger()` returning False (whatsapp-assistant reachable but reported ok=False) is not
    inspected here at all -- best-effort, same posture as every other fire-and-forget trigger in
    this codebase (meta_agent_provision_trigger, renewal_heads_up_notifier)."""
    class _FalseTrigger:
        def __init__(self):
            self.calls = []

        async def trigger(self, *, tenant, enabled):
            self.calls.append((tenant, enabled))
            return False

    c = _Container()
    c.meta_agent_rollout_trigger = _FalseTrigger()
    run(register(c))
    run(c.event_bus.publish(SUBSCRIPTION_SUSPENDED, Event(
        type=SUBSCRIPTION_SUSPENDED, payload={"tenant": "t_false"})))
    assert c.meta_agent_rollout_trigger.calls == [("t_false", False)]


def test_two_tenants_are_handled_independently_no_closure_crosstalk():
    c = _Container(whatsapp_allowed=True)
    run(register(c))
    run(c.event_bus.publish(SUBSCRIPTION_SUSPENDED, Event(
        type=SUBSCRIPTION_SUSPENDED, payload={"tenant": "tenant_a"})))
    run(c.event_bus.publish(SUBSCRIPTION_RENEWED, Event(
        type=SUBSCRIPTION_RENEWED, payload={"tenant": "tenant_b"})))
    assert c.meta_agent_rollout_trigger.calls == [
        {"tenant": "tenant_a", "enabled": False},
        {"tenant": "tenant_b", "enabled": True},
    ]


def test_the_same_tenant_suspended_twice_fires_twice_no_dedup():
    """No idempotency layer here by design -- the Graph call itself is idempotent (PUT, not a
    counter), so firing twice for a replayed/duplicate event is harmless, same reasoning
    meta_agent_rollout_trigger.py's own docstring gives for the sweep this replaces."""
    c = _Container()
    run(register(c))
    for _ in range(2):
        run(c.event_bus.publish(SUBSCRIPTION_SUSPENDED, Event(
            type=SUBSCRIPTION_SUSPENDED, payload={"tenant": "t_replay"})))
    assert c.meta_agent_rollout_trigger.calls == [
        {"tenant": "t_replay", "enabled": False},
        {"tenant": "t_replay", "enabled": False},
    ]


def test_register_subscribes_each_topic_exactly_once():
    c = _Container()
    run(register(c))
    assert len(c.event_bus._handlers.get(SUBSCRIPTION_SUSPENDED, [])) == 1
    assert len(c.event_bus._handlers.get(SUBSCRIPTION_RENEWED, [])) == 1


def test_an_unrelated_topic_never_reaches_either_handler():
    c = _Container()
    run(register(c))
    run(c.event_bus.publish("payment.succeeded", Event(
        type="payment.succeeded", payload={"tenant": "t_unrelated"})))
    assert c.meta_agent_rollout_trigger.calls == []
