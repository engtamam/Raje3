"""Resolve a tenant's founding owner's own contact — identity-service (platform v0.19.13),
`GET /internal/tenancy/owner-phone?tenant=`.

WHY THIS EXISTS. The subscription-renewal Flow (core/renewal_trigger.py) is sent to the SHOP
OWNER, not an end customer — there is no subject_ref to resolve through operations the way every
other outbound send in this service works. identity-service holds no dedicated phone field; it
returns the founding owner's LOGIN IDENTIFIER (a phone when they registered by phone, else an
email) with an `is_phone` E.164 flag, so this adapter can refuse to message a non-number rather
than silently emailing nobody or sending to a malformed WhatsApp recipient.

A GONE OR UNREACHABLE OWNER ANSWERS None, NEVER A GUESS. `founding_owner()` on identity's own side
already treats "no owner"/"suspended owner"/"tenant does not exist" as the same 404 — an IDOR
guard, not an existence oracle — and this adapter passes that straight through as `None`, the same
"could not read, do not act as if we know" posture the rest of this service holds towards a peer
it cannot reach (see core/customer_lookup.py's own NullCustomerLookup)."""
from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class NullOwnerPhone:
    """No identity-service peer configured. Every tenant resolves to 'no recipient' — the
    renewal trigger simply does not send, never a fake number."""
    driver = "null"

    async def resolve(self, tenant: str) -> str:
        return ""


class HttpOwnerPhone:
    driver = "http"

    def __init__(self, *, url: str, path: str, token: str, timeout: int = 8) -> None:
        self._url = url.rstrip("/") + path
        self._token = token
        self._timeout = timeout

    async def resolve(self, tenant: str) -> str:
        """The founding owner's phone number, or `""` when there is none to message — a missing
        owner, a non-phone identifier (an email-only signup), or an unreachable peer all answer
        the same way: nothing this trigger may act on."""
        # OFF THE EVENT LOOP — see core/customer_lookup.py::HttpCustomerLookup.resolve.
        return await asyncio.to_thread(self._resolve_sync, tenant)

    def _resolve_sync(self, tenant: str) -> str:
        if not tenant:
            return ""
        query = urllib.parse.urlencode({"tenant": tenant})
        req = urllib.request.Request(
            f"{self._url}?{query}", headers={"X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                if not 200 <= resp.status < 300:
                    return ""
                data: dict[str, Any] = json.loads(resp.read() or b"{}")
        except (urllib.error.URLError, OSError, ValueError):
            return ""
        if not bool(data.get("is_phone")):
            return ""
        return str(data.get("identifier") or "")


def build(settings: Any) -> Any:
    if not settings.IDENTITY_SERVICE_URL:
        return NullOwnerPhone()
    return HttpOwnerPhone(
        url=settings.IDENTITY_SERVICE_URL, path=settings.IDENTITY_OWNER_PHONE_PATH,
        token=settings.INTERNAL_SERVICE_TOKEN, timeout=settings.PEER_TIMEOUT_SECONDS)
