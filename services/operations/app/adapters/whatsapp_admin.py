"""What the admin panel needs to MANAGE one shop's own connected WhatsApp number, beyond reading
its delivery history (`whatsapp_diagnostics.py`) or the platform's own status (`platform_status.py`).

Peers to `notification-service`'s `/internal/whatsapp/*` routes shipped in platform v0.19.9
(`app/core/whatsapp_admin.py`, `app/api/internal.py`), behind the shared internal-service token —
same shape as the two adapters next to this one: the internal route is never a declared admin
action on that service, so the operator-facing surface lives here in `platform.py`, gated by
`platform.operations` and audited there, and this adapter carries the browser's request onward
with the internal token instead of the browser's own.

ALL THREE OPERATE ON ONE SHOP'S OWN CONNECTED NUMBER (`tenant`), never the platform's own WhatsApp
identity (`AdminProviderSecrets.tsx`'s Meta secrets) — same distinction `whatsapp_diagnostics.py`
already draws for delivery history. They belong next to the per-shop diagnostics screen, not the
platform-wide "حالة واتساب المنصة" section.

A FAILURE IS ANSWERED, NEVER GUESSED — same reasoning as the two adapters above: an unreachable
peer or a non-2xx returns `None`/an explicit reason, never a silent empty success.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from starlette.concurrency import run_in_threadpool


class WhatsAppAdmin:
    def __init__(self, *, base_url: str, token: str, timeout: int = 8) -> None:
        self._base = (base_url or "").rstrip("/")
        self._token = token
        self._timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self._base)

    def _call(self, path: str, *, method: str = "GET", body: dict | None = None) -> dict[str, Any] | None:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(
            self._base + path, method=method, data=data,
            headers={"X-Internal-Token": self._token,
                     **({"Content-Type": "application/json"} if data is not None else {})})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:    # nosec B310
                return json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as exc:
            # A non-2xx still carries a body worth reading (NOT_CONNECTED/409, a Meta rejection
            # reason/400 or /502) — surfaced under `_status` so the caller can tell "refused with a
            # reason" apart from "could not reach the peer at all" (caught below).
            try:
                payload = json.loads(exc.read() or b"{}")
            except Exception:                                                   # noqa: BLE001
                payload = {}
            return {"_status": exc.code, **payload}
        except Exception:                                                       # noqa: BLE001
            return None

    async def set_two_step_pin(self, *, tenant: str, phone_number_id: str, pin: str) -> dict[str, Any] | None:
        """Set/rotate the number's 6-digit two-step-verification PIN. Write-only end to end: the PIN
        travels through this call and is never read back by any adapter method in this file."""
        if not self.configured:
            return None
        body = {"tenant": tenant, "pin": pin}
        if phone_number_id:
            body["phone_number_id"] = phone_number_id
        return await run_in_threadpool(self._call, "/internal/whatsapp/two-step-pin",
                                       method="POST", body=body)

    async def subscribed_fields(self, tenant: str) -> dict[str, Any] | None:
        """Which apps (and webhook fields) Meta is actually sending for this shop's WABA. Read-only."""
        if not self.configured:
            return None
        q = f"?tenant={urllib.parse.quote(tenant)}"
        return await run_in_threadpool(self._call, "/internal/whatsapp/subscribed-fields" + q)

    async def business_verification(self, tenant: str) -> dict[str, Any] | None:
        """The WABA's business_verification_status + overall status."""
        if not self.configured:
            return None
        q = f"?tenant={urllib.parse.quote(tenant)}"
        return await run_in_threadpool(self._call, "/internal/whatsapp/business-verification" + q)

    async def messaging_limit(self, tenant: str) -> dict[str, Any] | None:
        """This shop's messaging-limit tier + quality rating (Part 2 gap: shipped earlier than the
        three routes above, but never wired to any admin screen until now)."""
        if not self.configured:
            return None
        q = f"?tenant={urllib.parse.quote(tenant)}"
        return await run_in_threadpool(self._call, "/internal/whatsapp/messaging-limit" + q)


def build_whatsapp_admin(settings) -> WhatsAppAdmin:
    return WhatsAppAdmin(base_url=settings.NOTIFICATION_SERVICE_URL, token=settings.INTERNAL_SERVICE_TOKEN)
