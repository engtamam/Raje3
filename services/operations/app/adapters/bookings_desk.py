"""What a staff-hours edit needs from `bookings`: the shop's own working hours, so a custom
schedule can be refused at write time if it reaches outside them.

A FAILURE IS ANSWERED, NEVER GUESSED — same discipline as `loyalty_desk.py` beside this file. An
unreachable peer returns `None` and the caller SKIPS the write-time check rather than blocking
every staff-hours edit on a peer that may not be configured in every environment; `bookings`
itself still intersects a staff member's hours against the shop's own defensively at read time
(belt AND suspender, neither one alone).
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from starlette.concurrency import run_in_threadpool


class BookingsDesk:
    """The one question asked of `bookings`: this tenant's own weekly working-hours policy."""

    def __init__(self, *, base_url: str, path: str, token: str, timeout: int = 5) -> None:
        self._base = (base_url or "").rstrip("/")
        self._path = path
        self._token = token
        self._timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self._base)

    def _call(self, tenant: str) -> dict[str, Any] | None:
        q = f"?tenant={urllib.parse.quote(tenant)}"
        req = urllib.request.Request(
            self._base + self._path + q, method="GET",
            headers={"X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:    # nosec B310
                if not 200 <= resp.status < 300:
                    return None
                return json.loads(resp.read() or b"{}")
        except Exception:                                                       # noqa: BLE001
            return None

    async def working_hours(self, tenant: str) -> dict[str, Any] | None:
        """`None` when the peer cannot be reached — the caller must treat that as "cannot verify",
        never as "the shop has no hours", which would let every staff-hours edit through with no
        check at all in the opposite, wrong direction."""
        if not self.configured:
            return None
        # OFF THE EVENT LOOP, same reason `loyalty_desk.py` blocks this way: a staff-hours save is
        # a request another operator's screen is waiting on, not a background job.
        out = await run_in_threadpool(self._call, tenant)
        return out.get("weekly") if out else None


def build_bookings_desk(settings) -> BookingsDesk:
    return BookingsDesk(base_url=settings.BOOKINGS_SERVICE_URL,
                        path=settings.BOOKINGS_WORKING_HOURS_PATH,
                        token=settings.INTERNAL_SERVICE_TOKEN)
