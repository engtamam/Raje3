"""Has this establishment bought WhatsApp catalog ordering at all? -- `feature.whatsapp_delivery_orders`.

A SEPARATE APP FROM `feature.whatsapp` (core/licence.py), DELIBERATELY. The two happen to live in
the same microservice, but a shop buys them independently, and this file exists purely so neither
can silently borrow the other's entitlement: catalog ordering must work for a shop that never
bought the AI assistant, and the AI assistant's own subscription state/toggle must never be
touched by anything in this file.

CHECKED AT THE ACT, LIVE, NEVER CACHED, FAILS CLOSED -- same posture as `core/licence.py`, mirrored
on purpose rather than shared, so the two apps' entitlement checks never accidentally merge back
into one code path.
"""
from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

# The key as billing knows it. One string, one file -- never `feature.whatsapp`.
KEY = "feature.whatsapp_delivery_orders"


class NullOrderLicence:
    """Allows everything -- tests and local runs. Refused in production by the same boot guard
    every other NullLicence in this fleet is."""

    driver = "null"

    async def allowed(self, tenant: str) -> bool:
        return True


class HttpOrderLicence:
    """billing-service's entitlement check for this app's own key."""

    driver = "http"

    def __init__(self, *, billing_url: str, check_path: str, token: str,
                 timeout: int = 8) -> None:
        self._url = billing_url.rstrip("/") + check_path
        self._token = token
        self._timeout = timeout

    async def allowed(self, tenant: str) -> bool:
        return await asyncio.to_thread(self._allowed_sync, tenant)

    def _allowed_sync(self, tenant: str) -> bool:
        if not tenant:
            return False
        query = urllib.parse.urlencode({"tenant": tenant, "key": KEY})
        req = urllib.request.Request(
            f"{self._url}?{query}", method="GET",
            headers={"X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                out: dict[str, Any] = json.loads(resp.read() or b"{}")
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError):
            return False
        return bool(out.get("allowed"))


def build_order_licence(settings: Any) -> Any:
    """`http` when billing is wired, `null` otherwise -- and the boot guard refuses null in prod."""
    url = getattr(settings, "BILLING_SERVICE_URL", "") or ""
    path = getattr(settings, "BILLING_CHECK_PATH", "") or ""
    if not url or not path:
        return NullOrderLicence()
    return HttpOrderLicence(billing_url=url, check_path=path,
                            token=getattr(settings, "INTERNAL_SERVICE_TOKEN", "") or "",
                            timeout=int(getattr(settings, "PEER_TIMEOUT_SECONDS", 8) or 8))
