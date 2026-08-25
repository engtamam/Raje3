"""The third question this service asks `operations`: each candidate operator's own working-hours
OVERRIDE, batched per basket search rather than one call per operator.

`operations` owns `Operator.working_hours` — bookings does not, and does not import
`operations`' code. This is a stdlib urllib client of `POST /internal/operations/staff-hours`,
same shape as `app/adapters/duration_lookup/http.py`.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request


class HttpStaffHoursLookup:
    def __init__(self, *, operations_url: str, path: str, token: str, timeout: int = 8) -> None:
        self._url = operations_url.rstrip("/") + path
        self._token = token
        self._timeout = timeout

    async def __call__(self, tenant: str, operator_ids: tuple[str, ...]) -> dict[str, dict | None]:
        """`{}` on ANY failure — unreachable, malformed, or a status the peer refused — so every
        candidate operator is then treated as "inherits the shop's own hours" (the caller's own
        default when a key is simply absent), never as narrower hours nobody actually set. A `null`
        value for an operator that DID resolve means exactly the same thing, said by the peer
        itself rather than assumed."""
        body = json.dumps({"tenant": tenant, "operator_ids": list(operator_ids)}).encode()
        req = urllib.request.Request(
            self._url, data=body, method="POST",
            headers={"Content-Type": "application/json", "X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                out = json.loads(resp.read() or b"{}")
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
            return {}
        raw = out.get("working_hours")
        return raw if isinstance(raw, dict) else {}
