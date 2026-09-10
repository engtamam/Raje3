"""Ask `reminders` which offer a visit would apply.

THE SPLIT THIS IMPLEMENTS is spec 5.6.2's: reminders issues an offer and can say which one applies
— it alone knows what was sent, to whom, with what scope and expiry — and operations records that
it WAS applied, on the visit. The mark cannot live in the send log because that log is append-only
and every cap in 5.8 is counted against it.

A FAILURE REFUSES, NEVER GUESSES. An unreachable peer means we do not know whether the customer is
holding anything, and the two wrong answers are not equal: applying nothing costs a customer one
offer he still holds afterwards, while applying one we could not verify is a discount the owner
never agreed to, on an invoice he cannot explain.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any
from app.adapters import internal_http


class OfferPeerUnavailable(RuntimeError):
    """We could not ask. NOT «he has no offer».

    THE DIFFERENCE IS THE WHOLE POINT of this module's own docstring, and the code did the opposite
    for as long as it existed: every failure returned None, and None reads as «no offer he holds».
    A customer standing at the counter with an offer in his hand was told he had none, and the shop
    that sent it looked like it had not.
    """


def http_chooser(*, reminders_url: str, token: str, timeout: int = 5):
    """Build the callable `Operations.with_offer_chooser` wants.

    TIMES OUT FAST, because a worker is standing at a counter with a customer in front of him when
    this runs. Five seconds is already past the moment this decision belongs to.
    """
    async def choose(*, tenant: str, subject_ref: str,
                     service_ids: list[str]) -> dict[str, Any] | None:
        if not reminders_url:
            raise OfferPeerUnavailable("no reminders URL configured")
        # `tenant` IS REQUIRED BY THE PEER (ChooseOfferIn, min_length=1) and was never sent, so
        # every call in the product's history was rejected 422 and swallowed as «no offer». The
        # counter — the one moment the customer is paying — could not apply an offer at all.
        body = json.dumps({"tenant": tenant, "subject_ref": subject_ref, "visit_id": "",
                           "service_ids": list(service_ids)}).encode()
        try:
            # Built in adapters/internal_http.py, the one place this service attaches the token.
            # OFF THE EVENT LOOP — see core/customer_lookup.py::HttpCustomerLookup.resolve.
            status, raw = await asyncio.to_thread(
                internal_http.send,
                reminders_url.rstrip("/") + "/internal/reminders/offer/choose",
                timeout=timeout, method="POST", body=body,
                content_type=internal_http.JSON, token=token)
            if not 200 <= status < 300:
                raise OfferPeerUnavailable(f"reminders answered {status}")
            payload = json.loads(raw or b"{}")
        except OfferPeerUnavailable:
            raise
        except Exception as exc:                                            # noqa: BLE001
            # EVERY transport failure, and a body we cannot parse: all of them mean «we do not
            # know», and none of them mean «none».
            raise OfferPeerUnavailable(str(exc)) from exc
        # THE PEER ANSWERED. Now — and only now — an absent offer is the truth.
        offer = payload.get("offer")
        return offer if isinstance(offer, dict) and offer.get("ref") else None

    return choose
