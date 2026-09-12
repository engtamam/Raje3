"""One claim per invoice — so a consolidated renewal invoice (platform v0.19.11: one invoice
covering several of a tenant's subscriptions) does not open the Flow twice.

WHY THIS EXISTS. billing-service emits `subscription.renewed` ONCE PER SUBSCRIPTION even when
several subscriptions were consolidated into one invoice (`run_consolidated_cycle`'s own event
loop, verified against the platform source at repin time) — all of them carrying the SAME
`invoice_id`. Without a claim, a shop with three apps renewing together would get three Flow-
opening messages, all for the one invoice.

ATOMIC, VIA THE STORE'S OWN `claim()` — fixed 2026-09-12, a real gap a QA audit found: this used to
be a hand-rolled get-then-put with the same race a QA audit found and closed elsewhere in this
codebase (see `app/ports/datastore.py::DataStore.claim`'s own docstring — added 2026-09-07 for
exactly this class of bug). There was never a reason for this one call site to keep re-inventing a
non-atomic version of a primitive already available; it now just calls it, same as every other
`.claim()`-based lock in this service."""
from __future__ import annotations

from typing import Any

_COLL = "renewal_triggers"
# No real TTL semantics wanted here — a claim on an invoice_id is permanent (never re-sent for the
# same invoice), so the TTL is simply "forever" in practical terms.
_CLAIM_TTL_SECONDS = 10 * 365 * 86400


class RenewalTriggerStore:
    def __init__(self, store: Any) -> None:
        self._s = store

    async def claim(self, invoice_id: str, *, now: int) -> bool:
        """`True` the first time this invoice_id is seen — the caller should send. `False` on
        every call after — already claimed, never resend for the same invoice."""
        if not invoice_id:
            return False
        return await self._s.claim(
            _COLL, invoice_id, {"invoice_id": invoice_id, "claimed_at": now},
            ttl_seconds=_CLAIM_TTL_SECONDS, now=float(now))
