"""What we are waiting to hear back — one row per rating Flow actually sent.

WHY THIS EXISTS. `send()` (adapters/message_sender — the ordinary template send, carrying a
`flow_token` only for this one kind) only sends; it does not know which visit the message was
about, and it must not — a sender that also remembers things is a sender two callers can disagree
about. The caller that DOES know is tick.py's own send step: it writes one row here immediately
before the send, keyed by the same `flow_token` it hands to `send()`. When the customer's answer
comes back on the bus, that token is the ONLY thing the reply carries that means anything to us —
resolving it here is how a reply becomes "this visit, this tenant" rather than a stray message
from a number we do not recognise.

ONE ROW, RESOLVED ONCE. `resolve()` deletes the row it returns — a flow_token is a single-use
anchor: a second inbound reply for the same token (Meta's own retry, or a customer somehow
re-submitting) finds nothing and is silently a no-op, never a second write to the same visit.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_COLL = "rating_requests"


@dataclass
class RatingRequest:
    flow_token: str
    tenant: str
    subject_ref: str
    visit_id: str
    sent_at: int


class RatingRequestStore:
    def __init__(self, store: Any) -> None:
        self._s = store

    async def remember(self, *, flow_token: str, tenant: str, subject_ref: str,
                       visit_id: str, now: int) -> None:
        await self._s.put(_COLL, flow_token, {
            "flow_token": flow_token, "tenant": tenant, "subject_ref": subject_ref,
            "visit_id": visit_id, "sent_at": now})

    async def resolve(self, flow_token: str) -> RatingRequest | None:
        """The row for this token, consumed — a second call for the same token finds nothing."""
        if not flow_token:
            return None
        row = await self._s.get(_COLL, flow_token)
        if row is None:
            return None
        await self._s.delete(_COLL, flow_token)
        return RatingRequest(
            flow_token=str(row.get("flow_token") or ""), tenant=str(row.get("tenant") or ""),
            subject_ref=str(row.get("subject_ref") or ""),
            visit_id=str(row.get("visit_id") or ""), sent_at=int(row.get("sent_at") or 0))
