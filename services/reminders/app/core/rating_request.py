"""What we are waiting to hear back — one row per rating request actually sent.

WHY THIS EXISTS. `send()` (adapters/message_sender — the ordinary template send, carrying a
`flow_token` only for this one kind) only sends; it does not know which visit the message was
about, and it must not — a sender that also remembers things is a sender two callers can disagree
about. The caller that DOES know is tick.py's own send step: it writes one row here immediately
before the send, keyed by the same `flow_token` it hands to `send()` — the SAME string, now, also
doubles as the path segment in the hosted rating page's own link (portal's `/r/{ref}`,
[[task-service-procedure-checklists]] phase 2) rather than a WhatsApp Flow's completion payload;
either way it is the ONLY thing that means anything to us when the customer answers — resolving it
here is how an answer becomes "this visit, this tenant" rather than a stray request from someone
who guessed a URL.

TWO READS, ONE DESTRUCTIVE. `get()` peeks without consuming — the rating PAGE's own load, which a
customer may open, read, and come back to later before submitting anything. `resolve()` deletes
the row it returns, at the one moment that actually matters: the real submit. A flow_token is a
single-use anchor there — a second submit for the same token (a duplicate form post, a customer
somehow submitting twice) finds nothing and is silently a no-op, never a second write to the same
visit.
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
        return self._row(row)

    async def get(self, flow_token: str) -> RatingRequest | None:
        """The row, WITHOUT consuming it — the hosted rating page's own read
        ([[task-service-procedure-checklists]] phase 2). A customer may open the link, look at
        it, and come back later before actually submitting; a page load must not spend the same
        single-use anchor `resolve()` is for. Only the real submit (still `resolve()`, unchanged)
        consumes it."""
        if not flow_token:
            return None
        row = await self._s.get(_COLL, flow_token)
        return self._row(row) if row is not None else None

    @staticmethod
    def _row(row: dict[str, Any]) -> RatingRequest:
        return RatingRequest(
            flow_token=str(row.get("flow_token") or ""), tenant=str(row.get("tenant") or ""),
            subject_ref=str(row.get("subject_ref") or ""),
            visit_id=str(row.get("visit_id") or ""), sent_at=int(row.get("sent_at") or 0))
