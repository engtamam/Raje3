"""Which specific paid apps this tenant holds — the granular sibling of base_entitlement.py's
one all-or-nothing check. core/tools.py's `_TOOL_APP_KEYS` and core/conversation.py's
`PromptSection.app_keys` both filter against this SAME set, so a tool tied to "bookings" and a
persona rule tied to "bookings" can never disagree about whether this tenant holds it.

WHY NOT ASK operations-service's OWN services/operations/app/core/apps.py (it already computes
this exact set for the console's own AppGate) — that would add a THIRD peer dependency to a
service that already calls bookings-service, loyalty-service and billing-service directly. This
asks billing directly instead — the identical mechanism base_entitlement.py already uses one key
at a time, just fanned out concurrently over every key this service's tools/persona gate on.

`held(tenant)` returning `frozenset()` means "no EXTRA app beyond the base feature.whatsapp
subscription" — a tool or persona rule tagged with an app key is withheld, but every untagged
(general) tool/rule is never affected by this at all. See tools.py::tools_for_held_apps and
conversation.py::build_system_prompt for the two places this set is actually consumed.
"""
from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

# Every real app/console key (apps/console/src/apps.ts::APP_ROWS) that gates at least one tool or
# persona section in this service today. NOT every app in the catalogue — contacts/visit/rating/
# coupons gate nothing here; a tool or persona rule that starts depending on one of them adds its
# key here too, in the same change (see tools.py's own _TOOL_APP_KEYS docstring).
TOOL_APP_KEYS = (
    "feature.bookings", "feature.loyalty", "feature.mobile_requests",
    "feature.campaigns", "feature.insights.engine",
)


class NullHeldApps:
    """Holds everything — tests and local runs, and any deployment that never wired billing
    (same degrade-open convention as base_entitlement.py's NullBaseEntitlement)."""

    driver = "null"

    async def held(self, tenant: str) -> frozenset[str]:
        return frozenset(TOOL_APP_KEYS)


class HttpHeldApps:
    """billing-service's entitlement check, fanned out over every key in `keys` CONCURRENTLY —
    same stdlib-urllib call shape as base_entitlement.py's HttpBaseEntitlement, just returning the
    full held set instead of a single OR'd boolean."""

    driver = "http"

    def __init__(self, *, billing_url: str, check_path: str, token: str,
                 timeout: int = 8, keys: tuple[str, ...] = TOOL_APP_KEYS) -> None:
        self._url = billing_url.rstrip("/") + check_path
        self._token = token
        self._timeout = timeout
        self._keys = keys

    async def held(self, tenant: str) -> frozenset[str]:
        """Checked LIVE, every turn, never cached — same reasoning as base_entitlement.py's own
        `allowed()`: a lapsed app must stop gating its tools/persona on the very next reply, with
        no separate revocation job. A refusal, an error, or an outage all answer "not held" for
        that one key — fail closed toward the narrower experience, never toward offering a tool
        this tenant no longer pays for.

        OFF THE EVENT LOOP, and CONCURRENT across keys (asyncio.gather) — a sequential await per
        key would multiply this service's already-many peer round trips per turn by len(keys)."""
        if not tenant:
            return frozenset()
        results = await asyncio.gather(
            *(asyncio.to_thread(self._allowed_sync, tenant, key) for key in self._keys))
        return frozenset(key for key, ok in zip(self._keys, results) if ok)

    def _allowed_sync(self, tenant: str, key: str) -> bool:
        query = urllib.parse.urlencode({"tenant": tenant, "key": key})
        req = urllib.request.Request(
            f"{self._url}?{query}", method="GET",
            headers={"X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                out: dict[str, Any] = json.loads(resp.read() or b"{}")
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError):
            return False
        return bool(out.get("allowed"))


def build_held_apps(settings: Any) -> Any:
    """`http` when billing is wired, `null` otherwise — same convention as
    base_entitlement.py::build_base_entitlement."""
    url = getattr(settings, "BILLING_SERVICE_URL", "") or ""
    path = getattr(settings, "BILLING_CHECK_PATH", "") or ""
    if not url or not path:
        return NullHeldApps()
    return HttpHeldApps(billing_url=url, check_path=path,
                        token=getattr(settings, "INTERNAL_SERVICE_TOKEN", "") or "",
                        timeout=int(getattr(settings, "PEER_TIMEOUT_SECONDS", 8) or 8))
