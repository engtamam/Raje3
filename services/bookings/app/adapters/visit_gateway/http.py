"""The booking->visit gateway (docs/خطة-تنفيذ-الحجوزات.md §4) — the ONE way an attended booking
becomes a real Visit. A stdlib urllib client of `operations`'
`POST /internal/operations/visits/from-customer`, same shape as `duration_lookup/http.py`.

NEVER a direct write to a Visit row from this service — that is the whole point of §4's
architecture decision (a peer call, not a shared table): `operations` owns the Visit shape, its
loyalty/campaign side effects, and its own idempotency; bookings asks it to happen rather than
reimplementing it.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request


class HttpVisitGateway:
    def __init__(self, *, operations_url: str, path: str, token: str, timeout: int = 8) -> None:
        self._url = operations_url.rstrip("/") + path
        self._token = token
        self._timeout = timeout

    async def create(self, *, tenant: str, customer_id: str, service_ids: tuple[str, ...],
                     operator_id: str, branch_id: str, note: str, idempotency_key: str,
                     occurred_at: int) -> dict | None:
        """`None` on ANY failure — unreachable peer, a 404 (the customer vanished), a 400 (a
        service id the catalogue no longer knows). The caller (`BookingOperations.attend`) turns
        that into an explicit refusal — never a booking marked attended with no visit behind it."""
        body = json.dumps({
            "tenant": tenant, "customer_id": customer_id, "service_ids": list(service_ids),
            "operator_id": operator_id, "branch_id": branch_id, "note": note,
            "idempotency_key": idempotency_key, "occurred_at": occurred_at,
        }).encode()
        req = urllib.request.Request(
            self._url, data=body, method="POST",
            headers={"Content-Type": "application/json", "X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                return json.loads(resp.read() or b"{}")
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
            return None
