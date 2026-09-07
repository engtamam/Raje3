"""Read-only peer client for bookings-service's own `/internal/bookings/by-actor` — every booking
THIS SERVICE made (`created_by="whatsapp-assistant"`, booking_assignment.py's own `ACTOR`
constant), for `invoice_report.py`'s average-invoice-value stat.

SAME SHAPE as service_catalog.py/package_catalog.py: a Null driver when BOOKINGS_SERVICE_URL is
unset (a deployment still on `BOOKING_PROVIDER_DRIVER="config"` never reaches a real bookings peer
at all — see that setting's own note in config.py), an Http driver otherwise. A peer outage
degrades the SAME way those two already do: the report simply cannot see this window's bookings
this call, never a crash, never a silently wrong number.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


class NullBookingActorReport:
    driver = "null"

    async def by_actor(self, tenant: str, created_by: str, *, branch_id: str = "",
                       since: int | None = None, until: int | None = None) -> dict[str, Any]:
        return {"bookings": [], "truncated": False}


class HttpBookingActorReport:
    driver = "http"

    def __init__(self, *, url: str, path: str, token: str, timeout: int = 8) -> None:
        self._url = url.rstrip("/") + path
        self._token = token
        self._timeout = timeout

    async def by_actor(self, tenant: str, created_by: str, *, branch_id: str = "",
                       since: int | None = None, until: int | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {"tenant": tenant, "created_by": created_by}
        if branch_id:
            body["branch_id"] = branch_id
        if since is not None:
            body["since"] = since
        if until is not None:
            body["until"] = until
        req = urllib.request.Request(
            self._url, data=json.dumps(body).encode(), method="POST",
            headers={"Content-Type": "application/json", "X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                if not 200 <= resp.status < 300:
                    return {"bookings": [], "truncated": False}
                data: dict[str, Any] = json.loads(resp.read() or b"{}")
        except (urllib.error.URLError, OSError, ValueError):
            return {"bookings": [], "truncated": False}
        rows = data.get("bookings") or []
        return {"bookings": [b for b in rows if isinstance(b, dict) and b.get("id")],
                "truncated": bool(data.get("truncated"))}


def build(settings: Any) -> Any:
    if not settings.BOOKINGS_SERVICE_URL:
        return NullBookingActorReport()
    return HttpBookingActorReport(
        url=settings.BOOKINGS_SERVICE_URL, path=settings.BOOKINGS_BY_ACTOR_PATH,
        token=settings.INTERNAL_SERVICE_TOKEN, timeout=settings.PEER_TIMEOUT_SECONDS)
