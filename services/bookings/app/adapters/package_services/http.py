"""What a package IS, as far as `bookings` needs to know: its component service ids — resolved
once, at booking creation, and stamped onto `Booking.service_ids` so the picker/calendar card can
still name what was booked without this service holding its own copy of the catalogue.

`None` when the package is unknown/retired — the caller (`BookingOperations.create`) turns that
into an explicit refusal, same posture as an unconfigured service duration.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request


class HttpPackageServices:
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
        raw = out.get("service_ids")
        return list(raw) if isinstance(raw, list) else None
