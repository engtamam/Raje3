"""The one question this service asks a peer: what does a set of service_ids cost in minutes.

`operations` owns `Service.duration_minutes` — bookings does not, and does not import
`operations`' code (services deploy independently). This is a stdlib urllib client of
`POST /internal/operations/service-durations`, same shape as `app/core/licence.py`'s HttpLicence.
"""
from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request


class HttpDurationLookup:
    def __init__(self, *, operations_url: str, path: str, token: str, timeout: int = 8) -> None:
        self._url = operations_url.rstrip("/") + path
        self._token = token
        self._timeout = timeout

    async def __call__(self, tenant: str, service_ids: tuple[str, ...],
                       quantities: dict[str, int] | None = None) -> int | None:
        """`None` on ANY failure — unreachable, malformed, or the peer's own "not configured"
        answer — never a guessed number. A peer outage refusing a booking create is correct: the
        alternative is inventing a duration nobody set.

        `quantities` — how many of each service, so a booking for "2× غسيل خارجي" asks for a slot
        twice as long, not the single-unit duration a bare id list would give. Missing entry means
        one, same default `operations`' own peer route already carries."""
        # OFF THE EVENT LOOP — urllib has no async mode.
        return await asyncio.to_thread(self._call_sync, tenant, service_ids, quantities or {})

    def _call_sync(self, tenant: str, service_ids: tuple[str, ...],
                   quantities: dict[str, int] | None = None) -> int | None:
        body = json.dumps({"tenant": tenant, "service_ids": list(service_ids),
                          "quantities": quantities or {}}).encode()
        req = urllib.request.Request(
            self._url, data=body, method="POST",
            headers={"Content-Type": "application/json", "X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                out = json.loads(resp.read() or b"{}")
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
            return None
        value = out.get("duration_minutes")
        if value is None:
            return None
        n = int(value)
        return n if 0 < n <= 10_080 else None  # 7 days — no real booking is ever longer
