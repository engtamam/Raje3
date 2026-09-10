"""What the admin panel needs from `notification-service` about the PLATFORM's own WhatsApp —
never one shop's. Same shape as `whatsapp_diagnostics.py` right next to it: the internal route lives
on `notification-service` behind the shared service token, and this is the peer call `platform.py`
makes ON BEHALF of an operator who holds `platform.operations`, so the browser's own token never has
to carry the internal one.

A FAILURE IS ANSWERED, NEVER GUESSED — same reasoning as `whatsapp_diagnostics.py`: an unreachable
peer returns `None` and the caller says so plainly, never a silent zero that reads as "nothing is
being sent" when the truth is "we could not check".
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from starlette.concurrency import run_in_threadpool


class PlatformStatus:
    def __init__(self, *, base_url: str, token: str, timeout: int = 8) -> None:
        self._base = (base_url or "").rstrip("/")
        self._token = token
        self._timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self._base)

    def _call(self, path: str) -> dict[str, Any] | None:
        req = urllib.request.Request(
            self._base + path, method="GET",
            headers={"X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:    # nosec B310
                if not 200 <= resp.status < 300:
                    return None
                return json.loads(resp.read() or b"{}")
        except Exception:                                                       # noqa: BLE001
            return None

    async def read(self) -> dict[str, Any] | None:
        """The platform-wide delivery/number/opt-out figures — `None` means unreachable, not zero.

        The real route (shipped platform v0.19.6) has no time window: each figure is a capped count
        over the most-recent NOTIFY_PLATFORM_STATUS_CAP rows, not a clock-bounded slice — there was
        never a `window_hours` parameter to honour, so this no longer sends one."""
        if not self.configured:
            return None
        return await run_in_threadpool(self._call, "/internal/whatsapp/platform-status")


def build_platform_status(settings) -> PlatformStatus:
    return PlatformStatus(base_url=settings.NOTIFICATION_SERVICE_URL,
                          token=settings.INTERNAL_SERVICE_TOKEN)
