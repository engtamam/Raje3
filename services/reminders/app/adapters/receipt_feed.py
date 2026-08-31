"""The read that tells us whether our messages arrived.

ONE PAGE, ONE CURSOR, AND NO OPINIONS. The peer orders the receipts and returns the next cursor;
deriving one here from the last row is the one-line mistake that either replays everything or skips
a receipt, and the peer already knows the answer.

`{}` MEANS «WE COULD NOT ASK», never «no receipts». The consumer holds its watermark on that
answer, because a window skipped here is a message recorded as never delivered for ever.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
from typing import Any
from app.adapters import internal_http


class HttpReceiptFeed:
    def __init__(self, *, url: str, path: str, token: str, timeout: int = 8,
                 page: int = 200) -> None:
        self._url = (url.rstrip("/") + path) if url else ""
        self._token = token
        self._timeout = timeout
        self._page = max(1, min(1000, int(page)))

    @property
    def configured(self) -> bool:
        return bool(self._url)

    async def receipts(self, *, after: str = "") -> dict[str, Any]:
        if not self._url:
            return {}
        query = urllib.parse.urlencode({"after": after or "", "limit": self._page})
        try:
            # Built in adapters/internal_http.py, the one place this service attaches the token.
            status, raw = internal_http.send(
                f"{self._url}?{query}", timeout=self._timeout, method="GET", token=self._token)
            if not 200 <= status < 300:
                return {}
            out: dict[str, Any] = json.loads(raw or b"{}")
            return out
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
            return {}


class NullReceiptFeed:
    """Configured-off, and it says so rather than returning an empty page.

    The difference matters: an empty page advances nothing and reads as «all caught up», while
    `configured=False` makes the consumer report NOT_CONFIGURED — the deployment can then be told
    it is missing a wire instead of believing every message was delivered.
    """
    configured = False

    async def receipts(self, *, after: str = "") -> dict[str, Any]:
        return {}


def build(settings: Any) -> Any:
    url = getattr(settings, "NOTIFICATION_SERVICE_URL", "") or ""
    if not url:
        return NullReceiptFeed()
    return HttpReceiptFeed(
        url=url,
        path=getattr(settings, "NOTIFICATION_RECEIPTS_PATH",
                     "/internal/notifications/receipts"),
        token=getattr(settings, "INTERNAL_SERVICE_TOKEN", ""),
        timeout=int(getattr(settings, "PEER_TIMEOUT_SECONDS", 8) or 8))
