"""One claim per invoice — so a consolidated renewal invoice (platform v0.19.11: one invoice
covering several of a tenant's subscriptions) does not open the Flow twice.

WHY THIS EXISTS. billing-service emits `subscription.renewed` ONCE PER SUBSCRIPTION even when
several subscriptions were consolidated into one invoice (`run_consolidated_cycle`'s own event
loop, verified against the platform source at repin time) — all of them carrying the SAME
`invoice_id`. Without a claim, a shop with three apps renewing together would get three Flow-
opening messages, all for the one invoice.

A BENIGN RACE, ACCEPTED. `claim()` is read-then-write, not atomic — the same posture the bus
consumers elsewhere in this service already hold towards at-most-once delivery (see
`renewal_consumer.py`'s own docstring). Two events for the same invoice arriving within the same
instant could both see "not claimed" and both send — a rare, harmless duplicate (the shop gets the
same renewal Flow message twice), never a missed one. A real atomic claim would need the same
IdempotencyStore machinery billing-service itself uses; not built here until this gap is shown to
matter in practice."""
from __future__ import annotations

from typing import Any

_COLL = "renewal_triggers"


class RenewalTriggerStore:
    def __init__(self, store: Any) -> None:
        self._s = store

    async def claim(self, invoice_id: str, *, now: int) -> bool:
        """`True` the first time this invoice_id is seen — the caller should send. `False` on
        every call after — already claimed, never resend for the same invoice."""
        if not invoice_id:
            return False
        existing = await self._s.get(_COLL, invoice_id)
        if existing is not None:
            return False
        await self._s.put(_COLL, invoice_id, {"invoice_id": invoice_id, "claimed_at": now})
        return True
