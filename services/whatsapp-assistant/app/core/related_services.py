"""Read-only peer client for insights' association engine (core/associations.py, owned by
services/insights) — the SAME "frequently requested together" logic apps/console/src/ServiceGrid.tsx
already shows staff, reused rather than reimplemented, per the platform rule against duplicating a
peer's domain logic.

NEVER THE LIFT VALUE, NEVER A DISCOUNT. insights' own engine returns only a verdict and an anchor
id (core/associations.py's docstring: the arithmetic is the product's IP, deliberately invisible
outside that service) — there is no discount/price field anywhere in this response to begin with,
which is what makes the tool's contract in app/core/tools.py trivially unable to hand the model a
number to embellish. The output sanitizer (app/core/conversation.py's `_sanitize_reply`) is the
backstop for the same property, not the only defence.

THE PLAN GATE IS NOT BYPASSED. insights' internal route enforces the exact plan check its own
user-facing `/insights/associations` route does — a tenant who has not paid for the associations
indicator gets an empty list here too, same as on the dashboard.
"""
from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class NullRelatedServices:
    """No insights peer configured — the cross-sell tool simply has nothing to suggest."""
    driver = "null"

    async def related_to(self, tenant: str, service_id: str) -> list[str]:
        return []


class HttpRelatedServices:
    driver = "http"

    def __init__(self, *, url: str, path: str, token: str, timeout: int = 8) -> None:
        self._url = url.rstrip("/") + path
        self._token = token
        self._timeout = timeout

    async def related_to(self, tenant: str, service_id: str) -> list[str]:
        # OFF THE EVENT LOOP — see core/customer_lookup.py::HttpCustomerLookup.resolve.
        return await asyncio.to_thread(self._related_to_sync, tenant, service_id)

    def _related_to_sync(self, tenant: str, service_id: str) -> list[str]:
        qs = urllib.parse.urlencode({"tenant": tenant, "service_id": service_id})
        req = urllib.request.Request(
            f"{self._url}?{qs}", method="GET", headers={"X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                if not 200 <= resp.status < 300:
                    return []
                data: dict[str, Any] = json.loads(resp.read() or b"{}")
        except (urllib.error.URLError, OSError, ValueError):
            # A peer outage must not block the booking flow it is only decorating — the customer
            # still gets their booking, just without a cross-sell suggestion this turn.
            return []
        related = data.get("related") or []
        return [str(x) for x in related if isinstance(x, str)]


def build(settings: Any) -> Any:
    if not settings.INSIGHTS_SERVICE_URL:
        return NullRelatedServices()
    return HttpRelatedServices(
        url=settings.INSIGHTS_SERVICE_URL, path=settings.INSIGHTS_ASSOCIATED_SERVICES_PATH,
        token=settings.INTERNAL_SERVICE_TOKEN, timeout=settings.PEER_TIMEOUT_SECONDS)
