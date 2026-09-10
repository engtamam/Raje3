"""Has this establishment bought the smart assistant at all? — `feature.whatsapp`.

WHAT THIS FIXES. `feature.whatsapp` is an independent app on the price list, the same shape as
`feature.campaigns` (services/campaigns/app/core/licence.py, which this file mirrors on purpose —
two independently-priced apps checked two different ways is how one of them quietly stays free).
Ordinary service messages (a visit confirmation, a reminder) are NOT this key — those stay inside
the base subscription, unchanged. This key covers exactly one thing: an AI-composed reply and an
AI-driven booking over WhatsApp. A shop that has not bought it gets no AI turn at all — not a
degraded one, not a free trial run past this file.

CHECKED AT THE ACT, LIVE, NEVER CACHED — same posture as campaigns' own licence.py, and for the
same reason: "instant, no grace period" falls out of asking billing fresh on every reply rather
than needing anything to expire. See `conversation.py`'s own call site for exactly where this is
asked (as early as possible, and again right before the LLM call — the two places an outage or a
lapsed subscription must stop a reply from going out).

IT FAILS CLOSED. A shop that has not bought this must never receive a reply that looks like it —
showing the feature to somebody who has not paid for it is a leak that cannot be taken back; a
refusal during a billing outage is a customer told to wait, which resolves itself.
"""
from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

# The key as billing knows it. One string, one file.
KEY = "feature.whatsapp"


class NullLicence:
    """Allows everything — tests and local runs.

    REFUSED IN PRODUCTION by the boot guard in config.py, for the same reason every other
    NullLicence/NullQuota in this fleet is: a deployment that cannot read entitlements is a
    deployment giving the feature away for free, silently, for as long as nobody looks.
    """

    driver = "null"

    async def allowed(self, tenant: str) -> bool:
        return True


class HttpLicence:
    """billing-service's entitlement check. stdlib urllib, like every peer client in this service
    (core/wallet_balance.py, core/points.py) — there is no shared internal_http adapter here."""

    driver = "http"

    def __init__(self, *, billing_url: str, check_path: str, token: str,
                 timeout: int = 8) -> None:
        self._url = billing_url.rstrip("/") + check_path
        self._token = token
        self._timeout = timeout

    async def allowed(self, tenant: str) -> bool:
        """True only when billing SAYS yes. A refusal, an error, or an outage all answer False —
        the caller (conversation.py) decides what the customer reads for that.

        OFF THE EVENT LOOP — see core/customer_lookup.py::HttpCustomerLookup.resolve."""
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


def build_licence(settings: Any) -> Any:
    """`http` when billing is wired, `null` otherwise — and the boot guard refuses null in prod."""
    url = getattr(settings, "BILLING_SERVICE_URL", "") or ""
    path = getattr(settings, "BILLING_CHECK_PATH", "") or ""
    if not url or not path:
        return NullLicence()
    return HttpLicence(billing_url=url, check_path=path,
                       token=getattr(settings, "INTERNAL_SERVICE_TOKEN", "") or "",
                       timeout=int(getattr(settings, "PEER_TIMEOUT_SECONDS", 8) or 8))
