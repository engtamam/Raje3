"""Does this tenant hold the CORE PLATFORM subscription at all — `feature.base`.

WHAT THIS FIXES. "واتساب الذكي (مستقل)" (deploy/seed/plans.json) is bought with no base
underneath it, by design (operations/app/core/subscribe.py::is_standalone). Every data source
`_context_block` reads and every tool this service offers beyond plain conversation — the real
customer catalogue, the booking calendar, loyalty points, cross-sell suggestions — is OPERATIONS
data, and operations data belongs to a shop that has bought the base (or an app that itself
requires the base, e.g. bookings or loyalty; `may_add` refuses either without one). A standalone
buyer never wrote a single row into any of those stores through a route that would have required
it, so this check is a genuine boundary — not a convenience — for the one exception that matters:

A SHOP THAT USED TO HOLD A BASE AND CANCELLED IT keeps its old data in operations (cancellation
never deletes — see the platform's own "data stays, sending stops" rule), and `customer_lookup`/
`points`/`package_catalog` would otherwise still find and serve that OLD data forever, even though
the subscription that earned it is gone. This is what actually stops that: checked LIVE, every
turn, never cached — the instant a base lapses, the very next reply degrades, with no separate
revocation job and no stale grant window (same posture as licence.py's own feature.whatsapp check).

THE SERVICE CATALOGUE IS DELIBERATELY NOT GATED BY THIS. A standalone buyer may write his own
service catalogue in operations with no base at all (product decision, this session) — see
`conversation.py`'s own call site: `self._catalog` is read unconditionally, this check governs
everything else.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

# The key as billing knows it. One string, one file.
KEY = "feature.base"


class NullBaseEntitlement:
    """Allows everything — tests and local runs, and any deployment that never wired billing
    (matching every other Null*/degrade-open-to-full-service default in this service)."""

    driver = "null"

    async def allowed(self, tenant: str) -> bool:
        return True


class HttpBaseEntitlement:
    """billing-service's entitlement check for `feature.base`, same stdlib-urllib shape as this
    service's other peer clients (core/licence.py, core/wallet_balance.py)."""

    driver = "http"

    def __init__(self, *, billing_url: str, check_path: str, token: str,
                 timeout: int = 8) -> None:
        self._url = billing_url.rstrip("/") + check_path
        self._token = token
        self._timeout = timeout

    async def allowed(self, tenant: str) -> bool:
        """True only when billing SAYS yes. A refusal, an error, or an outage all answer False —
        fail closed toward the narrower (standalone) experience, never toward leaking a lapsed
        shop's old operations data."""
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


def build_base_entitlement(settings: Any) -> Any:
    """`http` when billing is wired, `null` otherwise — same convention as core/licence.py's own
    `build_licence`. Not boot-guarded to refuse null in prod like the PAID licence is: degrading
    open here means "behave as a full-service tenant", which is the pre-existing behaviour for
    every deployment before this feature shipped, not a new leak."""
    url = getattr(settings, "BILLING_SERVICE_URL", "") or ""
    path = getattr(settings, "BILLING_CHECK_PATH", "") or ""
    if not url or not path:
        return NullBaseEntitlement()
    return HttpBaseEntitlement(billing_url=url, check_path=path,
                               token=getattr(settings, "INTERNAL_SERVICE_TOKEN", "") or "",
                               timeout=int(getattr(settings, "PEER_TIMEOUT_SECONDS", 8) or 8))
