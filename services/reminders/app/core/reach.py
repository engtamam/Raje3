"""How many DIFFERENT people this shop has messaged in the last 24 hours.

THE CEILING COUNTS PEOPLE, NOT MESSAGES, and getting that wrong is expensive in the direction
nobody notices. WhatsApp allows a business to START conversations with a number of UNIQUE
customers per rolling 24 hours — 250 before the business is verified, 2,000 after (spec §6.2.2).
Three messages to one customer consume ONE of that allowance.

Our other counter counts messages, and using it here would report the shop as closer to its
ceiling than it is. We would then hold back sends WhatsApp would have accepted — quietly, with no
error anywhere, costing him customers he was entitled to reach. A meter that errs toward silence
in a product whose entire purpose is bringing people back is the worst error available to us.

────────────────────────────────────────────────────────────────────────────────────────────────
ROLLING, NEVER A CALENDAR DAY

The window slides: a customer messaged at 23:00 still counts at 22:00 the next evening. A midnight
reset would let a shop send its whole allowance at 23:30 and the whole allowance again at 00:30 —
and WhatsApp, which is measuring the real window, would refuse the second half while our own
numbers said everything was fine.

So the record is per person with the time we reached them, and the count is of those inside the
window at the moment we ask.

────────────────────────────────────────────────────────────────────────────────────────────────
IT ONLY COUNTS CONVERSATIONS WE START

Replying inside a window the customer opened is free and unlimited, and does not touch the
ceiling. Everything this service sends is business-initiated, so everything it sends counts — but
the distinction belongs in the name, because the day something answers a customer it must not be
counted here.

────────────────────────────────────────────────────────────────────────────────────────────────
AND IT IS READ ON THE HOT PATH

Once per send, before the send. So it is a bounded read of one tenant's window, and the rows are
pruned as they age rather than accumulating a row per customer per day for ever.

THE SUBJECT IS ALREADY A PSEUDONYM. This stores `subject_ref` and a timestamp — the same
pseudonym everything else here holds, so a service that never knew a phone number still does not.
"""
from __future__ import annotations

import time
from typing import Any

REACHED = "reached_24h"

# WhatsApp's window today. A DEFAULT, not a constant: it is Meta's number, they have changed their
# messaging rules more than once, and a value of theirs frozen into our code is a value that keeps
# being right until the morning it silently is not. Deployments set REACH_WINDOW_SECONDS.
DEFAULT_WINDOW = 24 * 3600


def _now() -> int:
    return int(time.time())


class Reach:
    """The unique-customer window for one establishment."""

    def __init__(self, store: Any, *, window: int = DEFAULT_WINDOW) -> None:
        self._s = store
        self._window = int(window)

    @staticmethod
    def _key(tenant: str, subject_ref: str) -> str:
        return f"{tenant}|{subject_ref}"

    async def record(self, tenant: str, subject_ref: str, *, now: int | None = None) -> None:
        """Note that we started a conversation with this person.

        ONE ROW PER PERSON, OVERWRITTEN. The question is "when did we last reach them", never "how
        many times" — a row per message would grow without bound and answer a question the ceiling
        does not ask.
        """
        at = _now() if now is None else now
        key = self._key(tenant, subject_ref)
        await self._s.put(REACHED, key, {"id": key, "tenant": tenant,
                                         "subject_ref": subject_ref, "at": at})

    async def count(self, tenant: str, *, now: int | None = None, limit: int = 5000
                    ) -> tuple[int, bool]:
        """Distinct people reached inside the window. Returns (count, truncated) — sorted newest
        first, so hitting `limit` means a tenant with more than `limit` rows total may have had
        some genuinely-in-window rows pushed past the cap; `truncated` is honest about that rather
        than silently under-reporting, same contract as this service's other capped reads."""
        at = _now() if now is None else now
        rows, _ = await self._s.find(REACHED, {"tenant": tenant}, limit=limit,
                                     sort=("at", "desc"))
        rows = rows or []
        return (sum(1 for r in rows if at - int(r.get("at") or 0) < self._window),
               len(rows) >= limit)

    async def would_be_new(self, tenant: str, subject_ref: str, *,
                           now: int | None = None) -> bool:
        """Whether reaching this person would consume one of the day's allowance.

        SOMEBODY ALREADY REACHED INSIDE THE WINDOW IS FREE — a second message to them costs
        nothing against the ceiling. This is what makes the difference between counting people and
        counting messages worth the extra table: a shop sending a confirmation and a follow-up to
        the same customer uses one.
        """
        at = _now() if now is None else now
        row = await self._s.get(REACHED, self._key(tenant, subject_ref))
        if row is None:
            return True
        return at - int(row.get("at") or 0) >= self._window

    async def prune(self, *, now: int | None = None, limit: int = 5000) -> int:
        """Drop what has aged out. Returns how many.

        Called by the tick rather than by a sweeper of its own: the rows are only meaningful for a
        day, and a table that is never pruned turns a bounded read into an unbounded one — the
        exact failure the read was written to avoid.
        """
        at = _now() if now is None else now
        rows = await self._s.scan_all(REACHED, limit)
        gone = 0
        for row in rows or []:
            if at - int(row.get("at") or 0) >= self._window:
                await self._s.delete(REACHED, row["id"])
                gone += 1
        return gone
