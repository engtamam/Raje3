"""Read-only peer client for ONE service's own ordered protocol — operations'
/internal/operations/service-procedure — resolved to real `{id, text, severity}` step rows.

DELIBERATELY PER-SERVICE, NEVER THE WHOLE CATALOGUE. This is the `get_service_procedure` tool's
own reason to exist (core/tools.py): the owner's explicit instruction was that the model must pull
ONE service's steps at a time, by id, to keep the tool's token cost bounded — a customer asking
"how do you wash the engine bay" needs one service's real steps, never every service's protocol at
once. A comparison across two services means the model calls this twice, never a batched call this
client does not offer.

NOT PII, same reasoning as core/service_catalog.py's own module docstring — a shop's own written
protocol is operational fact, not a customer's personal data, so it is sent to the model in full.
"""
from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from typing import Any


class NullServiceProcedure:
    driver = "null"

    async def get(self, tenant: str, service_id: str) -> dict[str, Any] | None:
        return None


class HttpServiceProcedure:
    driver = "http"

    def __init__(self, *, url: str, path: str, token: str, timeout: int = 8) -> None:
        self._url = url.rstrip("/") + path
        self._token = token
        self._timeout = timeout

    async def get(self, tenant: str, service_id: str) -> dict[str, Any] | None:
        # OFF THE EVENT LOOP — see core/customer_lookup.py::HttpCustomerLookup.resolve.
        return await asyncio.to_thread(self._get_sync, tenant, service_id)

    def _get_sync(self, tenant: str, service_id: str) -> dict[str, Any] | None:
        body = json.dumps({"tenant": tenant, "service_id": service_id}).encode()
        req = urllib.request.Request(
            self._url, data=body, method="POST",
            headers={"Content-Type": "application/json", "X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                if not 200 <= resp.status < 300:
                    return None
                data: dict[str, Any] = json.loads(resp.read() or b"{}")
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError):
            # A peer outage (or an unknown service id, operations' own 404) degrades to "the
            # assistant does not know this service's protocol right now" — the conversation still
            # runs, it just cannot ground a procedure-specific answer this turn.
            return None
        return data


def build(settings: Any) -> Any:
    if not settings.OPERATIONS_SERVICE_URL:
        return NullServiceProcedure()
    return HttpServiceProcedure(
        url=settings.OPERATIONS_SERVICE_URL, path=settings.OPERATIONS_SERVICE_PROCEDURE_PATH,
        token=settings.INTERNAL_SERVICE_TOKEN, timeout=settings.PEER_TIMEOUT_SECONDS)
