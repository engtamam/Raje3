"""The customer's pseudonym, from `operations` — the identifier this service needs for two
things: the DSAR fan-out (docs/خطة-تنفيذ-الحجوزات.md §6.5) and the `bookings.booking.changed`
event `reminders` keys its schedules on. Stdlib urllib client, same shape as duration_lookup and
visit_gateway.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request


class HttpSubjectRefLookup:
    def __init__(self, *, operations_url: str, path: str, token: str, timeout: int = 8) -> None:
        self._url = operations_url.rstrip("/") + path
        self._token = token
        self._timeout = timeout

    async def __call__(self, tenant: str, customer_id: str) -> str | None:
        """`None` on ANY failure — unreachable peer or a malformed reply — never a guessed or
        empty-string-as-success pseudonym. An empty string IS a valid, deliberate answer from the
        peer (an unknown customer); `None` means we could not ask at all, and the caller must
        treat the two differently (fail closed only on the second)."""
        body = json.dumps({"tenant": tenant, "customer_id": customer_id}).encode()
        req = urllib.request.Request(
            self._url, data=body, method="POST",
            headers={"Content-Type": "application/json", "X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                out = json.loads(resp.read() or b"{}")
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
            return None
        if "subject_ref" not in out:
            return None
        return str(out["subject_ref"])
