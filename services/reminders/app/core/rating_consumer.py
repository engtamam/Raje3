"""Turn one inbound `whatsapp.message` bus event into a written rating, or nothing.

THE BUS IS AT-MOST-ONCE (same fact `main.py`'s other subscriptions already document) — a rating
reply this consumer misses is not retried by anything, because Meta does not resend an nfm_reply
once its own delivery succeeded. That is an accepted gap for THIS phase: a full catch-up read
(mirroring `Ingest`'s `/internal/whatsapp/inbound` poll for ordinary messages) is future work if the
miss rate turns out to matter, not built ahead of evidence that it does.
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from app.core.rating_reply import parse_rating_reply
from app.core.rating_request import RatingRequestStore


class RatingConsumer:
    def __init__(self, *, requests: RatingRequestStore, writer: Any,
                bonus_points: Callable[[str], Awaitable[int]] | None = None) -> None:
        self._requests = requests
        self._writer = writer
        # OPTIONAL, LIKE `Ingest`'s OWN `rating_eligible` CALLBACK (main.py). A closure over the
        # container rather than the container itself, so this class stays testable with a plain
        # async lambda and does not need to know `app_entitlement` or `RatingSettingsStore` exist.
        self._bonus_points = bonus_points

    async def handle(self, message: dict[str, Any]) -> bool:
        """`True` iff a rating was written this call. `False` for everything else — not a rating
        reply, an unknown or already-consumed flow_token, or a write operations could not record
        — and NEVER raises: one malformed or unrelated inbound message must not stop this consumer
        from reading every message after it, the same contract `Ingest`'s own handlers hold.
        """
        reply = parse_rating_reply(message)
        if reply is None:
            return False
        pending = await self._requests.resolve(reply.flow_token)
        if pending is None:
            return False
        # COMPUTED HERE, FRESH, NEVER READ BACK FROM `pending` — the request row is only a
        # flow_token -> visit anchor (rating_request.py's own docstring), not a snapshot of what
        # the shop's points setting was worth at send time; that value is not durably recorded
        # anywhere in this product. See the operations rating route's own docstring for the full
        # design decision this mirrors.
        points = await self._bonus_points(pending.tenant) if self._bonus_points else 0
        return await self._writer.write(
            tenant=pending.tenant, visit_id=pending.visit_id, rating=reply.stars,
            feedback_text=reply.comment, subject_ref=pending.subject_ref, rating_points=points)
