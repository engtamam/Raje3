"""Does this establishment own ONE APP (a feature key), asked of billing-service directly.

`base_licence.py` asks the identical question for exactly one key (`feature.base`) and is kept as
its own small file because the base licence carries a REFUSAL an owner reads (`require_write`,
`LAPSED`/`CANNOT_ASK` sentences) — a policy, not just a fact. This module is the plain fact alone,
reusable for any app key a later feature needs to check (today: `feature.rating`) without a second
copy of the same HTTP call for each one.

THREE ANSWERS, NEVER TWO. `True`/`False`/`None` ("could not ask") — collapsing the third into
`False` is exactly the bug class `base_licence.py`'s own module docstring warns about: a billing
outage must never read as "this shop does not own the app it pays for". Here specifically, the
caller (scheduling) treats `None` the same as `False` (skip the rating message, fall back to the
plain confirmation) — a missed rating message for one visit during an outage costs nothing a retry
would fix anyway, unlike refusing a paid write.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from starlette.concurrency import run_in_threadpool


class NullAppEntitlement:
    """Answers from what a test put in it. Production requires the http driver."""

    driver = "null"

    def __init__(self, owned: set[str] | None = None) -> None:
        self._owned = set(owned or set())

    async def allowed(self, tenant: str, key: str) -> bool | None:
        return key in self._owned


class HttpAppEntitlement:
    """billing-service's entitlement check, asked with an arbitrary key — same peer, same route
    `base_licence.py` uses for `feature.base`."""

    driver = "http"

    def __init__(self, *, billing_url: str, check_path: str, token: str,
                 timeout: int = 8) -> None:
        self._url = billing_url.rstrip("/") + check_path
        self._token = token
        self._timeout = timeout

    async def allowed(self, tenant: str, key: str) -> bool | None:
        if not tenant:
            return False
        query = urllib.parse.urlencode({"tenant": tenant, "key": key})
        req = urllib.request.Request(f"{self._url}?{query}",
                                     headers={"X-Internal-Token": self._token})

        def _fetch() -> dict[str, Any]:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:    # nosec B310
                return json.loads(resp.read() or b"{}")

        try:
            out = await run_in_threadpool(_fetch)
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
            return None
        return bool(out.get("allowed"))


def build_app_entitlement(settings: Any) -> Any:
    """`http` when billing is wired, `null` otherwise — mirrors `build_base_licence` exactly."""
    url = getattr(settings, "BILLING_SERVICE_URL", "") or ""
    path = getattr(settings, "BILLING_CHECK_PATH", "") or ""
    if not url or not path:
        return NullAppEntitlement()
    return HttpAppEntitlement(billing_url=url, check_path=path,
                              token=getattr(settings, "INTERNAL_SERVICE_TOKEN", "") or "",
                              timeout=int(getattr(settings, "PEER_TIMEOUT_SECONDS", 8) or 8))
