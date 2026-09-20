"""Reacts to billing-service's own `subscription.suspended`/`subscription.renewed` events (base-
services v0.25.21+) by flipping Meta's own AI rollout switch — the real-time replacement for the
periodic sweep this codebase tried and deliberately removed (2026-09-20, see
meta_agent_rollout_trigger.py's own docstring).

BEST-EFFORT, LIKE EVERY EVENT ON THIS BUS (see app/ports/event_bus.py's own module docstring) — a
missed event here means Meta's AI stays in its last known state a little longer than it should,
never a money or safety consequence. There is currently no durable backstop for a missed event
(the sweep that used to be one was removed); accepted deliberately, same reasoning applies to every
other best-effort consumer already in this codebase.

WHY `subscription.renewed` STILL RE-CHECKS ENTITLEMENT AND THE AI TOGGLE RATHER THAN BLINDLY
ENABLING — the exact same posture `staff.py::set_ai_toggle` already takes on its own "on" branch:
a renewed subscription is not necessarily THIS shop's `feature.whatsapp` (a tenant can hold several
apps, each renewing independently), and the owner's own kill switch must still win even when the
subscription itself is healthy.
"""
from __future__ import annotations

from typing import Any

SUBSCRIPTION_SUSPENDED = "subscription.suspended"
SUBSCRIPTION_RENEWED = "subscription.renewed"


async def register(container: Any) -> None:
    """Subscribe both handlers on the container's own event bus — awaited once at startup (see
    `app/main.py`'s lifespan, same call shape audit-service's own startup subscription already
    uses), inert on the in-process memory bus (nothing else publishes cross-process there), real
    the moment EVENTBUS_DRIVER=redis is configured (already the case for this service — see
    `deploy/services/operations.values.yaml`'s own `eventbus: redis` line)."""
    bus = getattr(container, "event_bus", None)
    if bus is None:
        return

    async def _on_suspended(event: Any) -> None:
        payload = event.payload if isinstance(event.payload, dict) else {}
        tenant = str(payload.get("tenant") or "")
        if not tenant:
            return
        await container.meta_agent_rollout_trigger.trigger(tenant=tenant, enabled=False)

    async def _on_renewed(event: Any) -> None:
        payload = event.payload if isinstance(event.payload, dict) else {}
        tenant = str(payload.get("tenant") or "")
        if not tenant:
            return
        if not await container.whatsapp_licence.allowed(tenant):
            return
        from app.core import ai_toggle as AT

        if not await AT.AiToggleStore(container.datastore).get(tenant):
            return
        await container.meta_agent_rollout_trigger.trigger(tenant=tenant, enabled=True)

    await bus.subscribe(SUBSCRIPTION_SUSPENDED, _on_suspended)
    await bus.subscribe(SUBSCRIPTION_RENEWED, _on_renewed)
