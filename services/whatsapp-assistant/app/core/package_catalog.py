"""Read-only peer client for the shop's own packages (operations' /internal/operations/packages —
the same route insights reads, extended with `price_minor` for this service's own need: a
cross-sell suggestion naming a package is worthless without its real, owner-set price).

A PACKAGE'S PRICE IS SAFE TO STATE, UNLIKE THE ENGINE'S OWN SUGGESTION. See
core/related_services.py's own docstring on why an ordinary cross-sell reply may never mention a
discount — the engine returns no price at all for a bare pair of services. A package is different:
its price was typed by the owner himself and published as a real, bookable thing (operations'
Package.price_minor docstring), so naming it here is reading a fact, not inventing one.
"""
from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from typing import Any


class NullPackageCatalog:
    driver = "null"

    async def list_active(self, tenant: str) -> list[dict[str, Any]]:
        return []


class HttpPackageCatalog:
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
            # A peer outage degrades to "the assistant cannot name this package today" — the
            # conversation still runs; the cross-sell suggestion just falls back to a plain one.
            return []
        rows = data.get("packages") or []
        return [p for p in rows if isinstance(p, dict) and p.get("id") and p.get("active")]


def build(settings: Any) -> Any:
    if not settings.OPERATIONS_SERVICE_URL:
        return NullPackageCatalog()
    return HttpPackageCatalog(
        url=settings.OPERATIONS_SERVICE_URL, path=settings.OPERATIONS_PACKAGES_PATH,
        token=settings.INTERNAL_SERVICE_TOKEN, timeout=settings.PEER_TIMEOUT_SECONDS)
