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
    # THE ORDER IS NOT "RECEIVED" UNTIL IT IS PAID -- `pay_url` empty means the link itself could
    # not be minted (no gateway connected, payments-service unreachable), never "no payment
    # needed". `pay_reason` carries operations' own sentence for that case, same posture as
    # `OrderFailed` below.
    pay_url: str = ""
    pay_reason: str = ""
    # THE CAMPAIGN DISCOUNT (2026-10-04), if operations found one live for this phone — see
    # `OrderService.create()`'s own docstring on when it is applied vs. when it is actually
    # redeemed. Zero/empty is the overwhelming majority case: most orders carry no discount.
    discount_minor: int = 0
    discount_source: str = ""
    # A LIVE LOYALTY POINTS REWARD, IF ONE WAS OFFERED — never both this and a non-empty `pay_url`
    # at once: operations holds the pay link back the moment this is present (see
    # `OrderService.available_points_reward`'s own docstring), so `conversation.py` must ask the
    # customer before ever calling `choose_points_reward` below. `None` is the overwhelming
    # majority case.
    points_reward: dict | None = None
    # SET ONLY AFTER a points choice has actually been resolved (`choose_points_reward`) — the
    # amount/name a reward ENDED UP being worth, as opposed to `points_reward` above (what was
    # merely on offer). Zero/empty means no reward was redeemed for this order.
    points_reward_minor: int = 0
    points_reward_name: str = ""


class NullOrders:
    driver = "null"

    async def create(self, *, tenant: str, phone: str, customer_name: str,
                     items: list[tuple[str, int]], lat: float, lng: float,
                     idempotency_key: str, note: str = "") -> CreatedOrder:
        raise OrderFailed("WhatsApp ordering is not configured on this deployment")

    async def choose_points_reward(self, *, tenant: str, order_id: str, action: str,
                                   reward_id: str = "") -> CreatedOrder:
        raise OrderFailed("WhatsApp ordering is not configured on this deployment")
