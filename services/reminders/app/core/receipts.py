"""«هل وصلت رسالتي؟» — the one question this service could not answer about its own work.

WHAT WAS MISSING. `SendLog.read_at` and `clicked_at` were declared for delivery facts and fed by
NOTHING: the sender returned no handle, so no receipt could ever be matched to a row. Every message
this product has sent is recorded as `sent` and nothing more — which is «we handed it to Meta»,
not «it reached anybody». The engagement score reads absence as «we have not heard», and that was
literally true, permanently, for every customer.

WHAT ARRIVED. The platform now persists WhatsApp status webhooks against the delivery they belong
to (`provider_message_id`, the wamid both sides carry) and exposes them as an ORDERED, CURSORED
catch-up read. So this file is the consumer, and it is the same shape as `ingest`'s visit sweep and
`loyalty`'s recovery — because it has the same problem.

THE CURSOR MOVES ONLY AFTER THE WRITES. The status bus is at-most-once: a pod restarting through a
receipt hears it never. Advancing on receipt would move the watermark past the very rows the
catch-up exists to collect. Read forward, apply, THEN persist the cursor — a crash re-reads a page
and applies it twice, which is free because both writes are idempotent (a timestamp set to the same
value), and a skipped page is a message recorded as unread for ever.

AND AN UNREADABLE PEER DOES NOT ADVANCE ANYTHING. `{}` from the reader means «we could not ask»,
which is not «no receipts» — treating them alike would skip a window nobody can go back to.

DELIVERED AND READ ARE DIFFERENT FACTS, kept in different fields. Delivered is about the handset;
read is about the person. A product that collapsed them would call a man whose phone received a
message at 3am «engaged», and then decide what to send him next on that basis.
"""
from __future__ import annotations

from typing import Any

# See `core/ingest.VISIT_WATERMARKS`: this one tracks RECEIPTS and that one tracks visits,
# and until now both were called `WATERMARKS`.
RECEIPT_WATERMARKS = "reminders_watermarks"
CURSOR_KEY = "receipts"

# What the peer calls each state, mapped to the field it lands in. A status we do not recognise is
# IGNORED rather than guessed at — a new WhatsApp state must not silently become a read receipt.
DELIVERED = "delivered"
READ = "read"


class Receipts:
    """`run()` — match delivery receipts back to the sends they belong to."""

    def __init__(self, *, store: Any, log: Any, feed: Any, telemetry: Any = None,
                 max_pages: int = 20) -> None:
        self._store = store
        self._log = log
        self._feed = feed
        self._t = telemetry
        # BOUNDED. This is a repair that runs again in minutes; progress beats completeness, and an
        # unbounded loop on a busy fleet turns a cron into an outage.
        self._max_pages = max(1, int(max_pages))

    async def _cursor(self) -> str:
        row = await self._store.get(RECEIPT_WATERMARKS, CURSOR_KEY)
        return str((row or {}).get("cursor") or "")

    async def _advance(self, cursor: str) -> None:
        await self._store.put(RECEIPT_WATERMARKS, CURSOR_KEY,
                              {"id": CURSOR_KEY, "cursor": str(cursor)})

    async def run(self) -> dict[str, Any]:
        if self._feed is None or not getattr(self._feed, "configured", False):
            # SAID OUT LOUD. Returning zeros with no reason would read as «every message accounted
            # for», which is the silent-success shape this whole file answers.
            return {"read": 0, "matched": 0, "pages": 0, "configured": False}

        cursor = await self._cursor()
        seen = matched = pages = 0
        for _ in range(self._max_pages):
            page = await self._feed.receipts(after=cursor)
            if not page:
                return {"read": seen, "matched": matched, "pages": pages,
                        "configured": True, "unreadable": True}
            rows = list(page.get("receipts") or [])
            if not rows:
                break
            for r in rows:
                seen += 1
                if await self._apply(r):
                    matched += 1
            # AFTER THE WRITES, NEVER BEFORE.
            nxt = str(page.get("cursor") or "")
            if not nxt or nxt == cursor:
                break
            cursor = nxt
            await self._advance(cursor)
            pages += 1

        if self._t is not None:
            self._t.event("reminders_receipts", read=seen, matched=matched)
        return {"read": seen, "matched": matched, "pages": pages, "configured": True}

    async def _apply(self, receipt: dict[str, Any]) -> bool:
        status = str(receipt.get("receipt_status") or "")
        if status not in (DELIVERED, READ):
            return False
        delivery_id = str(receipt.get("delivery_id") or "")
        if not delivery_id:
            return False
        row = await self._log.by_delivery_id(delivery_id)
        if row is None:
            # A RECEIPT FOR A SEND WE DID NOT MAKE — another service on the same notification
            # peer, or a row already trimmed by retention. Not an error, and never invented.
            return False
        ts = int(float(receipt.get("receipt_ts") or 0))
        field = "read_at" if status == READ else "delivered_at"
        # MONOTONIC, so a page re-read after a crash and an out-of-order `delivered` arriving
        # behind a `read` both leave the row saying the furthest thing that actually happened.
        if ts <= int(row.get(field) or 0):
            return True
        row[field] = ts
        await self._log.update(row)
        return True
