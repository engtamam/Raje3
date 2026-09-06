"""Resolve a tenant id to the shop's display name AND its AI-assistant notes — for the persona this
service builds, never for anything billed or legal (see the peer route's own docstring on why the
name can drift after a rename).

SAME SHAPE AS customer_lookup.py: a peer call to operations, guarded the same way, degrading to a
null adapter rather than failing the whole request when unconfigured. The one place either is read
at all in this service — build_system_prompt (core/conversation.py) is the only consumer, and this
module never caches (see conversation.py's own note on why it deliberately does not wrap this in a
per-tenant cache the way it once did for the name alone): a rename, or an edit to the owner's notes,
is visible on the assistant's very next reply.

ONE ROUND TRIP, NOT TWO. Both fields live on the SAME operations response (`/internal/operations/
shop-name`, extended to also answer `ai_notes`) rather than a second peer call — an owner iterating
on his own instructions would otherwise pay for a second HTTP hop, and every turn already pays for
this one.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

# What the persona says when no shop name is available — never a literal shop name hardcoded here,
# and never a blank identity either (see build_system_prompt's docstring on why a generic assistant
# reads as untrustworthy for a WhatsApp receptionist).
GENERIC_SHOP_LABEL = "هذا المحل"


@dataclass(frozen=True)
class ShopContext:
    name: str
    #: The owner's own free-text instructions to the assistant, or "" if he wrote none, the
    #: feature is off (AI_NOTES_ENABLED=false on the operations side), or the peer call failed.
    #: NEVER pre-redacted here — build_system_prompt does that itself, right before merging, as a
    #: second, independent check (see that function's own docstring).
    ai_notes: str = ""


class NullShopIdentity:
    """No operations peer configured, or the lookup failed — the conversation still runs with the
    generic label and no notes rather than refusing to answer."""
    driver = "null"

    async def resolve(self, tenant: str) -> ShopContext:
        return ShopContext(name=GENERIC_SHOP_LABEL)


class HttpShopIdentity:
    driver = "http"

    def __init__(self, *, url: str, path: str, token: str, timeout: int = 8) -> None:
        self._url = url.rstrip("/") + path
        self._token = token
        self._timeout = timeout

    async def resolve(self, tenant: str) -> ShopContext:
        body = json.dumps({"tenant": tenant}).encode()
        req = urllib.request.Request(
            self._url, data=body, method="POST",
            headers={"Content-Type": "application/json", "X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                if not 200 <= resp.status < 300:
                    return ShopContext(name=GENERIC_SHOP_LABEL)
                data: dict[str, Any] = json.loads(resp.read() or b"{}")
        except (urllib.error.URLError, OSError, ValueError):
            # Fail open to the generic label and no notes, not an exception that would stall the
            # whole reply — neither is worth failing a customer's turn over.
            return ShopContext(name=GENERIC_SHOP_LABEL)
        name = str(data.get("name") or "").strip()
        notes = str(data.get("ai_notes") or "").strip()
        return ShopContext(name=name or GENERIC_SHOP_LABEL, ai_notes=notes)


def build(settings: Any) -> Any:
    if not settings.OPERATIONS_SERVICE_URL:
        return NullShopIdentity()
    return HttpShopIdentity(
        url=settings.OPERATIONS_SERVICE_URL, path=settings.OPERATIONS_SHOP_NAME_PATH,
        token=settings.INTERNAL_SERVICE_TOKEN, timeout=settings.PEER_TIMEOUT_SECONDS)
