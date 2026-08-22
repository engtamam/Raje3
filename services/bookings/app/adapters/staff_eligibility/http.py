"""The second question this service asks `operations`: which operators may perform each of a
chosen set of services.

`operations` owns `Service.eligible_staff_ids` — bookings does not, and does not import
`operations`' code (services deploy independently). This is a stdlib urllib client of
`POST /internal/operations/service-eligibility`, same shape as
`app/adapters/duration_lookup/http.py`.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request


class HttpStaffEligibility:
    def __init__(self, *, operations_url: str, path: str, token: str, timeout: int = 8) -> None:
        self._url = operations_url.rstrip("/") + path
        self._token = token
        self._timeout = timeout

    async def __call__(self, tenant: str, service_ids: tuple[str, ...]) -> dict[str, list[str] | None]:
        """`{}` on ANY failure — unreachable, malformed, or a status the peer refused — so the
        caller treats an outage exactly like "no restriction found" rather than inventing a
        narrower eligible-staff set than the shop actually configured. A missing key for a given
        service id (peer reachable, service unknown to it) is likewise "no restriction" from the
        caller's point of view, never a refusal."""
        body = json.dumps({"tenant": tenant, "service_ids": list(service_ids)}).encode()
        req = urllib.request.Request(
            self._url, data=body, method="POST",
            headers={"Content-Type": "application/json", "X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                out = json.loads(resp.read() or b"{}")
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
            return {}
        raw = out.get("eligible_staff_ids")
        return raw if isinstance(raw, dict) else {}
