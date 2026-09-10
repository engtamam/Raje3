"""What we are waiting to hear back — one row per subscription-renewal Flow actually sent.

MIRRORS services/reminders' `rating_request.py` exactly. Whatever sends the renewal Flow (not
built yet — see app/adapters/renewal_provider.py in services/operations for the provider half)
writes one row here, keyed by the same `flow_token` it seeds the Flow with, immediately before the
send. When the reply comes back on the bus, that token is the ONLY thing it carries that means
anything to us — resolving it here is how a reply becomes "reply to THIS shop, on THIS number"
rather than a stray message.

ONE ROW, RESOLVED ONCE. `resolve()` deletes the row it returns — a flow_token is a single-use
anchor: a second inbound reply for the same token (Meta's own retry) finds nothing and is silently
a no-op, never a second delivery of the same pay link.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_COLL = "renewal_requests"


@dataclass
class RenewalRequest:
    flow_token: str
    tenant: str
    to: str
    sent_at: int


class RenewalRequestStore:
    def __init__(self, store: Any) -> None:
        self._s = store

    async def remember(self, *, flow_token: str, tenant: str, to: str, now: int) -> None:
        await self._s.put(_COLL, flow_token, {
            "flow_token": flow_token, "tenant": tenant, "to": to, "sent_at": now})

    async def resolve(self, flow_token: str) -> RenewalRequest | None:
        """The row for this token, consumed — a second call for the same token finds nothing."""
        if not flow_token:
            return None
        row = await self._s.get(_COLL, flow_token)
        if row is None:
            return None
        await self._s.delete(_COLL, flow_token)
        return RenewalRequest(
            flow_token=str(row.get("flow_token") or ""), tenant=str(row.get("tenant") or ""),
            to=str(row.get("to") or ""), sent_at=int(row.get("sent_at") or 0))
