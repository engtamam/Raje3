"""Resolve a tenant id to the shop's display name — for the persona this service builds, never for
anything billed or legal (see the peer route's own docstring on why it can drift after a rename).

SAME SHAPE AS customer_lookup.py: a peer call to operations, guarded the same way, degrading to a
null adapter rather than failing the whole request when unconfigured. The one place a shop's name
is read at all in this service — build_system_prompt (core/conversation.py) is the only consumer,
and it never rests anywhere else (no caching here beyond what a caller chooses to add) so a rename
on the shop's side is visible on the assistant's next reply, not stuck behind a stale cache.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

# What the persona says when no shop name is available — never a literal shop name hardcoded here,
# and never a blank identity either (see build_system_prompt's docstring on why a generic assistant
# reads as untrustworthy for a WhatsApp receptionist).
GENERIC_SHOP_LABEL = "هذا المحل"


class NullShopIdentity:
    """No operations peer configured, or the lookup failed — the conversation still runs with the
    generic label rather than refusing to answer."""
    driver = "null"

    async def resolve(self, tenant: str) -> str:
        return GENERIC_SHOP_LABEL


class HttpShopIdentity:
    driver = "http"

    def __init__(self, *, url: str, path: str, token: str, timeout: int = 8) -> None:
        self._url = url.rstrip("/") + path
        self._token = token
        self._timeout = timeout

    async def resolve(self, tenant: str) -> str:
        body = json.dumps({"tenant": tenant}).encode()
        req = urllib.request.Request(
            self._url, data=body, method="POST",
            headers={"Content-Type": "application/json", "X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                if not 200 <= resp.status < 300:
                    return GENERIC_SHOP_LABEL
                data: dict[str, Any] = json.loads(resp.read() or b"{}")
        except (urllib.error.URLError, OSError, ValueError):
            # Fail open to the generic label, not an exception that would stall the whole reply —
            # a shop's name is a nicety of tone, not something worth failing a customer's turn over.
            return GENERIC_SHOP_LABEL
        name = str(data.get("name") or "").strip()
        return name or GENERIC_SHOP_LABEL


def build(settings: Any) -> Any:
    if not settings.OPERATIONS_SERVICE_URL:
        return NullShopIdentity()
    return HttpShopIdentity(
        url=settings.OPERATIONS_SERVICE_URL, path=settings.OPERATIONS_SHOP_NAME_PATH,
        token=settings.INTERNAL_SERVICE_TOKEN, timeout=settings.PEER_TIMEOUT_SECONDS)
