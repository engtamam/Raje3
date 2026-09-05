"""The package sibling of `http.py` — which operators may perform EVERY component of a package,
already intersected by `operations` (see its own `/internal/operations/package-eligibility`
docstring). `None` on ANY failure means "no restriction found", same convention as the service
lookup's `{}`-on-failure — an outage must never narrow eligibility below what the shop configured.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request


class HttpPackageEligibility:
    def __init__(self, *, operations_url: str, path: str, token: str, timeout: int = 8) -> None:
        self._url = operations_url.rstrip("/") + path
        self._token = token
        self._timeout = timeout

    async def __call__(self, tenant: str, package_id: str) -> list[str] | None:
        body = json.dumps({"tenant": tenant, "package_id": package_id}).encode()
        req = urllib.request.Request(
            self._url, data=body, method="POST",
            headers={"Content-Type": "application/json", "X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                out = json.loads(resp.read() or b"{}")
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
            return None
        raw = out.get("eligible_staff_ids")
        return list(raw) if isinstance(raw, list) else None
