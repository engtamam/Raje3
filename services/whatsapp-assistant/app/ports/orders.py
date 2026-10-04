"""Port to operations' WhatsApp Direct Ordering door (services/operations/app/api/internal.py::
internal_create_whatsapp_order) — the ONE write this flow ever makes: `create`, called only after
a catalog order (core/conversation.py::handle_order) AND the customer's own location
(core/conversation.py::handle_order_followup) have both arrived. Same shape as
app/ports/mobile_requests.py — a different flow, the identical "port + Null + Http" idiom."""
from __future__ import annotations

from dataclasses import dataclass


class OrderFailed(Exception):
    """The peer call itself failed, OR operations refused the order (no branch covers the
    customer's location, an unpriced/unknown service, a malformed request) — same posture as
    `ports/mobile_requests.py::MobileRequestFailed`: the caller turns this into one honest
    sentence, never a silent drop."""


@dataclass(frozen=True)
class CreatedOrder:
    order_id: str
    branch_id: str
    total_minor: int


class NullOrders:
    driver = "null"

    async def create(self, *, tenant: str, phone: str, customer_name: str,
                     items: list[tuple[str, int]], lat: float, lng: float,
                     idempotency_key: str, note: str = "") -> CreatedOrder:
        raise OrderFailed("WhatsApp ordering is not configured on this deployment")
