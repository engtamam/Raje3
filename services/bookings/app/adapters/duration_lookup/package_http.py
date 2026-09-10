"""The package sibling of `http.py` — what a PACKAGE costs in minutes, right now.

A separate class rather than a `package_id` branch inside `HttpDurationLookup`: the two ask
different peer routes (`/service-durations` vs `/package-durations`) with a different body shape,
and folding both into one class would make every caller pass an unused field either way. Same
"None on ANY failure, never a guessed number" contract as the service lookup.
"""
from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request


class HttpPackageDurationLookup:
    def __init__(self, *, operations_url: str, path: str, token: str, timeout: int = 8) -> None:
        self._url = operations_url.rstrip("/") + path
        self._token = token
        self._timeout = timeout

    async def __call__(self, tenant: str, package_id: str) -> int | None:
        # OFF THE EVENT LOOP — urllib has no async mode.
        return await asyncio.to_thread(self._call_sync, tenant, package_id)

    def _call_sync(self, tenant: str, package_id: str) -> int | None:
        body = json.dumps({"tenant": tenant, "package_id": package_id}).encode()
        req = urllib.request.Request(
            self._url, data=body, method="POST",
            headers={"Content-Type": "application/json", "X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                out = json.loads(resp.read() or b"{}")
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
            return None
        value = out.get("duration_minutes")
        return int(value) if value is not None else None
