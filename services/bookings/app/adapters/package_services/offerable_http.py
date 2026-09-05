"""Is a package bookable for a given day — `bookings`' schedule question, always asked against the
APPOINTMENT'S OWN date, never "now" (see operations' core/scheduling.py module docstring). `False`
on ANY failure — unreachable peer, an unknown package — never a guessed "yes": a schedule check
that fails open would let a booking through on a day the owner never turned the package on for.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request


class HttpPackageOfferable:
    def __init__(self, *, operations_url: str, path: str, token: str, timeout: int = 8) -> None:
        self._url = operations_url.rstrip("/") + path
        self._token = token
        self._timeout = timeout

    async def __call__(self, tenant: str, package_id: str, at: int) -> bool:
        body = json.dumps({"tenant": tenant, "package_id": package_id, "at": int(at)}).encode()
        req = urllib.request.Request(
            self._url, data=body, method="POST",
            headers={"Content-Type": "application/json", "X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                if not 200 <= resp.status < 300:
                    return False
                out = json.loads(resp.read() or b"{}")
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
            return False
        return bool(out.get("offerable"))
