"""The COEXISTENCE catch-up sweep: walk notification-service's durable echo feed forward, note every
owner-sent message so the AI goes quiet on that customer for a while (app/core/owner_presence.py).

Imitates app/core/inbound_poll.py::InboundPoller exactly — same shape, same reasoning. ONE CURSOR,
PERSISTED ONLY AFTER THE WRITES: a crash between ingesting a page and saving its cursor re-reads and
re-processes the same page next tick, which is free here (`note_owner_reply` is an idempotent
overwrite, not an append) — while advancing the cursor first would be the one mistake that lets an
echo go unseen forever.

`{}` FROM THE FEED MEANS «WE COULD NOT ASK», never «no echoes» — the watermark holds still on that
answer, same as the inbound poller, because a missed echo means the AI answers over the owner.

PER-TENANT LICENCE CHECK, INSIDE THE ROW LOOP — this sweep is fleet-wide, one call covers every
tenant's echoes, but a tenant whose AI is off (`ToggleGatedLicence`: billing entitlement AND
operations' own per-shop toggle) has nothing to protect: `compose_reply` never runs for it either
way, so noting a hand-off for it would only be an unnecessary write of customer-contact data. The
row is still consumed and still advances the cursor exactly like an allowed tenant's — only
`note_owner_reply` is skipped — so the poller never gets stuck re-reading a disallowed tenant's
echoes forever.
"""
from __future__ import annotations

from typing import Any

from app.core.owner_presence import note_owner_reply

COEXISTENCE_WATERMARKS = "wa_coexistence_watermarks"
CURSOR_KEY = "echo_poll"


class CoexistencePoller:
    def __init__(self, *, container: Any, settings: Any, logger: Any, max_pages: int = 20) -> None:
        self._container = container
        self._settings = settings
        self._logger = logger
        # BOUNDED, same reasoning as InboundPoller._max_pages: progress beats completeness.
        self._max_pages = max(1, int(max_pages))

    async def _cursor(self) -> str:
        row = await self._container.datastore.get(COEXISTENCE_WATERMARKS, CURSOR_KEY)
        return str((row or {}).get("cursor") or "")

    async def _advance(self, cursor: str) -> None:
        await self._container.datastore.put(
            COEXISTENCE_WATERMARKS, CURSOR_KEY, {"id": CURSOR_KEY, "cursor": str(cursor)})

    async def run(self, *, now: int) -> dict[str, Any]:
        feed = getattr(self._container, "coexistence_feed", None)
        if feed is None or not getattr(feed, "configured", False):
            # SAID OUT LOUD — see InboundPoller.run for why silently returning zeros here would
            # read exactly like «every echo accounted for».
            return {"read": 0, "noted": 0, "pages": 0, "configured": False}

        cooldown = int(getattr(self._settings, "COEXISTENCE_HUMAN_COOLDOWN_SECONDS", 1800) or 0)
        cursor = await self._cursor()
        seen = noted = pages = 0
        for _ in range(self._max_pages):
            page = await feed.echoes(after=cursor)
            if not page:
                return {"read": seen, "noted": noted, "pages": pages, "configured": True,
                        "unreadable": True}
            rows = list(page.get("messages") or [])
            if not rows:
                break
            for row in rows:
                seen += 1
                tenant = str(row.get("tenant") or "")
                contact = str(row.get("contact") or "")
                if not tenant or not contact or cooldown <= 0:
                    continue
                # PER-ROW, NOT PER-RUN — this sweep is fleet-wide (one page can hold several
                # tenants' echoes), and each tenant's own AI-enabled state (billing entitlement
                # AND operations' per-shop toggle, `ToggleGatedLicence`) can differ from the next
                # row's. A disallowed tenant's echo is still counted toward `seen` and still
                # advances the cursor with everyone else's — only the write is skipped, since
                # `compose_reply` never runs for that tenant anyway and there is nothing to
                # protect it from; recording it would just be a needless customer-contact write.
                licence = getattr(self._container, "licence", None)
                if licence is not None and not await licence.allowed(tenant):
                    continue
                await note_owner_reply(self._container, tenant=tenant, contact=contact,
                                       now=now, cooldown_seconds=cooldown)
                noted += 1
            # AFTER THE WRITES, NEVER BEFORE — see module docstring.
            nxt = str(page.get("cursor") or "")
            if not nxt or nxt == cursor:
                break
            cursor = nxt
            await self._advance(cursor)
            pages += 1

        return {"read": seen, "noted": noted, "pages": pages, "configured": True}
