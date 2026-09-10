"""Read-only peer client for the shop's own priced service catalogue (operations'
/internal/operations/catalogue-with-prices — a separate route from the one insights uses, because
insights never prices anything and this service must: a customer asking "how much" or a
cross-sell suggestion is worthless without a real price the model never invented).

NOT PII. A price list is not personally identifying — nothing here is a name or a phone number —
so it is exempt from the opaque-reference rule that governs customer data, and is sent to the model
in full (see app/core/context_builder.py and app/ports/llm.py's `context_block` docstring for why
a trimmed catalogue produces ungrounded, useless suggestions).
"""
from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from typing import Any


class NullServiceCatalog:
    driver = "null"

    async def list_active(self, tenant: str) -> list[dict[str, Any]]:
        return []


class HttpServiceCatalog:
    driver = "http"

    def __init__(self, *, url: str, path: str, token: str, timeout: int = 8) -> None:
        self._url = url.rstrip("/") + path
        self._token = token
        self._timeout = timeout

    async def list_active(self, tenant: str) -> list[dict[str, Any]]:
        # OFF THE EVENT LOOP — see core/customer_lookup.py::HttpCustomerLookup.resolve.
        return await asyncio.to_thread(self._list_active_sync, tenant)

    def _list_active_sync(self, tenant: str) -> list[dict[str, Any]]:
        body = json.dumps({"tenant": tenant}).encode()
        req = urllib.request.Request(
            self._url, data=body, method="POST",
            headers={"Content-Type": "application/json", "X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                if not 200 <= resp.status < 300:
                    return []
                data: dict[str, Any] = json.loads(resp.read() or b"{}")
        except (urllib.error.URLError, OSError, ValueError):
            # A peer outage degrades to "the assistant does not know today's price list" — the
            # conversation still runs, it just cannot ground a price-specific answer this turn.
            return []
        services = data.get("services") or []
        return [s for s in services if isinstance(s, dict) and s.get("id")]


def build(settings: Any) -> Any:
    if not settings.OPERATIONS_SERVICE_URL:
        return NullServiceCatalog()
    return HttpServiceCatalog(
        url=settings.OPERATIONS_SERVICE_URL, path=settings.OPERATIONS_CATALOGUE_WITH_PRICES_PATH,
        token=settings.INTERNAL_SERVICE_TOKEN, timeout=settings.PEER_TIMEOUT_SECONDS)
