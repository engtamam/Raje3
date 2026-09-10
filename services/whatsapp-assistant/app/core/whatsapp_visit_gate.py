"""Has this tenant's owner opted in to visit-registration over WhatsApp — read BEFORE the Flow
ever opens for an identified staff sender. See services/operations' `core/whatsapp_visit_flag.py`
own docstring for why this defaults OFF for every shop.

UNREADABLE IS OFF, NEVER A GUESS — same "the two mistakes are not equal" posture the owner's own
switch already holds server-side: a peer hiccup here must never widen who may record a visit.
"""
from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class NullWhatsAppVisitGate:
    """No operations peer configured. Every tenant reads as 'not opted in' — the trigger simply
    never opens the visit Flow, same fail-toward-off posture as the real client."""
    driver = "null"

    async def enabled(self, tenant: str) -> bool:
        return False


class HttpWhatsAppVisitGate:
    driver = "http"

    def __init__(self, *, url: str, path: str, token: str, timeout: int = 8) -> None:
        self._url = url.rstrip("/") + path
        self._token = token
        self._timeout = timeout

    async def enabled(self, tenant: str) -> bool:
        if not tenant:
            return False
        # OFF THE EVENT LOOP — see core/customer_lookup.py::HttpCustomerLookup.resolve.
        return await asyncio.to_thread(self._enabled_sync, tenant)

    def _enabled_sync(self, tenant: str) -> bool:
        query = urllib.parse.urlencode({"tenant": tenant})
        req = urllib.request.Request(
            f"{self._url}?{query}", headers={"X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                if not 200 <= resp.status < 300:
                    return False
                data: dict[str, Any] = json.loads(resp.read() or b"{}")
        except (urllib.error.URLError, OSError, ValueError):
            return False
        return bool(data.get("enabled"))


def build(settings: Any) -> Any:
    if not settings.OPERATIONS_SERVICE_URL:
        return NullWhatsAppVisitGate()
    return HttpWhatsAppVisitGate(
        url=settings.OPERATIONS_SERVICE_URL,
        path=settings.OPERATIONS_WHATSAPP_VISIT_REGISTRATION_PATH,
        token=settings.INTERNAL_SERVICE_TOKEN, timeout=settings.PEER_TIMEOUT_SECONDS)
