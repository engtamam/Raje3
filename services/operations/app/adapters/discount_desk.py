"""Ask `reminders` which campaign discount a WhatsApp Direct Ordering customer is holding, and
tell it once that discount has actually been spent.

SAME SPLIT AS `offer_choice.py`'S OWN, DELIBERATELY NOT THE SAME MECHANISM. `offer_choice.py`
implements spec 5.6.2 for VISITS: reminders issues an offer, operations records the spend ON THE
VISIT (never on reminders' own send log, which is append-only — every cap in 5.8 is counted
against it). Orders are a different domain this feature was scoped to, and reminders' own
`SendLogStore.find_unredeemed_discount`/`mark_redeemed` (2026-10-04) uses a single `redeemed_at`
flag it owns and mutates itself — a simpler, correct answer for a discount with exactly one
legitimate consumer (an order, paid once), at the cost of the two domains not cross-checking each
other yet (see that store method's own docstring on the known gap).

A FAILURE REFUSES, NEVER GUESSES — same posture `offer_choice.py` takes, for the same reason: an
order that silently loses a real discount costs a customer money they were promised, and an order
that silently APPLIES one we could not verify is a discount the owner never agreed to.
"""
from __future__ import annotations

import asyncio
import json
import urllib.parse
from typing import Any

from app.adapters import internal_http


class DiscountPeerUnavailable(RuntimeError):
    """We could not ask, or could not confirm the redemption. NOT «there is no discount» — the
    caller (`OrderService`) must treat this as «proceed with no discount this attempt», never as
    a confirmed absence, the same distinction `OfferPeerUnavailable` draws for visits."""


def http_discount_desk(*, reminders_url: str, token: str, timeout: int = 5):
    """Build the `{find, redeem}` pair `OrderService` wants.

    `find` IS A GET, LIKE `active_offers.py`'s OWN PEER CALL — a read with no side effect, same
    shape that client already uses for the identical "what is this phone holding" question asked
    from a different service (`whatsapp-assistant`). `redeem` is a POST, and is called from
    EXACTLY ONE PLACE: `OrderService.confirm_payment`, never `create()` — see that method's own
    docstring on why the discount must not be spent before the order is actually paid.
    """
    async def find(*, tenant: str, subject_ref: str) -> dict[str, Any] | None:
        if not reminders_url:
            raise DiscountPeerUnavailable("no reminders URL configured")
        qs = urllib.parse.urlencode({"tenant": tenant, "subject_ref": subject_ref})
        try:
            # OFF THE EVENT LOOP — see core/customer_lookup.py::HttpCustomerLookup.resolve.
            status, raw = await asyncio.to_thread(
                internal_http.send,
                reminders_url.rstrip("/") + "/internal/reminders/orders/active-discount?" + qs,
                timeout=timeout, method="GET", token=token)
            if not 200 <= status < 300:
                raise DiscountPeerUnavailable(f"reminders answered {status}")
            payload = json.loads(raw or b"{}")
        except DiscountPeerUnavailable:
            raise
        except Exception as exc:                                            # noqa: BLE001
            raise DiscountPeerUnavailable(str(exc)) from exc
        discount = payload.get("discount")
        return discount if isinstance(discount, dict) and discount.get("ref") else None

    async def redeem(*, tenant: str, ref: str, redeemed_by: str) -> bool:
        if not reminders_url:
            raise DiscountPeerUnavailable("no reminders URL configured")
        body = json.dumps({"tenant": tenant, "ref": ref, "redeemed_by": redeemed_by}).encode()
        try:
            status, raw = await asyncio.to_thread(
                internal_http.send,
                reminders_url.rstrip("/") + "/internal/reminders/orders/redeem",
                timeout=timeout, method="POST", body=body,
                content_type=internal_http.JSON, token=token)
            if not 200 <= status < 300:
                raise DiscountPeerUnavailable(f"reminders answered {status}")
            payload = json.loads(raw or b"{}")
        except DiscountPeerUnavailable:
            raise
        except Exception as exc:                                            # noqa: BLE001
            raise DiscountPeerUnavailable(str(exc)) from exc
        return bool(payload.get("redeemed"))

    return {"find": find, "redeem": redeem}


def build(settings: Any) -> dict[str, Any]:
    return http_discount_desk(reminders_url=getattr(settings, "REMINDERS_SERVICE_URL", "") or "",
                              token=getattr(settings, "INTERNAL_SERVICE_TOKEN", "") or "")
