"""The catch-up read: inbound WhatsApp messages forward from a cursor, oldest first, bounded.

Imitates services/reminders/app/adapters/receipt_feed.py::HttpReceiptFeed exactly — same
X-Internal-Token peer-call idiom, same `{}` means «we could not ask» (never «no messages») so the
consumer's watermark holds still rather than skipping a window it can never see again. Reads
notification-service's `GET /internal/whatsapp/inbound?after=&limit=` (platform v0.16.38, commit
31e556e): each row carries the wamid, sender, tenant (already resolved from the receiving
phone_number_id), and Meta's raw message object — see app/core/inbound_parse.py for how that raw
object becomes this service's flat kind/text/reply_id.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class HttpInboundFeed:
    def __init__(self, *, url: str, path: str, token: str, timeout: int = 8,
                 page: int = 200) -> None:
        self._url = (url.rstrip("/") + path) if url else ""
        self._token = token
        self._timeout = timeout
        self._page = max(1, min(1000, int(page)))

    @property
    def configured(self) -> bool:
        return bool(self._url)

    async def messages(self, *, after: str = "") -> dict[str, Any]:
        if not self._url:
            return {}
        query = urllib.parse.urlencode({"after": after or "", "limit": self._page})
        req = urllib.request.Request(
            f"{self._url}?{query}", method="GET",
            headers={"X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                if not 200 <= resp.status < 300:
                    return {}
                out: dict[str, Any] = json.loads(resp.read() or b"{}")
            return out
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
            return {}


class NullInboundFeed:
    """Configured-off, and it says so rather than returning an empty page — see HttpReceiptFeed's
    twin docstring in services/reminders for why `configured=False` must never look like an empty
    page: an empty page advances the cursor and reads as «all caught up»."""
    configured = False

    async def messages(self, *, after: str = "") -> dict[str, Any]:
        return {}


def build(settings: Any) -> Any:
    url = getattr(settings, "NOTIFICATION_SERVICE_URL", "") or ""
    if not url:
        return NullInboundFeed()
    return HttpInboundFeed(
        url=url,
        path=getattr(settings, "NOTIFICATION_INBOUND_PATH", "/internal/whatsapp/inbound"),
        token=getattr(settings, "INTERNAL_SERVICE_TOKEN", ""),
        timeout=int(getattr(settings, "PEER_TIMEOUT_SECONDS", 8) or 8),
        page=int(getattr(settings, "INBOUND_POLL_PAGE_SIZE", 200) or 200))
