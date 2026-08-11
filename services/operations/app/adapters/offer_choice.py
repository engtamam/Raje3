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

import json
import urllib.request
from typing import Any


def http_chooser(*, reminders_url: str, token: str, timeout: int = 5):
    """Build the callable `Operations.with_offer_chooser` wants.

    TIMES OUT FAST, because a worker is standing at a counter with a customer in front of him when
    this runs. Five seconds is already past the moment this decision belongs to.
    """
    async def choose(*, tenant: str, subject_ref: str,
                     service_ids: list[str]) -> dict[str, Any] | None:
        if not reminders_url:
            return None
        body = json.dumps({"subject_ref": subject_ref, "visit_id": "",
                           "service_ids": list(service_ids)}).encode()
        req = urllib.request.Request(
            reminders_url.rstrip("/") + "/internal/reminders/offer/choose",
            data=body, method="POST",
            headers={"Content-Type": "application/json", "X-Internal-Token": token})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:      # nosec B310
                if not 200 <= resp.status < 300:
                    return None
                payload = json.loads(resp.read() or b"{}")
        except Exception:                                                   # noqa: BLE001
            return None
        offer = payload.get("offer")
        return offer if isinstance(offer, dict) and offer.get("ref") else None

    return choose
