"""The catch-up sweep: walk notification-service's durable inbound feed forward, ingest anything
the bus subscription in app/main.py might have missed.

Imitates services/reminders/app/core/receipts.py::Receipts exactly — same shape, same reasoning,
same problem (an at-most-once bus that can silently drop an event). ONE CURSOR, PERSISTED ONLY
AFTER THE WRITES: the feed is read forward, every row in the page is ingested, and only THEN is the
returned `cursor` saved as the new watermark. A crash between those two steps re-reads and
re-ingests the same page on the next tick — free, because `ingest_inbound_message` dedups by wamid
through the SAME inbound_store the bus path uses — while advancing the cursor first (before the
writes landed) would be the one mistake that skips a message forever.

`{}` FROM THE FEED MEANS «WE COULD NOT ASK», never «no messages» — the watermark holds still on
that answer, exactly as reminders' Receipts.run does, because a window skipped here is a customer
message recorded as never received, for ever.
"""
from __future__ import annotations

from typing import Any

INBOUND_WATERMARKS = "wa_inbound_watermarks"
CURSOR_KEY = "inbound_poll"


class InboundPoller:
    def __init__(self, *, container: Any, settings: Any, logger: Any, max_pages: int = 20) -> None:
        self._container = container
        self._settings = settings
        self._logger = logger
        # BOUNDED, same reasoning as reminders' Receipts._max_pages: this sweep runs again next
        # tick — progress beats completeness, and an unbounded loop on a busy fleet turns a
        # scheduled tick into an outage.
        self._max_pages = max(1, int(max_pages))

    async def _cursor(self) -> str:
        row = await self._container.datastore.get(INBOUND_WATERMARKS, CURSOR_KEY)
        return str((row or {}).get("cursor") or "")

    async def _advance(self, cursor: str) -> None:
        await self._container.datastore.put(
            INBOUND_WATERMARKS, CURSOR_KEY, {"id": CURSOR_KEY, "cursor": str(cursor)})

    async def run(self, *, auditor: Any) -> dict[str, Any]:
        feed = getattr(self._container, "inbound_feed", None)
        if feed is None or not getattr(feed, "configured", False):
            # SAID OUT LOUD — see reminders' Receipts.run for why silently returning zeros here
            # would read exactly like «every message accounted for».
            return {"read": 0, "ingested": 0, "duplicates": 0, "pages": 0, "configured": False}

        from app.core.inbound_ingest import ingest_inbound_message
        from app.core.inbound_parse import parse_message

        cursor = await self._cursor()
        seen = ingested = duplicates = pages = 0
        for _ in range(self._max_pages):
            page = await feed.messages(after=cursor)
            if not page:
                return {"read": seen, "ingested": ingested, "duplicates": duplicates,
                        "pages": pages, "configured": True, "unreadable": True}
            rows = list(page.get("messages") or [])
            if not rows:
                break
            for row in rows:
                seen += 1
                message = row.get("message") or {}
                kind, text, reply_id = parse_message(message)
                result = await ingest_inbound_message(
                    container=self._container, logger=self._logger, settings=self._settings,
                    auditor=auditor,
                    tenant=str(row.get("tenant") or ""), wamid=str(row.get("wamid") or ""),
                    from_number=str(row.get("from") or ""), kind=kind, text=text,
                    reply_id=reply_id, raw_payload=row)
                if result.get("processed"):
                    ingested += 1
                elif result.get("reason") == "duplicate":
                    duplicates += 1
            # AFTER THE WRITES, NEVER BEFORE — see module docstring.
            nxt = str(page.get("cursor") or "")
            if not nxt or nxt == cursor:
                break
            cursor = nxt
            await self._advance(cursor)
            pages += 1

        return {"read": seen, "ingested": ingested, "duplicates": duplicates, "pages": pages,
                "configured": True}
