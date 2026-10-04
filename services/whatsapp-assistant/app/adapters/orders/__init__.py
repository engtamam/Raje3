"""HttpOrders — the one call app/ports/orders.py's docstring describes, against operations'
internal door. Same stdlib-urllib/X-Internal-Token/asyncio.to_thread idiom as
app/adapters/mobile_requests/__init__.py — the house pattern for every peer call this service
makes."""
from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from typing import Any

from app.ports.orders import CreatedOrder, NullOrders, OrderFailed


class HttpOrders:
    driver = "http"

    def __init__(self, *, url: str, path: str, token: str, timeout: int = 8) -> None:
        self._url = url.rstrip("/") + path
        self._token = token
        self._timeout = timeout

    async def create(self, *, tenant: str, phone: str, customer_name: str,
                     items: list[tuple[str, int]], lat: float, lng: float,
                     idempotency_key: str, note: str = "") -> CreatedOrder:
        return await asyncio.to_thread(
            self._create_sync, tenant, phone, customer_name, items, lat, lng,
            idempotency_key, note)

    def _create_sync(self, tenant: str, phone: str, customer_name: str,
                     items: list[tuple[str, int]], lat: float, lng: float,
                     idempotency_key: str, note: str) -> CreatedOrder:
        body = json.dumps({
            "tenant": tenant, "phone": phone, "customer_name": customer_name,
            "items": [{"service_id": sid, "quantity": qty} for sid, qty in items],
            "lat": lat, "lng": lng, "idempotency_key": idempotency_key, "note": note,
        }).encode()
        req = urllib.request.Request(
            self._url, data=body, method="POST",
            headers={"Content-Type": "application/json", "X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                if not 200 <= resp.status < 300:
                    raise OrderFailed(f"operations returned {resp.status}")
                data: dict[str, Any] = json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as exc:
            # A 422 here is operations' own Pydantic validation refusing a malformed body — this
            # service already validates items/lat/lng before ever reaching here, so a 422 at this
            # point is this service's own bug, surfaced honestly rather than silently swallowed.
            raise OrderFailed(f"operations returned {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise OrderFailed(f"operations unreachable: {exc}") from exc
        # operations' own door returns the refusal rather than raising it — surfaced here the
        # same way every other real failure is.
        if not data.get("created"):
            raise OrderFailed(str(data.get("reason") or "operations refused the order"))
        return CreatedOrder(order_id=str(data.get("order_id") or ""),
                           branch_id=str(data.get("branch_id") or ""),
                           total_minor=int(data.get("total_minor") or 0))


def build(settings: Any) -> Any:
    if not settings.OPERATIONS_SERVICE_URL:
        return NullOrders()
    return HttpOrders(
        url=settings.OPERATIONS_SERVICE_URL, path=settings.OPERATIONS_WHATSAPP_ORDERS_PATH,
        token=settings.INTERNAL_SERVICE_TOKEN, timeout=settings.PEER_TIMEOUT_SECONDS)
