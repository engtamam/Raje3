"""One shape, any `feature.*` key — same file, same reasoning, as
`operations/app/core/feature_licence.py`'s own docstring (this service's twin, both peers of the
same billing-service).

WHY REMINDERS HAS NO `feature.reminders`/`feature.messaging` KEY OF ITS OWN. Reminders is not a
sellable product — it is the shared machinery (scheduling, adaptive rhythm, engagement scoring)
BEHIND a customer event a shop already pays to record: a visit (`feature.visit`) or an appointment
(`feature.bookings`). The product decision (2026-09-10, retiring الأساس): messaging is a FEATURE
of an event-recording app, not an app of its own — a shop that owns either app gets the messaging
that comes with it; a shop that owns neither has no customer events to message about in the first
place. See `api/subscribed.py::subscribed_write`'s own comment for the concrete OR.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from starlette.concurrency import run_in_threadpool


class NullFeatureLicence:
    """Allows everything — tests and local runs."""

    driver = "null"

    def __init__(self, key: str, allowed: bool | None = True) -> None:
        self.key = key
        self._allowed = allowed

    async def allowed(self, tenant: str) -> bool | None:
        return self._allowed


class HttpFeatureLicence:
    """billing-service's entitlement check for ONE `feature.*` key. True, False, or None for
    "could not ask"."""

    driver = "http"

    def __init__(self, *, key: str, billing_url: str, check_path: str, token: str,
                 timeout: int = 8) -> None:
        self.key = key
        self._url = billing_url.rstrip("/") + check_path
        self._token = token
        self._timeout = timeout

    async def allowed(self, tenant: str) -> bool | None:
        if not tenant:
            return False
        query = urllib.parse.urlencode({"tenant": tenant, "key": self.key})
        req = urllib.request.Request(f"{self._url}?{query}",
                                     headers={"X-Internal-Token": self._token})

        def _fetch() -> dict[str, Any]:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                return json.loads(resp.read() or b"{}")

        try:
            out = await run_in_threadpool(_fetch)
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
            return None
        return bool(out.get("allowed"))


def build_feature_licence(settings: Any, key: str) -> Any:
    """`http` when billing is wired, `null` otherwise — and the boot guard refuses null in prod."""
    url = getattr(settings, "BILLING_SERVICE_URL", "") or ""
    path = getattr(settings, "BILLING_CHECK_PATH", "") or ""
    if not url or not path:
        return NullFeatureLicence(key)
    return HttpFeatureLicence(key=key, billing_url=url, check_path=path,
                              token=getattr(settings, "INTERNAL_SERVICE_TOKEN", "") or "",
                              timeout=int(getattr(settings, "PEER_TIMEOUT_SECONDS", 8) or 8))
