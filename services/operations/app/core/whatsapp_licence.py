"""Is a STANDALONE WhatsApp subscription live — `feature.whatsapp`, checked the same shape as
`base_licence.py`'s own `feature.base` check, deliberately a separate small file rather than a
parametrised one (same convention whatsapp-assistant's own licence.py follows relative to
campaigns' — two independently-priced apps checked two different ways is how one of them quietly
stays free).

WHY THIS EXISTS AT ALL. `subscribed_write` (api/subscribed.py) refuses every mutating route unless
`feature.base` is live — correct for every shop until "واتساب الذكي (مستقل)" (plans.json), which is
bought with NO base at all. The WhatsApp connect routes (`api/v1/connect.py`) are the one door a
standalone buyer must be able to open, so they need "base OR standalone whatsapp", not base alone —
see `api/subscribed.py::subscribed_write_or_whatsapp`, the only caller of this file.

SAME POSTURE AS EVERY OTHER LICENCE HERE: checked live, never cached, fails closed.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from starlette.concurrency import run_in_threadpool

# The key as billing knows it. One string, one file.
KEY = "feature.whatsapp"


class NullWhatsappLicence:
    """Allows everything — tests and local runs. Refused in production by the same boot guard
    every other Null* licence in this fleet is (see base_licence.py's own comment)."""

    driver = "null"

    def __init__(self, allowed: bool | None = True) -> None:
        self._allowed = allowed

    async def allowed(self, tenant: str) -> bool | None:
        return self._allowed


class HttpWhatsappLicence:
    """billing-service's entitlement check for `feature.whatsapp`. True, False, or None for
    "could not ask" — same three-answer shape as `HttpBaseLicence`."""

    driver = "http"

    def __init__(self, *, billing_url: str, check_path: str, token: str,
                 timeout: int = 8) -> None:
        self._url = billing_url.rstrip("/") + check_path
        self._token = token
        self._timeout = timeout

    async def allowed(self, tenant: str) -> bool | None:
        if not tenant:
            return False
        query = urllib.parse.urlencode({"tenant": tenant, "key": KEY})
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


def build_whatsapp_licence(settings: Any) -> Any:
    """`http` when billing is wired, `null` otherwise — and the boot guard refuses null in prod."""
    url = getattr(settings, "BILLING_SERVICE_URL", "") or ""
    path = getattr(settings, "BILLING_CHECK_PATH", "") or ""
    if not url or not path:
        return NullWhatsappLicence()
    return HttpWhatsappLicence(billing_url=url, check_path=path,
                               token=getattr(settings, "INTERNAL_SERVICE_TOKEN", "") or "",
                               timeout=int(getattr(settings, "PEER_TIMEOUT_SECONDS", 8) or 8))
