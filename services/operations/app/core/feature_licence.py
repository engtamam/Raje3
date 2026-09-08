"""One shape, any `feature.*` key — for every standalone app that joins the OR-gate in
api/subscribed.py after `feature.base` and `feature.whatsapp` did (base_licence.py,
whatsapp_licence.py).

WHY THIS FILE EXISTS AND THE OTHER TWO DO NOT SHARE IT. `whatsapp_licence.py`'s own docstring
says the choice explicitly: "deliberately a separate small file rather than a parametrised one...
two independently-priced apps checked two different ways is how one of them quietly stays free".
That was true for TWO keys, hand-written once each. It stops being true the moment a THIRD app
needs the same check — a shop deciding whether to gate `feature.contacts`, `feature.bookings` and
`feature.visit` behind their own hand-copied `NullXLicence`/`HttpXLicence` pair is exactly the
kind of decision that drifts: one of the three copies gets the tenant-empty check wrong, or the
timeout, or the JSON key, and nobody notices until that ONE app is free for everybody.

So every key from here on shares ONE tested implementation, parametrised by `KEY`
(`app.core.feature_licence.build_feature_licence(settings, "feature.contacts")`), and joining the
OR-gate in `subscribed.py` is genuinely one line: build the licence, wire it onto the container
under its own attribute name, add that attribute to the gate's list. Nothing here is copied.

SAME POSTURE AS EVERY OTHER LICENCE IN THIS FLEET: checked live, never cached, fails closed —
`allowed()` returns True, False, or None for "could not ask", identical to `HttpBaseLicence` and
`HttpWhatsappLicence`.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from starlette.concurrency import run_in_threadpool


class NullFeatureLicence:
    """Allows everything — tests and local runs. Refused in production by the same boot guard
    every other Null* licence in this fleet is (`assert_subscription_config_ok`, config.py)."""

    driver = "null"

    def __init__(self, key: str, allowed: bool | None = True) -> None:
        self.key = key
        self._allowed = allowed

    async def allowed(self, tenant: str) -> bool | None:
        return self._allowed


class HttpFeatureLicence:
    """billing-service's entitlement check for ONE `feature.*` key. True, False, or None for
    "could not ask" — same three-answer shape as `HttpBaseLicence`/`HttpWhatsappLicence`."""

    driver = "http"

    def __init__(self, *, key: str, billing_url: str, check_path: str, token: str,
                 timeout: int = 8) -> None:
        self.key = key
        self._url = billing_url.rstrip("/") + check_path
        self._token = token
        self._timeout = timeout

    async def allowed(self, tenant: str) -> bool | None:
        if not tenant:
            # No establishment on the credential is not a shop, and asking would be asking about
            # everybody. A definite no.
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
