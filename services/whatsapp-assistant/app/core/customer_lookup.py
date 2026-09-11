"""Resolve an inbound WhatsApp number to a tenant customer's pseudonym.

# ESCALATED: no phone->customer lookup existed anywhere in operations before this. The narrowest
possible addition was made — /internal/operations/customer-by-phone — reusing
CustomerStore.by_phone (already there, serving the field screen's save-time lookup) rather than
building anything new; see services/operations/app/api/internal.py for the route and
deploy/services/whatsapp-assistant.values.yaml for the same note in operator-facing form.

RETURNS A PSEUDONYM, NEVER A NAME. Design point 5: no raw customer name/phone in the LLM prompt.
This is the one place a phone number is read at all in this service's request path, and it never
rests anywhere — the response is used to compute `subject_ref` and immediately discarded.
"""
from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class NullCustomerLookup:
    """No operations peer configured. Every inbound number resolves to 'unknown' — the conversation
    still runs, but points/visit-pattern tools have nothing to summarise."""
    driver = "null"

    async def resolve(self, tenant: str, phone: str) -> dict[str, Any]:
        return {"found": False, "subject_ref": "", "visit_count_90d": 0}

    async def register(self, tenant: str, phone: str) -> bool:
        return False


class HttpCustomerLookup:
    driver = "http"

    def __init__(self, *, url: str, path: str, token: str, timeout: int = 8,
                auto_register_flag_path: str = "", customer_id_by_phone_path: str = "") -> None:
        base = url.rstrip("/")
        self._url = base + path
        self._token = token
        self._timeout = timeout
        # BOTH EMPTY MEANS "NOT WIRED" — a deployment that has not set these two extra paths
        # simply never auto-registers, same "opt in, never silently upgrade" posture every other
        # optional peer in this service already holds. `register()` below checks for this itself.
        self._auto_register_flag_url = f"{base}{auto_register_flag_path}" if auto_register_flag_path else ""
        self._customer_id_by_phone_url = f"{base}{customer_id_by_phone_path}" if customer_id_by_phone_path else ""

    async def resolve(self, tenant: str, phone: str) -> dict[str, Any]:
        # OFF THE EVENT LOOP (urllib has no async mode) — a blocking call here freezes this pod's
        # entire single-worker event loop for the round trip, including its own /healthz, exactly
        # the incident adapters/token_verifier/jwks.py's own docstring documents for a different
        # call site on the sibling service.
        return await asyncio.to_thread(self._resolve_sync, tenant, phone)

    def _resolve_sync(self, tenant: str, phone: str) -> dict[str, Any]:
        body = json.dumps({"tenant": tenant, "phone": phone}).encode()
        req = urllib.request.Request(
            self._url, data=body, method="POST",
            headers={"Content-Type": "application/json", "X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                if not 200 <= resp.status < 300:
                    return {"found": False, "subject_ref": "", "visit_count_90d": 0}
                data: dict[str, Any] = json.loads(resp.read() or b"{}")
        except (urllib.error.URLError, OSError, ValueError):
            return {"found": False, "subject_ref": "", "visit_count_90d": 0}
        return data

    async def register(self, tenant: str, phone: str) -> bool:
        """Turn a stranger's number into a real جهات الاتصال row — ONLY ever called on a number
        `resolve()` just answered `found: False` for (see conversation.py's own call site), and
        only ever DOES anything once this tenant's own owner has opted in.

        TWO PEER CALLS, NEVER ONE ASSUMED. The flag is read fresh every time rather than cached —
        an owner who just turned this off must not have the very next stranger registered anyway
        because a stale answer said yes a minute ago. `False` on any failure of either call —
        an unreachable operations must never silently register (or silently fail to) a real
        customer; the conversation itself is never blocked on this either way (see the caller).
        """
        if not self._auto_register_flag_url or not self._customer_id_by_phone_url:
            return False
        return await asyncio.to_thread(self._register_sync, tenant, phone)

    def _register_sync(self, tenant: str, phone: str) -> bool:
        if not self._flag_enabled_sync(tenant):
            return False
        body = json.dumps({"tenant": tenant, "phone": phone}).encode()
        req = urllib.request.Request(
            self._customer_id_by_phone_url, data=body, method="POST",
            headers={"Content-Type": "application/json", "X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                if not 200 <= resp.status < 300:
                    return False
                data: dict[str, Any] = json.loads(resp.read() or b"{}")
        except (urllib.error.URLError, OSError, ValueError):
            return False
        return bool(data.get("customer_id"))

    def _flag_enabled_sync(self, tenant: str) -> bool:
        url = f"{self._auto_register_flag_url}?tenant={urllib.parse.quote(tenant)}"
        req = urllib.request.Request(
            url, method="GET", headers={"X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                if not 200 <= resp.status < 300:
                    return False
                data: dict[str, Any] = json.loads(resp.read() or b"{}")
        except (urllib.error.URLError, OSError, ValueError):
            return False
        return bool(data.get("enabled"))


def build(settings: Any) -> Any:
    if not settings.OPERATIONS_SERVICE_URL:
        return NullCustomerLookup()
    return HttpCustomerLookup(
        url=settings.OPERATIONS_SERVICE_URL, path=settings.OPERATIONS_CUSTOMER_BY_PHONE_PATH,
        token=settings.INTERNAL_SERVICE_TOKEN, timeout=settings.PEER_TIMEOUT_SECONDS,
        auto_register_flag_path=getattr(settings, "OPERATIONS_WHATSAPP_AUTO_REGISTER_PATH", ""),
        customer_id_by_phone_path=getattr(settings, "OPERATIONS_CUSTOMER_ID_BY_PHONE_PATH", ""))
