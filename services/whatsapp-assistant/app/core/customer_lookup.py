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

import json
import urllib.error
import urllib.request
from typing import Any


class NullCustomerLookup:
    """No operations peer configured. Every inbound number resolves to 'unknown' — the conversation
    still runs, but points/visit-pattern tools have nothing to summarise."""
    driver = "null"

    async def resolve(self, tenant: str, phone: str) -> dict[str, Any]:
        return {"found": False, "subject_ref": "", "visit_count_90d": 0}


class HttpCustomerLookup:
    driver = "http"

    def __init__(self, *, url: str, path: str, token: str, timeout: int = 8) -> None:
        self._url = url.rstrip("/") + path
        self._token = token
        self._timeout = timeout

    async def resolve(self, tenant: str, phone: str) -> dict[str, Any]:
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


def build(settings: Any) -> Any:
    if not settings.OPERATIONS_SERVICE_URL:
        return NullCustomerLookup()
    return HttpCustomerLookup(
        url=settings.OPERATIONS_SERVICE_URL, path=settings.OPERATIONS_CUSTOMER_BY_PHONE_PATH,
        token=settings.INTERNAL_SERVICE_TOKEN, timeout=settings.PEER_TIMEOUT_SECONDS)
