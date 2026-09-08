"""The catch-up read: WhatsApp COEXISTENCE message echoes forward from a cursor, oldest first.

Byte-for-byte the same idiom as app/adapters/inbound_feed/http.py::HttpInboundFeed — same
X-Internal-Token peer-call shape, same `{}` means «we could not ask» (never «no messages») so the
consumer's watermark holds still rather than skipping a window it can never see again. Reads
notification-service's `GET /internal/whatsapp/coexistence/echoes?after=&limit=` (platform v0.18.56)
— an echo is a message the shop OWNER sent from their own phone's WhatsApp Business app on the same
number; see app/core/coexistence_poll.py for what this service does with one.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class HttpCoexistenceEchoFeed:
    def __init__(self, *, url: str, path: str, token: str, timeout: int = 8,
                 page: int = 200) -> None:
        self._url = (url.rstrip("/") + path) if url else ""
        self._token = token
        self._timeout = timeout
        self._page = max(1, min(1000, int(page)))

    @property
    def configured(self) -> bool:
        return bool(self._url)

    async def echoes(self, *, after: str = "") -> dict[str, Any]:
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


class NullCoexistenceEchoFeed:
    """Configured-off, and it says so rather than returning an empty page — see NullInboundFeed's
    twin docstring for why `configured=False` must never look like an empty page: an empty page
    advances the cursor and reads as «all caught up»."""
    configured = False

    async def echoes(self, *, after: str = "") -> dict[str, Any]:
        return {}


def build(settings: Any) -> Any:
    # A LOCAL gate, deliberately separate from notification-service's own WHATSAPP_COEXISTENCE_ENABLED
    # (which decides whether the platform records echoes at all): the two are meant to flip together
    # at install time (see deploy/bring-up.sh), but this service must not poll a feed the platform has
    # not turned on — an unreachable-looking 404 on every tick is not the same as "no work to do".
    url = getattr(settings, "NOTIFICATION_SERVICE_URL", "") or ""
    if not url or not getattr(settings, "WHATSAPP_COEXISTENCE_ENABLED", False):
        return NullCoexistenceEchoFeed()
    return HttpCoexistenceEchoFeed(
        url=url,
        path=getattr(settings, "NOTIFICATION_COEXISTENCE_ECHOES_PATH",
                     "/internal/whatsapp/coexistence/echoes"),
        token=getattr(settings, "INTERNAL_SERVICE_TOKEN", ""),
        timeout=int(getattr(settings, "PEER_TIMEOUT_SECONDS", 8) or 8),
        page=int(getattr(settings, "COEXISTENCE_POLL_PAGE_SIZE", 200) or 200))
