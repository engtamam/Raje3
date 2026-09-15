"""One claim per (subscription, period_end) — mirrors `renewal_trigger_store.py` exactly, but keyed
on the CYCLE the heads-up is FOR rather than an invoice id, because at send time no invoice exists
yet (this fires 2 days before one would). Without this, a daily scan that finds the same still-
upcoming subscription on two consecutive days would open the heads-up Flow twice for the same
renewal — `period_end` changing is the only real signal that a NEW cycle is now being announced."""
from __future__ import annotations

from typing import Any

_COLL = "upcoming_renewal_triggers"
_CLAIM_TTL_SECONDS = 10 * 365 * 86400


class UpcomingRenewalTriggerStore:
    def __init__(self, store: Any) -> None:
        self._s = store

    async def claim(self, subscription_id: str, period_end: int, *, now: int) -> bool:
        """`True` the first time THIS (subscription, period_end) pair is seen — the caller should
        send. `False` on every call after, including a later cycle's own claim under a NEW
        period_end (a different key, so it claims cleanly rather than staying stuck on the old
        one)."""
        if not subscription_id or not period_end:
            return False
        key = f"{subscription_id}:{int(period_end)}"
        return await self._s.claim(
            _COLL, key, {"subscription_id": subscription_id, "period_end": int(period_end),
                        "claimed_at": now},
            ttl_seconds=_CLAIM_TTL_SECONDS, now=float(now))
